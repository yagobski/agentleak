"""Tests for the unified one-line API: agentleak.watch()."""

from __future__ import annotations

import agentleak
from agentleak.track import Run, active_run


def test_watch_records_and_autoanalyzes():
    with agentleak.watch(submit=False, print_summary=False) as run:
        run.tool_call({"email": "a@b.com", "ssn": "123-45-6789"}, target="crm")
        run.final_output("All done!")
    assert run.report is not None
    types = {f.data_type for f in run.report.findings}
    assert "email" in types and "ssn" in types


def test_watch_channel_shortcuts_map_to_channels():
    with agentleak.watch(submit=False, print_summary=False) as run:
        run.user_input("hi", source="user", target="agent")
        run.inter_agent_message("ssn 123-45-6789", source="a", target="b")
        run.shared_memory({"x": 1})
        run.log("info")
        run.final_output("done")
    channels = {e.channel_value for e in run.trace.events}
    assert {"user_input", "inter_agent_message", "shared_memory", "log",
            "final_output"} <= channels


def test_watch_callback_shares_single_trace():
    with agentleak.watch(submit=False, print_summary=False) as run:
        cb = run.callback
        cb.on_tool_start({"name": "crm"}, "lookup alex@example.com")
        cb.on_tool_end("account ACC-99887")
        run.tool_call({"ssn": "123-45-6789"}, target="crm")
    # Callback events and direct records land in the *same* trace.
    assert cb.trace is run.trace
    types = {f.data_type for f in run.report.findings}
    assert "email" in types and "ssn" in types


def test_watch_ingest_messages_swarm_handoff():
    messages = [
        {"role": "user", "content": "look up 42", "sender": "user"},
        {"role": "assistant", "sender": "triage", "content": "Transferring.",
         "tool_calls": [{"function": {"name": "crm", "arguments": '{"email":"a@b.com"}'}}]},
        {"role": "tool", "sender": "crm", "content": "ssn 123-45-6789"},
        {"role": "assistant", "sender": "support", "content": "Here is your summary."},
    ]
    with agentleak.watch(submit=False, print_summary=False) as run:
        run.ingest_messages(messages)
    channels = {e.channel_value for e in run.trace.events}
    assert "tool_response" in channels
    assert any(f.data_type == "ssn" for f in run.report.findings)


def test_watch_ingest_steps_computer_use_agent():
    steps = [
        {"action": "read_file", "path": "customer.yaml", "observation": "ssn: 456-78-9012"},
        {"action": "write_file", "path": "report.md",
         "content": "Customer ssn 456-78-9012 had a failed payment."},
        {"action": "finish", "content": "Report written. No PII included here."},
    ]
    with agentleak.watch(submit=False, print_summary=False) as run:
        run.ingest_steps(steps)
    channels = {e.channel_value for e in run.trace.events}
    assert "generated_file" in channels
    leaked = run.report.leaked_findings()
    assert any(f.channel == "generated_file" and f.data_type == "ssn" for f in leaked)


def test_watch_ingest_spans_openinference():
    spans = [
        {"name": "crm", "attributes": {
            "openinference.span.kind": "TOOL", "tool.name": "crm",
            "output.value": "ssn: 456-78-9012"}},
        {"name": "llm", "attributes": {
            "openinference.span.kind": "LLM",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.content": "leaking ssn 456-78-9012 onward"}},
    ]
    with agentleak.watch(submit=False, print_summary=False) as run:
        run.ingest_spans(spans)
    channels = {e.channel_value for e in run.trace.events}
    assert "tool_response" in channels
    assert any(f.data_type == "ssn" for f in run.report.findings)


def test_watch_record_module_function_works_inside_block():
    # agentleak.record() targets the active run (so it works from inside any
    # framework node/callback without passing the run around).
    with agentleak.watch(submit=False, print_summary=False) as run:
        agentleak.record("shared_memory", {"ssn": "123-45-6789"}, source="node")
    assert active_run() is None  # cleared on exit
    assert any(f.data_type == "ssn" for f in run.report.findings)


def test_watch_summary_is_string():
    with agentleak.watch(submit=False, print_summary=False) as run:
        run.final_output("clean")
    assert isinstance(run.summary(), str)
    assert "AgentLeak" in run.summary()


def test_watch_does_not_submit_without_project():
    with agentleak.watch(submit=None, print_summary=False) as run:
        run.final_output("clean")
    assert run.submitted is None


def test_watch_propagates_user_exception_without_analyzing():
    try:
        with agentleak.watch(submit=False, print_summary=False) as run:
            run.tool_call({"ssn": "123-45-6789"})
            raise ValueError("boom")
    except ValueError:
        pass
    # On error we don't mask it with analysis.
    assert run.report is None


def test_run_class_exported():
    assert agentleak.Run is Run
    assert callable(agentleak.watch)
