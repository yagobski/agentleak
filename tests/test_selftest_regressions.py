# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Engine bugs the self-test loop surfaced, each pinned.

1. Applying the recommended fix (Sanitizer placeholders) was itself reported
   as a leak: `ssn: [REDACTED_SSN]` -> keyname "ssn", `TOKEN=[REDACTED_…]` ->
   secret_assignment. An agent following next_steps could never reach green.
2. `medical record number: [REDACTED_…]` captured the word "number" as an MRN.
3. A canary shaped like a credential (an AWS-format key) was dropped by the
   "match inside a credential" filter, so canary mode silently lost its proof.
4. Format converters: OpenAI Agents SDK items and OTel GenAI spans lost events
   (in the SDK adapters too, until they moved to the shared converters).
"""

from __future__ import annotations

import json
from pathlib import Path

from agentleak import AgentLeakRunner, Trace
from agentleak.core.canary import CanarySet
from agentleak.defenses import Sanitizer
from agentleak.integrations.openai_swarm import trace_from_messages
from agentleak.integrations.otel import trace_from_spans
from agentleak.selftest import formats

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "selftest"


def _leaks(content: object) -> list[tuple[str, str]]:
    trace = Trace.from_dict({"events": [{"channel": "log", "content": content}]})
    return [(f.data_type, f.matched_value) for f in AgentLeakRunner().analyze(trace).leaked_findings()]


def test_sanitized_output_is_not_reported_as_a_leak():
    record = {"name": "Avery Novak", "ssn": "412-55-9087", "card_number": "4111 1111 1111 1111",
              "GITHUB_TOKEN": "ghp_" + "b" * 36, "phone": "+1 415 555 0142"}
    cleaned = Sanitizer().sanitize_dict(record)
    flat = ", ".join(f"{k}={v}" for k, v in cleaned.items())
    types = {t for t, _ in _leaks(flat)} | {t for t, _ in _leaks(cleaned)}
    assert not types & {"ssn", "credit_card", "secret_assignment", "github_token", "phone_number"}


def test_a_real_value_after_a_sensitive_key_is_still_reported():
    assert ("ssn", "412-55-9087") in _leaks("ssn: 412-55-9087")
    assert any(t == "secret_assignment" for t, _ in _leaks("API_KEY=abc123def456ghi789"))


def test_a_redacted_record_number_label_is_not_an_mrn():
    assert not [v for t, v in _leaks("medical record number: [REDACTED_MRN]")
                if t == "health_identifier"]
    assert ("health_identifier", "12345678") in _leaks("MRN: 12345678")


def test_a_credential_shaped_canary_is_kept():
    key = "AKIA" + "Q7X3NB5PLW2KDJ4M"  # built at run time: no key-shaped literal in the repo
    trace = Trace.from_dict({"events": [{"channel": "generated_file", "content": f"KEY={key}"}]})
    result = AgentLeakRunner().analyze(trace, canary_set=CanarySet(realistic=[key]))
    types = {f.data_type for f in result.leaked_findings()}
    assert {"canary", "aws_access_key"} <= types


def test_agents_sdk_items_keep_tool_calls_in_both_entry_points():
    items = json.loads((FIXTURES / "agents_sdk_items.json").read_text())
    # The SDK adapter used to keep 2 of these 6 events (the gap closed in 0.20).
    adapter = trace_from_messages(items)
    new = formats.from_openai_responses(items, run_id="r")
    assert [(e.channel_value, e.target) for e in adapter.events] == \
        [(e.channel_value, e.target) for e in new.events]
    calls = [e for e in new.events if e.channel_value == "tool_call"]
    assert [e.target for e in calls] == ["lookup_customer", "send_crm_note"]
    assert [e.channel_value for e in new.events].count("tool_response") == 2
    assert new.events[-1].channel_value == "final_output"


def test_agents_sdk_handoff_is_an_inter_agent_message():
    items = json.loads((FIXTURES / "agents_sdk_handoff.json").read_text())
    trace = formats.from_openai_responses(items, run_id="r")
    handoff = next(e for e in trace.events if e.channel_value == "inter_agent_message")
    assert handoff.target == "billing" and handoff.metadata["handoff"]
    assert trace.events[-1].source == "billing"


def test_otel_genai_spans_produce_events():
    payload = json.loads((FIXTURES / "otel_genai_otlp.json").read_text())
    # The OpenInference adapter used to return no event at all (closed in 0.20).
    adapter = trace_from_spans(payload)
    loaded = formats.load_any(payload)
    assert [e.channel_value for e in adapter.events] == \
        [e.channel_value for e in loaded.trace.events]
    assert loaded.format == "otel_genai"
    channels = [e.channel_value for e in loaded.trace.events]
    assert channels.count("tool_call") == 1  # the output-message call is not counted twice
    assert "tool_response" in channels and channels[-1] == "final_output"


def test_chat_tool_names_are_recovered_from_tool_call_ids():
    messages = json.loads((FIXTURES / "chat_completions_messages.json").read_text())
    trace = formats.from_openai_chat(messages, run_id="r")
    responses = [e for e in trace.events if e.channel_value == "tool_response"]
    assert [e.source for e in responses] == ["lookup_patient", "post_to_slack"]


def test_claude_code_main_session_mapping():
    lines = (FIXTURES / "claude_code_session.jsonl").read_text().splitlines()
    loaded = formats.load_text("\n".join(lines), label="session.jsonl")
    assert loaded.format == "claude_code"
    by_channel = {}
    for e in loaded.trace.events:
        by_channel.setdefault(e.channel_value, []).append(e)
    assert by_channel["user_input"][0].source == "user"
    assert by_channel["generated_file"][0].target.endswith("deploy.yaml")
    assert by_channel["tool_call"][0].target == "Read"
    assert by_channel["final_output"][0].source == "claude_code"
    assert "log" in by_channel  # non-empty thinking


def test_claude_code_subagent_mapping_matches_the_example():
    text = (Path(__file__).resolve().parent.parent / "examples"
            / "claude_code_subagent_transcript.jsonl").read_text()
    loaded = formats.load_text(text, label="agent-sample.jsonl")
    first = loaded.trace.events[0]
    assert first.channel_value == "inter_agent_message" and first.source == "main_agent"
    assert loaded.trace.events[-1].target == "main_agent"
