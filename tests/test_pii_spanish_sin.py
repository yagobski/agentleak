# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Spanish mobile vs Canadian SIN false positive (issue #4).

A Spanish mobile national part is 9 digits in 3-3-3 groups ("612 345 678"),
which collides with the Canadian SIN shape. When the match is immediately
preceded by the Spanish country code (+34 / 0034), it must NOT be flagged
as a SIN. A bare 3-3-3 run without a country code stays flagged: without
context the ambiguity cannot be resolved, and the project prefers a
documented flag over a silent guess.
"""
from agentleak.detectors.pii import PIIDetector


def _sin_values(text):
    return [m.matched_value for m in PIIDetector().detect(text) if m.data_type == "sin"]


def _phones(text):
    return [m.matched_value for m in PIIDetector().detect(text) if m.data_type == "phone_number"]


def test_spanish_mobile_with_plus34_not_sin():
    # Exact case reported by Claudio Martín Sosa (issue #4).
    assert _sin_values("call me at +34 600 000 000") == []


def test_spanish_mobile_variants_not_sin():
    assert _sin_values("+34 612 345 678") == []
    assert _sin_values("0034 612 345 678") == []
    assert _sin_values("tel (+34) 612 345 678") == []
    assert _sin_values("+34-612 345 678") == []


def test_bare_333_run_still_flagged():
    # No country code: ambiguity stays a documented flag, not a guess.
    assert _sin_values("my number 612 345 678") == ["612 345 678"]


def test_real_sin_still_flagged():
    assert _sin_values("SIN 046 454 286") != []
    assert _sin_values("130-692-544") == ["130-692-544"]


def test_sin_after_spanish_prefix_kept():
    # A real SIN mentioned after an unrelated +34 stays flagged.
    vals = _sin_values("call +34 then my SIN 046 454 286")
    assert "046 454 286" in vals


def test_spanish_number_with_prefix_is_a_phone_in_any_grouping():
    # Not a SIN, but still a phone: skipping the SIN match alone would let it
    # through unreported.
    for text in ["call me at +34 600 000 000", "+34 612 345 678", "+34 612345678",
                 "+34 612 34 56 78", "+34 91 123 45 67", "0034 912 345 678",
                 "tel (+34) 612 345 678", "+34-612-345-678"]:
        assert len(_phones(text)) == 1, text
        assert _sin_values(text) == [], text
