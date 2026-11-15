# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Regression tests for the security review of the code added in 0.20.

Each input is shaped to hit one defect the review reproduced; the bounds are
generous so a slow CI machine passes while the old behaviour (minutes, a
crash, or markup in a report) fails.
"""

from __future__ import annotations

import time


def test_otel_genai_spans_convert_in_linear_time() -> None:
    """``trace_from_spans`` rescanned every event for every GenAI span: 8 000
    tool spans took 10 s, and /api/agent/selftest reaches it with
    ``trace_format: otel_openinference``."""
    from agentleak.integrations.otel import trace_from_spans

    spans = [{"name": "t", "span_id": f"s{i}", "start_time": i, "end_time": i + 1,
              "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "x",
                             "gen_ai.tool.call.arguments": "a", "gen_ai.tool.call.result": "b"}}
             for i in range(20_000)]
    start = time.perf_counter()
    trace = trace_from_spans(spans)
    assert time.perf_counter() - start < 10.0
    assert len(trace.events) == 40_000


def test_otel_genai_input_is_still_taken_once() -> None:
    """The incremental 'user input seen' flag reads the same as the rescan."""
    from agentleak.integrations.otel import trace_from_spans

    def chat(i: int) -> dict:
        return {"name": f"c{i}", "span_id": f"c{i}", "start_time": i, "end_time": i + 1,
                "attributes": {"gen_ai.operation.name": "chat",
                               "gen_ai.input.messages": f'[{{"role": "user", "parts": '
                                                        f'[{{"type": "text", "content": "q{i}"}}]}}]'}}

    trace = trace_from_spans([chat(1), chat(2), chat(3)])
    assert [e.content for e in trace.events if e.channel_value == "user_input"] == ["q1"]
