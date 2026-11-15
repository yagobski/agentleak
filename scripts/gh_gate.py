#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""GitHub Action entry point for the AgentLeak privacy gate.

Runs one analysis (a captured trace, a built-in/benchmark scenario, or a static
code scan), then turns the result into things GitHub understands: workflow
annotations on the offending lines or channels, a job summary a reviewer can
read without opening logs, step outputs for downstream jobs, and an exit code
that blocks the merge.

Optional, off by default: a SARIF file for GitHub code scanning (``sarif``)
and a sticky pull-request comment (``pr-comment``) with the verdict, the
per-channel table and, given a baseline report, new and resolved findings.

Every value that comes from a report (data types, channels, run ids, file
names) is escaped before it reaches a workflow command, the job summary, a
comment or ``GITHUB_OUTPUT``; the CLI's own output runs between
``stop-commands`` markers so a trace cannot inject workflow commands either.

Kept dependency-free on purpose: it shells out to the installed ``agentleak``
CLI, so the Action pins the tool, not a private import surface.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

# GitHub truncates annotations past this; keep well under it.
MAX_ANNOTATIONS = 40
LEVEL_TO_ANNOTATION = {4: "error", 3: "error", 2: "warning", 1: "notice"}
# Environment the agentleak CLI must not inherit (see _run_cli).
_PRIVATE_ENV = frozenset({"AL_GITHUB_TOKEN"})


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _escape_data(value: str) -> str:
    """Workflow-command message escaping, as GitHub's toolkit does it.

    ``%`` first, so a literal ``%0A`` in a finding stays text; ``\r`` and
    ``\n`` would otherwise end the command and start a new one on the next
    line, which is how a crafted file name or data type injects commands.
    """
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Property values also reserve ``,`` (between properties) and ``::``
    (end of properties). A lone ``:`` is left readable, as in titles such as
    "AgentLeak L4: ssn in log"; the runner only splits on ``::``."""
    return _escape_data(value).replace(",", "%2C").replace("::", "%3A%3A")


def _emit(kind: str, message: str, **props: Any) -> None:
    """Write one GitHub workflow command (annotation)."""
    parts = ",".join(
        f"{k}={_escape_property(str(v))}" for k, v in props.items() if v not in (None, "")
    )
    prefix = f"::{kind} {parts}::" if parts else f"::{kind}::"
    print(prefix + _escape_data(message))


def _set_output(name: str, value: Any) -> None:
    """One ``name=value`` line. A newline in ``value`` would start another
    output (or a heredoc), so line breaks and NULs become spaces."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    text = re.sub(r"[\r\n\x00]", " ", str(value))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{name}={text}\n")


_MD_ESCAPES = {ch: f"&#{ord(ch)};" for ch in "&<>\"'`|[]\\@*~#!()"}


def _md(value: Any, limit: int = 200) -> str:
    """Report text made inert in Markdown and HTML: no tags, links, images,
    table breaks, mentions or code spans; one line; bounded length."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value)).strip()
    if len(text) > limit:
        text = text[:limit] + "..."
    return "".join(_MD_ESCAPES.get(ch, ch) for ch in text)


def _code(value: Any, limit: int = 80) -> str:
    """A code span holding only identifier characters."""
    text = re.sub(r"[^A-Za-z0-9_.:/=-]", "?", str(value))[:limit]
    return f"`{text or '?'}`"


def _write_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(markdown + "\n")


def _run_cli(args: list[str]) -> int:
    """Run the agentleak CLI, streaming its output into the job log.

    The CLI prints values taken from the trace (agent names, run ids). Between
    ``::stop-commands::`` and the matching token, GitHub ignores workflow
    commands, so a line in a trace cannot become one.
    """
    print("$ " + _escape_data(shlex.join(["agentleak", *args])), flush=True)
    token = secrets.token_hex(16)
    print(f"::stop-commands::{token}", flush=True)
    # The comment token is for this script only. The CLI reads a config that
    # the pull request can change, and a config can name any environment
    # variable as an LLM-judge key sent to a URL it chooses.
    env = {k: v for k, v in os.environ.items() if k not in _PRIVATE_ENV}
    try:
        return subprocess.run(["agentleak", *args], check=False, env=env).returncode
    finally:
        print(f"::{token}::", flush=True)


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


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _channel_table(leaked: list[dict[str, Any]]) -> list[str]:
    """Per-channel table of leaked data types, every cell escaped."""
    by_channel: dict[str, set[str]] = {}
    worst: dict[str, int] = {}
    for finding in leaked:
        channel = str(finding.get("channel", "?"))
        by_channel.setdefault(channel, set()).add(str(finding.get("data_type", "?")))
        worst[channel] = max(worst.get(channel, 0), int(_float(finding.get("level", 0))))
    lines = ["| Channel | Leaked | Worst level |", "| --- | --- | --- |"]
    for channel, types in sorted(by_channel.items()):
        lines.append(f"| {_code(channel)} | {_md(', '.join(sorted(types)))} | L{worst[channel]} |")
    return lines


def _observation_line(report: dict[str, Any]) -> str | None:
    obs = report.get("observation") or {}
    if not isinstance(obs, dict) or not obs.get("unobserved_channels"):
        return None
    return (f"Imported from {_md(obs.get('source', '?'), 40)}: only "
            f"{_md(', '.join(map(str, obs.get('observable_channels') or [])))} could be observed. "
            f"Not observed, so not audited: {_md(', '.join(map(str, obs['unobserved_channels'])))}.")


def _summarize_trace(report: dict[str, Any], threshold: int, blocked: bool) -> str:
    score = int(_float(report.get("privacy_score", 0)))
    risk = _float(report.get("agentrisk", {}).get("risk_index", report.get("risk_index", 0)))
    verdict = str(report.get("verdict", "?"))
    leaked = [f for f in report.get("findings", []) if _float(f.get("level", 0)) > 0]

    lines = [
        "## AgentLeak privacy gate",
        "",
        f"{_verdict_emoji(verdict)} **{_md(verdict, 40)}** — privacy score **{score}/100** "
        f"(threshold {threshold}), AgentRisk **{risk:.2f}**",
        "",
    ]
    observed = _observation_line(report)
    if observed:
        lines += [observed, ""]
    if leaked:
        lines += [*_channel_table(leaked), ""]
        first = leaked[0]
        if first.get("recommendation"):
            lines += ["**Fix first:** " + _md(first["recommendation"], 400), ""]
    else:
        lines += ["No sensitive value crossed the boundary in this run.", ""]

    # Say how strong this verdict is: a Pass from regex alone should not be
    # read as a Pass from the full pipeline.
    detection = report.get("detection", {})
    if detection:
        tiers = ", ".join(str(t) for t in detection.get("tiers", [])) or "regex"
        note = f"Detection: {_code(detection.get('mode', '?'))} mode, tiers: {_md(tiers)}"
        if detection.get("degraded"):
            note += " — **degraded**: a requested tier could not run."
        lines += [note, ""]

    compliance = report.get("compliance", {})
    # The report keeps them under compliance.posture; the flat key is older.
    failed = (
        (compliance.get("posture") or {}).get("failed_frameworks")
        or compliance.get("failed_frameworks")
        or []
    )
    if failed:
        lines.append(f"**Compliance at risk:** {_md(', '.join(str(f) for f in failed[:6]))}")
        lines.append("")
    if blocked:
        lines.append("This run **blocks the merge**: it crossed the configured privacy policy.")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# baseline comparison and pull-request comment
# ----------------------------------------------------------------------
COMMENT_MARKER = "<!-- agentleak-privacy-gate -->"


def _finding_key(report: dict[str, Any], finding: dict[str, Any]) -> tuple[str, ...]:
    """What makes two findings "the same" across commits: event ids and
    values may move, the run, channel, data type and detector do not."""
    return (str(report.get("run_id", "")), str(finding.get("channel", "")),
            str(finding.get("data_type", "")), str(finding.get("detector", "")))


def _load_reports(path: str) -> list[dict[str, Any]]:
    """A report JSON file, a JSON list of reports, or a directory of report files."""
    target = Path(path)
    files = sorted(target.glob("*.json")) if target.is_dir() else [target]
    reports: list[dict[str, Any]] = []
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        reports += [r for r in items if isinstance(r, dict) and "findings" in r]
    return reports


def _diff(current: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> tuple[Counter, Counter]:
    now = Counter(_finding_key(r, f) for r in current for f in r.get("findings", []))
    before = Counter(_finding_key(r, f) for r in baseline for f in r.get("findings", []))
    return now - before, before - now


def _comment_body(reports: list[dict[str, Any]], threshold: int,
                  baseline: list[dict[str, Any]] | None, baseline_error: str | None = None) -> str:
    """The sticky pull-request comment. Every report value is escaped."""
    worst = min(reports, key=lambda r: _float(r.get("privacy_score", 0)))
    verdict = str(worst.get("verdict", "?"))
    blocked = sum(bool(r.get("blocked")) for r in reports)
    lines = [
        COMMENT_MARKER,
        "### AgentLeak privacy gate",
        "",
        f"{_verdict_emoji(verdict)} **{_md(verdict, 40)}** — lowest privacy score "
        f"**{int(_float(worst.get('privacy_score', 0)))}/100** (threshold {threshold}); "
        f"{len(reports)} run(s), {blocked} blocked.",
        "",
    ]
    observed = _observation_line(worst)
    if observed:
        lines += [observed, ""]
    leaked = [f for r in reports for f in r.get("findings", []) if _float(f.get("level", 0)) > 0]
    lines += [*_channel_table(leaked), ""] if leaked else ["No leak found by the enabled detectors.", ""]
    if baseline_error:
        lines += [f"Baseline not compared: {_md(baseline_error)}", ""]
    elif baseline is not None:
        new, resolved = _diff(reports, baseline)
        lines += [f"**Against the baseline:** {sum(new.values())} new, "
                  f"{sum(resolved.values())} resolved.", ""]
        for title, items in (("New", new), ("Resolved", resolved)):
            if not items:
                continue
            lines += [f"| {title} | Run | Channel | Data type | Count |", "| --- | --- | --- | --- | --: |"]
            for (run_id, channel, data_type, _detector), count in sorted(items.items())[:25]:
                lines.append(f"| {title.lower()} | {_code(run_id)} | {_code(channel)} | "
                             f"{_md(data_type, 60)} | {count} |")
            lines.append("")
    lines.append("<sub>Values are never shown. Generated by the AgentLeak Action.</sub>")
    return "\n".join(lines)


def _github_request(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "agentleak-action",
        **({"Content-Type": "application/json"} if data else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed GitHub API host
        payload = response.read()
    return json.loads(payload) if payload else None


def _pull_request_number() -> int | None:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).is_file():
        return None
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    number = (event.get("pull_request") or {}).get("number")
    return number if isinstance(number, int) else None


def _post_sticky_comment(body: str) -> str:
    """Create or update the one AgentLeak comment on this pull request.

    Returns what happened. Never raises: a comment that cannot be posted
    (a fork's read-only token, say) must not change the gate's verdict.
    """
    token = _env("AL_GITHUB_TOKEN")
    repo = _env("GITHUB_REPOSITORY")
    number = _pull_request_number()
    if not token or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
        return "skipped: no token or repository"
    if number is None:
        return "skipped: not a pull_request event"
    api = (_env("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    if not api.startswith("https://"):
        return "skipped: GITHUB_API_URL is not https"
    base = f"{api}/repos/{repo}/issues/{number}/comments"
    try:
        existing = None
        for page in range(1, 11):
            comments = _github_request("GET", f"{base}?per_page=100&page={page}", token) or []
            existing = next((c for c in comments if isinstance(c, dict)
                             and COMMENT_MARKER in str(c.get("body", ""))
                             and (c.get("user") or {}).get("type") == "Bot"), None)
            if existing or len(comments) < 100:
                break
        if existing:
            _github_request("PATCH", f"{api}/repos/{repo}/issues/comments/{int(existing['id'])}",
                            token, {"body": body})
            return "updated"
        _github_request("POST", base, token, {"body": body})
        return "created"
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
        _emit("warning", f"Could not post the pull-request comment: {exc}",
              title="AgentLeak PR comment")
        return "failed"


# ----------------------------------------------------------------------
# SARIF
# ----------------------------------------------------------------------
def _merge_sarif(files: list[Path], destination: Path) -> int:
    """One SARIF log holding every run's results. Returns the result count."""
    logs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    merged = {"$schema": logs[0].get("$schema"), "version": "2.1.0",
              "runs": [run for log in logs for run in log.get("runs", [])]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return sum(len(run.get("results", [])) for run in merged["runs"])


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
        f"Code privacy score **{int(_float(score))}/100** (threshold {threshold}): "
        f"{len(findings)} finding(s) across {int(_float(summary.get('files_scanned', 0)))} file(s)",
        "",
    ]
    if findings:
        lines += ["| Level | File | Rule |", "| --- | --- | --- |"]
        for finding in sorted(findings, key=lambda f: -int(f.get("level", 0)))[:15]:
            lines.append(
                f"| L{int(_float(finding.get('level', 0)))} | "
                f"{_md(finding.get('file', '?'))}:{int(_float(finding.get('line', 0)))} | "
                f"{_md(finding.get('rule', '?'), 80)} |"
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
    sarif_path = _env("AL_SARIF")
    pr_comment = _env("AL_PR_COMMENT", "false").lower() == "true"
    baseline_path = _env("AL_BASELINE")
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
        formats = "json,sarif" if sarif_path else "json"
        args = ["run", "--output", str(workdir), "--format", formats, "--fail-under", str(threshold)]
        if trace:
            args += ["--trace", trace]
        if pack:
            args += ["--pack", pack]
        if scenario:
            args += ["--scenario", scenario]
        if config:
            args += ["--config", config]

    exit_code = _run_cli(args)

    others: list[dict[str, Any]] = []
    if not is_scan:
        produced = sorted(workdir.glob("*.json"))
        report_path = produced[0] if produced else None
        if len(produced) > 1:
            # `scenario: all` and `pack` write one report per run. Reading only
            # the first (alphabetically) let a clean run speak for the batch:
            # outputs and summary said Pass while the exit code said Fail.
            # Headline the worst run and count every run's findings.
            loaded = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in produced]
            loaded.sort(key=lambda pr: (int(pr[1].get("privacy_score", 0)), str(pr[0])))
            report_path = loaded[0][0]
            others = [r for _, r in loaded[1:]]

    if report_path is None or not Path(report_path).exists():
        _emit(
            "error",
            "AgentLeak produced no report; see the step log above.",
            title="AgentLeak gate failed to run",
        )
        return exit_code or 1

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    total_findings = len(report.get("findings", [])) + sum(
        len(r.get("findings", [])) for r in others
    )

    if is_scan:
        score = int(_float(report.get("score", 0)))
        verdict = "Fail" if score < threshold else "Pass"
        risk = ""
        if annotate:
            _annotate_scan(report)
        if summarize:
            _write_summary(_summarize_scan(report, threshold))
    else:
        score = int(_float(report.get("privacy_score", 0)))
        verdict = str(report.get("verdict", "?"))
        risk = f"{_float(report.get('agentrisk', {}).get('risk_index', report.get('risk_index', 0))):.4f}"
        if annotate:
            _annotate_trace(report)
        if summarize:
            text = _summarize_trace(report, threshold, bool(report.get("blocked")))
            if others:
                blocked_runs = sum(bool(r.get("blocked")) for r in [report, *others])
                text = (
                    f"{len(others) + 1} runs analyzed, {blocked_runs} blocked. "
                    f"Showing the lowest-scoring run, {_code(report.get('run_id', '?'))}.\n\n" + text
                )
            _write_summary(text)

    if sarif_path:
        destination = Path(sarif_path)
        if is_scan:
            sarif_args = ["scan", scan_path, "--format", "sarif", "--output", str(destination)]
            if config:
                sarif_args += ["--config", config]
            _run_cli(sarif_args)
        else:
            files = sorted(workdir.glob("*.sarif"))
            if files:
                _merge_sarif(files, destination)
        if destination.is_file():
            _set_output("sarif", str(destination))
        else:
            _emit("warning", "No SARIF file was produced; see the step log above.",
                  title="AgentLeak SARIF")

    if pr_comment and not is_scan:
        baseline = None
        baseline_error = None
        if baseline_path:
            try:
                baseline = _load_reports(baseline_path)
            except (OSError, ValueError) as exc:
                baseline_error = f"could not read the baseline report ({type(exc).__name__})"
        body = _comment_body([report, *others], threshold, baseline, baseline_error)
        _set_output("comment", _post_sticky_comment(body))

    _set_output("score", score)
    _set_output("risk-index", risk)
    _set_output("verdict", verdict)
    _set_output("findings", total_findings)
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
