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


# -- submission failure handling (network unreachable) -------------------
# A platform submission failure must never destroy the local analysis result
# or crash the user's `with` block — it should be surfaced (not swallowed).

def test_watch_submission_failure_keeps_local_report_and_surfaces_error():
    with agentleak.watch(
        "some-project", base_url="http://127.0.0.1:59999",  # nothing listening
        print_summary=False,
    ) as run:
        run.tool_call({"ssn": "123-45-6789"}, target="crm")
        run.final_output("All done.")

    # The local analysis is complete and correct...
    assert run.report is not None
    assert any(f.data_type == "ssn" for f in run.report.findings)
    # ...even though submission failed and was not silently dropped.
    assert run.submitted is None
    assert run.submit_error is not None
    assert "127.0.0.1:59999" in run.submit_error or "agentleak serve" in run.submit_error


def test_watch_submission_failure_does_not_crash_the_with_block():
    # No exception should escape the `with` block just because the platform
    # submission failed — this must run to completion without raising.
    with agentleak.watch("p", base_url="http://127.0.0.1:59999", print_summary=False) as run:
        run.final_output("clean")
    assert run.report is not None


def test_watch_summary_includes_submission_failure_warning():
    with agentleak.watch("p", base_url="http://127.0.0.1:59999", print_summary=False) as run:
        run.final_output("clean")
    summary = run.summary()
    assert "submission failed" in summary
    assert run.submit_error in summary


def test_watch_successful_submission_leaves_submit_error_none(monkeypatch):
    from agentleak.client import AgentLeakClient

    class FakeServer:
        def __init__(self) -> None:
            self.projects: list[dict] = []

        def request(self, method: str, path: str, body=None):
            if path == "/api/projects" and method == "GET":
                return list(self.projects)
            if path == "/api/projects" and method == "POST":
                p = {"id": "proj_1", "name": body["name"]}
                self.projects.append(p)
                return p
            if path.endswith("/runs") and method == "POST":
                return {"id": "run_1", "risk_index": 0.0, "verdict": "Pass"}
            raise AssertionError(f"unexpected {method} {path}")

    server = FakeServer()
    monkeypatch.setattr(AgentLeakClient, "_request", lambda self, m, p, b=None: server.request(m, p, b))
    with agentleak.watch("p", base_url="http://test", print_summary=False) as run:
        run.final_output("clean")
    assert run.submit_error is None
    assert run.submitted is not None
    assert run.submitted["id"] == "run_1"


def test_watch_unexpected_submission_bug_is_not_swallowed(monkeypatch):
    """Only the client's own AgentLeakError is treated as best-effort; any
    other exception (a real bug) must still propagate, not be hidden."""
    import pytest

    from agentleak.client import AgentLeakClient

    def boom(self, project, **kw):
        raise TypeError("unexpected bug, not a network error")

    monkeypatch.setattr(AgentLeakClient, "ensure_project", boom)
    with pytest.raises(TypeError, match="unexpected bug"):
        with agentleak.watch("p", base_url="http://test", print_summary=False) as run:
            run.final_output("clean")
    # The local report was still produced before the (re-raised) submission bug.
    assert run.report is not None
