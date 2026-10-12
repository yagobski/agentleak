# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AutoGen integration.

AutoGen drives multi-agent conversations as lists of messages. This adapter
ingests a conversation (e.g. ``ChatResult.chat_history`` or any list of
``{"name"/"role", "content"}`` dicts) and maps it to inter-agent messages, with
the final assistant turn as the final output.

Usage::

    from agentleak.integrations.autogen import trace_from_messages
    from agentleak import AgentLeakRunner

    trace = trace_from_messages(chat_result.chat_history, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace


def _field(msg: Any, *names: str) -> Any:
    for name in names:
        val = msg.get(name) if isinstance(msg, dict) else getattr(msg, name, None)
        if val not in (None, ""):
            return val
    return None


def trace_from_messages(
    messages: list[dict[str, Any]] | list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "autogen_agent",
) -> Trace:
    """Map an AutoGen conversation to a trace.

    The speaker is read from ``name`` (classic AutoGen), ``source`` (AgentChat
    0.4+ messages) or ``role``. A leading message from ``user`` is the user
    input; each later turn is addressed to the next speaker, and the last turn
    is the final output.
    """
    trace = Trace(run_id=run_id, agent_name=agent_name)
    msgs = list(messages)
    speakers = [str(_field(m, "name", "source", "role") or "agent") for m in msgs]
    for i, msg in enumerate(msgs):
        name = speakers[i]
        content = _field(msg, "content") or ""
        tool_calls = _field(msg, "tool_calls")
        nxt = speakers[i + 1] if i + 1 < len(msgs) else "user"

        if tool_calls:
            trace.add_event(
                channel="tool_call", content=tool_calls, source=name,
                target="tool", metadata={"origin": "autogen"},
            )

        if i == 0 and name == "user" and len(msgs) > 1:
            trace.add_event(channel="user_input", content=content, source="user", target=nxt)
            continue
        is_last = i == len(msgs) - 1
        trace.add_event(
            channel="final_output" if is_last else "inter_agent_message",
            content=content,
            source=name,
            target="user" if is_last else nxt,
        )
    return trace


__all__ = ["trace_from_messages"]
