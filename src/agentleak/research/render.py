# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Human-readable renderings of a run summary: ``REPORT.md`` and the table
selections shared by the Markdown and LaTeX exports."""

from __future__ import annotations

from typing import Any

CHANNEL_LABELS = {
    "tool_call": "Tool call",
    "shared_memory": "Shared memory",
    "inter_agent_message": "Inter-agent message",
    "log": "Log",
    "generated_file": "Generated file",
    "final_output": "Final output",
}


def fmt_estimate(record: dict[str, Any], digits: int = 3) -> str:
    est = record.get("estimate")
    return "n/a" if est is None else f"{est:.{digits}f}"


def fmt_ci(record: dict[str, Any], digits: int = 3, sep: str = "–") -> str:
    lo, hi = record.get("ci_low"), record.get("ci_high")
    if lo is None or hi is None:
        return "n/a"
    return f"{lo:.{digits}f}{sep}{hi:.{digits}f}"


def fmt_frac(record: dict[str, Any]) -> str:
    num, den = record.get("numerator"), record.get("denominator")
    if num is None or den is None:
        return f"n={record.get('n', '')}"
    if isinstance(num, float) and not num.is_integer():
        return f"{num:g}/{den:g}"
    return f"{int(num)}/{int(den)}"


def _by_id(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["id"]: m for m in summary.get("metrics", [])}


def detection_rows(summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(label, record) pairs for the detection-performance table."""
    m = _by_id(summary)
    out: list[tuple[str, dict[str, Any]]] = []
    if "recall" in m:
        out.append(("Recall, all leaking fixtures", m["recall"]))
    for rec in summary.get("metrics", []):
        if rec["id"].startswith("recall.source."):
            out.append((f"Recall, {rec['group_value']}", rec))
    for kind in ("independent", "derived"):
        if f"specificity.{kind}" in m:
            out.append((f"Specificity, {kind} clean negatives", m[f"specificity.{kind}"]))
    for rec in summary.get("metrics", []):
        if rec["id"].startswith("specificity.derived.source."):
            out.append((f"Specificity, derived from {rec['group_value']}", rec))
    return out


def secondary_rows(summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    m = _by_id(summary)
    out = []
    for kind in ("independent", "derived"):
        if f"precision.vs_{kind}" in m:
            out.append((f"Precision vs {kind} negatives", m[f"precision.vs_{kind}"]))
        if f"f1.vs_{kind}" in m:
            out.append((f"F1 vs {kind} negatives", m[f"f1.vs_{kind}"]))
    for group in ("domain", "failure_mode", "adversary"):
        for rec in summary.get("metrics", []):
            if rec["id"].startswith(f"recall.{group}."):
                out.append((f"Recall, {group.replace('_', ' ')} {rec['group_value']}", rec))
    return out


def channel_rows(summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    m = _by_id(summary)
    out = []
    for rec in summary.get("metrics", []):
        if rec["id"].startswith("channel_leak_rate."):
            out.append((CHANNEL_LABELS.get(rec["group_value"], rec["group_value"]), rec))
    if "internal_only" in m:
        out.append(("Internal-only (share of detected leaks)", m["internal_only"]))
    if "missed_by_output_only_audit" in m:
        out.append(("Missed by an output-only audit (share of all)",
                    m["missed_by_output_only_audit"]))
    return out


def agentrisk_rows(summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    labels = {
        "ri.mean.leaking": "Mean RI, leaking fixtures",
        "ri.mean.clean.independent": "Mean RI, independent clean",
        "ri.mean.clean.derived": "Mean RI, derived clean",
        "ri.mean.live": "Mean RI, live runs",
        "ri.pooled": "Pooled RI (sum WSL / sum rho_S)",
        "leak_rate": "Leak rate (live)",
        "leak_fraction.mean": "Mean leak fraction over repetitions",
    }
    m = _by_id(summary)
    return [(label, m[key]) for key, label in labels.items() if key in m]


def integrity_rows(summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    labels = {
        "integrity.leaking_has_reference_leak": "Leaking fixtures whose ground truth is on a disclosure channel",
        "integrity.derived_free_of_reference": "Derived counterparts free of ground-truth values",
        "internal_only.reference": "Ground-truth leaks that never reach final output",
    }
    m = _by_id(summary)
    return [(label, m[key]) for key, label in labels.items() if key in m]


def provenance_line(summary: dict[str, Any]) -> str:
    parts = [
        f"{p['source']} ({p['license'] or 'licence not stated'}, sha256 {p['sha256'][:12]})"
        for p in summary.get("provenance", [])
    ]
    return "; ".join(parts)


def tier_line(summary: dict[str, Any]) -> str:
    det = summary.get("detector", {})
    run = ", ".join(det.get("tiers_run", [])) or "none"
    req = ", ".join(det.get("tiers_requested", [])) or "?"
    degraded = " DEGRADED: a requested tier did not run." if det.get("degraded") else ""
    return f"mode {det.get('mode', '?')}; tiers requested: {req}; tiers run: {run}.{degraded}"


def _md_table(rows: list[tuple[str, dict[str, Any]]]) -> list[str]:
    lines = ["| Metric | Estimate | n/N | CI | Method |", "|---|---:|---:|---|---|"]
    for label, rec in rows:
        lines.append(
            f"| {label} | {fmt_estimate(rec)} | {fmt_frac(rec)} | {fmt_ci(rec)} | "
            f"{rec.get('ci_method', '')} |"
        )
    return lines


def render_report(summary: dict[str, Any], lock: dict[str, Any]) -> str:
    """The ``REPORT.md`` of a run."""
    counts = summary.get("counts", {})
    settings = summary.get("settings", {})
    env = lock.get("environment", {})
    conf = round(float(settings.get("confidence", 0.95)) * 100)
    lines = [
        f"# {summary.get('experiment', 'Benchmark')}: AgentLeak benchmark report",
        "",
        f"AgentLeak {summary.get('software', {}).get('agentleak_version', '?')} · "
        f"detection {tier_line(summary)}",
        f"Generated {summary.get('generated_at', '')} · seed {settings.get('seed')} · "
        f"{conf}% intervals ({settings.get('interval')} for proportions, bootstrap BCa with "
        f"{settings.get('bootstrap_resamples')} resamples for means and F1).",
        f"Python {env.get('python', '?')} on {env.get('platform', '?')}; "
        f"git commit {(env.get('git') or {}).get('commit') or 'n/a'}.",
        "",
        f"Data: {provenance_line(summary)}.",
        "",
        "## What was run",
        "",
        f"- {counts.get('units', 0)} units, {counts.get('rows', 0)} rows "
        "(one per unit, repetition and disclosure channel).",
        f"- Leaking fixtures: {counts.get('leaking', 0)}. Independent clean controls: "
        f"{counts.get('clean_independent', 0)}. Derived clean counterparts: "
        f"{counts.get('clean_derived', 0)}.",
    ]
    if counts.get("live"):
        lines.append(f"- Live agent runs: {counts['live']} scenarios.")
    lines += [
        "- The detectors were not given the fixtures' ground truth (no canaries). "
        "Labels come from how each fixture was built, not from the detectors.",
        "",
    ]
    det = detection_rows(summary)
    if det:
        lines += ["## Detection performance", "",
                  "Independent and derived negatives have separate denominators and are "
                  "never pooled.", ""]
        lines += _md_table(det)
        sec = secondary_rows(summary)
        if sec:
            lines += ["", "Secondary breakdowns (precision and F1 depend on the corpus' "
                      "positive:negative ratio, which is set by construction):", ""]
            lines += _md_table(sec)
        lines.append("")
    ch = channel_rows(summary)
    if ch:
        lines += ["## Where detected leaks travel", "",
                  "Share of leaking units with a detector finding on each disclosure "
                  "channel. A unit can leak on several channels.", ""]
        lines += _md_table(ch)
        lines.append("")
    ar = agentrisk_rows(summary)
    if ar:
        lines += ["## AgentRisk", ""]
        lines += _md_table(ar)
        lines.append("")
    integ = integrity_rows(summary)
    if integ:
        lines += ["## Fixture integrity (corpus checks, not detector accuracy)", "",
                  "These compare each fixture with its own ground-truth values. They "
                  "describe the corpus and say nothing about how well the detectors work.",
                  ""]
        lines += _md_table(integ)
        lines.append("")
    types = [r for r in summary.get("metrics", []) if r["id"].startswith("data_type_prevalence.")]
    if types:
        lines += ["## Data types found on disclosure channels (descriptive)", "",
                  "| Data type | Units | Share |", "|---|---:|---:|"]
        for rec in sorted(types, key=lambda r: (-r["numerator"], r["group_value"])):
            lines.append(f"| `{rec['group_value']}` | {fmt_frac(rec)} | {fmt_estimate(rec)} |")
        lines.append("")
    lines += [
        "## Reading these numbers",
        "",
        "- A unit with no finding means *no finding from the enabled detectors*, not that "
        "the trace is safe. The fast tier is regex and dictionaries only.",
        "- Labels are defined by construction of the fixtures. Derived counterparts remove "
        "every disclosure event that carries a ground-truth value; a detector finding on "
        "one is a value outside that ground truth (for example an address the task "
        "legitimately sent), counted as a false positive against the label.",
        "- The corpus is small and built to exercise internal channels, so channel shares "
        "describe these fixtures, not deployed agents. Read the interval, not the point.",
    ]
    for note in summary.get("notes", []):
        lines.append(f"- {note}")
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "agentleak bench run manifest.yaml --out replay   # same manifest, same seed",
        "```",
        "",
        "`rows.csv` must be byte-identical and `summary.json` identical except "
        "`generated_at`; `manifest.lock.json` records the hashes to compare.",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "CHANNEL_LABELS",
    "agentrisk_rows",
    "channel_rows",
    "detection_rows",
    "fmt_ci",
    "fmt_estimate",
    "fmt_frac",
    "integrity_rows",
    "provenance_line",
    "render_report",
    "secondary_rows",
    "tier_line",
]
