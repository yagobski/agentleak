# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Field names and cues in French, Spanish, German, Portuguese and Italian.

A Québec agent writes ``{"date_de_naissance": …}`` and a Madrid one
``{"salario": …}``; before these lexicons the key-name detector only read
English, so the field name gave no lift outside English.
"""

from __future__ import annotations

import pytest

from agentleak.detectors.healthcare import HealthcareDetector
from agentleak.detectors.hr import HRDetector
from agentleak.detectors.keyname import SensitiveKeyDetector


@pytest.mark.parametrize(
    "text, data_type",
    [
        ("date_de_naissance: 12/03/1985", "date_of_birth"),
        ("fecha_nacimiento: 1975-04-03", "date_of_birth"),
        ("Geburtsdatum: 03.04.1975", "date_of_birth"),
        ("data_di_nascita: 07/07/1990", "date_of_birth"),
        ('{"salaire": "52 000 €"}', "salary"),
        ('{"Gehalt": "4.100 EUR"}', "salary"),
        ("salário: 7.500 reais", "salary"),
        ("telefono: 922 123 456", "phone_number"),
        ("téléphone: 06 12 34 56 78", "phone_number"),
        ("adresse: 12 rue de la Paix", "address"),
        ("indirizzo: Via Roma 10", "address"),
        ("diagnostic: diabète de type 2", "health_condition"),
        ("médicament: lévothyroxine", "medication"),
        ("numero_securite_sociale: 1 85 05 78 006 084 91", "national_id"),
        ("codice_fiscale: RSSMRA85T10A562S", "national_id"),
        ("nom_complet: Jean Tremblay", "person_name"),
        ("current_salary: 83000", "salary"),
        ("chief_complaint: chest pain", "health_condition"),
        ("patient_diagnosis: asthma", "health_condition"),
    ],
)
def test_field_name_in_another_language(text, data_type) -> None:
    assert data_type in {m.data_type for m in SensitiveKeyDetector().detect(text)}


@pytest.mark.parametrize(
    "text",
    ["nom de fichier: rapport.pdf", "is_diagnosis_confirmed: true", "salary_band_count: 4",
     "telefono_verificado: true", "La reunión pasa a las 15:00 en la sala B"],
)
def test_no_finding_without_a_sensitive_key(text) -> None:
    found = SensitiveKeyDetector().detect(text)
    assert not [m for m in found if m.matched_value not in {"true"}], found


@pytest.mark.parametrize(
    "text",
    ["52 000 € brut annuel", "3 200 € net par mois", "45.000 euros brutos anuales",
     "$95,000 gross per year", "60.000 EUR brutto"],
)
def test_pay_figure_with_gross_or_net(text) -> None:
    assert "salary" in {m.data_type for m in HRDetector().detect(text)}


@pytest.mark.parametrize("text", ["loyer 1 200 € par mois", "Invoice total 1 420 EUR", "65000 EUR"])
def test_amount_without_gross_or_net_is_not_salary(text) -> None:
    assert "salary" not in {m.data_type for m in HRDetector().detect(text)}


@pytest.mark.parametrize("text", ["épilepsie", "sclérose en plaques", "insuffisance rénale"])
def test_french_conditions(text) -> None:
    assert "health_condition" in {m.data_type for m in HealthcareDetector().detect(f"Patient: {text}.")}
