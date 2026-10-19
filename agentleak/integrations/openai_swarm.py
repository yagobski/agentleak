# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""OpenAI Swarm and OpenAI Agents SDK trace adapters.

Swarm returns chat messages (``role``/``content``, optional ``tool_calls`` and
``sender``); the Agents SDK returns Responses items and richer ``new_items``
wrappers. This adapter maps both onto AgentLeak channels, including tool calls,
tool outputs, and agent-to-agent handoffs.

Works with:

* **Swarm** — ``response = client.run(...)`` then ``response.messages``.
* **Agents SDK** — ``result = await Runner.run(...)`` then
  ``trace_from_agents_result(result)``. Plain ``result.to_input_list()`` items
  are also accepted by ``trace_from_messages``.

Usage::

    from agentleak.integrations.openai_swarm import trace_from_messages
    from agentleak import AgentLeakRunner

    response = client.run(agent=triage, messages=[...])
    trace = trace_from_messages(response.messages, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace


def _field(item: Any, name: str, default: Any = None) -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _text(content: Any) -> Any:
    """Extract text blocks without stringifying SDK model objects."""
    if isinstance(content, list):
        parts = [part if isinstance(part, str) else _field(part, "text") for part in content]
        return "\n".join(part for part in parts if isinstance(part, str))
    return content


def _content_of(msg: Any) -> Any:
    if isinstance(msg, dict):
        return _text(msg.get("content", ""))
    return _text(getattr(msg, "content", ""))


def _role_of(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("role") or "agent")
    return str(getattr(msg, "role", "agent"))


def _sender_of(msg: Any, role: str) -> str:
    if isinstance(msg, dict):
        return str(msg.get("sender") or msg.get("name") or role)
    return str(getattr(msg, "sender", None) or getattr(msg, "name", None) or role)


def _tool_calls_of(msg: Any) -> Any:
    if isinstance(msg, dict):
        return msg.get("tool_calls")
    return getattr(msg, "tool_calls", None)


def trace_from_messages(
    messages: list[dict[str, Any]] | list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "swarm_agent",
) -> Trace:
    """Build a trace from Swarm messages or plain Responses input items.

    Assistant tool-call arguments become ``tool_call`` events; ``tool``/``function``
    role messages become ``tool_response`` events; assistant turns where the
    active agent changed are recorded as ``inter_agent_message`` (a handoff); the
    last assistant turn is the ``final_output``.
    """
    trace = Trace(run_id=run_id, agent_name=agent_name)
    msgs = list(messages)
    last_sender: str | None = None

    # Index of the last assistant message with textual content -> final output.
    final_idx = -1
    for i, msg in enumerate(msgs):
        raw = _field(msg, "raw_item", msg)
        if _role_of(raw) == "assistant" and _content_of(raw):
            final_idx = i

    for i, msg in enumerate(msgs):
        item_type = _field(msg, "type")
        raw = _field(msg, "raw_item", msg)
        raw_type = _field(raw, "type")
        agent = _field(msg, "agent")
        agent_sender = _field(agent, "name")
        if item_type == "handoff_output_item":
            source = _field(_field(msg, "source_agent"), "name", "agent")
            target = _field(_field(msg, "target_agent"), "name", "agent")
            trace.add_event(
                channel="inter_agent_message", content=_field(raw, "output", "handoff"),
                source=str(source), target=str(target), metadata={"handoff": True},
            )
            last_sender = str(target)
            continue
        if item_type == "handoff_call_item":
            # The matching handoff_output_item records the transfer. Its call
            # arguments are still an outbound tool invocation.
            raw_type = "function_call"
        if raw_type == "function_call" or item_type == "tool_call_item":
            arguments = _field(raw, "arguments")
            if arguments is not None:
                trace.add_event(
                    channel="tool_call", content=arguments,
                    source=str(agent_sender or "assistant"),
                    target=str(_field(raw, "name", "tool")),
                    metadata={"origin": "agents_sdk"},
                )
            continue
        if raw_type == "function_call_output" or item_type == "tool_call_output_item":
            output = _field(msg, "output", _field(raw, "output", ""))
            trace.add_event(
                channel="tool_response", content=output if output is not None else "",
                source=str(_field(raw, "call_id", "tool")), target="agent",
                metadata={"origin": "agents_sdk"},
            )
            continue
        if item_type == "message_output_item":
            msg = raw
        elif item_type is not None and raw_type != "message":
            # Reasoning and other SDK items do not represent user-visible text.
            continue
        role = _role_of(msg)
        content = _content_of(msg)
        sender = str(agent_sender or _sender_of(msg, role))

        if role in ("tool", "function"):
            trace.add_event(
                channel="tool_response", content=content or "",
                source=str(sender), target="agent", metadata={"origin": "swarm"},
            )
            continue

        tool_calls = _tool_calls_of(msg)
        if tool_calls:
            trace.add_event(
                channel="tool_call", content=tool_calls, source=str(sender),
                target="tool", metadata={"origin": "swarm"},
            )

        if not content:
            last_sender = sender
            continue

        if i == final_idx:
            trace.add_event(
                channel="final_output", content=content,
                source=str(sender), target="user",
            )
        elif role == "assistant":
            handoff = last_sender is not None and sender != last_sender
            trace.add_event(
                channel="inter_agent_message", content=content,
                source=str(sender), target="agent",
                metadata={"handoff": handoff, "from": last_sender} if handoff else {},
            )
        elif role == "user":
            trace.add_event(
                channel="user_input", content=content, source="user", target=str(sender),
            )
        last_sender = sender

    return trace


def trace_from_agents_result(
    result: Any, *, run_id: str = "run", agent_name: str = "agents_sdk_agent",
) -> Trace:
    """Convert completed ``Runner.run``/``Runner.run_sync`` results.

    ``new_items`` carries the agent associations and tool outputs that a plain
    replay list may omit. Include the run input to populate the source vault.
    Call this after consuming a streamed run to completion.
    """
    run_input = _field(result, "input", [])
    if isinstance(run_input, str):
        inputs: list[Any] = [{"role": "user", "content": run_input}]
    elif isinstance(run_input, list):
        inputs = run_input
    else:
        inputs = []
    return trace_from_messages(
        inputs + list(_field(result, "new_items", []) or []),
        run_id=run_id, agent_name=agent_name,
    )


__all__ = ["trace_from_messages", "trace_from_agents_result"]
