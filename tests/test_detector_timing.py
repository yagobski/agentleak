# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""No detector pattern may backtrack catastrophically.

Detection runs on every event of every trace, and an event is whatever an agent
wrote: a 200 KB tool response, a log line of repeated separators, a base64
blob. Each input below is shaped to stress one family of patterns (long digit
runs with separators for the identifier rules, long token alphabets for the
provider rules, repeated key names for the assignment rules). A linear-time
detector clears them in milliseconds; the bound is generous so a slow CI
machine does not fail it, while an exponential pattern would take minutes.
"""

from __future__ import annotations

import time

import pytest

from agentleak.detectors import build_detectors
from agentleak.detectors.national_ids import scan

N = 50_000

ADVERSARIAL = {
    "digits": "1" * N,
    "digit_groups": "12 " * (N // 3),
    "dotted_digits": "1." * (N // 2),
    "dashed_digits": "1-" * (N // 2),
    "letters": "a" * N,
    "upper_alnum": "A1" * (N // 2),
    "urlsafe": "a_-" * (N // 3),
    "base64ish": "aB3+/" * (N // 5),
    "hex": "deadbeef" * (N // 8),
    "prefixes": "sk-proj-" * (N // 8),
    "key_names": "password=" * (N // 9),
    "labels": "SIN " * (N // 4),
    "nir_like": "1 85 05 78 " * (N // 11),
    "phones": "+33 6 " * (N // 6),
    "spaces": " " * N,
    "mixed_seps": "1 .-/" * (N // 5),
    "dsn": "postgres://" + "a:" * (N // 2),
    "kv_conn": "Server=x;" * (N // 9),
    "dob": "born " * (N // 5),
    "street": "12 Main " * (N // 8),
    # A run of local-part characters ending in "@": quadratic for an email
    # pattern without the start-of-run look-behind (1.8 s at this size).
    "email_run_then_at": "a" * N + "@",
    "email_long_domain": "a@" + "b" * N,
}


@pytest.mark.parametrize("name", sorted(ADVERSARIAL))
def test_every_detector_is_linear_on_adversarial_input(name) -> None:
    text = ADVERSARIAL[name]
    for detector in build_detectors(None, None):
        start = time.perf_counter()
        detector.detect(text)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"{detector.name} took {elapsed:.2f}s on {name}"


def test_identifier_scan_is_linear() -> None:
    for text in ADVERSARIAL.values():
        start = time.perf_counter()
        scan(text)
        assert time.perf_counter() - start < 2.0


@pytest.mark.parametrize("name", sorted(ADVERSARIAL))
def test_decoders_are_linear_on_adversarial_input(name) -> None:
    from agentleak.core.transforms import decoded_views

    for text in (ADVERSARIAL[name], ADVERSARIAL[name] + "%41&#65;\\u0041\u200bа"):
        start = time.perf_counter()
        decoded_views(text)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"decoded_views took {elapsed:.2f}s on {name}"


def test_trie_pattern_matches_like_a_longest_first_alternation() -> None:
    import re

    from agentleak.detectors._text import trie_pattern

    terms = ["diabetes", "diabète", "diab", "type 2 diabetes", "cancer", "cancer du", "a", "ab"]
    old = re.compile(r"\b(" + "|".join(sorted(map(re.escape, terms), key=len, reverse=True)) + r")\b")
    new = re.compile(r"\b(" + trie_pattern(terms) + r")\b")
    for text in ("type 2 diabetes and diabète, cancer du sein, diab ab a", "cancer dub", "abc ab"):
        assert [m.group(0) for m in old.finditer(text)] == [m.group(0) for m in new.finditer(text)]


def test_email_pattern_is_linear_on_a_run_ending_in_at() -> None:
    """The QA report measured 1.8 s for this input with the plain pattern;
    the shipped one starts only where a run starts. A tight bound, because a
    regression here is quadratic, not slow."""
    from agentleak.detectors.pii import EMAIL_RE

    for text in ("a" * N + "@", "a." * (N // 2) + "@", "a@" + "b" * N):
        start = time.perf_counter()
        EMAIL_RE.findall(text)
        assert time.perf_counter() - start < 0.2
