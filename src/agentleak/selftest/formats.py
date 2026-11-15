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
it is ever executed or followed.

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

#: Refuse to load anything larger: a trace this size is almost certainly not one.
MAX_BYTES = 64 * 1024 * 1024
TRACE_SUFFIXES = (".json", ".jsonl", ".ndjson")

_RESPONSES_TYPES = {
    "function_call", "function_call_output", "message", "reasoning",
    "computer_call", "computer_call_output", "web_search_call", "file_search_call",
    "custom_tool_call", "custom_tool_call_output", "mcp_call", "local_shell_call",
    "local_shell_call_output", "code_interpreter_call",
}
_CHANNELS = {c.value for c in Channel}
_GENAI_OPS = {
    "chat", "text_completion", "generate_content", "execute_tool", "invoke_agent",
    "create_agent", "embeddings", "retrieval", "invoke_workflow", "invoke_runner",
    "plan", "fetch_response", "realtime_inference",
}
_FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


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
# converters
# ----------------------------------------------------------------------
def _text_of(content: Any) -> str:
    """Flatten message content (string, or a list of typed parts) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content") or part.get("refusal")
                if isinstance(text, (str, list)):
                    parts.append(_text_of(text))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        return _text_of(content.get("text") or content.get("content"))
    return str(content)


def from_openai_chat(messages: list[dict[str, Any]], *, run_id: str) -> Trace:
    """Chat-completions messages -> trace.

    ``system``/``user`` -> user_input; assistant ``tool_calls`` -> tool_call
    (target is the function name); ``tool``/``function`` -> tool_response
    (the tool name is recovered from ``tool_call_id`` when the message has no
    ``name``); assistant text -> inter_agent_message, except the last assistant
    text, which is the final_output.
    """
    trace = Trace(run_id=run_id, agent_name="chat_agent")
    names: dict[str, str] = {}
    last_text = max(
        (i for i, m in enumerate(messages)
         if m.get("role") == "assistant" and _text_of(m.get("content")).strip()),
        default=-1,
    )
    for i, m in enumerate(messages):
        role = str(m.get("role") or "")
        text = _text_of(m.get("content"))
        if role in ("system", "developer", "user"):
            if text.strip():
                trace.add_event("user_input", text, source=role, target="agent")
        elif role in ("tool", "function"):
            call_id = str(m.get("tool_call_id") or "")
            tool = str(m.get("name") or names.get(call_id) or "tool")
            trace.add_event("tool_response", text, source=tool, target="agent",
                            metadata={"tool_name": tool, "tool_call_id": call_id})
        elif role == "assistant":
            calls = list(m.get("tool_calls") or [])
            if isinstance(m.get("function_call"), dict):
                calls.append({"function": m["function_call"]})
            for call in calls:
                fn = call.get("function") or {} if isinstance(call, dict) else {}
                tool = str(fn.get("name") or "tool")
                if isinstance(call, dict) and call.get("id"):
                    names[str(call["id"])] = tool
                trace.add_event("tool_call", str(fn.get("arguments") or ""), source="agent",
                                target=tool, metadata={"tool_name": tool,
                                                       "tool_call_id": call.get("id") if isinstance(call, dict) else None})
            if text.strip():
                if i == last_text:
                    trace.add_event("final_output", text, source="agent", target="user")
                else:
                    trace.add_event("inter_agent_message", text, source="agent", target="agent")
    return trace


def from_openai_responses(items: list[dict[str, Any]], *, run_id: str) -> Trace:
    """Responses API / OpenAI Agents SDK items -> trace.

    Verified against ``RunResult.to_input_list()`` from openai-agents 0.24 and
    the ``openai`` 3.x Responses types:

    * ``{"role": "user"|"system"|"developer", "content": ...}`` -> user_input
    * ``function_call`` (``name``, ``arguments``, ``call_id``) -> tool_call;
      a ``transfer_to_<agent>`` call is an agent handoff -> inter_agent_message
    * ``function_call_output`` (``call_id``, ``output``) -> tool_response
    * ``reasoning`` summaries -> log
    * assistant ``message`` (``content[].output_text``) -> inter_agent_message,
      the last one -> final_output
    * other ``*_call`` items (web search, computer, shell, MCP) -> tool_call,
      their ``*_output`` -> tool_response
    """
    trace = Trace(run_id=run_id, agent_name="responses_agent")
    names: dict[str, str] = {}
    handoffs: set[str] = set()
    agent = "agent"

    def is_assistant_message(item: dict[str, Any]) -> bool:
        return item.get("role") == "assistant" and item.get("type", "message") == "message"

    last_msg = max(
        (i for i, it in enumerate(items) if is_assistant_message(it) and _text_of(it.get("content")).strip()),
        default=-1,
    )
    for i, item in enumerate(items):
        kind = str(item.get("type") or "")
        role = item.get("role")
        if role in ("user", "system", "developer") and kind in ("", "message"):
            text = _text_of(item.get("content"))
            if text.strip():
                trace.add_event("user_input", text, source=str(role), target=agent)
        elif kind == "function_call" or kind == "custom_tool_call":
            name = str(item.get("name") or "tool")
            call_id = str(item.get("call_id") or item.get("id") or "")
            names[call_id] = name
            args = item.get("arguments", item.get("input", ""))
            if name.startswith("transfer_to_"):
                handoffs.add(call_id)
                peer = name.removeprefix("transfer_to_")
                trace.add_event("inter_agent_message", str(args or ""), source=agent, target=peer,
                                metadata={"handoff": True, "tool_name": name, "call_id": call_id})
                agent = peer
            else:
                trace.add_event("tool_call", str(args or ""), source=agent, target=name,
                                metadata={"tool_name": name, "call_id": call_id})
        elif kind.endswith("_call_output"):
            call_id = str(item.get("call_id") or "")
            if call_id in handoffs:
                continue
            name = names.get(call_id, kind.removesuffix("_output"))
            output = item.get("output", "")
            trace.add_event("tool_response", output if isinstance(output, str) else json.dumps(output),
                            source=name, target=agent, metadata={"tool_name": name, "call_id": call_id})
        elif kind.endswith("_call"):
            name = kind.removesuffix("_call")
            payload = {k: v for k, v in item.items() if k not in ("id", "status", "type")}
            call_id = str(item.get("call_id") or item.get("id") or "")
            names[call_id] = name
            trace.add_event("tool_call", payload, source=agent, target=name,
                            metadata={"tool_name": name, "call_id": call_id})
        elif kind == "reasoning":
            text = _text_of(item.get("summary")) or _text_of(item.get("content"))
            if text.strip():
                trace.add_event("log", text, source=agent, target="reasoning")
        elif is_assistant_message(item):
            text = _text_of(item.get("content"))
            if text.strip():
                if i == last_msg:
                    trace.add_event("final_output", text, source=agent, target="user")
                else:
                    trace.add_event("inter_agent_message", text, source=agent, target="agent")
    return trace


def from_claude_code(records: list[dict[str, Any]], *, run_id: str) -> Trace:
    """A Claude Code transcript (one JSON object per line) -> trace.

    Main session: the human's turns -> user_input; assistant text -> final_output
    (it is shown to the user as it is written). Sub-agent transcript
    (``isSidechain: true``): the task string from the main agent and the
    sub-agent's text -> inter_agent_message. In both: ``thinking`` -> log;
    ``tool_use`` -> tool_call, except Write/Edit/MultiEdit/NotebookEdit ->
    generated_file (the content written, targeted at the file path);
    ``tool_result`` -> tool_response. Other record types (summary, system,
    attachment, snapshots) carry no agent action and are skipped.
    """
    trace = Trace(run_id=run_id, agent_name="claude_code")
    tool_names: dict[str, str] = {}
    sidechain = any(r.get("isSidechain") for r in records if isinstance(r, dict))
    me = "subagent" if sidechain else "claude_code"
    boss = "main_agent" if sidechain else "user"
    for record in records:
        if not isinstance(record, dict) or record.get("type") not in ("user", "assistant"):
            continue
        message = record.get("message") or {}
        role = message.get("role") or record.get("type")
        content = message.get("content")
        if isinstance(content, str):
            if role == "user":
                channel = "inter_agent_message" if sidechain else "user_input"
                trace.add_event(channel, content, source=boss, target=me)
            elif content.strip():
                channel = "inter_agent_message" if sidechain else "final_output"
                trace.add_event(channel, content, source=me, target=boss)
            continue
        for block in content or []:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text" and str(block.get("text") or "").strip():
                if role == "user":
                    trace.add_event("inter_agent_message" if sidechain else "user_input",
                                    block["text"], source=boss, target=me)
                else:
                    trace.add_event("inter_agent_message" if sidechain else "final_output",
                                    block["text"], source=me, target=boss)
            elif kind == "thinking" and str(block.get("thinking") or "").strip():
                trace.add_event("log", block["thinking"], source=me, target="reasoning")
            elif kind == "tool_use":
                name = str(block.get("name") or "tool")
                tool_input = block.get("input") or {}
                tool_names[str(block.get("id") or "")] = name
                if name in _FILE_TOOLS and isinstance(tool_input, dict):
                    written = (tool_input.get("content") or tool_input.get("new_string")
                               or tool_input.get("new_source") or tool_input.get("edits") or "")
                    trace.add_event("generated_file", written if isinstance(written, (str, list, dict)) else str(written),
                                    source=me, target=str(tool_input.get("file_path") or tool_input.get("notebook_path") or "file"),
                                    metadata={"tool_name": name, "tool_use_id": block.get("id")})
                else:
                    trace.add_event("tool_call", tool_input, source=me, target=name,
                                    metadata={"tool_name": name, "tool_use_id": block.get("id")})
            elif kind == "tool_result":
                name = tool_names.get(str(block.get("tool_use_id") or ""), "tool")
                trace.add_event("tool_response", _text_of(block.get("content")), source=name, target=me,
                                metadata={"tool_name": name, "tool_use_id": block.get("tool_use_id")})
    return trace


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def from_otel_genai(spans: list[Any], *, run_id: str) -> Trace:
    """OpenTelemetry GenAI semantic-convention spans -> trace.

    Verified against semantic-conventions-genai (execute-tool.md,
    client-inference.md, gen-ai-output-messages.json) and spans emitted by the
    OpenTelemetry Python SDK:

    * ``execute_tool``: ``gen_ai.tool.call.arguments`` -> tool_call,
      ``gen_ai.tool.call.result`` -> tool_response (both opt-in in the
      convention: without them the span carries no content and nothing is
      recorded — the report says so)
    * inference (``chat`` …): ``gen_ai.system_instructions`` and
      ``gen_ai.input.messages`` of the first span -> user_input;
      ``gen_ai.output.messages`` text parts -> inter_agent_message, the last
      one -> final_output; ``tool_call`` parts are not recorded twice when an
      ``execute_tool`` span carries the same call id
    * ``invoke_agent`` spans only give structure; their content, when present,
      is read the same way as an inference span
    Values may be structured (AnyValue) or JSON strings; both are read.
    """
    from ..integrations.otel import _ms

    trace = Trace(run_id=run_id, agent_name="otel_genai_agent")
    rows = []
    for span in spans:
        attrs = _span_attrs(span)
        start = _ms(span.get("startTimeUnixNano") if isinstance(span, dict) else None)
        rows.append((start, attrs, span))
    if all(r[0] is not None for r in rows):
        rows.sort(key=lambda r: r[0] or 0.0)
    executed_ids = {
        str(a.get("gen_ai.tool.call.id")) for _, a, _ in rows
        if a.get("gen_ai.operation.name") == "execute_tool" and a.get("gen_ai.tool.call.id")
    }
    seen_input = False
    outputs: list[int] = []
    for _, attrs, _span in rows:
        op = str(attrs.get("gen_ai.operation.name") or "")
        agent = str(attrs.get("gen_ai.agent.name") or "agent")
        if op == "execute_tool":
            tool = str(attrs.get("gen_ai.tool.name") or "tool")
            args = attrs.get("gen_ai.tool.call.arguments")
            if args is not None:
                trace.add_event("tool_call", _maybe_json(args), source=agent, target=tool,
                                metadata={"tool_name": tool, "origin": "otel_genai",
                                          "tool_call_id": attrs.get("gen_ai.tool.call.id")})
            result = attrs.get("gen_ai.tool.call.result")
            if result is not None:
                trace.add_event("tool_response", _maybe_json(result), source=tool, target=agent,
                                metadata={"tool_name": tool, "origin": "otel_genai"})
            continue
        if not seen_input:
            for key in ("gen_ai.system_instructions", "gen_ai.input.messages"):
                value = _maybe_json(attrs.get(key))
                text = _genai_text(value)
                if text:
                    trace.add_event("user_input", text, source="user", target=agent,
                                    metadata={"origin": "otel_genai", "attribute": key})
                    seen_input = True
        for message in _as_list(_maybe_json(attrs.get("gen_ai.output.messages"))):
            if not isinstance(message, dict):
                continue
            for part in message.get("parts") or []:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text" and str(part.get("content") or "").strip():
                    trace.add_event("inter_agent_message", part["content"], source=agent, target="agent",
                                    metadata={"origin": "otel_genai"})
                    outputs.append(len(trace.events) - 1)
                elif ptype == "tool_call" and str(part.get("id")) not in executed_ids:
                    tool = str(part.get("name") or "tool")
                    trace.add_event("tool_call", part.get("arguments") or "", source=agent, target=tool,
                                    metadata={"tool_name": tool, "origin": "otel_genai",
                                              "tool_call_id": part.get("id")})
                elif ptype == "reasoning" and str(part.get("content") or "").strip():
                    trace.add_event("log", part["content"], source=agent, target="reasoning",
                                    metadata={"origin": "otel_genai"})
    if outputs:
        final = trace.events[outputs[-1]]
        final.channel = Channel.FINAL_OUTPUT
        final.target = "user"
    return trace


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def _genai_text(value: Any) -> str:
    """Text of system instructions or input messages (parts with ``content``)."""
    texts: list[str] = []
    for item in _as_list(value):
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict):
            if isinstance(item.get("parts"), list):
                for part in item["parts"]:
                    if isinstance(part, dict) and part.get("type") in ("text", None) and part.get("content"):
                        texts.append(str(part["content"]))
            elif item.get("content"):
                texts.append(str(item["content"]))
    return "\n".join(t for t in texts if t.strip())


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


_MALFORMED = (AttributeError, TypeError, KeyError, IndexError, RecursionError)


def _detect_and_convert(data: Any, fmt: str | None, *, jsonl: bool, run_id: str) -> tuple[str, Trace]:
    """Detection and conversion, with malformed shapes reported as format errors.

    The converters walk untrusted JSON; a field of the wrong type (a string
    where spans were expected) raised AttributeError and the server answered
    500. Any such shape is now a :class:`TraceFormatError` (400 / exit 2).
    """
    try:
        detected = fmt or detect(data, jsonl=jsonl)
        return detected, convert(data, detected, run_id=run_id)
    except _MALFORMED as exc:
        raise TraceFormatError(
            f"the input has the wrong shape for {fmt or 'any known format'}: "
            f"{type(exc).__name__}"
        ) from exc


def load_text(text: str, *, label: str, fmt: str | None = None) -> LoadedTrace:
    """Parse, detect (unless ``fmt`` is given), and convert one input."""
    data, jsonl = _parse_text(text)
    run_id = Path(label).stem if label not in ("<stdin>", "") else "stdin"
    detected, trace = _detect_and_convert(data, fmt, jsonl=jsonl, run_id=run_id or "run")
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
    detected, trace = _detect_and_convert(data, fmt, jsonl=False, run_id="payload")
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
