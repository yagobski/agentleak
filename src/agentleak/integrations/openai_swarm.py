# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""OpenAI Swarm / Agents SDK integration.

Swarm and the OpenAI Agents SDK orchestrate *multiple* agents that hand control
to one another. A run produces a list of chat messages (``role``/``content``,
optional ``tool_calls`` and a ``sender``/agent name). This adapter maps that
conversation onto AgentLeak channels, with agent-to-agent handoffs surfaced as
``inter_agent_message`` — exactly the internal channel output-only audits miss.

Works with:

* **Swarm** — ``response = client.run(...)`` then ``response.messages``.
* **Agents SDK** — ``result = await Runner.run(...)`` then
  ``result.to_input_list()`` (or any list of message dicts).

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


def _content_of(msg: Any) -> Any:
    if isinstance(msg, dict):
        return msg.get("content", "")
    return getattr(msg, "content", "")


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
    """Build a trace from a Swarm/Agents-SDK message list.

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
        if _role_of(msg) == "assistant" and _content_of(msg):
            final_idx = i

    for i, msg in enumerate(msgs):
        role = _role_of(msg)
        content = _content_of(msg)
        sender = _sender_of(msg, role)

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


__all__ = ["trace_from_messages"]
