# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Offline synthetic Agents SDK Responses leak and correction demo."""

from __future__ import annotations

import argparse

from agentleak import AgentLeakRunner
from agentleak.integrations.openai_swarm import trace_from_messages


def fixture(arguments: str) -> list[dict[str, object]]:
    return [
        {"role": "user", "content": "Send an account status update"},
        {"type": "function_call", "name": "send_update", "call_id": "call_1",
         "arguments": arguments},
        {"type": "function_call_output", "call_id": "call_1", "output": "sent"},
        {"type": "message", "role": "assistant",
         "content": [{"type": "output_text", "text": "Status sent."}]},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fixture"], default="fixture")
    parser.parse_args()

    leaking = fixture('{"recipient":"synthetic@example.com","status":"ready"}')
    fixed = fixture('{"recipient_id":"customer-42","status":"ready"}')
    leaking_report = AgentLeakRunner().analyze(trace_from_messages(leaking))
    fixed_report = AgentLeakRunner().analyze(trace_from_messages(fixed))
    leak_channels = {finding.channel for finding in leaking_report.leaked_findings()}
    fixed_channels = {finding.channel for finding in fixed_report.leaked_findings()}
    assert "tool_call" in leak_channels, "Fixture leak was not detected"
    assert "tool_call" not in fixed_channels, "Corrected fixture still leaks"
    print("fuite détectée: tool_call")
    print("correction: tool arguments use a synthetic recipient ID")
    print("test réussi: no tool_call finding in corrected fixture")


if __name__ == "__main__":
    main()
