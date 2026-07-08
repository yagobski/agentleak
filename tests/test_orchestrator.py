"""Multi-agent orchestration tests (no network / no LLM)."""

from __future__ import annotations

from agentleak import AgentLeakRunner
from agentleak.agent import AgentDef, agents_from_config, run_pipeline
from agentleak.agent.context import RunContext


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

