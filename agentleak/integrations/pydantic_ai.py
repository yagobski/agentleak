"""Pydantic AI integration.

A Pydantic AI ``result`` exposes the full exchange via ``result.all_messages()``
— a list of ``ModelRequest`` / ``ModelResponse`` objects whose ``parts`` carry
typed fragments (``UserPromptPart``, ``TextPart``, ``ToolCallPart``,
``ToolReturnPart``). This adapter maps those parts onto AgentLeak channels.

Usage::

    from agentleak.integrations.pydantic_ai import trace_from_messages
    from agentleak import AgentLeakRunner

    result = await agent.run("...")
    trace = trace_from_messages(result.all_messages(), run_id="run_001")
    result_al = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace


def _kind(part: Any) -> str:
    return str(getattr(part, "part_kind", "") or "").lower()


def trace_from_messages(
    messages: list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "pydantic_ai_agent",
) -> Trace:
    """Build a trace from ``result.all_messages()``."""
    trace = Trace(run_id=run_id, agent_name=agent_name)
    msgs = list(messages)

    # Find the last text part across all responses -> final output.
    text_positions: list[tuple[int, int]] = []
    for mi, msg in enumerate(msgs):
        for pi, part in enumerate(getattr(msg, "parts", []) or []):
            if _kind(part) == "text":
                text_positions.append((mi, pi))
    final_pos = text_positions[-1] if text_positions else None

    for mi, msg in enumerate(msgs):
        for pi, part in enumerate(getattr(msg, "parts", []) or []):
            kind = _kind(part)
            content = getattr(part, "content", None)
            if kind == "user-prompt":
                trace.add_event(channel="user_input", content=str(content or ""),
                                source="user", target="agent")
            elif kind == "tool-call":
                name = getattr(part, "tool_name", "tool")
                args = getattr(part, "args", None)
                trace.add_event(
                    channel="tool_call",
                    content={"tool": str(name), "args": args} if args is not None else str(name),
                    source="agent", target=str(name),
                    metadata={"tool_name": str(name), "origin": "pydantic_ai"},
                )
            elif kind == "tool-return":
                name = getattr(part, "tool_name", "tool")
                trace.add_event(channel="tool_response", content=str(content or ""),
                                source=str(name), target="agent")
            elif kind == "text":
                if (mi, pi) == final_pos:
                    trace.add_event(channel="final_output", content=str(content or ""),
                                    source="agent", target="user")
                else:
                    trace.add_event(channel="inter_agent_message", content=str(content or ""),
                                    source="agent", target="agent")

    return trace


__all__ = ["trace_from_messages"]
