"""Computer-use / autonomous-coding agent integration.

This covers the *action–observation* genre of agent — OpenHands, Open
Interpreter, Cline / "openclaw"-style coders, SWE-agent, browser-use, and Claude
computer-use. Instead of chatting, these agents **act**: they run shell commands,
execute code, read and **write files**, and drive a browser. That makes their
dangerous leakage surfaces different from a chat agent's:

- a **file they generate** can embed a customer's SSN or an API key on disk
  (``generated_file``);
- a **shell command / code cell** can echo a secret (``tool_call``);
- their **internal reasoning / scratchpad** can restate private data (``log``);
- a **browser form fill** can post PII to a third party (``tool_call``).

Each step is a plain, duck-typed dict — no framework import required::

    {
        "action": "write_file",            # or run/execute/read/browse/think/finish
        "path": "report.md",               # file ops
        "content": "...",                  # what the agent WROTE  -> generated_file
        "command": "cat /etc/passwd",      # shell/code               -> tool_call
        "url": "https://...",              # browser                  -> tool_call
        "thought": "the SSN is ...",       # reasoning                -> log
        "observation": "...",              # the result               -> tool_response
        "agent": "coder",                  # optional
    }

Usage::

    from agentleak.integrations.computer_use import trace_from_steps
    from agentleak import AgentLeakRunner

    trace = trace_from_steps(agent_steps, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)

Or, with the unified API::

    with agentleak.watch("my-coder") as run:
        run.ingest_steps(agent_steps)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace

# Action-name keywords → how the step is classified. Matched case-insensitively
# as substrings so framework-specific names map cleanly (e.g. OpenHands
# "FileWriteAction", Cline "write_to_file", Open Interpreter "create").
_WRITE = ("write", "create", "edit", "save", "patch", "append", "str_replace")
_READ = ("read", "open", "view", "cat", "load", "get_file")
_RUN = ("run", "exec", "bash", "shell", "cmd", "command", "ipython", "python", "code", "cell")
_BROWSE = ("browse", "navigate", "goto", "click", "fill", "browser", "web", "type")
_THINK = ("think", "thought", "reason", "scratch", "plan", "reflect")
_FINISH = ("finish", "final", "message", "respond", "answer", "complete", "done")


def _g(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        val = getattr(obj, name, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(name)
        if val not in (None, ""):
            return val
    return default


def _kind(action: str) -> str:
    a = action.lower()
    # Order matters: a write is a write even if it contains "file".
    if any(k in a for k in _WRITE):
        return "write"
    if any(k in a for k in _THINK):
        return "think"
    if any(k in a for k in _READ):
        return "read"
    if any(k in a for k in _BROWSE):
        return "browse"
    if any(k in a for k in _RUN):
        return "run"
    if any(k in a for k in _FINISH):
        return "finish"
    return "run"  # default: treat an unknown action as an executed tool call


def trace_from_steps(
    steps: list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "computer_use_agent",
    default_agent: str = "agent",
) -> Trace:
    """Build a trace from an action–observation step list.

    Files the agent writes are recorded on the ``generated_file`` channel — the
    on-disk artifact is where computer-use agents most often persist sensitive
    data where an output-only check never looks.
    """
    trace = Trace(run_id=run_id, agent_name=agent_name)
    steps = list(steps or [])

    # Index of the last "finish"/message step → final_output.
    final_idx = -1
    for i, step in enumerate(steps):
        if _kind(str(_g(step, "action", "type", "tool", "name", default=""))) == "finish":
            final_idx = i

    for i, step in enumerate(steps):
        action = str(_g(step, "action", "type", "tool", "name", default="act"))
        agent = str(_g(step, "agent", "source", default=default_agent))
        kind = _kind(action)
        path = _g(step, "path", "file", "filename")
        command = _g(step, "command", "cmd", "code", "input")
        url = _g(step, "url", "href")
        thought = _g(step, "thought", "reasoning", "scratchpad")
        observation = _g(step, "observation", "result", "output", "stdout", "response")
        content = _g(step, "content", "text", "body")

        # Internal reasoning — restating private data here still leaks it.
        if thought:
            trace.add_event(channel="log", content=str(thought),
                            source=agent, target="scratchpad",
                            metadata={"action": action, "origin": "computer_use"})

        if kind == "write":
            trace.add_event(
                channel="generated_file",
                content=content if content is not None else (command or ""),
                source=agent, target=str(path or "file"),
                metadata={"action": action, "path": str(path or ""), "origin": "computer_use"},
            )
        elif kind == "read":
            if observation is not None or content is not None:
                trace.add_event(
                    channel="tool_response",
                    content=str(observation if observation is not None else content),
                    source=str(path or "file"), target=agent,
                    metadata={"action": action, "origin": "computer_use"},
                )
        elif kind == "browse":
            payload: dict[str, Any] = {"url": str(url or "")}
            if command:
                payload["input"] = command
            trace.add_event(channel="tool_call", content=payload,
                            source=agent, target=str(url or "browser"),
                            metadata={"action": action, "origin": "computer_use"})
            if observation is not None:
                trace.add_event(channel="tool_response", content=str(observation),
                                source=str(url or "browser"), target=agent,
                                metadata={"action": action, "origin": "computer_use"})
        elif kind == "finish":
            msg = content if content is not None else (command or observation or "")
            if i == final_idx:
                trace.add_event(channel="final_output", content=str(msg),
                                source=agent, target="user",
                                metadata={"action": action, "origin": "computer_use"})
            elif msg:
                trace.add_event(channel="inter_agent_message", content=str(msg),
                                source=agent, target="agent",
                                metadata={"action": action, "origin": "computer_use"})
        else:  # run / execute / code
            if command is not None:
                trace.add_event(channel="tool_call",
                                content=command if isinstance(command, (dict, list)) else str(command),
                                source=agent, target=action,
                                metadata={"action": action, "origin": "computer_use"})
            if observation is not None:
                trace.add_event(channel="tool_response", content=str(observation),
                                source=action, target=agent,
                                metadata={"action": action, "origin": "computer_use"})

    return trace


__all__ = ["trace_from_steps"]
