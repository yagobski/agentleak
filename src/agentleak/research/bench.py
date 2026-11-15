# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Run a benchmark described by a manifest and write its outputs.

Outputs, all in the run directory:

``rows.csv``            one row per scenario x repetition x disclosure channel
``summary.json``        metric records with numerators, denominators, intervals
``manifest.yaml``       the resolved manifest that was run
``manifest.lock.json``  manifest + environment + source hashes + output hashes
``REPORT.md``           the human-readable report
``traces/``             live mode only: every captured trace, for re-analysis

The run is resumable: finished units are appended to ``.partial/rows.jsonl``
as they complete, and a re-run of the same manifest skips them.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..core.agentrisk import BASELINE_CHANNELS
from ..core.config import Config
from ..core.runner import AgentLeakRunner
from ..core.trace import Trace
from ..detectors import BUILTIN_DETECTORS
from .corpus import DISCLOSURE_CHANNELS, Unit, select_units, source_provenance, trace_digest
from .manifest import Manifest, ManifestError, environment
from .rows import read_rows, rows_to_csv
from .summary import summarize

LOCK_SCHEMA = "agentleak.bench.lock/1"
ProgressFn = Callable[[int, int, str], None]


class RunError(RuntimeError):
    """A run that cannot proceed; the message says why and what to do."""


@dataclass
class BenchRun:
    """A finished (or loaded) benchmark run. ``rows`` are plain dicts."""

    out_dir: Path
    manifest: Manifest
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    lock: dict[str, Any]
    resumed_units: int = 0
    notes: list[str] = field(default_factory=list)
    #: True when the directory already held a finished run of this manifest,
    #: which was loaded instead of recomputed.
    reused: bool = False

    def metric(self, metric_id: str) -> dict[str, Any] | None:
        """One metric record from the summary, by id (e.g. ``"recall"``)."""
        for record in self.summary.get("metrics", []):
            if record["id"] == metric_id:
                return dict(record)
        return None

    def metrics(self) -> list[dict[str, Any]]:
        """All metric records (plain dicts, ready for ``pandas.DataFrame``)."""
        return [dict(r) for r in self.summary.get("metrics", [])]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def build_config(manifest: Manifest) -> Config:
    """The analyzer :class:`Config` a manifest's ``detection`` block describes."""
    det = manifest.detection
    toggles = {name: True for name in BUILTIN_DETECTORS}
    if isinstance(det.detectors, dict):
        unknown = sorted(set(det.detectors) - set(BUILTIN_DETECTORS))
        if unknown:
            raise ManifestError(
                f"detection.detectors: unknown detector(s) {unknown}. "
                f"Known: {', '.join(BUILTIN_DETECTORS)}"
            )
        toggles.update({k: bool(v) for k, v in det.detectors.items()})
    presidio = {"enabled": det.mode in ("standard", "hybrid"), **det.presidio}
    llm_judge = {"enabled": det.mode == "hybrid", **det.llm_judge}
    return Config.model_validate({
        "project": {"name": manifest.name},
        "detectors": toggles,
        "detection": {
            "mode": det.mode,
            "obscured_copies": det.obscured_copies,
            "presidio": presidio,
            "llm_judge": llm_judge,
        },
    })


def requested_tiers(mode: str) -> list[str]:
    tiers = ["regex"]
    if mode in ("standard", "hybrid"):
        tiers.append("presidio")
    if mode == "hybrid":
        tiers.append("semantic")
    return tiers


# ---------------------------------------------------------------------------
# Per-unit analysis
# ---------------------------------------------------------------------------
def analyze_unit(
    runner: AgentLeakRunner, unit: Unit, trace: Trace, repetition: int, *, label: str | None = None
) -> list[dict[str, Any]]:
    """Analyze one trace and return its six channel rows."""
    result = runner.analyze(trace)
    report = result.score.agentrisk
    leaked = [f for f in result.findings if f.channel not in BASELINE_CHANNELS]
    by_channel: dict[str, list[Any]] = {c: [] for c in DISCLOSURE_CHANNELS}
    for f in leaked:
        by_channel.setdefault(f.channel, []).append(f)
    reference = unit.reference_channels(trace)
    has_reference = bool(unit.ground_truth)
    scenario_leaked = int(report.leaked_count > 0)
    digest = trace_digest(trace)
    common = {
        "scenario_id": unit.unit_id,
        "source": unit.source,
        "origin_id": unit.origin_id,
        "domain": unit.domain,
        "failure_mode": unit.failure_mode,
        "adversary": unit.adversary,
        "label": label or unit.label,
        "negative_kind": unit.negative_kind if (label or unit.label) == "clean" else "",
        "counterpart_of": unit.counterpart_of,
        "repetition": repetition,
        "scenario_leaked": scenario_leaked,
        "findings": len(leaked),
        "severity_max": max((f.level for f in leaked), default=0),
        "ri": round(report.ri_global, 6),
        "wsl": report.wsl,
        "rho_s": report.rho_s,
        "leaked_secrets": report.leaked_count,
        "vault_secrets": report.vault_count,
        "privacy_score": result.privacy_score,
        "verdict": result.verdict,
        "outcome": "leak_detected" if scenario_leaked else "no_finding",
        "detection_mode": result.detection_mode,
        "tiers_run": ";".join(result.tiers),
        "degraded": int(result.degraded),
        "trace_sha256": digest,
    }
    rows = []
    for channel in DISCLOSURE_CHANNELS:
        items = by_channel.get(channel, [])
        rows.append({
            **common,
            "channel": channel,
            "channel_findings": len(items),
            "channel_severity_max": max((f.level for f in items), default=0),
            "channel_ri": round(report.ri_by_channel.get(channel, 0.0), 6),
            "channel_data_types": ";".join(sorted({f.data_type for f in items})),
            "channel_leaked": int(bool(items)),
            "reference_leak": ("1" if channel in reference else "0") if has_reference else "",
        })
    return rows


def _live_llm(manifest: Manifest) -> Any:
    from ..agent.llm import LLMConfig, OpenAICompatLLM

    agent = manifest.agent
    key = os.environ.get(agent.api_key_env, "") if agent.api_key_env else ""
    cfg = LLMConfig(
        base_url=agent.base_url or "https://api.openai.com/v1",
        model=agent.model,
        api_key=key,
        temperature=agent.temperature,
    )
    return OpenAICompatLLM(cfg)


def _live_trace(unit: Unit, llm: Any, max_steps: int) -> tuple[Trace, bool]:
    from ..agent.context import build_run_context
    from ..agent.runner import AgentRunError, run_scenario

    ctx = build_run_context({
        "id": unit.origin_id,
        "spec": unit.spec,
        "trace": unit.trace.to_dict(),
        "domain": unit.domain,
        "description": unit.description,
    })
    try:
        return run_scenario(ctx, llm, max_steps=max_steps), False
    except AgentRunError as exc:
        partial = exc.trace or Trace(run_id=f"failed_{unit.origin_id}")
        return partial, True


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary_digest(summary: dict[str, Any]) -> str:
    """SHA-256 of a summary with its timestamp blanked: the reproducibility check."""
    clean = dict(summary)
    clean["generated_at"] = ""
    return hashlib.sha256(dump_json(clean).encode("utf-8")).hexdigest()


def dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _detector_info(manifest: Manifest, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ran = sorted({t for r in rows for t in r["tiers_run"].split(";") if t})
    dets = manifest.detection.detectors
    return {
        "mode": manifest.detection.mode,
        "tiers_requested": requested_tiers(manifest.detection.mode),
        "tiers_run": ran,
        "degraded": any(r["degraded"] for r in rows),
        "detectors": dict(sorted(dets.items())) if isinstance(dets, dict) else "all",
        "obscured_copies": manifest.detection.obscured_copies,
        "canaries_used_by_detectors": False,
    }


def _safe_name(unit_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in unit_id)


def run_benchmark(
    manifest: Manifest | str | Path,
    out_dir: str | Path | None = None,
    *,
    fresh: bool = False,
    allow_drift: bool = False,
    progress: ProgressFn | None = None,
    llm: Any = None,
    traces_from: str | Path | None = None,
    generated_at: str | None = None,
) -> BenchRun:
    """Run a benchmark and write its outputs. Returns the :class:`BenchRun`.

    ``manifest`` may be a :class:`Manifest` or a path to a manifest YAML.
    ``out_dir`` overrides ``manifest.output_dir``. ``fresh`` discards any
    previous (partial) results in the directory. ``llm`` injects a chat client
    for live mode (tests); by default one is built from ``manifest.agent``.
    ``traces_from`` (live mode) re-analyzes the traces a previous live run
    saved in its ``traces/`` folder instead of calling the model again.
    """
    if not isinstance(manifest, Manifest):
        manifest = Manifest.load(manifest)
    out = Path(out_dir or manifest.resolved_output_dir())

    drift = manifest.check_pins()
    if drift and not allow_drift:
        raise RunError(
            "the manifest's pins do not match the installed software:\n  - "
            + "\n  - ".join(drift)
            + "\nRe-pin with `agentleak bench init --force`, or run with --allow-drift "
            "(the drift is then recorded in manifest.lock.json)."
        )

    digest = manifest.digest()
    lock_path = out / "manifest.lock.json"
    partial_dir = out / ".partial"
    partial_rows = partial_dir / "rows.jsonl"
    if fresh and out.exists():
        for name in ("rows.csv", "summary.json", "manifest.lock.json", "REPORT.md",
                     "manifest.yaml"):
            (out / name).unlink(missing_ok=True)
        shutil.rmtree(partial_dir, ignore_errors=True)
        shutil.rmtree(out / "traces", ignore_errors=True)

    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock.get("manifest_sha256") != digest:
            raise RunError(
                f"{out} already holds results of a different manifest. Choose another "
                "output directory, or pass --fresh to overwrite them."
            )
        if (out / "rows.csv").exists() and (out / "summary.json").exists():
            existing = load_run(out)
            existing.reused = True
            return existing

    state_path = partial_dir / "state.json"
    done: dict[tuple[str, int], list[dict[str, Any]]] = {}
    if partial_rows.exists():
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if state.get("manifest_sha256") != digest:
            raise RunError(
                f"{out} holds a partial run of a different manifest. Pass --fresh to "
                "discard it, or choose another output directory."
            )
        for line in partial_rows.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[(rec["unit"], rec["repetition"])] = rec["rows"]

    config = build_config(manifest)
    runner = AgentLeakRunner(config)
    live = manifest.agent.mode == "live"
    sel = manifest.scenarios
    units = select_units(
        sources=sel.sources, domains=sel.domains, failure_modes=sel.failure_modes,
        labels=sel.labels, ids=sel.ids, max_per_source=sel.max_per_source,
        counterparts="none" if live else sel.counterparts, seed=manifest.seed,
    )
    if not units:
        raise RunError("the manifest's scenario selection matched no scenarios. "
                       "Loosen scenarios.domains / failure_modes / ids.")
    if live and llm is None and traces_from is None:
        llm = _live_llm(manifest)

    out.mkdir(parents=True, exist_ok=True)
    partial_dir.mkdir(exist_ok=True)
    state_path.write_text(dump_json({"manifest_sha256": digest}), encoding="utf-8")
    total = len(units) * manifest.repetitions
    resumed = len(done)
    notes: list[str] = []
    step = 0
    with open(partial_rows, "a", encoding="utf-8") as sink:
        for unit in units:
            for rep in range(1, manifest.repetitions + 1):
                step += 1
                key = (unit.unit_id, rep)
                if key not in done:
                    if live:
                        fname = f"{_safe_name(unit.unit_id)}__rep{rep}.json"
                        if traces_from is not None:
                            saved = Path(traces_from) / fname
                            if not saved.exists():
                                raise RunError(f"no saved trace {saved} to re-analyze")
                            trace = Trace.from_json_file(str(saved))
                            failed = False
                        else:
                            trace, failed = _live_trace(unit, llm, manifest.agent.max_steps)
                        traces_dir = out / "traces"
                        traces_dir.mkdir(exist_ok=True)
                        (traces_dir / fname).write_text(
                            dump_json(trace.to_dict()), encoding="utf-8")
                        rows = analyze_unit(runner, unit, trace, rep, label="live")
                        if failed:
                            for r in rows:
                                r["degraded"] = 1
                            notes.append(f"{unit.unit_id} rep {rep}: the agent run failed "
                                         "part-way; the partial trace was analyzed.")
                    else:
                        rows = analyze_unit(runner, unit, unit.trace, rep)
                    done[key] = rows
                    sink.write(json.dumps({"unit": unit.unit_id, "repetition": rep,
                                           "rows": rows}, sort_keys=True) + "\n")
                    sink.flush()
                if progress:
                    progress(step, total, unit.unit_id)

    rows = [r for unit in units for rep in range(1, manifest.repetitions + 1)
            for r in done[(unit.unit_id, rep)]]
    sources = [source_provenance(s) for s in sel.sources]
    stamp = generated_at or _now()
    context = {
        "experiment": manifest.name,
        "generated_at": stamp,
        "agentleak_version": environment()["agentleak_version"],
        "detector": _detector_info(manifest, rows),
        "provenance": [
            {k: p[k] for k in ("source", "name", "license", "sha256", "source_url")}
            for p in sources
        ],
        "seed": manifest.seed,
        "confidence": manifest.statistics.confidence,
        "interval": manifest.statistics.interval,
        "bootstrap_resamples": manifest.statistics.bootstrap_resamples,
        "agent_mode": manifest.agent.mode,
        "manifest_sha256": digest,
    }
    summary = summarize(rows, context)
    if notes:
        summary["notes"] = [*summary["notes"], *notes]

    (out / "rows.csv").write_text(rows_to_csv(rows), encoding="utf-8")
    (out / "summary.json").write_text(dump_json(summary), encoding="utf-8")
    (out / "manifest.yaml").write_text(
        yaml.safe_dump(manifest.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    lock = {
        "schema": LOCK_SCHEMA,
        "generated_at": stamp,
        "manifest": manifest.to_dict(),
        "manifest_sha256": digest,
        "environment": environment(),
        "sources": sources,
        "pins": {
            "declared": manifest.pins,
            "current": manifest.current_pins(),
            "drift": drift,
            "drift_allowed": bool(drift and allow_drift),
        },
        "selection": {
            "units": len(units),
            "repetitions": manifest.repetitions,
            "unit_ids_sha256": hashlib.sha256(
                "\n".join(u.unit_id for u in units).encode("utf-8")).hexdigest(),
        },
        "detector": context["detector"],
        "outputs": {
            "rows.csv": _sha256_file(out / "rows.csv"),
            "summary.json (timestamp blanked)": summary_digest(summary),
        },
        "reproduce": f"agentleak bench run manifest.yaml --out {out.name}-replay",
    }
    lock_path.write_text(dump_json(lock), encoding="utf-8")

    from .render import render_report  # local: render imports this module's types

    (out / "REPORT.md").write_text(render_report(summary, lock), encoding="utf-8")
    shutil.rmtree(partial_dir, ignore_errors=True)
    return BenchRun(out, manifest, rows, summary, lock, resumed, notes)


def load_run(path: str | Path) -> BenchRun:
    """Load a finished run directory (rows, summary, lock and manifest)."""
    out = Path(path)
    missing = [n for n in ("rows.csv", "summary.json", "manifest.lock.json")
               if not (out / n).exists()]
    if missing:
        hint = " It looks unfinished; re-run the same manifest to resume." \
            if (out / ".partial").exists() else ""
        raise RunError(f"{out} is not a finished benchmark run (missing {', '.join(missing)}).{hint}")
    lock = json.loads((out / "manifest.lock.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    manifest = Manifest.from_dict(lock["manifest"], where=str(out / "manifest.lock.json"))
    return BenchRun(out, manifest, read_rows(out / "rows.csv"), summary, lock)


__all__ = [
    "BenchRun",
    "RunError",
    "analyze_unit",
    "build_config",
    "dump_json",
    "load_run",
    "requested_tiers",
    "run_benchmark",
    "summary_digest",
]
