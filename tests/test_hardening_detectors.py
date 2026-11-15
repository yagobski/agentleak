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
