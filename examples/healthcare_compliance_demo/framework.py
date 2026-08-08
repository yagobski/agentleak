"""Lightweight multi-agent framework — no external dependencies.

Provides the minimal scaffolding for a realistic agent pipeline:

* ``Agent`` — named actor with a clearance level and a set of tools
* ``Tool`` — callable with typed inputs/outputs
* ``Pipeline`` — message bus that wires agents together and records
  every communication as an AgentLeak :class:`~agentleak.core.trace.Trace`
  event so the whole run is auditable

This is intentionally simple so the healthcare demo can focus on the
privacy patterns rather than framework boilerplate.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agentleak.core.trace import Trace
from agentleak.defenses.internal_channel import (
    AgentProfile,
    ClearanceLevel,
    GuardDecision,
    InternalChannelGuard,
)
from agentleak.defenses.sanitizer import RedactionStyle, Sanitizer

# ---------------------------------------------------------------------------
# Agent & Tool definitions
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    """A typed callable exposed to agents."""

    name: str
    description: str
    fn: Callable[..., Any]

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


@dataclass
class Agent:
    """A named actor in the pipeline.

    Args:
        name: Unique identifier (used as source/target in trace events).
        role: Human-readable description of its responsibility.
        clearance: The highest data sensitivity level this agent may handle.
        tools: Tools this agent may call directly.
    """

    name: str
    role: str
    clearance: ClearanceLevel = ClearanceLevel.INTERNAL
    tools: dict[str, Tool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pipeline (message bus + trace recorder)
# ---------------------------------------------------------------------------

class Pipeline:
    """Wires agents together and records every interaction as a trace event.

    All trace events are written to ``self.trace``; call
    :meth:`reset` to start a new run.

    Args:
        run_id: Optional trace run identifier.
        hardened: When *True* the pipeline applies defense middleware:
            - :class:`~agentleak.defenses.sanitizer.Sanitizer` on every
              inter-agent message and shared-memory write.
            - :class:`~agentleak.defenses.internal_channel.InternalChannelGuard`
              that blocks SECRET-level data flowing to INTERNAL-clearance agents.
    """

    def __init__(
        self,
        run_id: str | None = None,
        *,
        hardened: bool = False,
    ) -> None:
        self.hardened = hardened
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.trace = Trace(run_id=self.run_id, agent_name="healthcare_pipeline")
        self._agents: dict[str, Agent] = {}
        self._shared_memory: dict[str, Any] = {}
        self._log_buffer: list[str] = []
        self._start_ts = time.time()

        # Defense middleware (active only when hardened=True)
        if hardened:
            self._sanitizer = Sanitizer(style=RedactionStyle.MASKED)
        else:
            self._sanitizer = None

    # ------------------------------------------------------------------
    # Agent registry
    # ------------------------------------------------------------------

    def register(self, agent: Agent) -> Agent:
        """Register an agent with this pipeline."""
        self._agents[agent.name] = agent
        return agent

    def _get_profile(self, agent_name: str) -> AgentProfile:
        agent = self._agents.get(agent_name)
        clearance = agent.clearance if agent else ClearanceLevel.PUBLIC
        return AgentProfile(name=agent_name, clearance=clearance)

    # ------------------------------------------------------------------
    # User entry point
    # ------------------------------------------------------------------

    def receive_input(self, text: str) -> None:
        """Record the initial user request."""
        self.trace.add_event("user_input", text, source="user")

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def call_tool(
        self,
        caller: str,
        tool_name: str,
        target: str,
        params: dict[str, Any],
    ) -> Any:
        """Execute a tool and record the call + response in the trace."""
        agent = self._agents.get(caller)
        tool = (agent.tools if agent else {}).get(tool_name)

        self.trace.add_event(
            "tool_call",
            {"tool": tool_name, **params},
            source=caller,
            target=target,
        )

        if tool is None:
            result: Any = {"error": f"Tool {tool_name!r} not found for agent {caller!r}"}
        else:
            result = tool(**params)

        self.trace.add_event("tool_response", result, source=target, target=caller)
        return result

    # ------------------------------------------------------------------
    # Inter-agent messaging
    # ------------------------------------------------------------------

    def send_message(
        self,
        sender: str,
        recipient: str,
        message: str,
    ) -> str:
        """Send a message between agents, optionally sanitizing it first."""
        final_msg = message

        if self.hardened and self._sanitizer:
            sender_agent = self._agents.get(sender)
            recipient_agent = self._agents.get(recipient)
            sender_profile = AgentProfile(
                name=sender,
                clearance=sender_agent.clearance if sender_agent else ClearanceLevel.PUBLIC,
            )
            recipient_profile = AgentProfile(
                name=recipient,
                clearance=recipient_agent.clearance if recipient_agent else ClearanceLevel.PUBLIC,
            )
            guard = InternalChannelGuard(
                sender=sender_profile,
                recipient=recipient_profile,
                sanitizer=self._sanitizer,
                block_on_secret=False,  # redact instead of block in hardened mode
            )
            # Pass data_level=None → guard auto-estimates from content
            result = guard.check(message, "inter_agent_message", data_level=None)

            if result.decision in (GuardDecision.REDACT, GuardDecision.WARN):
                final_msg = result.sanitized_text or message
            elif result.decision == GuardDecision.BLOCK:
                final_msg = "[BLOCKED: message contained SECRET-level data above recipient clearance]"

        self.trace.add_event(
            "inter_agent_message",
            final_msg,
            source=sender,
            target=recipient,
        )
        return final_msg

    # ------------------------------------------------------------------
    # Shared memory
    # ------------------------------------------------------------------

    def write_memory(self, writer: str, key: str, value: Any) -> None:
        """Write to shared memory and record the event."""
        if self.hardened and self._sanitizer:
            if isinstance(value, dict):
                value = self._sanitizer.sanitize_dict(value)
            elif isinstance(value, str):
                value = self._sanitizer.sanitize(value)

        self._shared_memory[key] = value
        self.trace.add_event(
            "shared_memory",
            {key: value},
            source=writer,
        )

    def read_memory(self, key: str) -> Any:
        """Read from shared memory (no trace event — reads are passive)."""
        return self._shared_memory.get(key)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, agent_name: str, message: str, level: str = "INFO") -> None:
        """Write a structured log entry and record it in the trace."""
        if self.hardened and self._sanitizer:
            message = self._sanitizer.sanitize(message)

        entry = f"[{level}] [{agent_name}] {message}"
        self._log_buffer.append(entry)
        self.trace.add_event("log", entry, source=agent_name)

    # ------------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------------

    def emit_output(self, agent_name: str, content: str) -> None:
        """Record the pipeline's final output."""
        self.trace.add_event("final_output", content, source=agent_name, target="user")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def elapsed_ms(self) -> int:
        return int((time.time() - self._start_ts) * 1000)
