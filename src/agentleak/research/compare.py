# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Paired comparison of two benchmark runs.

Units are paired by scenario id. For each metric the comparison reports both
rates with their counts, the paired difference ``B - A`` with a paired
bootstrap interval, an exact McNemar test (binary outcomes) or an exact /
Monte Carlo sign-flip test (Risk Index), Cohen's h, and Holm-adjusted p-values
across the whole family of metrics compared. It also lists every scenario
whose outcome flipped.

Before any of that it checks that the runs are comparable. Different source
hashes, different labels for the same scenario, or replay against live are
refused; different detector tiers, degraded runs, different software versions
and different Risk Index denominators are warned about in the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import stats
from .bench import BenchRun, dump_json, load_run
from .corpus import DISCLOSURE_CHANNELS
from .render import CHANNEL_LABELS
from .rows import scenario_table
from .summary import metric_seed

COMPARISON_SCHEMA = "agentleak.bench.comparison/1"


class ComparisonError(RuntimeError):
    """The two runs cannot be compared as asked."""


@dataclass
class _Binary:
    metric_id: str
    label: str
    population: str
    a: list[int]
    b: list[int]
    ids: list[str]


def _checks(a: BenchRun, b: BenchRun, paired: list[str], only_a: int, only_b: int,
            ta: dict[str, dict[str, Any]], tb: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def add(check: str, status: str, detail: str) -> None:
        out.append({"check": check, "status": status, "detail": detail})

    src_a = {s["source"]: s["sha256"] for s in a.lock.get("sources", [])}
    src_b = {s["source"]: s["sha256"] for s in b.lock.get("sources", [])}
    differ = sorted(s for s in set(src_a) & set(src_b) if src_a[s] != src_b[s])
    if differ:
        add("sources", "fail", f"scenario source files differ between runs: {', '.join(differ)}")
    else:
        add("sources", "ok", "every shared scenario source has the same SHA-256")

    mode_a, mode_b = a.manifest.agent.mode, b.manifest.agent.mode
    if mode_a != mode_b:
        add("agent_mode", "fail", f"run A is {mode_a}, run B is {mode_b}")
    else:
        add("agent_mode", "ok", f"both runs are {mode_a}")

    if not paired:
        add("pairing", "fail", "the runs have no scenario in common")
    elif only_a or only_b:
        add("pairing", "warn", f"{len(paired)} scenarios paired; {only_a} only in A and "
            f"{only_b} only in B are left out")
    else:
        add("pairing", "ok", f"all {len(paired)} scenarios paired")

    mislabelled = [s for s in paired if ta[s]["label"] != tb[s]["label"]]
    if mislabelled:
        add("labels", "fail", f"{len(mislabelled)} scenarios carry different labels, "
            f"e.g. {mislabelled[0]}")
    else:
        add("labels", "ok", "every paired scenario has the same label")

    det_a, det_b = a.summary.get("detector", {}), b.summary.get("detector", {})
    tiers_a, tiers_b = det_a.get("tiers_run", []), det_b.get("tiers_run", [])
    if tiers_a != tiers_b or det_a.get("mode") != det_b.get("mode"):
        add("detector_tiers", "warn",
            f"A ran {det_a.get('mode')} [{', '.join(tiers_a)}], B ran {det_b.get('mode')} "
            f"[{', '.join(tiers_b)}]: differences include the change of tier")
    else:
        add("detector_tiers", "ok", f"both ran {det_a.get('mode')} [{', '.join(tiers_a)}]")
    if det_a.get("degraded") or det_b.get("degraded"):
        which = " and ".join(n for n, d in (("A", det_a), ("B", det_b)) if d.get("degraded"))
        add("degraded", "warn", f"run {which} is degraded: a requested tier did not run, "
            "so its leakage may be under-reported")
    else:
        add("degraded", "ok", "neither run is degraded")

    va = a.summary.get("software", {}).get("agentleak_version")
    vb = b.summary.get("software", {}).get("agentleak_version")
    if va != vb:
        add("software_version", "warn", f"A used agentleak {va}, B used {vb}")
    else:
        add("software_version", "ok", f"both used agentleak {va}")

    rho_diff = sum(1 for s in paired if ta[s]["rho_s"] != tb[s]["rho_s"])
    if rho_diff:
        add("vault_denominator", "warn",
            f"rho_S differs for {rho_diff} of {len(paired)} paired scenarios (the observed "
            "vault depends on what the detectors find), so Risk Index differences mix "
            "numerator and denominator changes")
    else:
        add("vault_denominator", "ok", "rho_S is identical for every paired scenario")
    return out


def _binary_metrics(paired: list[str], ta: dict[str, dict[str, Any]],
                    tb: dict[str, dict[str, Any]]) -> list[_Binary]:
    def units(pred: Any) -> list[str]:
        return [s for s in paired if pred(ta[s])]

    out: list[_Binary] = []
    leaking = units(lambda s: s["label"] == "leaking")
    live = units(lambda s: s["label"] == "live")
    if leaking:
        out.append(_Binary("recall", "Recall", "leaking fixtures",
                           [ta[s]["leaked"] for s in leaking],
                           [tb[s]["leaked"] for s in leaking], leaking))
    for kind in ("independent", "derived"):
        neg = units(lambda s, k=kind: s["label"] == "clean" and s["negative_kind"] == k)
        if neg:
            out.append(_Binary(f"specificity.{kind}", f"Specificity ({kind})",
                               f"{kind} clean negatives",
                               [1 - ta[s]["leaked"] for s in neg],
                               [1 - tb[s]["leaked"] for s in neg], neg))
    if live:
        out.append(_Binary("leak_rate", "Leak rate", "live runs",
                           [ta[s]["leaked"] for s in live],
                           [tb[s]["leaked"] for s in live], live))
    base = leaking or live
    if base:
        name = "leaking fixtures" if leaking else "live runs"
        for channel in DISCLOSURE_CHANNELS:
            a = [int(channel in ta[s]["channels"]) for s in base]
            b = [int(channel in tb[s]["channels"]) for s in base]
            if any(a) or any(b):
                out.append(_Binary(f"channel_leak_rate.{channel}",
                                   f"Leak on {CHANNEL_LABELS.get(channel, channel)}",
                                   name, a, b, base))

        def missed(s: dict[str, Any]) -> int:
            return int(bool(s["leaked"]) and "final_output" not in s["channels"])

        out.append(_Binary("missed_by_output_only_audit", "Missed by output-only audit", name,
                           [missed(ta[s]) for s in base], [missed(tb[s]) for s in base], base))
    return out


def compare_runs(
    run_a: BenchRun | str | Path,
    run_b: BenchRun | str | Path,
    *,
    force: bool = False,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compare two runs (B relative to A). Returns the comparison document.

    Raises :class:`ComparisonError` when a comparability check fails, unless
    ``force`` is set (the failures are then kept in the output). With
    ``out_dir``, writes ``comparison.json``, ``COMPARISON.md`` and
    ``comparison.tex`` there.
    """
    a = run_a if isinstance(run_a, BenchRun) else load_run(run_a)
    b = run_b if isinstance(run_b, BenchRun) else load_run(run_b)
    ta = {s["scenario_id"]: s for s in scenario_table(a.rows)}
    tb = {s["scenario_id"]: s for s in scenario_table(b.rows)}
    paired = [s for s in ta if s in tb]
    only_a = sum(1 for s in ta if s not in tb)
    only_b = sum(1 for s in tb if s not in ta)
    checks = _checks(a, b, paired, only_a, only_b, ta, tb)
    failures = [c for c in checks if c["status"] == "fail"]
    if failures and not force:
        raise ComparisonError(
            "the runs are not comparable:\n  - "
            + "\n  - ".join(f"{c['check']}: {c['detail']}" for c in failures)
            + "\nFix the cause, or pass --force to compare anyway (the failure is kept "
            "in the output)."
        )
    if not paired:
        raise ComparisonError("the runs have no scenario in common; nothing to compare")

    seed = a.manifest.seed
    n_boot = a.manifest.statistics.bootstrap_resamples
    conf = a.manifest.statistics.confidence
    results: list[dict[str, Any]] = []
    for m in _binary_metrics(paired, ta, tb):
        n = len(m.ids)
        ka, kb = sum(m.a), sum(m.b)
        b01 = sum(1 for x, y in zip(m.a, m.b, strict=True) if x == 0 and y == 1)
        b10 = sum(1 for x, y in zip(m.a, m.b, strict=True) if x == 1 and y == 0)
        diff = stats.paired_bootstrap_diff(
            [float(x) for x in m.a], [float(y) for y in m.b], n_boot=n_boot,
            seed=metric_seed(seed, f"compare:{m.metric_id}"), confidence=conf,
        )
        exact = stats.mcnemar_exact(b10, b01)
        chi2 = stats.mcnemar_chi2(b10, b01)
        results.append({
            "id": m.metric_id,
            "label": m.label,
            "type": "binary",
            "population": m.population,
            "n": n,
            "a": {"numerator": ka, "denominator": n, "estimate": round(ka / n, 6)},
            "b": {"numerator": kb, "denominator": n, "estimate": round(kb / n, 6)},
            "difference": diff.to_dict(),
            "discordant": {"a_only": b10, "b_only": b01},
            "test": exact.to_dict(),
            "test_chi2_cc": chi2.to_dict(),
            "cohens_h": round(stats.cohens_h(kb / n, ka / n), 6),
        })
    for name, label_name in (("leaking", "leaking"), ("derived", "clean"), ("live", "live")):
        ids = [s for s in paired if ta[s]["label"] == label_name
               and (name != "derived" or ta[s]["negative_kind"] == "derived")]
        if not ids:
            continue
        ra = [float(ta[s]["ri"]) for s in ids]
        rb = [float(tb[s]["ri"]) for s in ids]
        metric_id = f"ri.mean.{name}"
        diff = stats.paired_bootstrap_diff(
            ra, rb, n_boot=n_boot, seed=metric_seed(seed, f"compare:{metric_id}"),
            confidence=conf,
        )
        test = stats.sign_flip_test([y - x for x, y in zip(ra, rb, strict=True)],
                                    seed=metric_seed(seed, f"signflip:{metric_id}"))
        results.append({
            "id": metric_id,
            "label": f"Mean RI ({name})",
            "type": "continuous",
            "population": f"{name} units",
            "n": len(ids),
            "a": {"estimate": round(stats.mean(ra), 6)},
            "b": {"estimate": round(stats.mean(rb), 6)},
            "difference": diff.to_dict(),
            "test": test.to_dict(),
        })
    adjusted = stats.holm_bonferroni([r["test"]["p_value"] for r in results])
    for r, p in zip(results, adjusted, strict=True):
        r["p_holm"] = round(p, 6)

    flips = []
    for sid in paired:
        la, lb = ta[sid]["leaked"], tb[sid]["leaked"]
        if la != lb:
            flips.append({
                "scenario_id": sid,
                "label": ta[sid]["label"],
                "negative_kind": ta[sid]["negative_kind"],
                "direction": "no_finding->leak_detected" if lb else "leak_detected->no_finding",
                "channels_a": sorted(ta[sid]["channels"]),
                "channels_b": sorted(tb[sid]["channels"]),
            })

    doc = {
        "schema": COMPARISON_SCHEMA,
        "a": {"path": str(a.out_dir), "experiment": a.summary.get("experiment"),
              "detector": a.summary.get("detector"),
              "agentleak_version": a.summary.get("software", {}).get("agentleak_version")},
        "b": {"path": str(b.out_dir), "experiment": b.summary.get("experiment"),
              "detector": b.summary.get("detector"),
              "agentleak_version": b.summary.get("software", {}).get("agentleak_version")},
        "checks": checks,
        "forced": bool(failures and force),
        "settings": {"seed": seed, "bootstrap_resamples": n_boot, "confidence": conf,
                     "multiple_comparisons": "holm-bonferroni over all metrics below"},
        "paired_units": len(paired),
        "metrics": results,
        "flips": flips,
    }
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "comparison.json").write_text(dump_json(doc), encoding="utf-8")
        (out / "COMPARISON.md").write_text(render_comparison(doc), encoding="utf-8")
        from .export import comparison_latex

        (out / "comparison.tex").write_text(comparison_latex(doc), encoding="utf-8")
    return doc


def _rate(side: dict[str, Any]) -> str:
    if "numerator" in side:
        return f"{side['estimate']:.3f} ({side['numerator']}/{side['denominator']})"
    return f"{side['estimate']:.3f}"


def render_comparison(doc: dict[str, Any]) -> str:
    """Markdown rendering of a comparison."""
    conf = round(doc["settings"]["confidence"] * 100)
    lines = [
        f"# Comparison: {doc['b']['experiment']} (B) vs {doc['a']['experiment']} (A)",
        "",
        f"A: `{doc['a']['path']}` · B: `{doc['b']['path']}` · {doc['paired_units']} paired "
        "scenarios.",
        "",
        "## Comparability",
        "",
    ]
    marks = {"ok": "ok", "warn": "WARNING", "fail": "NOT COMPARABLE"}
    for c in doc["checks"]:
        lines.append(f"- **{marks[c['status']]}** {c['check']}: {c['detail']}")
    if doc.get("forced"):
        lines.append("- Compared with --force despite the failures above.")
    lines += [
        "",
        "## Paired differences (B - A)",
        "",
        f"Intervals: {conf}% paired bootstrap ({doc['settings']['bootstrap_resamples']} "
        "resamples). Tests: exact McNemar for rates, sign-flip for mean RI. p (Holm) is "
        "adjusted over every row of this table.",
        "",
        "| Metric | A | B | B - A | CI | Test | p | p (Holm) | Cohen's h |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for r in doc["metrics"]:
        d = r["difference"]
        h = f"{r['cohens_h']:+.3f}" if "cohens_h" in r else ""
        lines.append(
            f"| {r['label']} | {_rate(r['a'])} | {_rate(r['b'])} | {d['estimate']:+.3f} | "
            f"{d['ci_low']:+.3f} to {d['ci_high']:+.3f} | {r['test']['test']} | "
            f"{r['test']['p_value']:.4f} | {r['p_holm']:.4f} | {h} |"
        )
    lines += ["", f"## Scenarios that flipped ({len(doc['flips'])})", ""]
    if not doc["flips"]:
        lines.append("None.")
    else:
        lines += ["| Scenario | Label | Change | Channels A | Channels B |", "|---|---|---|---|---|"]
        for f in doc["flips"]:
            label = f["label"] + (f" ({f['negative_kind']})" if f["negative_kind"] else "")
            lines.append(
                f"| `{f['scenario_id']}` | {label} | {f['direction']} | "
                f"{', '.join(f['channels_a']) or '-'} | {', '.join(f['channels_b']) or '-'} |"
            )
    lines.append("")
    return "\n".join(lines)


__all__ = ["COMPARISON_SCHEMA", "ComparisonError", "compare_runs", "render_comparison"]
