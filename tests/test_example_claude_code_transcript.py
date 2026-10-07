# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The Claude Code transcript example: what it attributes, and to whom."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from agentleak import AgentLeakRunner

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _example():
    spec = importlib.util.spec_from_file_location(
        "claude_code_transcript", EXAMPLES / "claude_code_transcript.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_report_is_clean_and_the_transcript_is_not():
    example = _example()
    trace = example.trace_from_transcript(example.SAMPLE)
    result = AgentLeakRunner().analyze(trace)

    from_subagent = [
        f for f in result.findings
        if str(f.channel) == "inter_agent_message" and f.source == "subagent"
    ]
    on_disk = {f.data_type for f in result.findings if str(f.channel) == "generated_file"}
    assert from_subagent == []
    assert {"ssn", "iban", "email"} <= on_disk


def test_default_attribution_is_the_tool_name():
    example = _example()
    trace = example.trace_from_transcript(example.SAMPLE)
    assert [e.target for e in trace.events_for_channel("tool_call")] == ["Write", "Bash"]


def test_store_resource_follows_a_script_the_agent_wrote():
    example = _example()
    trace = example.trace_from_transcript(
        example.SAMPLE, example.store_resource(r"customer_records\.csv", "direct_store")
    )
    # The second call never names the store: it runs the script that opens it.
    assert [e.target for e in trace.events_for_channel("tool_call")] == [
        "direct_store", "direct_store",
    ]
    assert {e.source for e in trace.events_for_channel("tool_response")} == {"direct_store"}


def test_store_resource_leaves_unrelated_calls_alone():
    example = _example()
    resource_of = example.store_resource(r"customer_records\.csv", "direct_store")
    assert resource_of("Bash", {"command": "ls /tmp/work"}) == "Bash"
    assert resource_of("Read", {"file_path": "/tmp/work/notes.txt"}) == "Read"


def test_report_tools_turn_a_tool_call_into_the_report(tmp_path):
    example = _example()
    transcript = tmp_path / "agent-x.jsonl"
    call = {"type": "tool_use", "id": "t1", "name": "hand_back", "input": {"message": "done"}}
    record = {"type": "assistant", "message": {"role": "assistant", "content": [call]}}
    transcript.write_text(json.dumps(record) + "\n", encoding="utf-8")

    as_tool = example.trace_from_transcript(transcript)
    as_report = example.trace_from_transcript(transcript, report_tools=frozenset({"hand_back"}))

    assert [e.target for e in as_tool.events_for_channel("tool_call")] == ["hand_back"]
    assert as_report.events_for_channel("tool_call") == []
    assert [e.target for e in as_report.events_for_channel("inter_agent_message")] == ["main_agent"]


def test_empty_thinking_and_attachments_add_no_events():
    example = _example()
    trace = example.trace_from_transcript(example.SAMPLE)
    assert trace.events_for_channel("log") == []
    assert len(trace.events) == 7
