# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Scope-rule ablation: what changes if accessible inputs count as emissions.

AgentRisk treats ``user_input`` and ``tool_response`` as *sources*: data the
agent was given, which fills the vault but is not a leak. This ablation scores
the same findings twice with the unchanged formula, once under that rule and
once with an empty source set (every channel an emission), and reports what
moves: clean units that would become "leaks", how far the Risk Index rises,
and how much of the ablated leakage comes from the input channels alone.

Nothing in :mod:`agentleak.core.agentrisk` changes; only the
``baseline_channels`` argument the core function already accepts.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from ..core.agentrisk import BASELINE_CHANNELS, compute_agentrisk
from ..core.runner import AgentLeakRunner
from . import stats
from .bench import RunError, build_config, dump_json, load_run
from .corpus import select_units
from .manifest import Manifest
from .summary import metric_seed

INPUT_CHANNELS = tuple(sorted(BASELINE_CHANNELS))


def _resolve(target: Manifest | str | Path) -> tuple[Manifest, Path]:
    if isinstance(target, Manifest):
        return target, Path(target.resolved_output_dir())
    p = Path(target)
    if p.is_dir():
        return load_run(p).manifest, p
    m = Manifest.load(p)
    return m, Path(m.resolved_output_dir())


def scope_ablation(
    target: Manifest | str | Path, *, out_dir: str | Path | None = None
) -> dict[str, Any]:
    """Run the ablation for a manifest (or a finished run directory).

    Returns the result document; with ``out_dir`` (default: ``ablation/``
    inside the run directory) also writes ``scope_ablation.json``,
    ``scope_ablation.csv`` and ``SCOPE-ABLATION.md``.
    """
    manifest, run_dir = _resolve(target)
    if manifest.agent.mode != "replay":
        raise RunError("the scope ablation re-analyzes fixed traces; use a replay manifest")
    sel = manifest.scenarios
    units = select_units(
        sources=sel.sources, domains=sel.domains, failure_modes=sel.failure_modes,
        labels=sel.labels, ids=sel.ids, max_per_source=sel.max_per_source,
        counterparts=sel.counterparts, seed=manifest.seed,
    )
    runner = AgentLeakRunner(build_config(manifest))
    rows: list[dict[str, Any]] = []
    for unit in units:
        findings = runner.analyze(unit.trace).findings
        default = compute_agentrisk(findings, baseline_channels=BASELINE_CHANNELS)
        ablated = compute_agentrisk(findings, baseline_channels=())
        from_inputs = sum(v for c, v in ablated.ri_by_channel.items() if c in INPUT_CHANNELS)
        rows.append({
            "scenario_id": unit.unit_id,
            "source": unit.source,
            "label": unit.label,
            "negative_kind": unit.negative_kind,
            "leaked_default": int(default.leaked_count > 0),
            "leaked_ablated": int(ablated.leaked_count > 0),
            "ri_default": round(default.ri_global, 6),
            "ri_ablated": round(ablated.ri_global, 6),
            "wsl_default": default.wsl,
            "wsl_ablated": ablated.wsl,
            "rho_s": default.rho_s,
            "input_channel_ri_ablated": round(from_inputs, 6),
        })

    conf = manifest.statistics.confidence
    method = manifest.statistics.interval
    metrics: list[dict[str, Any]] = []

    def prop(metric_id: str, label: str, population: str, k: int, n: int,
             definition: str) -> None:
        metrics.append({"id": metric_id, "label": label, "population": population,
                        "definition": definition,
                        **stats.proportion(k, n, method, conf).to_dict()})

    groups = {
        "leaking": [r for r in rows if r["label"] == "leaking"],
        "independent": [r for r in rows if r["negative_kind"] == "independent"],
        "derived": [r for r in rows if r["negative_kind"] == "derived"],
    }
    for name, group in groups.items():
        if not group:
            continue
        positive = "flagged as leaking" if name == "leaking" else "with no leak"
        title = {"leaking": "Leaking fixtures flagged", "independent": "Independent clean, no leak",
                 "derived": "Derived clean, no leak"}[name]
        for rule in ("default", "ablated"):
            k = sum(r[f"leaked_{rule}"] for r in group)
            if name != "leaking":
                k = len(group) - k
            prop(f"{name}.{rule}", f"{title} ({rule} rule)", f"{name} units", k, len(group),
                 f"{name} units {positive} under the {rule} scope rule / {name} units")
        flips = sum(1 for r in group if not r["leaked_default"] and r["leaked_ablated"])
        prop(f"{name}.flipped_to_leak", f"{title.split(',')[0]}: flipped to leak",
             f"{name} units", flips, len(group),
             f"{name} units with no leak by default that leak once inputs count as emissions")
    paired = []
    for name, group in groups.items():
        if len(group) < 2:
            continue
        diff = stats.paired_bootstrap_diff(
            [r["ri_default"] for r in group], [r["ri_ablated"] for r in group],
            n_boot=manifest.statistics.bootstrap_resamples,
            seed=metric_seed(manifest.seed, f"ablation:{name}"), confidence=conf,
        )
        paired.append({"group": name, "n": len(group),
                       "mean_ri_default": round(stats.mean([r["ri_default"] for r in group]), 6),
                       "mean_ri_ablated": round(stats.mean([r["ri_ablated"] for r in group]), 6),
                       "difference": diff.to_dict()})
    doc = {
        "schema": "agentleak.bench.scope-ablation/1",
        "experiment": manifest.name,
        "rule_default": {"source_channels": list(INPUT_CHANNELS)},
        "rule_ablated": {"source_channels": []},
        "note": "Same findings, same formula; only the set of source channels differs.",
        "metrics": metrics,
        "mean_ri": paired,
        "rows": rows,
    }
    out = Path(out_dir) if out_dir else run_dir / "ablation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "scope_ablation.json").write_text(dump_json(doc), encoding="utf-8")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else ["scenario_id"],
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (out / "scope_ablation.csv").write_text(buf.getvalue(), encoding="utf-8")
    (out / "SCOPE-ABLATION.md").write_text(render_ablation(doc), encoding="utf-8")
    doc["out_dir"] = str(out)
    return doc


def render_ablation(doc: dict[str, Any]) -> str:
    lines = [
        f"# Scope-rule ablation: {doc['experiment']}",
        "",
        "Default rule: `user_input` and `tool_response` are sources (data given to the "
        "agent), not leaks. Ablated rule: every channel counts as an emission. Same "
        "findings, same AgentRisk formula.",
        "",
        "| Measure | Estimate | n/N | CI |",
        "|---|---:|---:|---|",
    ]
    for m in doc["metrics"]:
        est = "n/a" if m["estimate"] is None else f"{m['estimate']:.3f}"
        ci = "n/a" if m["ci_low"] is None else f"{m['ci_low']:.3f}–{m['ci_high']:.3f}"
        lines.append(f"| {m['label']} | {est} | {m['numerator']}/{m['denominator']} | {ci} |")
    lines += ["", "| Group | Mean RI (default) | Mean RI (ablated) | Difference | CI |",
              "|---|---:|---:|---:|---|"]
    for p in doc["mean_ri"]:
        d = p["difference"]
        lines.append(
            f"| {p['group']} (n={p['n']}) | {p['mean_ri_default']:.3f} | "
            f"{p['mean_ri_ablated']:.3f} | {d['estimate']:+.3f} | "
            f"{d['ci_low']:+.3f} to {d['ci_high']:+.3f} |"
        )
    lines += [
        "",
        "With an observed vault, every detected value is on some channel, so under the "
        "ablated rule any unit with a detection scores RI = 1 and every clean control "
        "that reads sensitive data becomes a leak. The source rule is what lets the Risk "
        "Index separate reading data from disclosing it.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["INPUT_CHANNELS", "render_ablation", "scope_ablation"]
