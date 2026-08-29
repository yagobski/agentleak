# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Anything AgentLeak can detect, AgentLeak must be able to redact.

Detection and prevention used to be two inventories. ``defenses/sanitizer.py``
carried a hand-written table of ten patterns, described in its own comment as
"a simplified subset of the full detector", while the detector registry emitted
thirty-eight data types. The subset had drifted, and nobody was checking:

* no Canadian SIN pattern in any format — the identifier this project's own
  README uses to explain Law 25, and the detectors find it;
* no diagnosis and no medication — GDPR Article 9 special-category data, the L4
  severity class the product is built around;
* a credit-card pattern requiring contiguous digits, so ``4111 1111 1111 1111``
  and ``4111-1111-1111-1111``, the two ways cards are written, passed through;
* a health identifier of ``[A-Z]{4}\\d{8}``, which cannot match the
  ``TR12345678`` in the bundled demo trace.

``agentleak redact`` is sold as the door into prevention and is exposed to
coding agents as an MCP tool. It returned text that looked sanitised and was
not — silently, which is the part that matters.

These tests fail if a data type is ever again detectable but not redactable
without saying so on the record in ``DETECT_ONLY``.
"""

from __future__ import annotations

import inspect
import re

import pytest

from agentleak.defenses.sanitizer import (
    DETECT_ONLY,
    Sanitizer,
    redaction_coverage,
    sanitize_text,
)
from agentleak.detectors import build_detectors


def _emitted_data_types() -> set[str]:
    """Every data type the built-in detector chain can produce."""
    emitted: set[str] = set()
    for detector in build_detectors(None, None):
        source = inspect.getsource(type(detector))
        emitted |= set(re.findall(r'data_type\s*=\s*"([a-z_]+)"', source))
        emitted |= set(re.findall(r'"([a-z_]+)",\s*Severity\.', source))
    return emitted


# ----------------------------------------------------------------------
# The conformance gate
# ----------------------------------------------------------------------
def test_every_detectable_type_is_redactable_or_declared() -> None:
    """The gate. A type is redactable, or it is on the record as detect-only
    with a reason. There is no third option, and no silent one.
    """
    coverage = redaction_coverage()
    unaccounted = _emitted_data_types() - set(coverage["redactable"]) - set(DETECT_ONLY)
    assert not unaccounted, (
        f"detectable but neither redactable nor declared detect-only: "
        f"{sorted(unaccounted)}. Add a pattern, or add the type to DETECT_ONLY "
        f"with the reason redaction would do more harm than good."
    )


def test_detect_only_entries_carry_their_reason() -> None:
    for data_type, reason in DETECT_ONLY.items():
        assert len(reason) > 40, (
            f"{data_type} is exempted from redaction without a real "
            f"justification: {reason!r}"
        )


def test_coverage_is_reported_by_the_running_software() -> None:
    """Published claims have to be checkable against the engine, not a README."""
    coverage = redaction_coverage()
    assert coverage["redactable_count"] == len(coverage["redactable"])
    assert coverage["redactable_count"] > 25
    assert set(coverage["detect_only"]) <= set(DETECT_ONLY)


# ----------------------------------------------------------------------
# The values that used to survive redaction
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "text,leaked",
    [
        # A SIN, in each of the three ways it gets written. None of these were
        # removed before; the README's own Law 25 example uses this identifier.
        ("SIN 123 456 789", "123 456 789"),
        ("sin: 123-456-789", "123-456-789"),
        ("SIN 123456789", "123456789"),
        # Cards, as people actually write them.
        ("card 4111 1111 1111 1111", "4111 1111 1111 1111"),
        ("card: 4111-1111-1111-1111", "4111-1111-1111-1111"),
        ("card 4111111111111111", "4111111111111111"),
        # Special-category health data: the L4 class the product is built on,
        # and the identifier from its own demo trace.
        ("health ID: TR12345678", "TR12345678"),
        ("diagnosis: Type 2 diabetes", "diabetes"),
        ("medication: insulin", "insulin"),
        # Credentials.
        ("token ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
         "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"),
        ("AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
        # Contact PII, which did work and must keep working.
        ("Contact jean.tremblay@clinic.qc.ca", "jean.tremblay@clinic.qc.ca"),
    ],
)
def test_the_sensitive_value_does_not_survive(text: str, leaked: str) -> None:
    assert leaked not in sanitize_text(text), (
        f"{leaked!r} survived redaction of {text!r}"
    )


def test_a_nine_digit_number_is_not_a_sin_without_the_word() -> None:
    """The unseparated form is matched only next to the word that names it.
    Redacting every run of nine digits would strip order numbers and timestamps,
    and a guardrail that mangles ordinary text gets switched off.
    """
    assert "123456789" in sanitize_text("order 123456789 shipped")


# ----------------------------------------------------------------------
# Redaction must remove the secret without destroying the sentence
# ----------------------------------------------------------------------
def test_redaction_keeps_the_surrounding_sentence() -> None:
    """A key-name match locates a secret only as precisely as the punctuation
    allows. Taking the outer span would delete the rest of the line.
    """
    result = sanitize_text("SSN: 412-55-9087 and more text")
    assert "412-55-9087" not in result
    assert "and more text" in result


def test_two_secrets_under_one_key_are_both_removed() -> None:
    result = sanitize_text("ssn: 412-55-9087 email: a@b.com")
    assert "412-55-9087" not in result
    assert "a@b.com" not in result


def test_an_unlisted_value_under_a_sensitive_key_is_still_removed() -> None:
    """No dictionary lists every diagnosis. When nothing tighter matches inside
    the key-name span, that span *is* the signal — which is why the key-name
    detector exists.
    """
    result = sanitize_text("diagnosis: acute idiopathic pseudo-syndrome")
    assert "acute idiopathic pseudo-syndrome" not in result


def test_clean_text_is_returned_untouched() -> None:
    clean = "The order shipped on Tuesday and arrived Thursday."
    assert sanitize_text(clean) == clean


def test_redaction_count_matches_what_is_removed() -> None:
    assert Sanitizer().redaction_count("SSN: 412-55-9087 email: a@b.com") == 2


def test_a_modifier_may_survive_and_that_is_the_documented_trade() -> None:
    """Chosen behaviour, pinned so it stays a decision rather than a drift.

    The dictionary match is ``diabetes``, so the inner-span rule leaves
    ``Type 2`` behind. A modifier is not a re-identifier, and the alternative —
    always taking the key-name span — deletes the rest of any sentence a
    sensitive key appears in.
    """
    result = sanitize_text("diagnosis: Type 2 diabetes")
    assert "diabetes" not in result
    assert "REDACTED_HEALTH_CONDITION" in result
