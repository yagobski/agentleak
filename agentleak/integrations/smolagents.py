"""Hugging Face smolagents integration.

smolagents records each reasoning/acting step in ``agent.memory.steps``. A
``TaskStep`` holds the user task; each ``ActionStep`` holds the model output,
the ``tool_calls`` it issued (``ToolCall`` with ``name``/``arguments``), and the
``observations`` returned. This adapter ingests that memory, and also exposes a
``step_callback`` for live capture.

Usage::

    from agentleak.integrations.smolagents import trace_from_steps
    from agentleak import AgentLeakRunner

    agent.run("...")
    trace = trace_from_steps(agent.memory.steps, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config
from ..core.report import AnalysisResult
from ..core.runner import AgentLeakRunner
from ..core.trace import Trace
from .generic import TraceRecorder


def _record_step(rec: TraceRecorder, step: Any, *, is_final: bool = False) -> None:
    # TaskStep -> user input.
    task = getattr(step, "task", None)
    if task is not None:
        rec.user_input(str(task), source="user", target="agent")
        return

    model_output = getattr(step, "model_output", None)
    if model_output:
        rec.inter_agent_message(str(model_output), source="agent", target="agent",
                                metadata={"origin": "smolagents"})

    for call in getattr(step, "tool_calls", None) or []:
        name = getattr(call, "name", None) or "tool"
        args = getattr(call, "arguments", None)
        rec.tool_call(
            {"tool": str(name), "arguments": args} if args is not None else str(name),
            source="agent", target=str(name), metadata={"tool_name": str(name)},
        )

    observations = getattr(step, "observations", None)
    if observations:
        rec.tool_response(str(observations), source="tool", target="agent")

    action_output = getattr(step, "action_output", None)
    if action_output is not None and (is_final or getattr(step, "is_final_answer", False)):
        rec.final_output(str(action_output), source="agent", target="user")


def trace_from_steps(
    steps: list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "smolagents_agent",
) -> Trace:
    """Build a trace from ``agent.memory.steps``."""
    rec = TraceRecorder(run_id=run_id, agent_name=agent_name)
    items = list(steps)
    for i, step in enumerate(items):
        _record_step(rec, step, is_final=(i == len(items) - 1))
    return rec.trace


class SmolagentsCallback(TraceRecorder):
    """Pass ``cb.step_callback`` as a smolagents ``step_callbacks`` entry."""

    def __init__(self, run_id: str = "run", agent_name: str = "smolagents_agent",
                 config: Config | None = None) -> None:
        super().__init__(run_id=run_id, agent_name=agent_name)
        self.config = config

    def step_callback(self, step: Any, *args: Any, **kw: Any) -> None:
        _record_step(self, step)

    def analyze(self) -> AnalysisResult:
        return AgentLeakRunner(self.config).analyze(self.trace)


__all__ = ["trace_from_steps", "SmolagentsCallback"]
