# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""LangChain integration.

``LangChainCallback`` is duck-typed: LangChain calls ``on_*`` methods on any
object passed via ``callbacks=[...]``, so this works without importing
LangChain. Tool inputs/outputs, LLM outputs, and agent actions are mapped onto
AgentLeak channels.

Usage::

    from agentleak.integrations.langchain import LangChainCallback

    cb = LangChainCallback(run_id="run_001")
    chain.invoke(inputs, config={"callbacks": [cb]})
    result = cb.analyze()
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config
from ..core.report import AnalysisResult
from ..core.runner import AgentLeakRunner
from ..core.trace import Channel
from .generic import TraceRecorder

# Try to inherit from BaseCallbackHandler when LangChain is available.
# This avoids attribute errors in LangChain 0.3.x which checks for raise_error,
# ignore_chain, etc. on every handler in the callback manager.
try:
    from langchain_core.callbacks import BaseCallbackHandler as _Base  # type: ignore[import]
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _Base = object  # type: ignore[misc,assignment]
    _LANGCHAIN_AVAILABLE = False


class LangChainCallback(TraceRecorder, _Base):  # type: ignore[misc]
    def __init__(self, run_id: str = "run", agent_name: str = "langchain_agent",
                 config: Config | None = None) -> None:
        TraceRecorder.__init__(self, run_id=run_id, agent_name=agent_name)
        if _LANGCHAIN_AVAILABLE:
            _Base.__init__(self)  # type: ignore[call-arg]
        self.config = config
        # In a multi-node graph there are several LLM/agent turns but only one
        # *final* answer. We optimistically tag the latest turn as final_output
        # and demote the previous one to inter_agent_message, so intermediate
        # agent turns aren't misattributed to what the user actually saw.
        self._last_final_event_id: str | None = None
        # LangChain passes run_id/parent_run_id to every hook but node metadata
        # only to the *_start hooks; remember which node owns each run so the
        # matching *_end hook can attribute its event to the same actor.
        self._run_actor: dict[str, str] = {}
        self._run_tool: dict[str, str] = {}
        self._user_input_recorded = False

    def _actor(self, kw: dict[str, Any], default: str) -> str:
        meta = kw.get("metadata") or {}
        node = meta.get("langgraph_node") or meta.get("agent_name")
        run_id = kw.get("run_id")
        parent = kw.get("parent_run_id")
        if not node and run_id is not None:
            node = self._run_actor.get(str(run_id))
        if not node and parent is not None:
            node = self._run_actor.get(str(parent))
        node = str(node) if node else default
        if run_id is not None:
            self._run_actor.setdefault(str(run_id), node)
        return node

    def _promote_final(self, content: Any, *, source: str, target: str = "user") -> None:
        """Record a final_output, demoting any previous one to an agent handoff."""
        if self._last_final_event_id is not None:
            for ev in self.trace.events:
                if ev.event_id == self._last_final_event_id:
                    ev.channel = Channel.INTER_AGENT_MESSAGE
                    ev.target = "agent"
                    ev.metadata = {**(ev.metadata or {}), "demoted_from": "final_output"}
                    break
        event = self.trace.add_event(
            channel="final_output", content=content, source=source, target=target,
        )
        self._last_final_event_id = event.event_id

    # -- LangChain callback surface (duck-typed) ------------------------
    def on_chain_start(self, serialized: dict[str, Any], inputs: Any, **kw: Any) -> None:
        # The outermost chain/graph input is what the user asked for.
        actor = self._actor(kw, "agent")
        if kw.get("parent_run_id") is None and not self._user_input_recorded and inputs:
            self._user_input_recorded = True
            self.trace.add_event(channel="user_input", content=inputs, source="user",
                                 target=actor, metadata={"origin": "langchain"})

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kw: Any) -> None:
        name = (serialized or {}).get("name") or kw.get("name") or "tool"
        actor = self._actor(kw, "agent")
        if kw.get("run_id") is not None:
            self._run_tool[str(kw["run_id"])] = str(name)
        self.tool_call(input_str, source=actor, target=name, metadata={"tool_name": name})

    def on_tool_end(self, output: Any, **kw: Any) -> None:
        run_id = kw.get("run_id")
        tool = self._run_tool.get(str(run_id), "tool") if run_id is not None else "tool"
        actor = self._actor(kw, "agent")
        self.tool_response(str(output), source=tool, target=actor)

    def on_llm_start(self, serialized: dict[str, Any], prompts: Any, **kw: Any) -> None:
        self._actor(kw, "llm")

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kw: Any) -> None:
        self._actor(kw, "llm")

    def on_agent_action(self, action: Any, **kw: Any) -> None:
        tool = getattr(action, "tool", "tool")
        tool_input = getattr(action, "tool_input", action)
        self.inter_agent_message(
            {"tool": tool, "tool_input": tool_input}, source=self._actor(kw, "agent"),
            target=tool,
        )

    def on_llm_end(self, response: Any, **kw: Any) -> None:
        text = _extract_llm_text(response)
        if text:
            self._promote_final(text, source=self._actor(kw, "llm"))

    def on_agent_finish(self, finish: Any, **kw: Any) -> None:
        output = (getattr(finish, "return_values", None) or {}).get("output", "")
        if output:
            self._promote_final(str(output), source=self._actor(kw, "agent"))

    def on_text(self, text: str, **kw: Any) -> None:
        if text:
            self.log(text, source="chain", target="stdout")

    # -- analysis -------------------------------------------------------
    def analyze(self) -> AnalysisResult:
        return AgentLeakRunner(self.config).analyze(self.trace)


def _extract_llm_text(response: Any) -> str:
    # LangChain LLMResult has .generations: list[list[Generation]].
    generations = getattr(response, "generations", None)
    if generations:
        try:
            return generations[0][0].text  # type: ignore[index]
        except (IndexError, AttributeError):
            pass
    return str(response) if response is not None else ""


__all__ = ["LangChainCallback"]
