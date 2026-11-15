# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The SDK adapters and the self-test loader read a format the same way.

Before 0.20, ``openai_swarm.trace_from_messages`` kept 2 of the 6 events of a
real Agents SDK ``to_input_list()`` (every function_call and its output were
dropped, so an SSN passed to a tool disappeared), and ``otel.trace_from_spans``
returned no event at all for OpenTelemetry GenAI spans. Both now delegate to
:mod:`agentleak.interop.convert`, the converters the self-test loader uses.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentleak import AgentLeakRunner
from agentleak.integrations.openai_swarm import trace_from_messages
from agentleak.integrations.otel import trace_from_spans
from agentleak.integrations.promptfoo_assert import get_assert
from agentleak.selftest import formats

FIX = Path(__file__).resolve().parent / "fixtures" / "selftest"


def _shape(trace) -> list[tuple[str, str, str]]:
    return [(e.channel_value, e.source, e.target) for e in trace.events]


def _leaks(trace) -> set[str]:
    return {f"{f.data_type}@{f.channel}" for f in AgentLeakRunner().analyze(trace).leaked_findings()}


def test_swarm_adapter_keeps_agents_sdk_tool_traffic():
    items = json.loads((FIX / "agents_sdk_items.json").read_text())
    trace = trace_from_messages(items, run_id="r")
    assert [e.channel_value for e in trace.events] == [
        "user_input", "tool_call", "tool_response", "tool_call", "tool_response", "final_output"]
    assert _shape(trace) == _shape(formats.from_openai_responses(items, run_id="r"))
    # The leak that used to vanish: the SSN written into the CRM note.
    assert "ssn@tool_call" in _leaks(trace)
    assert trace.agent_name == "swarm_agent"


def test_swarm_adapter_keeps_handoffs_and_reasoning():
    items = json.loads((FIX / "agents_sdk_handoff.json").read_text())
    items.insert(1, {"type": "reasoning", "id": "rs_1",
                     "summary": [{"type": "summary_text", "text": "Patient SSN 412-55-9087 seen"}]})
    trace = trace_from_messages(items)
    channels = [e.channel_value for e in trace.events]
    assert "inter_agent_message" in channels and "log" in channels
    handoff = next(e for e in trace.events if e.channel_value == "inter_agent_message")
    assert handoff.target == "billing" and handoff.metadata["handoff"]
    assert "ssn@log" in _leaks(trace)


def test_swarm_adapter_reads_sdk_item_objects():
    class Item:
        def __init__(self, **kw):
            self._kw = kw

        def model_dump(self, exclude_none=False):
            return dict(self._kw)

    items = [Item(role="user", content="hi"),
             Item(type="function_call", name="crm", arguments='{"ssn": "412-55-9087"}', call_id="c1"),
             Item(type="function_call_output", call_id="c1", output="ok")]
    trace = trace_from_messages(items)
    assert [e.channel_value for e in trace.events] == ["user_input", "tool_call", "tool_response"]


def test_swarm_chat_messages_are_unchanged_except_system():
    messages = [
        {"role": "system", "content": "You are support. Customer SSN 412-55-9087 is on file."},
        {"role": "user", "content": "look up customer 42", "sender": "user"},
        {"role": "assistant", "sender": "triage", "content": "Transferring you to support.",
         "tool_calls": [{"function": {"name": "crm", "arguments": '{"email": "a@b.com"}'}}]},
        {"role": "tool", "sender": "crm", "content": "account ACC-99887"},
        {"role": "assistant", "sender": "support", "content": "Here is your summary."},
    ]
    trace = trace_from_messages(messages)
    assert [e.channel_value for e in trace.events] == [
        "user_input", "user_input", "tool_call", "inter_agent_message", "tool_response",
        "final_output"]
    assert trace.events[0].source == "system"     # used to be dropped


def test_otel_adapter_reads_genai_spans_like_the_loader():
    payload = json.loads((FIX / "otel_genai_otlp.json").read_text())
    adapter = trace_from_spans(payload, run_id="r")
    loaded = formats.load_any(payload).trace
    assert [e.channel_value for e in adapter.events] == [e.channel_value for e in loaded.events]
    assert [e.channel_value for e in adapter.events] == [
        "user_input", "tool_call", "tool_response", "final_output"]
    assert _leaks(adapter) == _leaks(loaded)
    # span identity is kept, as for OpenInference spans
    assert all("span_id" in e.metadata for e in adapter.events)


def test_otel_adapter_mixed_openinference_and_genai_spans():
    spans = [
        {"name": "agent", "spanId": "a", "attributes": {
            "openinference.span.kind": "AGENT", "input.value": "update the CRM"}},
        {"name": "tool", "spanId": "t", "parentSpanId": "a", "attributes": {
            "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "crm_update",
            "gen_ai.tool.call.id": "c1",
            "gen_ai.tool.call.arguments": '{"note": "SSN 412-55-9087"}',
            "gen_ai.tool.call.result": "ok"}},
        {"name": "chat", "spanId": "c", "parentSpanId": "a", "attributes": {
            "gen_ai.operation.name": "chat",
            "gen_ai.input.messages": json.dumps([{"role": "user", "parts": [
                {"type": "text", "content": "update the CRM"}]}]),
            "gen_ai.output.messages": json.dumps([{"role": "assistant", "parts": [
                {"type": "tool_call", "id": "c1", "name": "crm_update", "arguments": {}},
                {"type": "reasoning", "content": "thinking"},
                {"type": "text", "content": "Done."}]}])}},
    ]
    trace = trace_from_spans(spans)
    channels = [e.channel_value for e in trace.events]
    # one user_input (the GenAI input repeats the chain input), the tool call
    # recorded once (the output-message part has the executed id), the answer.
    assert channels == ["user_input", "tool_call", "tool_response", "log", "final_output"]
    assert "ssn@tool_call" in _leaks(trace)


def test_promptfoo_assertion_now_grades_genai_spans():
    """A promptfoo trace whose application exports GenAI spans used to be
    INCOMPLETE ('no span carries agent content'); it is graded now."""
    trace = {"traceId": "t1", "spans": [
        {"spanId": "s1", "name": "tool", "startTime": 1, "endTime": 2, "attributes": {
            "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "crm",
            "gen_ai.tool.call.arguments": '{"ssn": "412-55-9087"}'}},
        {"spanId": "s2", "name": "chat", "startTime": 2, "endTime": 3, "attributes": {
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": json.dumps([{"role": "assistant", "parts": [
                {"type": "text", "content": "Saved."}]}])}},
    ]}
    graded = get_assert("", {"config": {"require_trace": True}, "trace": trace})
    assert graded["metadata"]["agentleak"]["status"] == "fail"
    assert {"channel": "tool_call", "data_type": "ssn"}.items() <= \
        graded["metadata"]["agentleak"]["leaks"][0].items()
