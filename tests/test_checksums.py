# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Check-digit validators and the identifier rules built on them.

Each validator is pinned with values that pass by construction and with the
same value after a one-digit change, which every check digit here must catch.
The algorithms were also compared against python-stdnum (LGPL, used only as an
outside oracle, never imported by the package) on 200,000 random inputs per
format; see DETECTION-REPORT.md for the disagreements that are deliberate.
"""

from __future__ import annotations

import pytest

from agentleak.detectors import checksums as cs
from agentleak.detectors.national_ids import RULES, scan
from agentleak.detectors.pii import PIIDetector

VALID = [
    (cs.it_codice_fiscale, "RSSMRA85T10A562S"),
    (cs.uk_nhs, "943 476 5919"),
    (cs.nl_bsn, "111222333"),
    (cs.pl_pesel, "44051401359"),
    (cs.br_cpf, "529.982.247-25"),
    (cs.br_cnpj, "11.222.333/0001-81"),
    (cs.au_tfn, "123 456 782"),
    (cs.se_personnummer, "811228-9874"),
    (cs.de_steuer_id, "86095742719"),
    (cs.ca_sin, "046 454 286"),
    (cs.fr_nir, "1 85 05 78 006 084 91"),
    (cs.be_national_number, "85.07.30-033.28"),
    (cs.in_aadhaar, "234567890124"),
    (cs.iban, "FR76 3000 6000 0112 3456 7890 189"),
    (cs.iban, "DE89370400440532013000"),
    (cs.iban, "GB82WEST12345698765432"),
    (cs.payment_card, "4111 1111 1111 1111"),
    (cs.payment_card, "378282246310005"),
    (cs.payment_card, "5555555555554444"),
]


@pytest.mark.parametrize("validator, value", VALID)
def test_valid_values_pass(validator, value) -> None:
    assert validator(value), value


@pytest.mark.parametrize("validator, value", VALID)
def test_one_changed_digit_fails(validator, value) -> None:
    # Change the last digit (or the last character) by one step.
    last = value[-1]
    changed = value[:-1] + (str((int(last) + 1) % 10) if last.isdigit() else
                            chr((ord(last) - ord("A") + 1) % 26 + ord("A")))
    assert not validator(changed), changed


def test_iban_rejects_the_shape_without_the_registry() -> None:
    assert not cs.iban("US133000000121212121212")  # the US has no IBAN
    assert not cs.iban("FR76 3000 6000 0112 3456 7890 18")  # wrong length
    assert not cs.iban("GB82 1234 1234 5698 7654 32")  # GB needs a letter bank code


def test_card_needs_a_network_as_well_as_luhn() -> None:
    assert cs.luhn("1234567812345670")
    assert not cs.payment_card("1234567812345670")  # no network starts with 1


def test_ssn_issuance_rules() -> None:
    assert cs.us_ssn("123-45-6789")
    assert cs.us_ssn("912-34-5678")  # ITIN range, kept on purpose
    for never_issued in ("000-12-3456", "666-12-3456", "123-00-4567", "123-45-0000"):
        assert not cs.us_ssn(never_issued)


def test_github_token_checksum() -> None:
    body = "a" * 30
    good = "ghp_" + body + cs.base62(__import__("zlib").crc32(body.encode()), 6)
    assert cs.crc32_token(good)
    assert not cs.crc32_token("ghp_" + "a" * 36)


@pytest.mark.parametrize(
    "text, rule",
    [
        ("NIR 1 85 05 78 006 084 91 au dossier", "fr_nir"),
        ("codice fiscale RSSMRA85T10A562S", "it_codice_fiscale"),
        ("Steuer-ID: 86095742719", "de_steuer_id"),
        ("NHS number 943 476 5919", "uk_nhs_number"),
        ("BSN 111222333", "nl_bsn"),
        ("rijksregisternummer 85.07.30-033.28", "be_national_number"),
        ("PESEL 44051401359", "pl_pesel"),
        ("personnummer 811228-9874", "se_personnummer"),
        ("CPF 529.982.247-25", "br_cpf"),
        ("CPF 52998224725", "br_cpf_labelled"),
        ("CNPJ 11.222.333/0001-81", "br_cnpj"),
        ("Aadhaar 2345 6789 0124", "in_aadhaar"),
        ("TFN 123 456 782", "au_tfn"),
        ("SSN 123456789", "us_ssn_labelled"),
    ],
)
def test_each_rule_fires_on_its_format(text, rule) -> None:
    assert rule in {r.rule for r, _value, _span in scan(text)}


@pytest.mark.parametrize(
    "text",
    [
        "Order 86095742719 shipped.",          # valid Steuer-ID digits, no label
        "Reference 111222333 attached.",       # valid BSN digits, no label
        "Row count 44051401359.",              # valid PESEL digits, no label
        "Batch 2345 6789 0124 processed.",     # valid Aadhaar digits, no label
        "NHS number 943 476 5918",             # label, wrong check digit
        "CPF 529.982.247-26",                  # shape, wrong check digit
        "RSSMRA85T10A562T is a code",          # shape, wrong control letter
    ],
)
def test_no_rule_fires_without_label_or_check_digit(text) -> None:
    assert scan(text) == []


def test_rule_ids_are_unique_and_documented() -> None:
    ids = [r.rule for r in RULES]
    assert len(ids) == len(set(ids))
    for r in RULES:
        assert r.validator.__doc__, r.rule


def test_national_id_claims_its_span_from_cards_and_phones() -> None:
    types = {m.data_type for m in PIIDetector().detect("NIR 1 85 05 78 006 084 91")}
    assert types == {"national_id"}


def test_unlabelled_space_separated_sin_needs_luhn() -> None:
    detect = PIIDetector().detect
    assert "sin" in {m.data_type for m in detect("ref 046 454 286")}
    # A Spanish landline printed 3-3-3 is not a SIN.
    assert "sin" not in {m.data_type for m in detect("llame al 922 123 456")}
    # The hyphenated SIN print format still counts, as synthetic data uses it.
    assert "sin" in {m.data_type for m in detect("sin 123-456-789")}
    assert "sin" in {m.data_type for m in detect('{"sin": "123-456-789"}')}


def test_phone_shaped_reference_is_not_a_phone() -> None:
    detect = PIIDetector().detect
    assert not [m for m in detect("Order 555-123-4567 has shipped.") if m.data_type == "phone_number"]
    assert [m for m in detect("Call 555-123-4567 tomorrow.") if m.data_type == "phone_number"]


@pytest.mark.parametrize(
    "text",
    ["Appelez le +33 6 12 34 56 78", "office +44 20 7946 0958", "tél. 06 12 34 56 78",
     "Telefon: 030 901820 77", "mobile 555-0152"],
)
def test_international_and_labelled_phones(text) -> None:
    assert "phone_number" in {m.data_type for m in PIIDetector().detect(text)}


@pytest.mark.parametrize(
    "text",
    ["Geburtsdatum: 03.04.1975", "née le 12 mars 1985", "data di nascita 7 luglio 1990",
     "data de nascimento: 22/02/2001", "born on March 3, 1975"],
)
def test_multilingual_date_of_birth(text) -> None:
    assert "date_of_birth" in {m.data_type for m in PIIDetector().detect(text)}
