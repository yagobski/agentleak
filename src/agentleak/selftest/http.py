# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The HTTP path of the self-test: same document as the CLI and MCP paths.

``POST /api/agent/selftest`` (key auth) calls :func:`selftest_http`. The only
differences from the local CLI are where history lives (the project's stored
runs, not ``.agentleak/``) and the ``rerun`` hint, which names the endpoint.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.report import AnalysisResult
from ..core.trace import Trace
from . import formats
from .document import ScoredInput, _runtime_findings, build_document, parse_level
from .runner import DEFAULT_FAIL_ON


def _previous_entry(store: Any, project_id: str) -> dict[str, Any] | None:
    """The project's latest stored run, in history-entry shape (for ``delta``)."""
    runs = store.list_runs(project_id, limit=1)
    if not runs:
        return None
    run = store.get_run(runs[0]["id"]) or {}
    report = run.get("report") or {}
    item = ScoredInput(label="previous", format="stored", report=report,
                       event_channels=[], event_ids=[])
    findings = _runtime_findings([item], value_in_fingerprint=True)
    return {
        "run_id": runs[0]["id"],
        "at": runs[0].get("created_at"),
        "passed": not bool(report.get("blocked")),
        "privacy_score": report.get("privacy_score"),
        "risk_index": report.get("risk_index"),
        "findings": [{"fingerprint": f["fingerprint"]} for f in findings],
    }


def selftest_http(
    payload: dict[str, Any],
    *,
    project: dict[str, Any],
    store: Any,
    analyze: Callable[..., AnalysisResult],
    resolve_trace: Callable[..., tuple[Trace, Any]],
) -> dict[str, Any]:
    """Score ``payload`` (``trace`` in any accepted format, or ``scenario_id``)."""
    fail_on = parse_level(payload.get("fail_on") or f"L{DEFAULT_FAIL_ON}")
    fmt = "agentleak_trace"
    label = "<request>"
    notes: list[str] = []
    if payload.get("trace") is not None:
        loaded = formats.load_any(payload["trace"], label=label, fmt=payload.get("trace_format"))
        trace, fmt = loaded.trace, loaded.format
        payload = {**payload, "trace": trace.to_dict()}
        notes.append(f"format detected: {fmt}")
    else:
        trace, _canaries = resolve_trace(payload, store)
        label = f"scenario:{payload.get('scenario_id')}"
        fmt = "scenario"
    previous = _previous_entry(store, project["id"])
    result = analyze(payload, project_name=project["name"], store=store)
    report = result.to_dict()
    run = store.create_run(project["id"], report, source="selftest")
    item = ScoredInput(
        label=label, format=fmt, report=report,
        event_channels=[e.channel_value for e in trace.events],
        event_ids=[e.event_id for e in trace.events], notes=notes,
    )
    doc = build_document(
        mode="http", inputs=[item], fail_on=fail_on, previous=previous,
        rerun={
            "cli": "agentleak selftest --trace <file> --json",
            "argv": ["agentleak", "selftest", "--trace", "<file>", "--json"],
            "http": {"method": "POST", "path": "/api/agent/selftest",
                     "headers": {"X-AgentLeak-Key": "<your key>"},
                     "body": {"trace": "<the new trace>", "fail_on": f"L{fail_on}"}},
        },
        network={"used_by_agentleak": False,
                 "note": ("Analyzed by the AgentLeak server you called. It makes no further "
                          "call unless the project enables the LLM judge (see detection.tiers).")},
    )
    doc["platform_run_id"] = run["id"]
    doc["project_id"] = project["id"]
    return doc


__all__ = ["selftest_http"]
