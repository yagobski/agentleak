# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""One converter per trace format, shared by every entry point.

The self-test format loader (:mod:`agentleak.selftest.formats`), the SDK
adapters (:mod:`agentleak.integrations.openai_swarm`,
:mod:`agentleak.integrations.otel`) and the red-team importers
(:mod:`agentleak.interop`) all call these functions, so a shape that one of
them reads correctly is read the same way by the others.

=====================  ====================================================
converter              input
=====================  ====================================================
``from_openai_chat``   chat-completions messages (``role``/``content``,
                       ``tool_calls``, ``tool`` messages)
``from_openai_responses``  Responses API / OpenAI Agents SDK items
                       (``result.to_input_list()``, ``response.output``)
``from_claude_code``   a Claude Code session or sub-agent transcript
``from_otel_genai``    OpenTelemetry GenAI semantic-convention spans
``genai_span_events``  the same mapping for one span, used inside the
                       OpenInference adapter for mixed span lists
=====================  ====================================================

Every converter is a faithful mapping, never a synthesis: an event exists only
when the input recorded one. Content in a trace is data to analyze; nothing in
it is ever executed or followed.
"""

from __future__ import annotations

import json
from typing import Any

from ..core.trace import Channel, Trace

#: Item ``type`` values of the Responses API and the Agents SDK.
RESPONSES_TYPES = frozenset({
    "function_call", "function_call_output", "message", "reasoning",
    "computer_call", "computer_call_output", "web_search_call", "file_search_call",
    "custom_tool_call", "custom_tool_call_output", "mcp_call", "local_shell_call",
    "local_shell_call_output", "code_interpreter_call",
})
#: ``gen_ai.operation.name`` values of the OpenTelemetry GenAI conventions.
GENAI_OPS = frozenset({
    "chat", "text_completion", "generate_content", "execute_tool", "invoke_agent",
    "create_agent", "embeddings", "retrieval", "invoke_workflow", "invoke_runner",
    "plan", "fetch_response", "realtime_inference",
})
_FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def text_of(content: Any) -> str:
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
                    parts.append(text_of(text))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        return text_of(content.get("text") or content.get("content"))
    return str(content)


def maybe_json(value: Any) -> Any:
    """Parse a JSON string; return anything else unchanged."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, RecursionError):
            return value
    return value


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def is_responses_items(items: list[Any]) -> bool:
    """True when a list holds Responses API / Agents SDK items rather than
    plain chat-completions messages: at least one item has a Responses
    ``type``, or an assistant message carries typed content parts."""
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind in RESPONSES_TYPES and kind != "message":
            return True
        if kind == "message" or (
            item.get("role") == "assistant" and isinstance(item.get("content"), list)
            and any(isinstance(p, dict) and p.get("type") == "output_text" for p in item["content"])
        ):
            return True
    return False


# ----------------------------------------------------------------------
# chat completions
# ----------------------------------------------------------------------
def from_openai_chat(messages: list[dict[str, Any]], *, run_id: str,
                     agent_name: str = "chat_agent") -> Trace:
    """Chat-completions messages -> trace.

    ``system``/``developer``/``user`` -> user_input; assistant ``tool_calls`` ->
    tool_call (target is the function name); ``tool``/``function`` ->
    tool_response (the tool name is recovered from ``tool_call_id`` when the
    message has no ``name``); assistant text -> inter_agent_message, except
    the last assistant text, which is the final_output.
    """
    trace = Trace(run_id=run_id, agent_name=agent_name)
    names: dict[str, str] = {}
    last_text = max(
        (i for i, m in enumerate(messages)
         if m.get("role") == "assistant" and text_of(m.get("content")).strip()),
        default=-1,
    )
    for i, m in enumerate(messages):
        role = str(m.get("role") or "")
        text = text_of(m.get("content"))
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
                fn = (call.get("function") or {}) if isinstance(call, dict) else {}
                tool = str(fn.get("name") or "tool")
                if isinstance(call, dict) and call.get("id"):
                    names[str(call["id"])] = tool
                trace.add_event("tool_call", str(fn.get("arguments") or ""), source="agent",
                                target=tool, metadata={
                                    "tool_name": tool,
                                    "tool_call_id": call.get("id") if isinstance(call, dict) else None})
            if text.strip():
                if i == last_text:
                    trace.add_event("final_output", text, source="agent", target="user")
                else:
                    trace.add_event("inter_agent_message", text, source="agent", target="agent")
    return trace


# ----------------------------------------------------------------------
# Responses API / Agents SDK
# ----------------------------------------------------------------------
def from_openai_responses(items: list[dict[str, Any]], *, run_id: str,
                          agent_name: str = "responses_agent") -> Trace:
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
    trace = Trace(run_id=run_id, agent_name=agent_name)
    names: dict[str, str] = {}
    handoffs: set[str] = set()
    agent = "agent"

    def is_assistant_message(item: dict[str, Any]) -> bool:
        return item.get("role") == "assistant" and item.get("type", "message") == "message"

    last_msg = max(
        (i for i, it in enumerate(items) if is_assistant_message(it) and text_of(it.get("content")).strip()),
        default=-1,
    )
    for i, item in enumerate(items):
        kind = str(item.get("type") or "")
        role = item.get("role")
        if role in ("user", "system", "developer") and kind in ("", "message"):
            text = text_of(item.get("content"))
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
            text = text_of(item.get("summary")) or text_of(item.get("content"))
            if text.strip():
                trace.add_event("log", text, source=agent, target="reasoning")
        elif is_assistant_message(item):
            text = text_of(item.get("content"))
            if text.strip():
                if i == last_msg:
                    trace.add_event("final_output", text, source=agent, target="user")
                else:
                    trace.add_event("inter_agent_message", text, source=agent, target="agent")
    return trace


# ----------------------------------------------------------------------
# Claude Code
# ----------------------------------------------------------------------
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
                    trace.add_event(
                        "generated_file",
                        written if isinstance(written, (str, list, dict)) else str(written),
                        source=me,
                        target=str(tool_input.get("file_path") or tool_input.get("notebook_path") or "file"),
                        metadata={"tool_name": name, "tool_use_id": block.get("id")})
                else:
                    trace.add_event("tool_call", tool_input, source=me, target=name,
                                    metadata={"tool_name": name, "tool_use_id": block.get("id")})
            elif kind == "tool_result":
                name = tool_names.get(str(block.get("tool_use_id") or ""), "tool")
                trace.add_event("tool_response", text_of(block.get("content")), source=name, target=me,
                                metadata={"tool_name": name, "tool_use_id": block.get("tool_use_id")})
    return trace


# ----------------------------------------------------------------------
# OpenTelemetry GenAI semantic conventions
# ----------------------------------------------------------------------
def genai_text(value: Any) -> str:
    """Text of system instructions or input messages (parts with ``content``)."""
    texts: list[str] = []
    for item in as_list(value):
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


def is_genai_span(attrs: dict[str, Any]) -> bool:
    """A GenAI semantic-convention span that carries no OpenInference kind."""
    return (str(attrs.get("gen_ai.operation.name") or "") in GENAI_OPS
            and not attrs.get("openinference.span.kind"))


def genai_executed_ids(all_attrs: list[dict[str, Any]]) -> set[str]:
    """Tool-call ids that an ``execute_tool`` span records itself."""
    return {
        str(a.get("gen_ai.tool.call.id")) for a in all_attrs
        if a.get("gen_ai.operation.name") == "execute_tool" and a.get("gen_ai.tool.call.id")
    }


def genai_span_events(trace: Trace, attrs: dict[str, Any], *, executed_ids: set[str],
                      seen_input: bool, origin: str = "otel_genai") -> bool:
    """Append the events of one GenAI span to ``trace``.

    * ``execute_tool``: ``gen_ai.tool.call.arguments`` -> tool_call,
      ``gen_ai.tool.call.result`` -> tool_response (both opt-in in the
      convention: without them nothing is recorded)
    * inference / agent spans: ``gen_ai.system_instructions`` and
      ``gen_ai.input.messages`` -> user_input (first span that has them only,
      since every later span repeats the history); ``gen_ai.output.messages``
      text parts -> inter_agent_message; ``tool_call`` parts -> tool_call
      unless an ``execute_tool`` span carries the same call id; ``reasoning``
      parts -> log

    Returns whether the user input has now been recorded.
    """
    op = str(attrs.get("gen_ai.operation.name") or "")
    agent = str(attrs.get("gen_ai.agent.name") or "agent")
    if op == "execute_tool":
        tool = str(attrs.get("gen_ai.tool.name") or "tool")
        args = attrs.get("gen_ai.tool.call.arguments")
        if args is not None:
            trace.add_event("tool_call", maybe_json(args), source=agent, target=tool,
                            metadata={"tool_name": tool, "origin": origin,
                                      "tool_call_id": attrs.get("gen_ai.tool.call.id")})
        result = attrs.get("gen_ai.tool.call.result")
        if result is not None:
            trace.add_event("tool_response", maybe_json(result), source=tool, target=agent,
                            metadata={"tool_name": tool, "origin": origin})
        return seen_input
    if not seen_input:
        for key in ("gen_ai.system_instructions", "gen_ai.input.messages"):
            text = genai_text(maybe_json(attrs.get(key)))
            if text:
                trace.add_event("user_input", text, source="user", target=agent,
                                metadata={"origin": origin, "attribute": key})
                seen_input = True
    for message in as_list(maybe_json(attrs.get("gen_ai.output.messages"))):
        if not isinstance(message, dict):
            continue
        for part in message.get("parts") or []:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text" and str(part.get("content") or "").strip():
                trace.add_event("inter_agent_message", part["content"], source=agent, target="agent",
                                metadata={"origin": origin})
            elif ptype == "tool_call" and str(part.get("id")) not in executed_ids:
                tool = str(part.get("name") or "tool")
                trace.add_event("tool_call", part.get("arguments") or "", source=agent, target=tool,
                                metadata={"tool_name": tool, "origin": origin,
                                          "tool_call_id": part.get("id")})
            elif ptype == "reasoning" and str(part.get("content") or "").strip():
                trace.add_event("log", part["content"], source=agent, target="reasoning",
                                metadata={"origin": origin})
    return seen_input


def from_otel_genai(spans: list[Any], *, run_id: str) -> Trace:
    """OpenTelemetry GenAI semantic-convention spans -> trace.

    Verified against semantic-conventions-genai (execute-tool.md,
    client-inference.md, gen-ai-output-messages.json) and spans emitted by the
    OpenTelemetry Python SDK. See :func:`genai_span_events` for the per-span
    mapping; the last text output becomes the final_output. Values may be
    structured (AnyValue) or JSON strings; both are read.
    """
    from ..integrations.otel import _attrs_of, _ms

    trace = Trace(run_id=run_id, agent_name="otel_genai_agent")
    rows = []
    for span in spans:
        start = _ms(span.get("startTimeUnixNano") if isinstance(span, dict) else None)
        rows.append((start, _attrs_of(span)))
    if all(r[0] is not None for r in rows):
        rows.sort(key=lambda r: r[0] or 0.0)
    executed = genai_executed_ids([a for _, a in rows])
    seen_input = False
    for _, attrs in rows:
        seen_input = genai_span_events(trace, attrs, executed_ids=executed, seen_input=seen_input)
    outputs = [e for e in trace.events if e.channel_value == "inter_agent_message"]
    if outputs:
        outputs[-1].channel = Channel.FINAL_OUTPUT
        outputs[-1].target = "user"
    return trace


__all__ = [
    "GENAI_OPS",
    "RESPONSES_TYPES",
    "as_list",
    "from_claude_code",
    "from_openai_chat",
    "from_openai_responses",
    "from_otel_genai",
    "genai_executed_ids",
    "genai_span_events",
    "genai_text",
    "is_genai_span",
    "is_responses_items",
    "maybe_json",
    "text_of",
]
