"""Model Context Protocol (MCP) integration.

MCP-based agents reach external **tools** and **resources** through MCP servers.
Every argument an agent sends to an MCP tool — and everything the server returns
— is data crossing a trust boundary, which makes MCP calls a first-class leakage
surface. This adapter normalizes a list of MCP tool-call records into a
:class:`~agentleak.core.trace.Trace` so the same AgentRisk scoring applies.

Each record is a plain dict (framework-agnostic, duck-typed)::

    {
        "server": "github-mcp",        # the MCP server that owns the tool
        "tool": "create_issue",        # the tool name
        "arguments": {"title": ...},   # what the agent SENT  -> tool_call (sink)
        "result": "...",               # what the server RETURNED -> tool_response
        "agent": "Researcher",         # optional: the calling agent
    }

Usage::

    from agentleak.integrations.mcp import trace_from_mcp
    from agentleak import AgentLeakRunner

    trace = trace_from_mcp(mcp_calls, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    """Read the first present attribute/key from an object or dict."""
    for name in names:
        val = getattr(obj, name, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(name)
        if val is not None:
            return val
    return default


def _server_target(server: str, tool: str) -> str:
    """A stable node name for an MCP tool, e.g. ``mcp:github-mcp/create_issue``."""
    server = str(server or "mcp")
    tool = str(tool or "tool")
    return f"mcp:{server}/{tool}"


def trace_from_mcp(
    calls: list[Any],
    *,
    run_id: str = "run",
    agent_name: str = "mcp_agent",
    default_agent: str = "agent",
) -> Trace:
    """Build a trace from a list of MCP tool-call records.

    Sending arguments to an MCP server is recorded as ``tool_call`` (the server
    is the sink); the server's reply is recorded as ``tool_response`` (a source).
    """
    trace = Trace(run_id=run_id, agent_name=agent_name)

    for call in calls or []:
        server = str(_get(call, "server", "server_name", default="mcp"))
        tool = str(_get(call, "tool", "tool_name", "name", default="tool"))
        agent = str(_get(call, "agent", "caller", default=default_agent))
        target = _server_target(server, tool)

        arguments = _get(call, "arguments", "args", "input", "params")
        if arguments is not None:
            content = arguments if isinstance(arguments, (dict, list)) else {"input": str(arguments)}
            trace.add_event(
                channel="tool_call",
                content=content,
                source=agent,
                target=target,
                metadata={"tool_name": tool, "mcp_server": server, "origin": "mcp"},
            )

        result = _get(call, "result", "response", "output", "content")
        if result is not None:
            trace.add_event(
                channel="tool_response",
                content=result if isinstance(result, (dict, list)) else str(result),
                source=target,
                target=agent,
                metadata={"tool_name": tool, "mcp_server": server, "origin": "mcp"},
            )

    return trace


__all__ = ["trace_from_mcp"]
