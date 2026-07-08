"""End-to-end runner tests — the product's core promise."""

from __future__ import annotations

from agentleak import AgentLeakRunner, Trace
from agentleak.core.config import Config
from agentleak.scenarios import load_example_trace


def test_healthcare_demo_leaks_internally_not_in_output():
    """The headline: clean final output, leaks in internal channels."""
    trace = load_example_trace("healthcare_patient_summary")
    result = AgentLeakRunner().analyze(trace)

    channels = {cr.channel for cr in result.score.channel_risks}
    # Final output and tool_response (a source) carry no agent leak.
    assert "final_output" not in channels
    assert "tool_response" not in channels
    # Internal disclosure channels do leak.
    assert "shared_memory" in channels
    # shared_memory carries a Level-4 leak (the NAM health identifier).
    mem = next(cr for cr in result.score.channel_risks if cr.channel == "shared_memory")
    assert mem.level == 4
    assert mem.ri > 0
    # Partial leakage -> a real but sub-maximal Risk Index.
    assert 0.3 < result.risk_index < 0.9
    assert result.verdict in {"High risk", "Fail"}
    assert result.has_critical is True   # NAM + diagnosis (L4) leaked to memory
    assert result.blocked is True


def test_tool_response_is_a_source_not_a_leak():
    # A secret returned by a tool but never re-emitted is in the vault, not leaked.
    from agentleak import Trace
    trace = Trace(run_id="r")
    trace.add_event("tool_call", {"query": "lookup"})
    trace.add_event("tool_response", {"ssn": "412-55-9087"})   # received, not leaked
    trace.add_event("final_output", "Done.")
    result = AgentLeakRunner().analyze(trace)
    assert result.risk_index == 0.0          # nothing emitted onto a disclosure channel
    assert {f.channel for f in result.findings} == {"tool_response"}


def test_runner_assigns_finding_ids_and_context():
    trace = Trace(run_id="run_x", agent_name="a")
    trace.add_event("tool_call", {"email": "a@b.com"}, source="agent", target="crm")
    result = AgentLeakRunner().analyze(trace)
    assert result.findings
    f = result.findings[0]
    assert f.finding_id.startswith("finding_")
    assert f.run_id == "run_x"
    assert f.channel == "tool_call"
    assert f.target == "crm"


def test_runner_dedupes_same_value_in_event():
    # Two detectors might match the same value; the runner keeps one.
    trace = Trace(run_id="r")
    trace.add_event("log", "email a@b.com a@b.com")  # same value twice
    result = AgentLeakRunner().analyze(trace)
    emails = [f for f in result.findings if f.data_type == "email"]
    assert len(emails) == 1


def test_channel_filter_from_config_excludes_disabled_channels():
    cfg = Config.from_dict({
        "channels": ["final_output"],  # only scan final output
        "detectors": {"pii": True, "secrets": True, "healthcare": True},
    })
    trace = Trace(run_id="r")
    trace.add_event("tool_call", {"email": "a@b.com"})  # should be ignored
    trace.add_event("final_output", "contact a@b.com")  # scanned
    result = AgentLeakRunner(cfg).analyze(trace)
    channels = {f.channel for f in result.findings}
    assert channels == {"final_output"}


def test_clean_trace_passes():
    trace = Trace(run_id="r")
    trace.add_event("final_output", "Your request has been processed successfully.")
    result = AgentLeakRunner().analyze(trace)
    assert result.findings == []
    assert result.privacy_score == 100
    assert result.verdict == "Pass"
    assert result.blocked is False


def test_redact_values_off_includes_raw():
    cfg = Config.from_dict({"privacy": {"redact_values": False},
                            "detectors": {"pii": True}})
    trace = Trace(run_id="r")
    trace.add_event("log", "email leaked@example.com")
    result = AgentLeakRunner(cfg).analyze(trace)
    data = result.to_dict()
    assert any("leaked@example.com" == f.get("matched_value") for f in data["findings"])


# -- Agent scenarios: cases an agent can actually produce ----------------
# These exercise the newer detectors end-to-end through the runner and assert
# channel-aware result quality (sources are not leaks; internal channels are).

def test_agent_forwards_its_own_llm_key_to_another_agent():
    """A planner agent accidentally pastes its provider key into a handoff."""
    trace = Trace(run_id="key", agent_name="planner")
    trace.add_event("user_input", "Book the trip", source="user", target="planner")
    trace.add_event(
        "inter_agent_message",
        "Use my key OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno to call the API",
        source="planner", target="worker",
    )
    trace.add_event("final_output", "Your trip is booked.", source="worker", target="user")
    result = AgentLeakRunner().analyze(trace)
    leaked = {(f.channel, f.data_type) for f in result.findings}
    assert ("inter_agent_message", "llm_api_key") in leaked
    assert result.has_critical is True
    # The user-facing answer stays clean.
    assert "final_output" not in {f.channel for f in result.findings}


def test_agent_logs_authorization_bearer_header():
    """A tool wrapper logs the outbound request including the auth header."""
    trace = Trace(run_id="bear", agent_name="agent")
    trace.add_event("user_input", "Fetch my orders", source="user", target="agent")
    trace.add_event(
        "log",
        "GET /orders Authorization: Bearer abcdef0123456789abcdef0123456789",
        source="agent", target="logger",
    )
    trace.add_event("final_output", "You have 3 orders.", source="agent", target="user")
    result = AgentLeakRunner().analyze(trace)
    assert ("log", "bearer_token") in {(f.channel, f.data_type) for f in result.findings}


def test_version_string_in_output_is_not_an_ip_leak():
    """Precision: a build version must never be reported as a client IP."""
    trace = Trace(run_id="ver")
    trace.add_event("final_output", "Running version 1.2.3.4 of the assistant.")
    result = AgentLeakRunner().analyze(trace)
    assert result.findings == []
    assert result.verdict == "Pass"


def test_nino_from_tool_response_only_leaks_when_re_emitted():
    """A UK NINO arrives from a datastore (source) then leaks to shared memory."""
    trace = Trace(run_id="nino", agent_name="A1")
    trace.add_event("user_input", "Check my benefits", source="user", target="A1")
    trace.add_event("tool_response", {"nino": "AB123456C"}, source="datastore", target="A1")
    trace.add_event("shared_memory", "note: claimant NINO AB123456C", source="A1", target="memory")
    trace.add_event("final_output", "Your benefits are up to date.", source="A1", target="user")
    result = AgentLeakRunner().analyze(trace)
    by_channel = {f.channel for f in result.leaked_findings()
                  if f.data_type == "national_insurance_number"}
    # Arrival via tool_response is a source, not a leak; re-emission to memory is.
    assert by_channel == {"shared_memory"}
