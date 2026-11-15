# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""SARIF 2.1.0 for trace findings (``agentleak run --format sarif``).

Code scans already emit SARIF (:meth:`agentleak.core.codescan.ScanResult.to_sarif`);
this is the same for a trace, so leaks can appear in GitHub code scanning.

* one rule per leaked data type, with a stable id ``agentleak/trace/<data_type>``
  and a ``security-severity`` GitHub uses to rank it
* one result per leaked finding: ``level`` from the AgentRisk level (L3-L4
  error, L2 warning, L1 note); channel, level, detector and event id in
  ``properties``
* messages name the data type, the channel and the target; they never carry
  the value, not even its redacted form
* location: a logical location for the event (``<run_id>/<event_id>``, kind
  ``member``) and, when the trace file is known, a physical location in it,
  on the line that holds the event's id when it can be found
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_LEVEL = {4: "error", 3: "error", 2: "warning", 1: "note"}
#: GitHub ranks code-scanning alerts by this (critical >= 9, high >= 7, medium >= 4).
_SECURITY_SEVERITY = {4: "9.0", 3: "7.5", 2: "5.0", 1: "2.0"}
_SAFE_RULE = re.compile(r"[^a-z0-9_.-]+")


def rule_id(data_type: str) -> str:
    return "agentleak/trace/" + (_SAFE_RULE.sub("_", str(data_type).lower()).strip("_") or "unknown")


def _event_lines(trace_path: str | None) -> tuple[str | None, dict[str, int]]:
    """Repository-relative URI of the trace and the line of each event id in it."""
    if not trace_path:
        return None, {}
    path = Path(trace_path)
    uri = path.as_posix()
    if path.is_absolute():
        try:
            uri = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            uri = path.name
    lines: dict[str, int] = {}
    try:
        if path.is_file() and path.stat().st_size <= 64 * 1024 * 1024:
            pattern = re.compile(r'"event_id"\s*:\s*"([^"]+)"')
            with path.open(encoding="utf-8", errors="replace") as fh:
                for number, line in enumerate(fh, start=1):
                    for match in pattern.finditer(line):
                        lines.setdefault(match[1], number)
    except OSError:
        pass
    return uri, lines


def _fingerprint(run_id: str, finding: dict[str, Any]) -> str:
    key = "|".join(str(finding.get(k, "")) for k in ("data_type", "channel", "source", "target",
                                                       "event_id"))
    return hashlib.sha256(f"{run_id}|{key}".encode()).hexdigest()[:32]


def to_sarif(report: dict[str, Any], *, trace_path: str | None = None) -> dict[str, Any]:
    """A SARIF 2.1.0 log for one AgentLeak trace report (the ``run`` JSON)."""
    run_id = str(report.get("run_id") or "run")
    uri, lines = _event_lines(trace_path)
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for finding in report.get("findings", []):
        level = int(finding.get("level") or 1)
        data_type = str(finding.get("data_type") or "sensitive_data")
        channel = str(finding.get("channel") or "unknown")
        rid = rule_id(data_type)
        rule = rules.setdefault(rid, {
            "id": rid,
            "name": data_type.replace("_", " ").title().replace(" ", ""),
            "shortDescription": {"text": f"{data_type} disclosed by the agent"},
            "fullDescription": {"text": (
                f"A value of type {data_type} left the agent through a disclosure channel "
                "(a tool call, memory, a log, another agent, a file or the final answer).")},
            "help": {"text": str(finding.get("recommendation") or
                                 "Keep this value out of the channel it was written to.")},
            "defaultConfiguration": {"level": _LEVEL.get(level, "warning")},
            "properties": {"tags": ["privacy", "agent", "security"],
                           "precision": "high", "security-severity": _SECURITY_SEVERITY.get(level, "5.0"),
                           "privacyLevel": f"L{level}"},
        })
        # A rule's severity is its worst finding's.
        if float(_SECURITY_SEVERITY.get(level, "0")) > float(rule["properties"]["security-severity"]):
            rule["properties"]["security-severity"] = _SECURITY_SEVERITY[level]
            rule["properties"]["privacyLevel"] = f"L{level}"
            rule["defaultConfiguration"]["level"] = _LEVEL[level]
        event_id = str(finding.get("event_id") or "")
        location: dict[str, Any] = {
            "logicalLocations": [{
                "name": event_id or "event",
                "fullyQualifiedName": f"{run_id}/{event_id or 'event'}",
                "kind": "member",
            }],
            "message": {"text": f"event {event_id or '?'} on channel {channel}"},
        }
        if uri:
            physical: dict[str, Any] = {"artifactLocation": {"uri": uri}}
            physical["region"] = {"startLine": lines.get(event_id, 1)}
            location["physicalLocation"] = physical
        target = str(finding.get("target") or "")
        results.append({
            "ruleId": rid,
            "ruleIndex": list(rules).index(rid),
            "level": _LEVEL.get(level, "warning"),
            "message": {"text": (
                f"L{level} {data_type} disclosed on channel {channel}"
                + (f" to {target}" if target and target != "unknown" else "")
                + f" (event {event_id or '?'}, detector {finding.get('detector', '?')}). "
                "The value is redacted.")},
            "locations": [location],
            "partialFingerprints": {"agentleakFinding/v1": _fingerprint(run_id, finding)},
            "properties": {
                "channel": channel,
                "privacyLevel": f"L{level}",
                "severity": finding.get("severity"),
                "dataType": data_type,
                "detector": finding.get("detector"),
                "confidence": finding.get("confidence"),
                "eventId": event_id,
                "source": finding.get("source"),
                "target": target,
                "redacted": True,
            },
        })
    run_props: dict[str, Any] = {
        "runId": run_id,
        "privacyScore": report.get("privacy_score"),
        "riskIndex": report.get("risk_index"),
        "verdict": report.get("verdict"),
        "blocked": report.get("blocked"),
    }
    if report.get("observation"):
        run_props["observation"] = report["observation"]
    sarif_run: dict[str, Any] = {
        "tool": {"driver": {
            "name": "AgentLeak",
            "informationUri": "https://www.agentleak.org/docs#trace-analysis",
            "semanticVersion": _version(),
            "rules": list(rules.values()),
        }},
        "automationDetails": {"id": f"agentleak/trace/{run_id}/"},
        "properties": run_props,
        "results": results,
    }
    if uri:
        sarif_run["artifacts"] = [{"location": {"uri": uri}}]
    return {"$schema": SARIF_SCHEMA, "version": "2.1.0", "runs": [sarif_run]}


def _version() -> str:
    from .. import __version__

    return __version__


def render_sarif(report: dict[str, Any], *, trace_path: str | None = None) -> str:
    return json.dumps(to_sarif(report, trace_path=trace_path), indent=2, ensure_ascii=False)
