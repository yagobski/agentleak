"""LlamaIndex integration.

LlamaIndex agents (``FunctionAgent``, ``ReActAgent``, ``AgentWorkflow`` for
multi-agent systems) return a chat response that carries the tool calls made
along the way in ``response.sources`` (a list of ``ToolOutput``). This adapter
ingests that response, mapping each tool's input to a ``tool_call`` and its
output to a ``tool_response``, with the final text as ``final_output``.

A duck-typed ``LlamaIndexCallback`` is also provided for live instrumentation via
LlamaIndex's ``CallbackManager`` — it never imports LlamaIndex.

Usage::

    from agentleak.integrations.llamaindex import trace_from_response
    from agentleak import AgentLeakRunner

    response = await agent.run("...")          # or agent.chat("...")
    trace = trace_from_response(response, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config
from ..core.report import AnalysisResult
from ..core.runner import AgentLeakRunner
from ..core.trace import Trace
from .generic import TraceRecorder


def _tool_name(src: Any) -> str:
    return str(getattr(src, "tool_name", None) or getattr(src, "name", None) or "tool")


def trace_from_response(
    response: Any,
    *,
    run_id: str = "run",
    agent_name: str = "llamaindex_agent",
) -> Trace:
    """Build a trace from a LlamaIndex agent/chat response.

    ``response.sources`` (``ToolOutput`` objects) become ``tool_call`` +
    ``tool_response`` events; ``str(response)`` / ``response.response`` is the
    ``final_output``.
    """
    trace = Trace(run_id=run_id, agent_name=agent_name)

    sources = getattr(response, "sources", None) or []
    for src in sources:
        name = _tool_name(src)
        raw_input = getattr(src, "raw_input", None)
        if raw_input is not None:
            trace.add_event(
                channel="tool_call", content=raw_input, source="agent",
                target=name, metadata={"tool_name": name, "origin": "llamaindex"},
            )
        output = getattr(src, "content", None)
        if output is None:
            output = getattr(src, "raw_output", None)
        if output is not None:
            trace.add_event(
                channel="tool_response", content=str(output), source=name, target="agent",
            )

    final = getattr(response, "response", None)
    if final is None:
        final = str(response) if response is not None else ""
    if final:
        trace.add_event(channel="final_output", content=str(final), source="agent", target="user")

    return trace


class LlamaIndexCallback(TraceRecorder):
    """Duck-typed LlamaIndex ``CallbackManager`` handler.

    LlamaIndex calls ``on_event_start``/``on_event_end`` with an event type and a
    payload dict. We stringify keys/types so no LlamaIndex import is needed.
    """

    event_starts_to_ignore: tuple = ()
    event_ends_to_ignore: tuple = ()

    def __init__(self, run_id: str = "run", agent_name: str = "llamaindex_agent",
                 config: Config | None = None) -> None:
        super().__init__(run_id=run_id, agent_name=agent_name)
        self.config = config

    def _payload_text(self, payload: Any, *want: str) -> str:
        if not isinstance(payload, dict):
            return str(payload) if payload else ""
        for key, value in payload.items():
            ks = str(key).lower()
            if any(w in ks for w in want):
                return str(value)
        return ""

    def on_event_start(self, event_type: Any, payload: Any = None, event_id: str = "",
                       parent_id: str = "", **kw: Any) -> str:
        et = str(event_type).lower()
        if "function_call" in et or "agent_step" in et:
            text = self._payload_text(payload, "function_call", "tool", "input")
            if text:
                self.tool_call(text, source="agent", target="tool", metadata={"origin": "llamaindex"})
        return event_id or ""

    def on_event_end(self, event_type: Any, payload: Any = None, event_id: str = "", **kw: Any) -> None:
        et = str(event_type).lower()
        if "function_call" in et:
            text = self._payload_text(payload, "function_output", "output", "response")
            if text:
                self.tool_response(text, source="tool", target="agent")

    def start_trace(self, trace_id: str | None = None) -> None:  # noqa: D401 - LlamaIndex hook
        return None

    def end_trace(self, trace_id: str | None = None, trace_map: Any = None) -> None:
        return None

    def analyze(self) -> AnalysisResult:
        return AgentLeakRunner(self.config).analyze(self.trace)


__all__ = ["trace_from_response", "LlamaIndexCallback"]
