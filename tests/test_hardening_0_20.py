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


def test_promptfoo_span_chain_check_is_linear() -> None:
    """The cycle check walked every span's chain to its root: a 8 000-span
    chain took 1.9 s and grew with the square of its length."""
    from agentleak.interop.promptfoo import trace_problem

    n = 200_000
    spans = [{"spanId": f"s{i}", "name": "x", "startTime": 1, "endTime": 2,
              **({"parentSpanId": f"s{i - 1}"} if i else {})} for i in range(n)]
    start = time.perf_counter()
    assert trace_problem({"traceId": "t", "spans": spans}) is None
    assert time.perf_counter() - start < 10.0
    spans[0]["parentSpanId"] = f"s{n - 1}"
    assert "form a cycle" in (trace_problem({"traceId": "t", "spans": spans}) or "")
    assert "form a cycle" in (trace_problem({"traceId": "t", "spans": [
        {"spanId": "a", "name": "x", "startTime": 1, "endTime": 2, "parentSpanId": "a"}]}) or "")


def test_markdown_report_escapes_the_imported_source_name() -> None:
    """``observation.source`` comes from the trace file's metadata; the Markdown
    report printed it raw (HTML, a line break starting a heading, a link)."""
    from agentleak import AgentLeakRunner, Trace
    from agentleak.reporters import render

    hostile = "<img src=x onerror=alert(1)>\n# owned [x](https://attacker.example)"
    trace = Trace.from_dict({"metadata": {"observation": {
        "source": hostile, "observable_channels": ["final_output"], "unobserved_channels": ["log"]}},
        "events": [{"channel": "final_output", "content": "hi"}]})
    md = render(AgentLeakRunner().analyze(trace).to_dict(), "markdown")
    line = next(ln for ln in md.splitlines() if ln.startswith("> Imported from"))
    assert "<img" not in md and "[x](" not in md and "\\[x\\](" in line
    assert "owned" in line and not any(ln.startswith("# owned") for ln in md.splitlines())
    assert "only final_output could be observed" in line and "audited: log." in line


def test_triage_resolution_is_not_findings_times_decisions() -> None:
    """Every finding was matched against every decision of the project: a run
    of 2 000 findings in a project at the 50 000-decision cap took 19 s per
    triage request (and per write, which returns the view)."""
    from agentleak.core import triage as tri

    findings = [{"finding_id": f"f{i}", "channel": "log", "data_type": "ssn", "level": 4,
                 "redacted_value": f"***{i}"} for i in range(2000)]
    decisions = [{"id": f"d{j:05d}", "run_id": "r0", "finding_id": f"f{j % 2000}", "run_created_at": 0,
                  "identity_key": f"m1|log|ssn|4|***{j % 4000}", "masked_key": f"m1|log|ssn|4|***{j % 4000}",
                  "state": "false_positive", "created_at": j} for j in range(50_000)]
    start = time.perf_counter()
    resolved = tri.resolve(findings, {}, run_id="r1", run_created_at=1, decisions=decisions, now=2)
    assert time.perf_counter() - start < 5.0
    # The newest matching decision is carried over (f5 matches every j with j % 4000 == 5).
    newest = max(j for j in range(50_000) if j % 4000 == 5)
    assert resolved[5].carried and resolved[5].decision["id"] == f"d{newest:05d}"


def test_postal_codes_inside_many_emails_are_linear() -> None:
    """Each postal-code candidate was checked against every email span."""
    from agentleak.detectors.pii import PIIDetector

    text = "".join(f"x{i}.a1b2c3@ex.co " for i in range(25_000))
    start = time.perf_counter()
    found = PIIDetector().detect(text)
    assert time.perf_counter() - start < 10.0
    assert not [m for m in found if m.data_type == "address"]
    # Outside an email the same shape is still a postal code.
    assert any(m.data_type == "address" for m in PIIDetector().detect("x@ex.co then H2X 1Y4 here"))


def test_json_in_a_string_cannot_bypass_the_depth_cap(tmp_path) -> None:
    """A tool call whose arguments are a JSON string nested 900 levels deep was
    parsed into the trace: ``agentleak import`` then crashed writing it, and a
    self-test of OTel spans failed in analysis."""
    import json

    from typer.testing import CliRunner

    from agentleak import AgentLeakRunner
    from agentleak.cli import app
    from agentleak.interop.convert import from_otel_genai, maybe_json

    nested = "[" * 900 + "1" + "]" * 900
    assert maybe_json(nested) == nested
    assert maybe_json('{"a": [1, 2]}') == {"a": [1, 2]}

    doc = [{"role": "user", "is_simulated": False, "pieces": [{"data_type": "text", "original_value": "hi"}]},
           {"role": "assistant", "is_simulated": False,
            "pieces": [{"data_type": "tool_call", "original_value": nested}]}]
    src = tmp_path / "pyrit.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    result = CliRunner().invoke(app, ["import", str(src), "-o", str(tmp_path / "out"), "--score",
                                      "--report-dir", str(tmp_path / "rep")])
    assert result.exception is None or isinstance(result.exception, SystemExit), result.exception
    assert result.exit_code == 0, result.output

    spans = [{"name": "t", "attributes": {"gen_ai.operation.name": "execute_tool",
                                          "gen_ai.tool.name": "x", "gen_ai.tool.call.arguments": nested}}]
    AgentLeakRunner().analyze(from_otel_genai(spans, run_id="deep"))


# Long events of many distinct values: de-duplication compared each new value
# with every earlier one (context rules, US address rules), and the sanitizer
# scanned the whole text once per distinct value. At 400 KB the old code took
# 3 s (US addresses) to 25 s (salaries) per detector.
_MANY = 400_000
_MANY_VALUES = {
    "phone": "".join(f"call 555-{i % 10000:04d} " for i in range(_MANY // 14)),
    "account": "".join(f"account {1000000 + i} " for i in range(_MANY // 16)),
    "salary": "".join(f"salary {10000 + i} " for i in range(_MANY // 13)),
    "health": "".join(f"diagnosed with osteoarthritis{i} " for i in range(_MANY // 30)),
    "us_zip": "".join(f"{i} Kaiser Plain, Lloydside, AL {10000 + i % 89999:05d} "
                      for i in range(_MANY // 36)),
}


def test_value_deduplication_is_not_quadratic() -> None:
    from agentleak.detectors import build_detectors

    detectors = build_detectors(None, None)
    for name, text in _MANY_VALUES.items():
        for detector in detectors:
            start = time.perf_counter()
            detector.detect(text)
            elapsed = time.perf_counter() - start
            assert elapsed < 3.0, f"{detector.name} took {elapsed:.2f}s on {name}"


def test_sanitizer_locates_many_values_in_linear_time() -> None:
    from agentleak.defenses.sanitizer import Sanitizer

    text = _MANY_VALUES["salary"]
    start = time.perf_counter()
    out = Sanitizer().sanitize(text)
    assert time.perf_counter() - start < 5.0
    assert "10000" not in out and "salary" in out


def test_substring_index_answers_like_the_pairwise_scan() -> None:
    import random

    from agentleak.detectors._text import SubstringIndex

    rng = random.Random(5)
    for _ in range(5000):
        values = ["".join(rng.choice("ab1 -") for _ in range(rng.randint(0, 6)))
                  for _ in range(rng.randint(0, 8))]
        both = rng.random() < 0.5
        index, taken = SubstringIndex(values[:3], both_ways=both), list(values[:3])
        for value in values[3:]:
            expected = any(value in v or (both and v in value) for v in taken)
            assert index.related(value) == expected, (taken, value, both)
            if rng.random() < 0.7:
                index.add(value)
                taken.append(value)


def test_occurrences_match_repeated_find(monkeypatch) -> None:
    import random

    from agentleak.defenses import sanitizer

    rng = random.Random(6)
    for slide_from in (1, 10**9):
        monkeypatch.setattr(sanitizer, "_SLIDE_FROM", slide_from)
        for _ in range(2000):
            text = "".join(rng.choice("ab1") for _ in range(rng.randint(0, 40)))
            values = {"".join(rng.choice("ab1") for _ in range(rng.randint(1, 4))) for _ in range(20)}
            found = sanitizer._occurrences(text, values)
            for value in values:
                expected, start = [], text.find(value)
                while start >= 0:
                    expected.append(start)
                    start = text.find(value, start + 1)
                assert found[value] == expected, (text, value)


def _hostile_trace(tmp_path):
    import json

    hostile = "agent\x1b]0;pwned\x07\x1b[2J\rX\x08\x9b31m\x7f"
    path = tmp_path / ("trace\x1b[31m.json")
    path.write_text(json.dumps({
        "run_id": "run\x1b]52;c;ZXZpbA==\x07", "agent_name": hostile,
        "metadata": {"observation": {"source": "tool\x1b[8m", "observable_channels": ["final_output"],
                                     "unobserved_channels": ["log"]}},
        "events": [{"channel": "tool_response", "source": "db\x1b[2K", "content": "SSN 123-45-6789"},
                   {"channel": "log", "source": "agent\r", "content": "SSN 123-45-6789"}],
    }), encoding="utf-8")
    return path


def _assert_terminal_safe(output: str) -> None:
    for ch in ("\x1b", "\x07", "\r", "\x08", "\x9b", "\x7f", "\x00"):
        assert ch not in output, repr(ch)


def test_cli_console_neutralises_terminal_controls_from_a_trace(tmp_path) -> None:
    """agent_name, run_id, observation.source, finding fields and file names
    reach the terminal; control characters in them must not act on it."""
    from typer.testing import CliRunner

    from agentleak.cli import app

    trace = _hostile_trace(tmp_path)
    result = CliRunner().invoke(app, ["run", "--trace", str(trace), "--output", str(tmp_path / "r"),
                                      "--format", "json"])
    assert result.exit_code in (0, 1), result.output
    _assert_terminal_safe(result.output)
    assert "\\u001b]0;pwned\\u0007" in result.output     # shown, inert
    assert "Observed by tool\\u001b[8m" in result.output


def test_console_clean_keeps_text_and_json() -> None:
    import json

    from agentleak._console import clean

    assert clean("line\n\tindented é ✓") == "line\n\tindented é ✓"
    doc = json.dumps({"v": "a\x85b\x7fc\x1bd"}, ensure_ascii=False)
    assert json.loads(clean(doc)) == {"v": "a\x85b\x7fc\x1bd"}
    _assert_terminal_safe(clean("".join(chr(c) for c in range(0x00, 0xA0) if chr(c) not in "\n\t")))
