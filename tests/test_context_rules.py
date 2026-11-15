# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Context-window rules: a cue makes an ambiguous value a finding, and only a cue.

Each rule is checked both ways: the value next to its cue is reported, with the
rule's name and a confidence below a shape-validated match; the same value
without the cue, and the cue without a plausible value, are not.
"""

from __future__ import annotations

import time

import pytest

from agentleak.core.runner import analyze
from agentleak.core.trace import Trace
from agentleak.detectors import build_detectors
from agentleak.detectors.context import RULES, scan

DETECTORS = build_detectors(None, None)


def found(text: str) -> set[tuple[str, str, str]]:
    return {(r.data_type, str(r.matched_value), r.rule) for d in DETECTORS for r in d.detect(text)}


def types(text: str) -> set[str]:
    return {t for t, _v, _r in found(text)}


@pytest.mark.parametrize("text, data_type, value, rule", [
    ("Her phone number is 555-0152.", "phone_number", "555-0152", "ctx_phone_local"),
    ("You can reach her at 555-0152 after six.", "phone_number", "555-0152", "ctx_phone_local"),
    ("Vous pouvez la joindre au 555-0152.", "phone_number", "555-0152", "ctx_phone_local"),
    ("Llámale al 612 34 56 78 mañana.", "phone_number", "612 34 56 78", "ctx_phone_local"),
    ("His date of birth is 1944-08-09, per the form.", "date_of_birth", "1944-08-09", "ctx_dob"),
    ("Elle est née à Lyon le 05/11/1972.", "date_of_birth", "05/11/1972", "ctx_dob"),
    ("Nació en Sevilla el 1990-01-31.", "date_of_birth", "1990-01-31", "ctx_dob"),
    ("His checking account number is 999153498-16188301.", "account_number",
     "999153498-16188301", "ctx_account_number"),
    ("Son numéro de compte est le 12345678901.", "account_number", "12345678901",
     "ctx_account_number"),
    ("Her salary is $116000 a year.", "salary", "$116000 a year", "ctx_salary"),
    ("Il gagne 65000 EUR.", "salary", "65000 EUR", "ctx_salary_verb"),
    ("Su sueldo es de 28.500 €/año.", "salary", "28.500 €/año", "ctx_salary"),
    ("He has been dealing with chronic back pain for months.", "health_condition",
     "chronic back pain", "ctx_health_symptom"),
    ("She was diagnosed with osteoarthritis last spring.", "health_condition",
     "osteoarthritis", "ctx_health_diagnosis"),
    ("La paciente padece asma.", "health_condition", "asma", "ctx_health_symptom"),
])
def test_a_cue_makes_the_value_a_finding(text, data_type, value, rule) -> None:
    assert (data_type, value, rule) in found(text)


@pytest.mark.parametrize("text, data_type", [
    # The value alone.
    ("The record shows 555-0152 for this case.", "phone_number"),
    ("The record shows 1944-08-09 for this case.", "date_of_birth"),
    ("The record shows 999153498-16188301 for this case.", "account_number"),
    ("The record shows $116000 for this case.", "salary"),
    ("The record shows chronic back pain for this case.", "health_condition"),
    # The cue alone.
    ("Call me when you are back.", "phone_number"),
    ("She was born in a small town.", "date_of_birth"),
    ("Your account is locked.", "account_number"),
    ("The salary review is next week.", "salary"),
    ("He has been dealing with the move.", "health_condition"),
    # A cue and a value that is something else.
    ("Call me about order 220-4410 when you can.", "phone_number"),
    ("She was born in 1984.", "date_of_birth"),
    ("The account sync job 99812 failed twice.", "account_number"),
    ("La incidencia de la cuenta 7781234 se cerró ayer.", "account_number"),
    ("He earns 4000 points a year in the loyalty program.", "salary"),
    ("The salary survey had 1200 responses this year.", "salary"),
    ("The server suffers from memory pressure under load.", "health_condition"),
    ("Diagnosed with a misconfigured proxy, the job was restarted.", "health_condition"),
    # A sentence break between cue and value cuts the link.
    ("Call him. 555-0152 is the part number.", "phone_number"),
    # A timestamp is not a date of birth.
    ("2024-03-12 10:22:01 INFO birthday-reminder service restarted", "date_of_birth"),
])
def test_no_cue_or_no_value_is_nothing(text, data_type) -> None:
    assert data_type not in types(text), found(text)


def test_context_matches_are_less_confident_than_shape_matches() -> None:
    raws = [r for d in DETECTORS for r in d.detect("Her phone number is 555-0152.")]
    ctx = [r for r in raws if r.rule == "ctx_phone_local"]
    shape = [r for d in DETECTORS for r in d.detect("Call 514-555-0152.") if r.data_type == "phone_number"]
    assert ctx and shape
    assert max(r.confidence for r in ctx) < min(r.confidence for r in shape)
    assert all(rule.confidence <= 0.6 for rule in RULES)


def test_a_finding_says_which_rule_fired() -> None:
    trace = Trace.model_validate({
        "run_id": "r", "agent_name": "a",
        "events": [{"event_id": "e1", "channel": "log", "source": "a", "target": "b",
                    "content": "Her date of birth is 1985-03-12."}],
    })
    finding = next(f for f in analyze(trace).findings if f.data_type == "date_of_birth")
    assert finding.metadata["rule"] == "ctx_dob"


@pytest.mark.parametrize("text, value, rule", [
    ("Ship it to 262 Kaiser Plain, Lloydside, AL 82804 today.",
     "262 Kaiser Plain, Lloydside, AL 82804", "address_us_zip"),
    ("Forward to PSC 9148, Box 4175, APO AE 64580.", "PSC 9148, Box 4175, APO AE 64580",
     "address_us_military"),
    ("Mail: USS Carlson, FPO AP 58705", "USS Carlson, FPO AP 58705", "address_us_military"),
])
def test_us_addresses_with_a_state_and_zip_tail(text, value, rule) -> None:
    assert ("address", value, rule) in found(text)


def test_a_state_code_must_be_a_real_one() -> None:
    assert "address" not in types("Build 12 Alpha, Beta Gamma, ZZ 12345 shipped.")


def test_scan_only_returns_the_types_asked_for() -> None:
    text = "Her phone number is 555-0152 and her salary is $90,000 a year."
    assert {r.data_type for r, _v, _s in scan(text, {"salary"})} == {"salary"}


N = 50_000
ADVERSARIAL = {
    "phone_cues": "call him at 555-0152 " * (N // 21),
    "cue_only": "call reach phone born account salary " * (N // 37),
    "dob_cues": "born on 1994-10-17 " * (N // 19),
    "account_digits": "account " + "1 " * (N // 2),
    "account_dashes": "account " + "1-" * (N // 2),
    "salary_groups": "salary " + "1,000 " * (N // 6),
    "salary_dots": "salary is $" + "100." * (N // 4),
    "health_cues": "diagnosed with " * (N // 15),
    "health_words": "suffers from " + "chronic pain " * (N // 12),
    "zip_tail": "12 Abc Def, Ghi Jkl, " * (N // 21),
    "cap_words": "12 " + "Abc " * (N // 4),
    "military": "PSC 1, Box 2, " * (N // 14),
    "glue": "account " + "is the of number " * (N // 17) + "123456",
}


@pytest.mark.parametrize("name", sorted(ADVERSARIAL))
def test_context_rules_are_linear_on_adversarial_input(name) -> None:
    text = ADVERSARIAL[name]
    for detector in DETECTORS:
        start = time.perf_counter()
        detector.detect(text)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"{detector.name} took {elapsed:.2f}s on {name}"
