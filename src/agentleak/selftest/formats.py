# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Read whatever trace an agent already has on disk, and say what it was.

An agent should not have to write a converter before it can test itself. This
module sniffs the shape of a file (or stdin) and maps it onto channels:

=====================  ====================================================
format id              what it is
=====================  ====================================================
``agentleak_trace``    ``{"events": [...]}`` — the native format
``agentleak_events``   JSON lines, one native event (``{"channel": ...}``) per line
``openai_chat``        chat-completions messages, bare list or ``{"messages": [...]}``
``openai_responses``   Responses API / OpenAI Agents SDK items
                       (``result.to_input_list()``, ``response.output``)
``claude_code``        a Claude Code session or sub-agent transcript (JSONL)
``otel_genai``         OpenTelemetry GenAI semantic-convention spans (OTLP JSON or list)
``otel_openinference`` OpenInference spans (OTLP JSON or list)
``agent_steps``        action/observation steps (OpenHands, Cline, computer use)
=====================  ====================================================

Every converter is a faithful mapping, never a synthesis: an event exists only
when the input recorded one. Content in a trace is data to analyze; nothing in
it is ever executed or followed. The converters themselves live in
:mod:`agentleak.interop.convert`, shared with the SDK adapters.

How each shape was verified is recorded in ``docs/reports/SELFTEST-REPORT.md``; the test
fixtures under ``tests/fixtures/selftest/`` were produced by the real SDKs
where one exists (OpenAI Agents SDK, ``openai`` types, OpenTelemetry SDK).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.trace import Channel, Trace
from ..interop import convert as _convert

#: Refuse to load anything larger: a trace this size is almost certainly not one.
MAX_BYTES = 64 * 1024 * 1024
TRACE_SUFFIXES = (".json", ".jsonl", ".ndjson")

_RESPONSES_TYPES = _convert.RESPONSES_TYPES
_CHANNELS = {c.value for c in Channel}
_GENAI_OPS = _convert.GENAI_OPS


class TraceFormatError(ValueError):
    """The input is readable but is not a trace this module understands."""


@dataclass
class LoadedTrace:
    label: str
    format: str
    trace: Trace
    notes: list[str]


# ----------------------------------------------------------------------
# reading
# ----------------------------------------------------------------------
def _parse_text(text: str) -> tuple[Any, bool]:
    """Parse JSON, falling back to JSON lines. Returns ``(data, was_jsonl)``."""
    stripped = text.strip()
    if not stripped:
        raise TraceFormatError("the input is empty")
    try:
        return json.loads(stripped), False
    except json.JSONDecodeError:
        pass
    rows: list[Any] = []
    bad = 0
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    if not rows:
        raise TraceFormatError("the input is neither JSON nor JSON lines")
    if bad > len(rows):
        raise TraceFormatError(f"{bad} of {bad + len(rows)} lines are not JSON")
    return rows, True


def read_source(source: str) -> list[tuple[str, str]]:
    """``(label, text)`` for a file, every trace file in a directory, or ``-`` (stdin).

    A directory is read one level deep, files ending in .json/.jsonl/.ndjson
    only. Only paths the caller named are read.
    """
    if source == "-":
        text = sys.stdin.read()
        if len(text.encode("utf-8", "ignore")) > MAX_BYTES:
            raise TraceFormatError("stdin is larger than 64 MB")
        return [("<stdin>", text)]
    path = Path(source)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix in TRACE_SUFFIXES)
        if not files:
            raise TraceFormatError(f"no .json/.jsonl files in {source}")
        return [(str(p), _read_file(p)) for p in files]
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {source}")
    return [(str(path), _read_file(path))]


def _read_file(path: Path) -> str:
    if path.stat().st_size > MAX_BYTES:
        raise TraceFormatError(f"{path} is larger than 64 MB")
    return path.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# detection
# ----------------------------------------------------------------------
def _span_attrs(span: Any) -> dict[str, Any]:
    from ..integrations.otel import _attrs_of

    return _attrs_of(span)


def _spans_of(data: Any) -> list[Any] | None:
    if isinstance(data, dict) and "resourceSpans" in data:
        from ..integrations.otel import _spans_from_otlp

        return _spans_from_otlp(data)
    if isinstance(data, dict) and isinstance(data.get("spans"), list):
        return list(data["spans"])
    if isinstance(data, list) and data and all(
        isinstance(s, dict) and "attributes" in s and ("name" in s or "spanId" in s or "span_id" in s)
        for s in data
    ):
        return list(data)
    return None


def detect(data: Any, *, jsonl: bool = False) -> str:
    """Name the format of parsed input, or raise :class:`TraceFormatError`."""
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return "agentleak_trace"
    if isinstance(data, list) and data and all(
        isinstance(r, dict) and r.get("channel") in _CHANNELS for r in data
    ):
        return "agentleak_events"
    if isinstance(data, list) and data and any(
        isinstance(r, dict) and r.get("type") in ("user", "assistant") and isinstance(r.get("message"), dict)
        for r in data
    ):
        return "claude_code"
    spans = _spans_of(data)
    if spans is not None:
        ops = {str(_span_attrs(s).get("gen_ai.operation.name") or "") for s in spans}
        return "otel_genai" if ops & _GENAI_OPS else "otel_openinference"
    items = _items_of(data)
    if items is not None:
        if any(isinstance(i, dict) and i.get("type") in _RESPONSES_TYPES for i in items):
            return "openai_responses"
        if all(isinstance(i, dict) and "role" in i for i in items):
            return "openai_chat"
    steps = data.get("steps") if isinstance(data, dict) else data
    if isinstance(steps, list) and steps and all(isinstance(s, dict) and "action" in s for s in steps):
        return "agent_steps"
    if isinstance(data, dict):
        from ..scenarios.convert import detect_format

        other = detect_format(data)
        if other in ("agentleak_spec", "ai4privacy", "privacylens", "agentdojo"):
            raise TraceFormatError(
                f"this is a {other} scenario definition, not a recording of your agent. "
                "Run your agent on it and score the run, or use `agentleak selftest --cmd`."
            )
        if other == "oss_scenario":
            return "agentleak_trace"
    raise TraceFormatError(
        "unrecognised trace format. Accepted: AgentLeak trace ({\"events\": [...]}), "
        "AgentLeak event JSON lines, OpenAI chat messages, OpenAI Responses / Agents SDK "
        "items, Claude Code transcript JSONL, OpenTelemetry GenAI or OpenInference spans, "
        "agent steps. See `agentleak schema trace`."
    )


def _items_of(data: Any) -> list[Any] | None:
    if isinstance(data, list) and data and all(isinstance(i, dict) for i in data):
        return data
    if isinstance(data, dict):
        for key in ("messages", "items", "output", "input"):
            value = data.get(key)
            if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
                return value
    return None


# ----------------------------------------------------------------------
# converters: one implementation, shared with the SDK adapters and importers
# ----------------------------------------------------------------------
from_openai_chat = _convert.from_openai_chat
from_openai_responses = _convert.from_openai_responses
from_claude_code = _convert.from_claude_code
from_otel_genai = _convert.from_otel_genai
_text_of = _convert.text_of
_maybe_json = _convert.maybe_json
_as_list = _convert.as_list
_genai_text = _convert.genai_text


def convert(data: Any, fmt: str, *, run_id: str) -> Trace:
    """Turn parsed input of a known format into a :class:`Trace`."""
    if fmt == "agentleak_trace":
        payload = data if "events" in data else data["trace"]
        return Trace.from_dict(payload)
    if fmt == "agentleak_events":
        return Trace.from_dict({"run_id": run_id, "events": data})
    if fmt == "openai_chat":
        return from_openai_chat(_items_of(data) or [], run_id=run_id)
    if fmt == "openai_responses":
        return from_openai_responses(_items_of(data) or [], run_id=run_id)
    if fmt == "claude_code":
        return from_claude_code(data, run_id=run_id)
    if fmt == "otel_genai":
        return from_otel_genai(_spans_of(data) or [], run_id=run_id)
    if fmt == "otel_openinference":
        from ..integrations.otel import trace_from_spans

        return trace_from_spans(_spans_of(data) or [], run_id=run_id)
    if fmt == "agent_steps":
        from ..integrations.computer_use import trace_from_steps

        steps = data.get("steps") if isinstance(data, dict) else data
        return trace_from_steps(list(steps or []), run_id=run_id)
    raise TraceFormatError(f"no converter for {fmt}")


def load_text(text: str, *, label: str, fmt: str | None = None) -> LoadedTrace:
    """Parse, detect (unless ``fmt`` is given), and convert one input."""
    data, jsonl = _parse_text(text)
    detected = fmt or detect(data, jsonl=jsonl)
    run_id = Path(label).stem if label not in ("<stdin>", "") else "stdin"
    trace = convert(data, detected, run_id=run_id or "run")
    notes: list[str] = []
    if not trace.events:
        raise TraceFormatError(
            f"read as {detected}, but it produced no events. An empty run cannot be "
            "scored; scoring it would be a false pass."
        )
    channels = {e.channel_value for e in trace.events}
    if detected in ("otel_genai", "otel_openinference") and not channels - {"user_input"}:
        notes.append("The spans carried no tool arguments or outputs (opt-in attributes in the "
                     "GenAI conventions); enable content capture in your instrumentation.")
    return LoadedTrace(label=label, format=detected, trace=trace, notes=notes)


def load_any(data: Any, *, label: str = "<payload>", fmt: str | None = None) -> LoadedTrace:
    """Same as :func:`load_text` for an already-parsed object (MCP / HTTP)."""
    detected = fmt or detect(data)
    trace = convert(data, detected, run_id="payload")
    if not trace.events:
        raise TraceFormatError(
            f"read as {detected}, but it produced no events. An empty run cannot be scored."
        )
    return LoadedTrace(label=label, format=detected, trace=trace, notes=[])


FORMATS: tuple[str, ...] = (
    "agentleak_trace", "agentleak_events", "openai_chat", "openai_responses",
    "claude_code", "otel_genai", "otel_openinference", "agent_steps",
)

__all__ = [
    "FORMATS",
    "LoadedTrace",
    "MAX_BYTES",
    "TraceFormatError",
    "convert",
    "detect",
    "from_claude_code",
    "from_openai_chat",
    "from_openai_responses",
    "from_otel_genai",
    "load_any",
    "load_text",
    "read_source",
]
