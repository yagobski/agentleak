#!/usr/bin/env python3
"""GitHub Action entry point for the AgentLeak privacy gate.

Runs one analysis (a captured trace, a built-in/benchmark scenario, or a static
code scan), then turns the result into things GitHub understands: workflow
annotations on the offending lines or channels, a job summary a reviewer can
read without opening logs, step outputs for downstream jobs, and an exit code
that blocks the merge.

Kept dependency-free on purpose: it shells out to the installed ``agentleak``
CLI, so the Action pins the tool, not a private import surface.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# GitHub truncates annotations past this; keep well under it.
MAX_ANNOTATIONS = 40
LEVEL_TO_ANNOTATION = {4: "error", 3: "error", 2: "warning", 1: "notice"}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _emit(kind: str, message: str, **props: Any) -> None:
    """Write one GitHub workflow command (annotation)."""
    parts = ",".join(f"{k}={v}" for k, v in props.items() if v not in (None, ""))
    prefix = f"::{kind} {parts}::" if parts else f"::{kind}::"
    # Newlines would end the command early; GitHub decodes %0A back to one.
    print(prefix + message.replace("\n", "%0A"))


def _set_output(name: str, value: Any) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{name}={value}\n")


def _write_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(markdown + "\n")


def _run_cli(args: list[str]) -> int:
    """Run the agentleak CLI, streaming its output into the job log."""
    print(f"$ agentleak {' '.join(args)}", flush=True)
    return subprocess.run(["agentleak", *args], check=False).returncode


def _verdict_emoji(verdict: str) -> str:
    return {
        "Pass": "✅",
        "Conditional pass": "🟡",
        "High risk": "🟠",
        "Fail": "❌",
    }.get(verdict, "•")


# ----------------------------------------------------------------------
# trace / scenario analysis
# ----------------------------------------------------------------------
def _annotate_trace(report: dict[str, Any]) -> None:
    """One annotation per leak, naming the channel it escaped through."""
    findings = [f for f in report.get("findings", []) if f.get("level", 0) > 0]
    findings.sort(key=lambda f: -int(f.get("level", 0)))
    for finding in findings[:MAX_ANNOTATIONS]:
        level = int(finding.get("level", 1))
        channel = finding.get("channel", "unknown")
        title = f"AgentLeak {finding.get('level_label', 'L?')}: {finding.get('data_type', 'sensitive data')} in {channel}"
        message = (
            f"{finding.get('data_type', 'Sensitive data')} left the boundary through "
            f"`{channel}` (detector: {finding.get('detector', '?')}, "
            f"confidence {finding.get('confidence', 0):.2f}).\n"
            f"{finding.get('recommendation', '')}"
        )
        _emit(LEVEL_TO_ANNOTATION.get(level, "warning"), message, title=title)


def _summarize_trace(report: dict[str, Any], threshold: int, blocked: bool) -> str:
    score = report.get("privacy_score", 0)
    risk = report.get("agentrisk", {}).get("risk_index", report.get("risk_index", 0))
    verdict = report.get("verdict", "?")
    leaked = [f for f in report.get("findings", []) if f.get("level", 0) > 0]

    lines = [
        "## AgentLeak privacy gate",
        "",
        f"{_verdict_emoji(verdict)} **{verdict}** — privacy score **{score}/100** "
        f"(threshold {threshold}), AgentRisk **{risk:.2f}**",
        "",
    ]
    if leaked:
        by_channel: dict[str, list[str]] = {}
        for finding in leaked:
            by_channel.setdefault(finding.get("channel", "?"), []).append(
                str(finding.get("data_type", "?"))
            )
        lines += ["| Channel | Leaked | Worst level |", "| --- | --- | --- |"]
        for channel, types in sorted(by_channel.items()):
            worst = max(
                (int(f.get("level", 0)) for f in leaked if f.get("channel") == channel),
                default=0,
            )
            lines.append(f"| `{channel}` | {', '.join(sorted(set(types)))} | L{worst} |")
        lines.append("")
        first = leaked[0]
        if first.get("recommendation"):
            lines += ["**Fix first:** " + str(first["recommendation"]), ""]
    else:
        lines += ["No sensitive value crossed the boundary in this run.", ""]

    compliance = report.get("compliance", {})
    failed = compliance.get("failed_frameworks") or []
    if failed:
        lines.append(f"**Compliance at risk:** {', '.join(str(f) for f in failed[:6])}")
        lines.append("")
    if blocked:
        lines.append("This run **blocks the merge**: it crossed the configured privacy policy.")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# static code scan
# ----------------------------------------------------------------------
def _annotate_scan(report: dict[str, Any]) -> None:
    """Annotations land on the exact file and line, like a linter."""
    findings = sorted(report.get("findings", []), key=lambda f: -int(f.get("level", 0)))
    for finding in findings[:MAX_ANNOTATIONS]:
        # Code findings carry `tier` (regex / entropy / correlation ...) where
        # trace findings carry `detector`, and no precomputed level label.
        level = int(finding.get("level", 1))
        title = f"AgentLeak L{level}: {finding.get('rule', 'privacy issue')}"
        message = (
            f"{finding.get('data_type', 'Sensitive data')} "
            f"({finding.get('rule', '?')}, {finding.get('severity', '?')} via "
            f"{finding.get('tier', '?')}).\n"
            f"{finding.get('recommendation', '')}"
        )
        _emit(
            LEVEL_TO_ANNOTATION.get(level, "warning"),
            message,
            title=title,
            file=finding.get("file", ""),
            line=finding.get("line", 1),
        )


def _summarize_scan(report: dict[str, Any], threshold: int) -> str:
    score = report.get("score", 0)
    findings = report.get("findings", [])
    # Counts live under `summary` in a code-scan document.
    summary = report.get("summary", {})
    lines = [
        "## AgentLeak code scan",
        "",
        f"Code privacy score **{score}/100** (threshold {threshold}): "
        f"{len(findings)} finding(s) across {summary.get('files_scanned', 0)} file(s)",
        "",
    ]
    if findings:
        lines += ["| Level | File | Rule |", "| --- | --- | --- |"]
        for finding in sorted(findings, key=lambda f: -int(f.get("level", 0)))[:15]:
            lines.append(
                f"| L{finding.get('level', '?')} | "
                f"`{finding.get('file', '?')}:{finding.get('line', '?')}` | "
                f"{finding.get('rule', '?')} |"
            )
        lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
def main() -> int:
    trace, scenario = _env("AL_TRACE"), _env("AL_SCENARIO")
    pack, scan_path = _env("AL_PACK"), _env("AL_SCAN")
    config = _env("AL_CONFIG")
    annotate = _env("AL_ANNOTATE", "true").lower() == "true"
    summarize = _env("AL_SUMMARY", "true").lower() == "true"
    try:
        threshold = int(_env("AL_FAIL_UNDER", "80") or 80)
    except ValueError:
        threshold = 80

    if not any((trace, scenario, pack, scan_path)):
        _emit(
            "error",
            "Nothing to analyze: set one of `trace`, `scenario`, `pack` or `scan`.",
            title="AgentLeak gate misconfigured",
        )
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="agentleak-gate-"))
    is_scan = bool(scan_path)

    if is_scan:
        report_path = workdir / "code-scan.json"
        args = ["scan", scan_path, "--output", str(report_path), "--fail-under", str(threshold)]
        if config:
            args += ["--config", config]
    else:
        report_path = None  # discovered after the run: named per run id
        args = ["run", "--output", str(workdir), "--format", "json", "--fail-under", str(threshold)]
        if trace:
            args += ["--trace", trace]
        if pack:
            args += ["--pack", pack]
        if scenario:
            args += ["--scenario", scenario]
        if config:
            args += ["--config", config]

    exit_code = _run_cli(args)

    if not is_scan:
        produced = sorted(workdir.glob("*.json"))
        report_path = produced[0] if produced else None

    if report_path is None or not Path(report_path).exists():
        _emit(
            "error",
            "AgentLeak produced no report; see the step log above.",
            title="AgentLeak gate failed to run",
        )
        return exit_code or 1

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    if is_scan:
        score = int(report.get("score", 0))
        verdict = "Fail" if score < threshold else "Pass"
        risk = ""
        if annotate:
            _annotate_scan(report)
        if summarize:
            _write_summary(_summarize_scan(report, threshold))
    else:
        score = int(report.get("privacy_score", 0))
        verdict = str(report.get("verdict", "?"))
        risk = f"{report.get('agentrisk', {}).get('risk_index', report.get('risk_index', 0)):.4f}"
        if annotate:
            _annotate_trace(report)
        if summarize:
            _write_summary(_summarize_trace(report, threshold, bool(report.get("blocked"))))

    _set_output("score", score)
    _set_output("risk-index", risk)
    _set_output("verdict", verdict)
    _set_output("findings", len(report.get("findings", [])))
    _set_output("report", str(report_path))

    if exit_code != 0:
        _emit(
            "error",
            f"Privacy gate failed: score {score}/100 is below the {threshold} threshold "
            "or the run crossed the configured policy.",
            title="AgentLeak privacy gate",
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
