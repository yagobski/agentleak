# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""One secret, one identity — the invariant AgentRisk's Definition 1 asserts.

AgentRisk keys a secret on ``data_type`` plus the matched string, which counts
distinct *strings*, not distinct *secrets*. Detectors disagree about where an
entity ends: the healthcare dictionary matched ``diabetes`` while the key-name
detector, reading ``diagnosis: Type 2 diabetes``, matched the field value. One
diagnosis entered the vault twice, and both sides of the Risk Index moved.

The failure was silent and it pointed both ways. In the bundled healthcare
scenario the duplicate sat on ``tool_response`` — a baseline channel — so it
padded rho_S without reaching WSL and the published Risk Index read *lower*
than the truth (0.3793 against 0.44). Add the same duplicate on a disclosure
channel and the score reads higher instead.

These tests pin the property the score needs in order to mean anything: the
same secrets, written differently, must produce the same denominator.
"""

from __future__ import annotations

from agentleak.core.coalesce import canonical_form, coalesce_findings
from agentleak.core.detector import Finding, Severity
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.trace import Trace
from agentleak.detectors.keyname import SensitiveKeyDetector


def _finding(data_type: str, value: str, *, severity: Severity, level: int,
             channel: str = "final_output", event_id: str = "evt_001") -> Finding:
    return Finding(
        finding_id=f"finding_{value[:6]}",
        run_id="run",
        event_id=event_id,
        channel=channel,
        data_type=data_type,
        severity=severity,
        confidence=0.6,
        matched_value=value,
        redacted_value=value,
        detector="test",
        level=level,
    )


def _analyze(text: str, *, channel: str = "final_output"):
    trace = Trace(run_id="identity", agent_name="agent")
    trace.add_event(channel=channel, content=text, source="agent", target="user")
    return AgentLeakRunner().analyze(trace)


# ----------------------------------------------------------------------
# The property: phrasing must not move the denominator
# ----------------------------------------------------------------------
def test_the_same_secrets_written_three_ways_score_the_same() -> None:
    """Structured, prose and padded prose carry four secrets. All three must
    agree on rho_S — otherwise "same trace, same score" is only true for traces
    that happen to be written the same way, and a CI regression is noise.
    """
    variants = [
        '{"patient_name": "Jean Tremblay", "health_id": "TR12345678", '
        '"diagnosis": "Type 2 diabetes", "medication": "insulin"}',

        "Patient Jean Tremblay, health ID: TR12345678, "
        "diagnosis: Type 2 diabetes, medication: insulin.",

        "Patient Jean Tremblay, health ID: TR12345678, diagnosis: Type 2 diabetes, "
        "medication: insulin. Please forward this to the specialist as soon as possible.",
    ]

    denominators = {_analyze(text).to_dict()["agentrisk"]["rho_s"] for text in variants}
    assert len(denominators) == 1, (
        f"rho_S differs by phrasing: {denominators}. The trailing sentence in the "
        "third variant used to be captured as part of the medication value, which "
        "entered the vault as a second, distinct medication."
    )


def test_one_diagnosis_is_one_secret_even_when_two_detectors_find_it() -> None:
    result = _analyze("diagnosis: Type 2 diabetes")
    conditions = {f.matched_value for f in result.findings if f.data_type == "health_condition"}
    assert conditions == {"diabetes"}, (
        f"expected one canonical diagnosis, got {conditions}"
    )


def test_coalescing_keeps_the_strongest_classification() -> None:
    """The dictionary rates a bare diagnosis medium; the ``diagnosis:`` key
    rates the value it carries critical. Merging must take the critical one —
    the key name is the stronger statement about what the value is — or the fix
    for double-counting would quietly become a way to lower scores.
    """
    result = _analyze("diagnosis: Type 2 diabetes")
    conditions = [f for f in result.findings if f.data_type == "health_condition"]
    assert conditions
    assert all(f.level == 4 for f in conditions)
    assert all(f.severity is Severity.CRITICAL for f in conditions)


# ----------------------------------------------------------------------
# Coalescing boundaries
# ----------------------------------------------------------------------
def test_a_shared_prefix_is_not_a_shared_secret() -> None:
    """``1234`` is a substring of ``12345`` but a different account. Merging on
    bare containment would silently erase a real secret from the vault.
    """
    findings = [
        _finding("account_number", "1234", severity=Severity.CRITICAL, level=4),
        _finding("account_number", "12345", severity=Severity.CRITICAL, level=4),
    ]
    coalesce_findings(findings)
    assert {f.matched_value for f in findings} == {"1234", "12345"}


def test_different_data_types_never_merge() -> None:
    """A name inside an address is still a name and an address."""
    findings = [
        _finding("person_name", "Jean Tremblay", severity=Severity.LOW, level=1),
        _finding("address", "Jean Tremblay, 120 Maple Street", severity=Severity.HIGH, level=3),
    ]
    coalesce_findings(findings)
    assert {f.matched_value for f in findings} == {
        "Jean Tremblay",
        "Jean Tremblay, 120 Maple Street",
    }


def test_the_canonical_value_is_the_tightest_span() -> None:
    findings = [
        _finding("health_condition", "Type 2 diabetes", severity=Severity.CRITICAL, level=4),
        _finding("health_condition", "diabetes", severity=Severity.MEDIUM, level=3),
    ]
    coalesce_findings(findings)
    assert {f.matched_value for f in findings} == {"diabetes"}


def test_coalescing_records_what_it_replaced() -> None:
    """The wider span is evidence too: an auditor asking "where did this come
    from" gets the original text back out of the finding.
    """
    findings = [
        _finding("health_condition", "Type 2 diabetes", severity=Severity.CRITICAL, level=4),
        _finding("health_condition", "diabetes", severity=Severity.MEDIUM, level=3),
    ]
    coalesce_findings(findings)
    replaced = [f.metadata.get("coalesced_from") for f in findings]
    assert "Type 2 diabetes" in replaced


def test_coalescing_does_not_drop_disclosures() -> None:
    """Merging identities must not merge *events*: a secret disclosed on two
    channels is still two findings, because the per-channel risk and the leak
    paths are built from them.
    """
    findings = [
        _finding("health_condition", "Type 2 diabetes", severity=Severity.CRITICAL,
                 level=4, channel="shared_memory", event_id="evt_001"),
        _finding("health_condition", "diabetes", severity=Severity.MEDIUM,
                 level=3, channel="log", event_id="evt_002"),
    ]
    coalesce_findings(findings)
    assert len(findings) == 2
    assert {f.channel for f in findings} == {"shared_memory", "log"}


def test_canonical_form_ignores_case_and_whitespace() -> None:
    assert canonical_form("  Type  2   Diabetes ") == "type 2 diabetes"


# ----------------------------------------------------------------------
# Key-name capture: prose is not JSON
# ----------------------------------------------------------------------
def test_a_field_value_stops_at_the_end_of_the_sentence() -> None:
    """``final_output``, ``log`` and ``inter_agent_message`` carry sentences.
    Without a sentence boundary the capture ran from the key to the end of the
    line: ``medication: insulin. Please forward…`` was stored as a
    42-character medication, and a 106-character health identifier reached the
    leak-path explorer as masked evidence nobody could read.
    """
    matches = SensitiveKeyDetector().detect(
        "medication: insulin. Please forward to the specialist."
    )
    medications = [m.matched_value for m in matches if m.data_type == "medication"]
    assert medications == ["insulin"]


def test_a_period_inside_a_value_does_not_end_it() -> None:
    """Only a period followed by whitespace or the end of the text closes the
    value, so decimals and dotted identifiers survive.
    """
    matches = SensitiveKeyDetector().detect("credit_score: 3.5 out of 10")
    assert [m.matched_value for m in matches] == ["3.5 out of 10"]


def test_json_values_are_unaffected() -> None:
    matches = SensitiveKeyDetector().detect(
        '{"diagnosis": "Type 2 diabetes", "mrn": "TR12345678"}'
    )
    found = {m.data_type: m.matched_value for m in matches}
    assert found["health_condition"] == "Type 2 diabetes"
    assert found["health_identifier"] == "TR12345678"


def test_a_runaway_capture_is_dropped_rather_than_stored() -> None:
    """Past the field-value cap the match has stopped describing a field. An
    unbounded span is not evidence, and storing it would put a phantom secret
    in the vault.
    """
    runaway = "diagnosis: " + "chronic condition and " * 20
    matches = SensitiveKeyDetector().detect(runaway)
    assert not [m for m in matches if len(m.matched_value) > 120]


def test_masked_evidence_stays_readable() -> None:
    """The redacted value is what an auditor reads. A 106-character bar of
    asterisks is not a finding anyone can act on.
    """
    result = _analyze(
        "Patient record — health ID: TR12345678, diagnosis: Type 2 diabetes, "
        "medication: insulin. Route to the specialist before end of day."
    )
    assert all(len(f.redacted_value) <= 40 for f in result.findings), [
        f.redacted_value for f in result.findings
    ]
