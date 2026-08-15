# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Detector behavior and precision tests."""

from __future__ import annotations

from agentleak.core.detector import Severity, redact
from agentleak.detectors import build_detectors
from agentleak.detectors.custom import CustomDetector, CustomRule
from agentleak.detectors.finance import FinanceDetector
from agentleak.detectors.healthcare import HealthcareDetector
from agentleak.detectors.hr import HRDetector
from agentleak.detectors.pii import PIIDetector
from agentleak.detectors.secrets import SecretsDetector


def _types(detector, text):
    return {m.data_type for m in detector.detect(text)}


# -- PII ----------------------------------------------------------------
def test_pii_detects_email_and_ssn():
    d = PIIDetector()
    types = _types(d, "Contact jane.doe@example.com, SSN 123-45-6789.")
    assert "email" in types
    assert "ssn" in types


def test_pii_credit_card_requires_luhn():
    d = PIIDetector()
    # Valid Visa test number (passes Luhn).
    assert "credit_card" in _types(d, "card 4111 1111 1111 1111")
    # 16 digits that fail Luhn should not be reported as a card.
    assert "credit_card" not in _types(d, "ref 1234 5678 9012 3456 7")


def test_pii_name_requires_keyword_anchor():
    d = PIIDetector()
    assert "person_name" in _types(d, "patient Jean Tremblay arrived")
    # No keyword -> no name match (avoids flagging arbitrary capitalized words).
    assert "person_name" not in _types(d, "New York Times reported today")


def test_pii_clean_text_has_no_findings():
    d = PIIDetector()
    assert d.detect("The patient requires a routine follow-up appointment.") == []


def test_pii_dob_only_with_keyword():
    d = PIIDetector()
    assert "date_of_birth" in _types(d, "DOB 1979-03-12")
    # A bare ISO date (e.g. a timestamp) is not flagged as DOB.
    assert "date_of_birth" not in _types(d, "event at 2026-06-19")


def test_pii_detects_french_quebec_address():
    d = PIIDetector()
    # English suffix form still works.
    assert "address" in _types(d, "123 Main Street")
    # French / Québec "<number> <street-type> <name>" form (Law 25 positioning).
    assert "address" in _types(d, "1240 Rue Saint-Denis, Montréal")
    assert "address" in _types(d, "85 Boulevard René-Lévesque Ouest")
    assert "address" in _types(d, "7 Chemin de la Côte-Sainte-Catherine")
    # A bare order number is not an address.
    assert "address" not in _types(d, "Order 1240 was shipped today")


# -- Secrets ------------------------------------------------------------
def test_secrets_detects_aws_and_private_key():
    d = SecretsDetector()
    types = _types(d, "AKIAIOSFODNN7EXAMPLE and -----BEGIN RSA PRIVATE KEY-----")
    assert "aws_access_key" in types
    assert "private_key" in types


def test_secrets_are_critical():
    d = SecretsDetector()
    matches = d.detect("token ghp_" + "a" * 36)
    assert matches
    assert all(m.severity is Severity.CRITICAL for m in matches if m.data_type == "github_token")


def test_secrets_password_assignment():
    d = SecretsDetector()
    assert "secret_assignment" in _types(d, 'password: "hunter2real"')
    # Obvious placeholders are skipped.
    assert "secret_assignment" not in _types(d, "password: redacted")


# -- Healthcare ---------------------------------------------------------
def test_healthcare_nam_is_critical():
    d = HealthcareDetector()
    matches = [m for m in d.detect("NAM TREM12345678") if m.data_type == "health_identifier"]
    assert matches and matches[0].severity is Severity.CRITICAL


def test_healthcare_conditions_and_meds():
    d = HealthcareDetector()
    types = _types(d, "patient has Type 2 diabetes, prescribed insulin")
    assert "health_condition" in types
    assert "medication" in types


# -- Finance ------------------------------------------------------------
def test_finance_account_and_internal_note():
    d = FinanceDetector()
    types = _types(d, "account number 99887766. Internal risk note: prior default.")
    assert "account_number" in types
    assert "internal_note" in types


def test_finance_credit_score_from_flattened_key():
    d = FinanceDetector()
    # Mirrors what content_to_text produces for {"credit_score": 712}.
    assert "credit_score" in _types(d, "credit score: 712")


# -- HR -----------------------------------------------------------------
def test_hr_salary_and_disciplinary():
    d = HRDetector()
    types = _types(d, "salary: 95000; disciplinary action: final warning for misconduct")
    assert "salary" in types
    assert "disciplinary_action" in types


# -- Custom -------------------------------------------------------------
def test_custom_detector_from_config():
    d = CustomDetector.from_config([
        {"name": "project_code", "pattern": r"PROJECT-[A-Z]{3}-[0-9]{4}",
         "severity": "high", "data_type": "internal_project"},
    ])
    matches = d.detect("see PROJECT-ABC-1234 for details")
    assert len(matches) == 1
    assert matches[0].data_type == "internal_project"
    assert matches[0].severity is Severity.HIGH
    assert matches[0].detector == "custom:project_code"


def test_custom_rule_invalid_regex_raises():
    import pytest
    with pytest.raises(ValueError):
        CustomDetector([CustomRule(name="bad", pattern="(")])


# -- Registry -----------------------------------------------------------
def test_build_detectors_respects_toggles():
    detectors = build_detectors({"pii": True, "secrets": False, "healthcare": False,
                                 "finance": False, "hr": False}, None)
    names = {d.name for d in detectors}
    assert names == {"pii_detector"}


def test_build_detectors_none_enables_all_builtins():
    detectors = build_detectors(None, None)
    assert len(detectors) == 6


# -- Redaction ----------------------------------------------------------
def test_redact_keeps_edges():
    assert redact("TREM12345678") == "TR********78"


def test_redact_short_value_fully_masked():
    assert redact("abcd") == "****"
    assert redact("ab") == "**"


# -- Secrets: model-provider & cloud keys (agent-runtime leaks) ----------
def test_secrets_detects_openai_and_anthropic_keys():
    d = SecretsDetector()
    assert "llm_api_key" in _types(d, "OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno")
    assert "llm_api_key" in _types(d, "key sk-ant-api03-AbCdEf1234567890ghijklmnop")


def test_secrets_llm_key_is_distinct_from_stripe():
    d = SecretsDetector()
    # Stripe uses an underscore form and must not be relabeled as an LLM key.
    types = _types(d, "sk_live_abcdef0123456789abcd")
    assert "stripe_key" in types
    assert "llm_api_key" not in types


def test_secrets_detects_google_api_key():
    d = SecretsDetector()
    # AIza + exactly 35 url-safe chars (real Google key length).
    key = "AIza" + "Syd0123456789abcdefghijklmnopqrstuv"
    assert len(key) == 39
    assert "google_api_key" in _types(d, f"maps key {key} here")


def test_secrets_bearer_token_and_no_jwt_double_count():
    d = SecretsDetector()
    # Opaque bearer token -> bearer_token.
    assert "bearer_token" in _types(d, "Authorization: Bearer abcdef0123456789abcdef0123456789")
    # A JWT bearer is reported once, as a jwt (not also as a bearer_token).
    jwt = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc"
    types = _types(d, jwt)
    assert "jwt" in types
    assert "bearer_token" not in types


def test_secrets_new_keys_are_critical():
    d = SecretsDetector()
    crit = {m.data_type for m in d.detect("sk-proj-abc123def456ghi789jkl012mno")
            if m.severity is Severity.CRITICAL}
    assert "llm_api_key" in crit


# -- PII: IPv6, version false positive, UK NINO --------------------------
def test_pii_detects_ipv6():
    d = PIIDetector()
    assert "ip_address" in _types(d, "session 2001:0db8:85a3:0000:0000:8a2e:0370:7334")
    assert "ip_address" in _types(d, "host fe80::1ff:fe23:4567:890a here")


def test_pii_ipv4_version_string_not_flagged():
    d = PIIDetector()
    # A software version is not a client IP leak.
    assert "ip_address" not in _types(d, "version 1.2.3.4 of the build")
    assert "ip_address" not in _types(d, "release 10.0.0.1 notes")
    # A real client IP is still caught.
    assert "ip_address" in _types(d, "client connected from 203.0.113.42")


def test_pii_ipv6_does_not_match_clock_time():
    d = PIIDetector()
    assert "ip_address" not in _types(d, "the meeting is at 12:34:56 today")


def test_pii_detects_uk_nino():
    d = PIIDetector()
    assert "national_insurance_number" in _types(d, "NINO AB123456C on file")
    # Administrative / invalid prefixes are excluded (precision).
    assert "national_insurance_number" not in _types(d, "code ZZ123456C is internal")


# -- Cross-detector precision: clean text yields nothing -----------------
def test_no_false_positives_on_realistic_clean_text():
    detectors = [PIIDetector(), SecretsDetector(), FinanceDetector(),
                 HealthcareDetector(), HRDetector()]
    clean_samples = [
        "The agent completed the task and returned a summary to the user.",
        "Build version 2.10.4 was deployed at 09:15:30 without errors.",
        "Please review the quarterly roadmap before the next sync.",
        "The function returns a list of results sorted by relevance.",
        "Order #4821 was shipped and the customer was notified by email.",
    ]
    for sample in clean_samples:
        for d in detectors:
            assert d.detect(sample) == [], f"{d.name} false-positive on: {sample!r}"
