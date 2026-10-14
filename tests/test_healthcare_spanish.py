# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Spanish health terms (issue #4): conditions and medications.

The bundled healthcare dictionaries knew English and some French; a Spanish
trace that mentioned a diagnosis or a prescription passed clean in `fast`
mode. These tests go in both directions: the terms are found with and without
their accent, and ordinary Spanish that only looks close is not flagged.
"""

from __future__ import annotations

import pytest

from agentleak.detectors.healthcare import HealthcareDetector


def _found(text: str) -> list[tuple[str, str]]:
    return [(m.data_type, m.matched_value.lower()) for m in HealthcareDetector().detect(text)]


@pytest.mark.parametrize("text, expected", [
    ("Le diagnosticaron depresión el año pasado.", ("health_condition", "depresión")),
    ("tiene depresion desde marzo", ("health_condition", "depresion")),
    ("su madre sufrió un ictus", ("health_condition", "ictus")),
    ("La migraña no le deja dormir.", ("health_condition", "migraña")),
    ("está de baja por un trastorno de ansiedad", ("health_condition", "trastorno de ansiedad")),
    ("Le han subido la sertralina.", ("medication", "sertralina")),
    ("toma Orfidal para dormir", ("medication", "orfidal")),
    ("empieza la quimioterapia el lunes", ("medication", "quimioterapia")),
])
def test_spanish_terms_are_found(text: str, expected: tuple[str, str]) -> None:
    assert expected in _found(text)


@pytest.mark.parametrize("text", [
    "Asma confirmó la reunión del martes.",         # a given name, left out on purpose
    "La batería de litio dura dos días.",           # batteries, not a prescription
    "Tic tac, toc toc, ¿hay alguien?",
    "Se concerta una cita con el notario.",
    "El informe trimestral está listo para revisar.",
])
def test_ordinary_spanish_is_not_flagged(text: str) -> None:
    assert _found(text) == []


def test_english_terms_still_match() -> None:
    assert ("health_condition", "depression") in _found("history of depression")
    assert ("medication", "insulin") in _found("on insulin since 2019")
