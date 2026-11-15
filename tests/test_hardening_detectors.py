# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Timing guards found in the hardening review. Synthetic inputs only."""

from __future__ import annotations

import time

import pytest

from agentleak.defenses import Sanitizer


@pytest.mark.parametrize("unit", ["1.", "a:a", "1.1 "])
def test_sanitizer_is_not_superlinear_on_repeated_matches(unit: str) -> None:
    """``"1." * 200`` took 0.4 s, ``* 400`` took 6.6 s and ``* 1000`` minutes:
    every occurrence of a repeated value was located once per detector hit,
    and the spans were then compared pairwise. The proxies and the gateway run
    this on every tool call."""
    text = unit * (4000 // len(unit))
    start = time.perf_counter()
    out = Sanitizer().sanitize(text)
    assert time.perf_counter() - start < 3.0
    assert isinstance(out, str)


def test_sanitizer_still_redacts_inside_and_whole() -> None:
    s = Sanitizer()
    assert "123-45-6789" not in s.sanitize("ssn: 123-45-6789 and more text")
    key = "AKIA" + "Q" * 16
    out = s.sanitize(f"aws key {key} end")
    assert key not in out and "Q" * 8 not in out


# ----------------------------------------------------------------------
# Code scan: any account can upload files; one file must not take minutes
# ----------------------------------------------------------------------
def _scan_seconds(tmp_path, text: str) -> tuple[float, object]:
    from agentleak.core.codescan import scan_path

    (tmp_path / "a.py").write_text(text)
    start = time.perf_counter()
    result = scan_path(tmp_path)
    return time.perf_counter() - start, result


def test_code_scan_long_identifier_is_linear(tmp_path) -> None:
    """``\\w+\\s*\\(`` restarted at every position of a long word: 32 KB, 11 s."""
    seconds, _ = _scan_seconds(tmp_path, 'x = "' + "a" * 64000 + '"\n')
    assert seconds < 4.0


def test_code_scan_repeated_value_is_bounded(tmp_path) -> None:
    """One finding per occurrence, each with a whole-file line count: 64 KB of
    "1.1.1..." took 5 s and grew quadratically."""
    seconds, result = _scan_seconds(tmp_path, 'x = "' + "1." * 64000 + '"\n')
    assert seconds < 6.0
    assert all(len(f.snippet) <= 200 for f in result.findings)


def test_code_scan_many_values_is_bounded(tmp_path) -> None:
    from agentleak.core.codescan import MAX_FINDINGS_PER_FILE

    text = "\n".join(f'x{i} = "user{i}@example.test"' for i in range(8000))
    seconds, result = _scan_seconds(tmp_path, text)
    assert seconds < 6.0
    assert len(result.findings) <= MAX_FINDINGS_PER_FILE
    assert result.score == 0
    assert not any("@example.test" in f.snippet for f in result.findings)


# ----------------------------------------------------------------------
# Analysis of one request: many events with distinct values
# ----------------------------------------------------------------------
def test_analysis_of_many_events_is_bounded_and_says_so() -> None:
    """2,000 log lines with an e-mail and an SSN each (about 100 KB) took 17 s:
    obscured-copy search, clustering of SSNs that share a first run and
    provenance all compared every value with every event."""
    from agentleak import AgentLeakRunner
    from agentleak.core.trace import Trace

    events = [{"channel": "log", "content": f"user{i}@example.test SSN 123-45-{i:04d} card"}
              for i in range(3000)]
    start = time.perf_counter()
    result = AgentLeakRunner().analyze(Trace.from_dict({"events": events}))
    assert time.perf_counter() - start < 8.0
    assert result.leaked_findings()
    # What was skipped is said, so the run cannot pass for a full one.
    assert result.degraded and any("budget" in w for w in result.warnings)


def test_small_traces_keep_the_full_search() -> None:
    from agentleak import AgentLeakRunner
    from agentleak.core.trace import Trace

    events = [{"channel": "log", "content": f"SSN 123-45-{i:04d}"} for i in range(50)]
    assert not AgentLeakRunner().analyze(Trace.from_dict({"events": events})).degraded
