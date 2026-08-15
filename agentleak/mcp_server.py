# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Expose AgentLeak to coding agents over the Model Context Protocol.

An agent writing code has no reason to shell out to a CLI, and it will not
compose four API calls on its own initiative. It calls tools. This module is
that surface: the same engine the CLI uses, presented as MCP tools an agent
already knows how to reach for.

Everything runs locally. No account, no key, no network — that is the default
and the point, because the teams that most need this are the ones whose traces
cannot leave the building. If a project key *is* configured, the result is also
sent to the platform so the run joins the project's history; a failure there is
reported and ignored, never allowed to swallow a local verdict.

## The tool that matters

`privacy_preflight` is the one an agent should reach for before it says "done".
It scans the source, optionally scores a run the agent supplies, and — this is
the part a bare scanner cannot do — says which findings are *new since the last
check*. See `core.memory` for why that distinction is load-bearing and why
identity deliberately ignores line numbers.

## What it does not do

It does not run the 283 bundled scenarios against the caller's agent. Those are
traces, and replaying them would require invoking the agent under test, which
MCP gives no way to do. They stay what they are: a corpus for the CLI and CI.
Saying so here, in the module that would be the natural place to fake it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.codescan import scan_path
from .core.memory import ProjectMemory, finding_id
from .core.trace import Trace
from .defenses import Sanitizer


def _parse_trace(payload: dict[str, Any]) -> Trace:
    """Turn a payload into a trace, refusing one with nothing in it.

    `Trace.from_dict` accepts a dict with no `events` and yields an empty run,
    which then scores a confident 100/100. An agent that sent a malformed trace
    would read that as "clean" — the precise failure this tool exists to catch,
    committed by the tool itself. An empty run is not a clean run.
    """
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError(
            "A trace needs a non-empty `events` list. An empty run cannot be "
            "scored, and scoring it as clean would be a false pass."
        )
    return Trace.from_dict(payload)


MCP_MISSING = (
    "The MCP server needs the `mcp` package. Install it with:\n"
    "    pip install 'agentleak[mcp]'"
)

# Long enough to act on, short enough that an agent reads all of it.
MAX_LISTED_FINDINGS = 20


def _code_findings(result: Any) -> list[dict[str, Any]]:
    """Flatten a code scan into the shape memory and agents both consume.

    Deduplicated by identity, because two detectors can land on the same value
    with the same rule and emit it twice. Left alone, an agent reads one problem
    as two and the counts here disagree with the counts in `since_last`, which
    are keyed by id. Same identity means same finding, by definition.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for f in result.findings:
        fid = finding_id(f.file, f.rule, f.snippet)
        if fid in seen:
            continue
        seen.add(fid)
        out.append(
            {
                "id": fid,
                "file": f.file,
                "line": f.line,
                "rule": f.rule,
                "data_type": f.data_type,
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "level": f.level,
                "snippet": f.snippet,
                "fix": f.recommendation,
            }
        )
    return out


def _next_steps(delta: Any, findings: list[dict[str, Any]], trace_report: dict | None) -> list[str]:
    """What to do next, most urgent first.

    Ordered by what actually blocks a release: a brand-new critical finding
    beats an old one the agent has already decided to live with.
    """
    steps: list[str] = []
    by_level = sorted(delta.new, key=lambda f: -f["level"])
    for finding in by_level[:3]:
        where = f"{finding['file']}:{finding['line']}"
        steps.append(f"New L{finding['level']} — {finding['rule']} at {where}. {finding['fix']}".strip())

    if delta.fixed:
        steps.append(f"{len(delta.fixed)} finding(s) fixed since the last check; keep them fixed.")

    if trace_report:
        # channel_risks is a list of records, each already carrying its L-label.
        leaking = sorted(
            r["channel"]
            for r in (trace_report.get("channel_risks") or [])
            if r.get("level_label") in ("L3", "L4") and r.get("channel") != "final_output"
        )
        if leaking:
            steps.append(
                "The run leaked on " + ", ".join(leaking)
                + ". The final answer being clean does not clear it."
            )

    if not steps:
        steps.append(
            "Nothing new. Re-run after the next change; a clean check is only "
            "as current as the code it read."
        )
    return steps


def preflight(path: str = ".", trace: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check a project before shipping it, and say what changed since last time.

    Pure function of the filesystem and the optional trace, so it is testable
    without an MCP client in the loop.
    """
    target = Path(path)
    if not target.exists():
        return {"error": f"No such path: {path}", "verdict": "Unknown"}

    result = scan_path(target)
    findings = _code_findings(result)

    memory = ProjectMemory(target if target.is_dir() else target.parent)
    delta = memory.compare(findings)

    trace_report: dict[str, Any] | None = None
    if trace:
        from . import AgentLeakRunner

        try:
            trace_report = AgentLeakRunner().analyze(_parse_trace(trace)).to_dict()
        except Exception as exc:  # noqa: BLE001 - a bad trace must not lose the scan
            trace_report = None
            findings.append(
                {
                    "id": "trace-error",
                    "file": "<trace>",
                    "line": 0,
                    "rule": "unreadable_trace",
                    "data_type": "n/a",
                    "severity": "info",
                    "level": 0,
                    "snippet": str(exc)[:200],
                    "fix": "Check the trace against the schema: agentleak schema trace",
                }
            )

    memory.record(
        findings,
        code_score=result.score,
        privacy_score=(trace_report or {}).get("privacy_score"),
    )

    verdict = "Pass"
    if any(f["level"] >= 4 for f in findings) or (trace_report or {}).get("verdict") == "Fail":
        verdict = "Fail"
    elif findings or (trace_report or {}).get("verdict") in ("High risk", "Conditional pass"):
        verdict = "Needs attention"

    return {
        "verdict": verdict,
        "code_score": result.score,
        "files_scanned": result.files_scanned,
        "privacy_score": (trace_report or {}).get("privacy_score"),
        "risk_index": (trace_report or {}).get("risk_index"),
        # Which tiers actually ran. A clean result from the regex tier alone is
        # a weaker claim than a clean result from the full pipeline, and an
        # agent that cannot see the difference will overstate it to a human.
        "detection": {
            "mode": result.detection_mode,
            "tiers": list(result.tiers),
            "degraded": bool((trace_report or {}).get("degraded")),
        },
        "since_last": delta.to_dict(),
        "summary": delta.summary(),
        "findings": findings[:MAX_LISTED_FINDINGS],
        "findings_truncated": max(0, len(findings) - MAX_LISTED_FINDINGS),
        "next_steps": _next_steps(delta, findings, trace_report),
    }


def scan_code(path: str = ".") -> dict[str, Any]:
    """Static privacy scan of source: secrets, PII in logs, unsafe sends."""
    target = Path(path)
    if not target.exists():
        return {"error": f"No such path: {path}"}
    result = scan_path(target)
    findings = _code_findings(result)
    return {
        "score": result.score,
        "files_scanned": result.files_scanned,
        "detection": {"mode": result.detection_mode, "tiers": list(result.tiers)},
        "findings": findings[:MAX_LISTED_FINDINGS],
        "findings_truncated": max(0, len(findings) - MAX_LISTED_FINDINGS),
    }


def check_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Score one agent run across all eight channels."""
    from . import AgentLeakRunner

    try:
        report = AgentLeakRunner().analyze(_parse_trace(trace)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Could not read the trace: {exc}"}
    return {
        "verdict": report["verdict"],
        "privacy_score": report["privacy_score"],
        "risk_index": report["risk_index"],
        "detection": report.get("detection", {}),
        "channel_risks": report.get("channel_risks", {}),
        "findings": report.get("findings", [])[:MAX_LISTED_FINDINGS],
        "recommendations": report.get("recommendations", []),
    }


def redact(text: str, style: str = "placeholder") -> dict[str, Any]:
    """Strip sensitive values out of text before it goes anywhere."""
    try:
        sanitized = Sanitizer(style=style).sanitize(text)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return {"text": sanitized, "style": style, "changed": sanitized != text}


# The description is the only prompt an agent ever sees for a tool, so each one
# says *when to reach for it*, not merely what it does. Input schemas are
# derived from the annotations by the SDK; writing them out here as well would
# be a second source of truth that can only drift.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "privacy_preflight",
        "fn": preflight,
        "description": (
            "Check this project for privacy problems before shipping, and report "
            "which findings are NEW since the last check. Call this after writing "
            "or changing code that touches user data, secrets, logging, or "
            "outbound calls. Optionally pass a trace of the run you just made to "
            "score it across all eight channels as well."
        ),
    },
    {
        "name": "privacy_scan_code",
        "fn": scan_code,
        "description": (
            "Scan source code for hardcoded secrets, PII written to logs, and "
            "sensitive values sent to third parties. Use when you only need the "
            "current state and not the change since last time."
        ),
    },
    {
        "name": "privacy_check_trace",
        "fn": check_trace,
        "description": (
            "Score one agent run for privacy leakage across tool calls, tool "
            "responses, shared memory, inter-agent messages, logs, generated "
            "files and the final answer. Use when you have captured a run and "
            "want to know whether data escaped on a channel nobody reads."
        ),
    },
    {
        "name": "privacy_redact",
        "fn": redact,
        "description": (
            "Remove sensitive values from text. Use before writing something to "
            "a log, an issue, a commit message, or any other place a secret "
            "should not end up. Styles: placeholder, masked, asterisk, "
            "category, hash, remove."
        ),
    },
]


def build_server() -> Any:
    """Assemble the MCP server, importing the SDK only when actually serving.

    The SDK import stays inside the function so the tool functions above remain
    unit-testable without it, and so a missing extra produces the install line
    rather than a traceback.
    """
    try:
        from mcp.server import MCPServer
    except ImportError as exc:  # pragma: no cover - exercised via the CLI path
        raise RuntimeError(MCP_MISSING) from exc

    server = MCPServer(
        "agentleak",
        instructions=(
            "Privacy checks for agent code and agent runs, run locally. Call "
            "privacy_preflight before telling a human the work is done: it "
            "reports what is wrong now and, more usefully, what is new since "
            "the last check."
        ),
    )
    for spec in TOOLS:
        server.add_tool(spec["fn"], name=spec["name"], description=spec["description"])
    return server


def run_stdio() -> None:  # pragma: no cover - process entry point
    """Serve over stdio, which is how editors and coding agents connect."""
    build_server().run("stdio")
