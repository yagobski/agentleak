# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""promptfoo eval results -> AgentLeak traces.

Verified against promptfoo 0.125.1: ``promptfoo eval -o results.json`` (and
``promptfoo export eval <id>``, which writes the same document) from a real
offline run with a stub provider, with and without OpenTelemetry tracing. See
``tests/fixtures/interop/README.md``.

The document::

    {"evalId": ..., "metadata": {"promptfooVersion": "0.125.1", ...},
     "results": {"version": 3, "results": [EvaluateResult, ...], ...},
     "traces": [TraceData, ...]}            # only when tracing was enabled

One trace per result row:

* ``prompt.raw`` (the rendered prompt sent to the target) -> user_input
* ``response.output`` -> final_output
* multi-turn red-team rows: ``response.metadata.redteamHistory``
  (``[{prompt, output}]``) -> one user_input and one final_output per turn.
  This field was read from the type definitions shipped in promptfoo 0.125.1
  (``RedteamHistoryEntry``); no offline multi-turn run produced one.
* when tracing was enabled, the row's ``traceId`` selects a ``TraceData``
  whose application spans (spans promptfoo did not create itself, that is,
  without ``promptfoo.span.role``) are read by the OpenInference / GenAI span
  adapter, exactly as the AgentLeak promptfoo assertion reads them with
  ``require_trace: true``. Tool calls, tool results, model turns and
  reasoning then become their own channels.

Without a trace, promptfoo saw only the prompt and the reply, and the report
says so.
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Channel, Event, Trace
from .base import (
    MAX_TRACES,
    ImportedTrace,
    ImportResult,
    obj,
    observation,
    safe_id,
    stamp,
)
from .source import Source

TOOL = "promptfoo"
BLACK_BOX = ["user_input", "final_output"]
#: What the span adapter can produce from an instrumented application.
TRACED = ["user_input", "tool_call", "tool_response", "inter_agent_message", "log", "final_output"]
_BLACK_BOX_NOTE = (
    "promptfoo recorded only the prompt sent and the reply received for this row. Tool calls, "
    "tool results, memory, logs, inter-agent messages and files were not observed, so they "
    "were not audited: no finding on them is not evidence that they are clean."
)
_TRACED_NOTE = (
    "Internal channels come from the OpenTelemetry spans the application exported to promptfoo. "
    "Only what the application instrumented is visible; shared memory and generated files are "
    "not represented in spans."
)


# ----------------------------------------------------------------------
# promptfoo's trace shape (shared with integrations.promptfoo_assert)
# ----------------------------------------------------------------------
def span_role(span: Any) -> Any:
    """``promptfoo.span.role`` of a span: test_case, target, grader, or None
    for a span the application exported itself."""
    attrs = span.get("attributes") if isinstance(span, dict) else None
    return attrs.get("promptfoo.span.role") if isinstance(attrs, dict) else None


def _time(value: Any) -> bool:
    """A non-negative span time the normalizer can actually convert."""
    from ..integrations.otel import _ms

    return _ms(value) is not None and value >= 0


def trace_problem(raw: dict[str, Any]) -> str | None:
    """Why promptfoo's trace (TraceData) cannot be trusted, if it cannot.

    Only what was exported can be checked: a span the application never
    created or never sent cannot be detected here.
    """
    if not isinstance(raw.get("traceId"), str) or not raw["traceId"]:
        return "trace is malformed: traceId must be a non-empty string"
    ids: set[str] = set()
    for i, span in enumerate(raw["spans"]):
        sid = span.get("spanId") if isinstance(span, dict) else None
        if not isinstance(sid, str) or not sid or sid in ids:
            return f"trace is malformed: span #{i} needs a unique spanId string"
        ids.add(sid)
        start, end = span.get("startTime"), span.get("endTime")
        if not _time(start) or (end is not None and not (_time(end) and end >= start)):
            return f"trace is malformed: span {sid} has an invalid startTime/endTime"
        # Optional fields may be absent, but a present value must have the right
        # type: an empty list is not a missing parent or empty attributes.
        parent, attrs = span.get("parentSpanId"), span.get("attributes")
        if not isinstance(span.get("name"), str) or (
                parent is not None and not isinstance(parent, str)):
            return f"trace is malformed: span {sid} needs a string name and parentSpanId"
        if attrs is not None and not isinstance(attrs, dict):
            return f"trace is malformed: span {sid} has non-object attributes"
        status = span.get("statusCode")
        if status is not None and (not isinstance(status, int) or isinstance(status, bool)):
            return f"trace is malformed: span {sid} has a non-integer statusCode"
    # Parent links must end at a root, not loop back: a span cannot be its own
    # ancestor, however long the chain.
    parent_of = {s["spanId"]: s["parentSpanId"] for s in raw["spans"] if s.get("parentSpanId")}
    for sid in parent_of:
        seen, node = {sid}, parent_of[sid]
        while node in parent_of:
            if node in seen:
                return f"trace is malformed: span {sid}'s parents form a cycle"
            seen.add(node)
            node = parent_of[node]
    for span in raw["spans"]:
        sid, parent = span["spanId"], span.get("parentSpanId")
        # promptfoo's test_case root stays open while assertions run, so only
        # its child, the target span, may point at a parent that is absent.
        if (parent and parent not in ids
                and (span.get("attributes") or {}).get("promptfoo.span.role") != "target"):
            return f"trace is partial: span {sid}'s parent {parent} is not in the trace"
        if span.get("endTime") is None:
            return f"trace is partial: span {sid} has no endTime (still open)"
        if span.get("statusCode") == 2:   # OTel ERROR
            return f"trace is partial: span {sid} ended with an error status"
    return None


def checked_spans(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """The spans to check (everything but promptfoo's graders, which may still
    be running) and the problem with them, if any."""
    spans = [s for s in raw["spans"] if span_role(s) != "grader"]
    return spans, trace_problem({**raw, "spans": spans})


def app_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Spans the application exported: promptfoo's own spans are not evidence
    of what the application did."""
    return [s for s in spans if span_role(s) is None]


# ----------------------------------------------------------------------
# detection
# ----------------------------------------------------------------------
def sniff(src: Source) -> tuple[bool, str]:
    doc = src.value
    if src.kind != "json" or not isinstance(doc, dict):
        return False, "not a JSON object"
    results = doc.get("results")
    if not isinstance(results, dict) or not isinstance(results.get("results"), list):
        return False, "no 'results.results' list"
    version = (doc.get("metadata") or {}).get("promptfooVersion") if isinstance(doc.get("metadata"), dict) else None
    if "evalId" not in doc and not version:
        return False, "no 'evalId' or 'metadata.promptfooVersion'"
    return True, (f"'evalId' and a 'results.results' list (results version "
                  f"{results.get('version')!r})" + (f", promptfooVersion {version}" if version else ""))


# ----------------------------------------------------------------------
# conversion
# ----------------------------------------------------------------------
def _output_content(output: Any) -> Any:
    if output is None:
        return None
    if isinstance(output, (str, dict, list)):
        return output
    return str(output)


def _labels(row: dict[str, Any]) -> dict[str, Any]:
    test = obj(row.get("testCase"))
    meta = obj(test.get("metadata"))
    grading = obj(row.get("gradingResult"))
    provider = obj(row.get("provider"))
    labels = {
        "provider": provider.get("label") or provider.get("id"),
        "test_index": row.get("testIdx"),
        "prompt_index": row.get("promptIdx"),
        "success": row.get("success"),
        "score": row.get("score"),
        "grading_pass": grading.get("pass"),
        "plugin_id": meta.get("pluginId"),
        "strategy_id": meta.get("strategyId"),
        "severity": meta.get("severity"),
        "description": row.get("description") or test.get("description"),
    }
    return {k: v for k, v in labels.items() if v not in (None, "")}


def _row_trace(row: dict[str, Any], run_id: str, tdata: dict[str, Any] | None,
               notes: list[str]) -> tuple[Trace, bool]:
    """One row -> trace. Returns the trace and whether spans contributed."""
    from ..integrations.otel import trace_from_spans

    response = obj(row.get("response"))
    prompt = obj(row.get("prompt"))
    meta = obj(response.get("metadata"))
    history = meta.get("redteamHistory")

    traced = False
    trace = Trace(run_id=run_id, agent_name="promptfoo-target")
    if tdata is not None:
        spans, problem = checked_spans(tdata)
        if problem:
            notes.append(f"row {run_id}: {problem}; the spans that are present were imported")
        own = app_spans(spans)
        if own:
            trace = trace_from_spans(own, run_id=run_id, agent_name="promptfoo-target")
            traced = bool(trace.events)
        else:
            notes.append(f"row {run_id}: the trace holds only promptfoo's own spans; the "
                         "application exported none")

    if isinstance(history, list) and history:
        # Multi-turn: every turn the target saw and every reply it gave.
        base = Trace(run_id=run_id, agent_name=trace.agent_name)
        for turn, entry in enumerate(history, start=1):
            if not isinstance(entry, dict):
                continue
            if entry.get("prompt") not in (None, ""):
                base.add_event("user_input", str(entry["prompt"]), source="attacker",
                               target="target", metadata={"turn": turn, "origin": "redteamHistory"})
            if entry.get("output") not in (None, ""):
                base.add_event("final_output", _output_content(entry["output"]), source="target",
                               target="user", metadata={"turn": turn, "origin": "redteamHistory"})
        base.events.extend(e for e in trace.events if e.channel_value not in ("user_input", "final_output"))
        trace = base
    else:
        if not trace.events_for_channel("user_input") and prompt.get("raw") not in (None, ""):
            trace.events.insert(0, Event(
                channel=Channel.USER_INPUT, content=str(prompt["raw"]), source="promptfoo",
                target="target", metadata={"origin": "prompt.raw"}))
        output = _output_content(response.get("output"))
        if not trace.events_for_channel("final_output") and output not in (None, ""):
            trace.add_event("final_output", output, source="target", target="user",
                            metadata={"origin": "response.output"})
    for number, event in enumerate(trace.events, start=1):
        event.event_id = f"evt_{number:03d}"
    return trace, traced


def convert(src: Source, reason: str) -> ImportResult:
    doc = src.value
    meta = obj(doc.get("metadata"))
    version = meta.get("promptfooVersion")
    results = doc["results"]
    notes: list[str] = []
    if results.get("version") not in (None, 3):
        notes.append(f"results version {results.get('version')!r}; this importer was verified "
                     "against version 3 (promptfoo 0.125.1)")
    traces_by_id: dict[str, dict[str, Any]] = {}
    for tdata in doc.get("traces") or []:
        if isinstance(tdata, dict) and isinstance(tdata.get("traceId"), str) \
                and isinstance(tdata.get("spans"), list):
            traces_by_id[tdata["traceId"]] = tdata

    result = ImportResult(
        tool=TOOL, tool_version=version, source_file=src.name, source_sha256=src.sha256,
        detected_because=reason,
        verification="real run (promptfoo 0.125.1); redteamHistory from type definitions only",
        observable_channels=TRACED if traces_by_id else BLACK_BOX, notes=notes,
    )
    eval_id = safe_id(doc.get("evalId"), "promptfoo")
    for index, row in enumerate(results["results"]):
        if len(result.traces) >= MAX_TRACES:
            notes.append(f"stopped after {MAX_TRACES} rows")
            break
        if not isinstance(row, dict):
            result.skipped += 1
            continue
        record_id = str(row.get("id") or f"{row.get('testIdx')}-{row.get('promptIdx')}")
        run_id = safe_id(f"{eval_id}_{row.get('testIdx', index)}_{row.get('promptIdx', 0)}",
                         f"promptfoo_{index}")
        tdata = traces_by_id.get(str(row.get("traceId"))) if row.get("traceId") else None
        trace, traced = _row_trace(row, run_id, tdata, notes)
        if not trace.events:
            result.skipped += 1
            continue
        obs = observation(TOOL, TRACED if traced else BLACK_BOX,
                          _TRACED_NOTE if traced else _BLACK_BOX_NOTE)
        stamp(trace, tool=TOOL, tool_version=version, source_file=src.name,
              source_sha256=src.sha256, record_id=record_id, observation_=obs,
              labels={**_labels(row), **({"trace_id": row.get("traceId")} if row.get("traceId") else {})})
        result.traces.append(ImportedTrace(record_id=record_id, trace=trace))
    if result.skipped:
        notes.append(f"{result.skipped} row(s) had neither a prompt nor a response (a provider "
                     "error, usually) and were not imported")
    if not traces_by_id:
        notes.append("the export has no 'traces': promptfoo saw only prompts and replies. Enable "
                     "`tracing:` in promptfoo and export spans from the application to audit "
                     "its internal channels")
    return result
