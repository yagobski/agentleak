"""Google Agent Development Kit (ADK) integration.

ADK runs emit a stream of ``Event`` objects, each authored by a named agent and
carrying a ``content`` with ``parts`` (text, ``function_call``,
``function_response``). Multi-agent ADK systems route between sub-agents, which
this adapter surfaces as ``inter_agent_message`` events.

Usage::

    from agentleak.integrations.google_adk import trace_from_events
    from agentleak import AgentLeakRunner

    events = list(runner.run(user_id="u", session_id="s", new_message=msg))
    trace = trace_from_events(events, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace


def _parts(event: Any) -> list[Any]:
    content = getattr(event, "content", None)
    if content is None and isinstance(event, dict):
        content = event.get("content")
    parts = getattr(content, "parts", None)
    if parts is None and isinstance(content, dict):
        parts = content.get("parts")
    return list(parts or [])


def _author(event: Any) -> str:
    author = getattr(event, "author", None)
    if author is None and isinstance(event, dict):
        author = event.get("author")
    return str(author or "agent")


def _is_final(event: Any) -> bool:
    fn = getattr(event, "is_final_response", None)
    if callable(fn):
        try:
            return bool(fn())
        except Exception:
            return False
    if isinstance(event, dict):
        return bool(event.get("is_final_response"))
    return False


def trace_from_events(
    events: list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "google_adk_agent",
) -> Trace:
    """Build a trace from a list of ADK ``Event`` objects."""
    trace = Trace(run_id=run_id, agent_name=agent_name)

    for event in events:
        author = _author(event)
        is_final = _is_final(event)
        for part in _parts(event):
            fc = getattr(part, "function_call", None)
            if fc is None and isinstance(part, dict):
                fc = part.get("function_call")
            if fc is not None:
                name = getattr(fc, "name", None) or (fc.get("name") if isinstance(fc, dict) else "tool")
                args = getattr(fc, "args", None) or (fc.get("args") if isinstance(fc, dict) else None)
                trace.add_event(
                    channel="tool_call",
                    content={"function": str(name), "args": args} if args is not None else str(name),
                    source=str(author), target=str(name),
                    metadata={"tool_name": str(name), "origin": "google_adk"},
                )
                continue

            fr = getattr(part, "function_response", None)
            if fr is None and isinstance(part, dict):
                fr = part.get("function_response")
            if fr is not None:
                name = getattr(fr, "name", None) or (fr.get("name") if isinstance(fr, dict) else "tool")
                resp = getattr(fr, "response", None) or (fr.get("response") if isinstance(fr, dict) else fr)
                trace.add_event(channel="tool_response", content=str(resp),
                                source=str(name), target=str(author))
                continue

            text = getattr(part, "text", None)
            if text is None and isinstance(part, dict):
                text = part.get("text")
            if not text:
                continue
            if author == "user":
                trace.add_event(channel="user_input", content=str(text), source="user", target="agent")
            elif is_final:
                trace.add_event(channel="final_output", content=str(text), source=str(author), target="user")
            else:
                trace.add_event(channel="inter_agent_message", content=str(text),
                                source=str(author), target="agent")

    return trace


__all__ = ["trace_from_events"]
