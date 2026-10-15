# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Spanish DNI/NIE: matched by shape, kept only when the control letter checks.

Issue #4: the bundled detectors missed the Spanish national ID. The last letter
of a DNI/NIE is the number modulo 23 in a fixed table, so the detector can
validate a match instead of guessing from the shape. These tests go in both
directions: valid numbers are found in every common spelling, and the same
shapes with a wrong letter, glued to a longer token, or in lowercase are not.
"""

from __future__ import annotations

import pytest

from agentleak.core.agentrisk import DATA_TYPE_LEVELS
from agentleak.core.contextual_integrity import BUILTIN_TYPE_GROUPS
from agentleak.detectors.pii import PIIDetector


def _ids(text: str) -> list[str]:
    return [m.matched_value for m in PIIDetector().detect(text)
            if m.data_type == "spanish_national_id"]


@pytest.mark.parametrize("text, value", [
    ("DNI 12345678Z on file", "12345678Z"),
    ("dni: 12345678-Z", "12345678-Z"),
    ("con DNI 12345678 Z y domicilio", "12345678 Z"),
    ("DNI 12.345.678-Z", "12.345.678-Z"),
    ("(00000000T)", "00000000T"),
    ("NIE X1234567L", "X1234567L"),
    ("NIE Y-1234567-X", "Y-1234567-X"),
    ("nie z1234567r is not, but Z1234567R is", "Z1234567R"),
])
def test_valid_dni_nie_found(text: str, value: str) -> None:
    assert _ids(text) == [value]


@pytest.mark.parametrize("text", [
    "DNI 12345678A",          # wrong control letter
    "NIE X1234567A",          # wrong control letter
    "dni 12345678z",          # lowercase letter: precision over recall
    "order ORD-12345678Z",    # part of a longer token
    "ref 123456789Z",         # nine digits
    "batch 12345678ZA",       # letter followed by more letters
    "build 1.12345678Z",      # glued to a version-like prefix
    "NIE W1234567L",          # not an NIE prefix
])
def test_invalid_or_embedded_not_found(text: str) -> None:
    assert _ids(text) == []


def test_ordinary_numbers_are_not_ids() -> None:
    text = "Invoice 20261014 paid on 2026-10-14, 12345678 units shipped to Madrid."
    assert _ids(text) == []


def test_registered_like_the_other_government_ids() -> None:
    assert "spanish_national_id" in BUILTIN_TYPE_GROUPS["government_ids"]
    assert DATA_TYPE_LEVELS["spanish_national_id"] == DATA_TYPE_LEVELS["national_insurance_number"]
