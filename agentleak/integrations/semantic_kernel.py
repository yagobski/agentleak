"""Microsoft Semantic Kernel integration.

Semantic Kernel runs single agents (``ChatCompletionAgent``) and multi-agent
orchestrations (``AgentGroupChat``) over a ``ChatHistory`` of
``ChatMessageContent``. Each message carries a role, the authoring agent's
``name``, and structured ``items`` (``FunctionCallContent`` /
``FunctionResultContent``). This adapter normalizes that history onto AgentLeak
channels — assistant turns from different agents become ``inter_agent_message``.

Usage::

    from agentleak.integrations.semantic_kernel import trace_from_chat_history
    from agentleak import AgentLeakRunner

    trace = trace_from_chat_history(chat.history, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace


def _role(msg: Any) -> str:
    role = getattr(msg, "role", None)
    if role is None and isinstance(msg, dict):
        role = msg.get("role")
    # AuthorRole is an enum with a .value; fall back to str.
    return str(getattr(role, "value", role) or "assistant").lower()


def _name(msg: Any, role: str) -> str:
    name = getattr(msg, "name", None)
    if name is None and isinstance(msg, dict):
        name = msg.get("name")
    return str(name or role)


def _content(msg: Any) -> str:
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content", "")
    return str(content or "")


def _items(msg: Any) -> list[Any]:
    items = getattr(msg, "items", None)
    if items is None and isinstance(msg, dict):
        items = msg.get("items")
    return list(items or [])


def trace_from_chat_history(
    messages: Any,
    *,
    run_id: str = "run",
    agent_name: str = "semantic_kernel_agent",
) -> Trace:
    """Build a trace from a Semantic Kernel ``ChatHistory`` (or list of messages)."""
    trace = Trace(run_id=run_id, agent_name=agent_name)
    msgs = list(getattr(messages, "messages", None) or messages)

    last_assistant_idx = -1
    for i, msg in enumerate(msgs):
        if _role(msg) == "assistant" and _content(msg):
            last_assistant_idx = i

    last_name: str | None = None
    for i, msg in enumerate(msgs):
        role = _role(msg)
        name = _name(msg, role)

        for item in _items(msg):
            fn = getattr(item, "function_name", None) or getattr(item, "name", None)
            args = getattr(item, "arguments", None)
            if fn is not None and args is not None:
                trace.add_event(
                    channel="tool_call", content={"function": str(fn), "arguments": args},
                    source=str(name), target=str(fn), metadata={"origin": "semantic_kernel"},
                )
            result = getattr(item, "result", None)
            if result is None:
                result = getattr(item, "value", None)
            if result is not None:
                trace.add_event(
                    channel="tool_response", content=str(result), source=str(fn or "tool"),
                    target=str(name),
                )

        content = _content(msg)
        if not content:
            continue
        if role == "user":
            trace.add_event(channel="user_input", content=content, source="user", target=str(name))
        elif role == "tool":
            trace.add_event(channel="tool_response", content=content, source=str(name), target="agent")
        elif i == last_assistant_idx:
            trace.add_event(channel="final_output", content=content, source=str(name), target="user")
        else:
            handoff = last_name is not None and name != last_name
            trace.add_event(
                channel="inter_agent_message", content=content, source=str(name),
                target="agent", metadata={"handoff": handoff, "from": last_name} if handoff else {},
            )
        last_name = name

    return trace


__all__ = ["trace_from_chat_history"]
