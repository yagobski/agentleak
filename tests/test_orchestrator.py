# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Multi-agent orchestration tests (no network / no LLM)."""

from __future__ import annotations

import json

import pytest

from agentleak import AgentLeakRunner
from agentleak.agent import (
    AgentDef,
    AgentRunError,
    LLMConfig,
    OpenAICompatLLM,
    agents_from_config,
    run_pipeline,
)
from agentleak.agent.context import RunContext
from agentleak.agent.orchestrator import _normalize_tools, _toolbox_for


def _ctx() -> RunContext:
    return RunContext(
        scenario_id="s",
        request="Summarize the client's file.",
        records=[{"ssn": "123-45-6789", "name": "Jane Doe", "email": "jane@example.com"}],
    )


def test_scripted_pipeline_propagates_and_leaks():
    agents = [
        AgentDef(id="a1", name="Researcher", role="researcher"),
        AgentDef(id="a2", name="Writer", role="writer"),
    ]
    trace = run_pipeline(_ctx(), agents)
    channels = {e.channel_value for e in trace.events}
    assert "user_input" in channels
    assert "tool_response" in channels
    assert "inter_agent_message" in channels
    assert trace.events[-1].channel_value == "final_output"

    # The handoff between agents carries the secret -> multi-agent propagation.
    iam = [e for e in trace.events if e.channel_value == "inter_agent_message"]
    assert iam and "123-45-6789" in iam[0].searchable_text
    assert iam[0].source == "Researcher"
    assert iam[0].target == "Writer"

    result = AgentLeakRunner().analyze(trace)
    assert any(f.data_type == "ssn" for f in result.findings)
    assert 0.0 < result.score.risk_index <= 1.0


def test_single_agent_pipeline_has_no_handoff():
    trace = run_pipeline(_ctx(), [AgentDef(id="a1", name="Solo")])
    channels = {e.channel_value for e in trace.events}
    assert "inter_agent_message" not in channels
    assert trace.events[-1].channel_value == "final_output"


def test_agents_from_config_endpoint_detection():
    cfg = {
        "agents": [
            {"id": "a1", "name": "Researcher", "framework": "langchain"},
            {"id": "a2", "name": "Writer", "framework": "crewai",
             "endpoint": {"base_url": "http://localhost:1234/v1", "model": "m"}},
        ]
    }
    agents = agents_from_config(cfg)
    assert len(agents) == 2
    assert agents[0].llm is None          # no endpoint -> scripted
    assert agents[1].llm is not None      # endpoint -> live
    assert agents[1].framework == "crewai"


def test_agents_inherit_default_endpoint():
    cfg = {"agents": [{"id": "a1", "name": "R", "framework": "generic"}]}
    agents = agents_from_config(cfg, default_endpoint={"base_url": "http://x/v1", "model": "m"})
    assert agents[0].llm is not None      # falls back to project default endpoint


def test_scripted_pipeline_routes_records_to_mcp_tool():
    cfg = {
        "agents": [
            {
                "id": "a1", "name": "Researcher", "framework": "langchain",
                "tools": [{"name": "create_issue", "kind": "mcp", "server": "github-mcp"}],
            },
            {"id": "a2", "name": "Writer", "framework": "crewai"},
        ]
    }
    agents = agents_from_config(cfg)
    assert agents[0].tools and agents[0].tools[0]["kind"] == "mcp"

    trace = run_pipeline(_ctx(), agents)
    mcp_calls = [e for e in trace.events if e.channel_value == "tool_call" and e.target.startswith("mcp:")]
    assert mcp_calls, "the MCP tool should be exercised"
    assert mcp_calls[0].target == "mcp:github-mcp/create_issue"
    assert mcp_calls[0].source == "Researcher"
    assert "123-45-6789" in mcp_calls[0].searchable_text

    # Sending the record to the MCP server is a leak surface.
    result = AgentLeakRunner().analyze(trace)
    assert any(f.channel == "tool_call" and f.data_type == "ssn" for f in result.findings)


def test_function_tool_routes_to_named_sink():
    cfg = {"agents": [{"id": "a1", "name": "Solo", "tools": [{"name": "send_email", "kind": "function"}]}]}
    agents = agents_from_config(cfg)
    trace = run_pipeline(_ctx(), agents)
    targets = {e.target for e in trace.events if e.channel_value == "tool_call"}
    assert "send_email" in targets


# -- config normalization edge cases -------------------------------------

def test_agents_from_config_skips_non_dict_entries():
    cfg = {"agents": [{"id": "a1", "name": "R"}, "not-a-dict", 42, None]}
    agents = agents_from_config(cfg)
    assert len(agents) == 1
    assert agents[0].id == "a1"


def test_normalize_tools_skips_non_dict_entries():
    assert _normalize_tools(["not-a-dict", 42, None, {"name": "ok"}]) == [
        {"name": "ok", "kind": "function", "server": "", "description": ""}
    ]


def test_normalize_tools_skips_empty_names():
    # No 'name' and no 'server' to fall back on -> dropped entirely.
    raw = [{"kind": "function"}, {"name": "  "}, {"name": "valid_tool"}]
    out = _normalize_tools(raw)
    assert [t["name"] for t in out] == ["valid_tool"]


def test_normalize_tools_falls_back_to_server_name():
    out = _normalize_tools([{"server": "github-mcp", "kind": "mcp"}])
    assert out == [{"name": "github-mcp", "kind": "mcp", "server": "github-mcp", "description": ""}]


def test_normalize_tools_none_input_is_empty():
    assert _normalize_tools(None) == []


def test_toolbox_includes_mcp_schema_only_when_mcp_tool_present():
    plain = AgentDef(id="a1", name="Plain", tools=[{"name": "send_email", "kind": "function", "server": "", "description": ""}])
    mcp = AgentDef(id="a2", name="Mcp", tools=[{"name": "create_issue", "kind": "mcp", "server": "github-mcp", "description": ""}])
    plain_names = {t["function"]["name"] for t in _toolbox_for(plain)}
    mcp_names = {t["function"]["name"] for t in _toolbox_for(mcp)}
    assert "call_mcp_tool" not in plain_names
    assert "call_mcp_tool" in mcp_names


# -- live pipeline (LLM mocked, no network) -------------------------------

class _Resp:
    """Minimal stand-in for the ``http.client.HTTPResponse`` urlopen returns."""

    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def _assistant_msg(*, content: str = "", tool_calls: list[dict] | None = None) -> dict:
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}]}


def _live_agent(name: str = "LiveAgent") -> AgentDef:
    return AgentDef(id=name.lower(), name=name, llm=OpenAICompatLLM(LLMConfig(model="m", api_key="k")))


def test_live_pipeline_malformed_tool_json_falls_back_to_empty_args(monkeypatch):
    """A tool call with unparsable JSON arguments must not crash the run."""
    calls = [
        _assistant_msg(tool_calls=[
            {"id": "c1", "function": {"name": "save_memory", "arguments": "{not valid json"}}
        ]),
        _assistant_msg(content="All done."),
    ]

    def fake(req, timeout=None):
        return _Resp(calls.pop(0))

    monkeypatch.setattr("agentleak.agent.llm.urllib.request.urlopen", fake)
    trace = run_pipeline(_ctx(), [_live_agent()])
    assert trace.events[-1].channel_value == "final_output"
    assert "All done." in str(trace.events[-1].content)
    # save_memory ran with empty args (fallback), not a crash.
    mem = [e for e in trace.events if e.channel_value == "shared_memory"]
    assert mem and mem[0].content == ""


def test_live_pipeline_max_steps_exhausted_ends_gracefully(monkeypatch):
    """An agent that never stops calling tools hits max_steps and the run still
    completes (with a graceful fallback message), instead of looping forever
    or raising."""
    call_count = {"n": 0}

    def fake(req, timeout=None):
        call_count["n"] += 1
        # Always returns a tool call, never a plain final answer.
        return _Resp(_assistant_msg(tool_calls=[
            {"id": f"c{call_count['n']}", "function": {"name": "log_event", "arguments": "{}"}}
        ]))

    monkeypatch.setattr("agentleak.agent.llm.urllib.request.urlopen", fake)
    agent = _live_agent()
    trace = run_pipeline(_ctx(), [agent], max_steps=3)
    assert call_count["n"] == 3  # stopped after exactly max_steps LLM calls
    assert trace.events[-1].channel_value == "final_output"
    assert "stopped without a final answer" in str(trace.events[-1].content)


def test_live_pipeline_llm_failure_raises_agent_run_error_with_partial_trace(monkeypatch):
    """When the LLM call fails mid-run, AgentRunError must carry the trace
    captured up to that point rather than losing it silently."""
    calls = [
        _assistant_msg(tool_calls=[{"id": "c1", "function": {"name": "get_records", "arguments": "{}"}}]),
    ]

    # Patch chat() directly so the second call raises LLMError as _live_run does.
    def fake_urlopen(req, timeout=None):
        if calls:
            return _Resp(calls.pop(0))
        import urllib.error
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr("agentleak.agent.llm.urllib.request.urlopen", fake_urlopen)
    agent = _live_agent()

    with pytest.raises(AgentRunError) as exc_info:
        run_pipeline(_ctx(), [agent])

    err = exc_info.value
    assert err.trace is not None
    # The first (successful) tool call was captured before the failure.
    channels = {e.channel_value for e in err.trace.events}
    assert "user_input" in channels
    assert "tool_call" in channels
    assert "tool_response" in channels


def test_live_pipeline_second_agent_llm_failure_preserves_first_agents_trace(monkeypatch):
    """In a multi-agent pipeline, if the second agent's LLM fails, the trace
    still carries the first agent's (successful) handoff."""
    calls = [
        _assistant_msg(content="Handing off to Writer."),  # Researcher's only turn
    ]

    def fake_urlopen(req, timeout=None):
        if calls:
            return _Resp(calls.pop(0))
        import urllib.error
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr("agentleak.agent.llm.urllib.request.urlopen", fake_urlopen)
    agents = [_live_agent("Researcher"), _live_agent("Writer")]

    with pytest.raises(AgentRunError) as exc_info:
        run_pipeline(_ctx(), agents)

    err = exc_info.value
    assert err.trace is not None
    inter = [e for e in err.trace.events if e.channel_value == "inter_agent_message"]
    assert any("Handing off to Writer" in e.searchable_text for e in inter)


def test_no_agents_configured_raises():
    with pytest.raises(AgentRunError, match="No agents configured"):
        run_pipeline(_ctx(), [])

