# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The SIN label vs the Spanish word "sin" ("without"), issue #4.

An unseparated nine-digit run is a SIN only next to the word that names it.
In Spanish "sin" is an everyday preposition, so "sin 123456789 dudas" is not
a label. The short labels count in capitals, or with a separator after them.
"""
from agentleak.detectors.pii import PIIDetector


def _sin_values(text):
    return [m.matched_value for m in PIIDetector().detect(text) if m.data_type == "sin"]


def test_spanish_preposition_is_not_a_label():
    assert _sin_values("Lo mandamos sin 123456789 dudas.") == []
    assert _sin_values("Sin 123456789 problemas, como dijo el jefe.") == []
    assert _sin_values("pedido nas 123456789") == []


def test_capital_labels_still_match():
    assert _sin_values("SIN 123456789") == ["123456789"]
    assert _sin_values("NAS 046454286") == ["046454286"]
    assert _sin_values("my SIN: 046454286") == ["046454286"]


def test_lowercase_label_with_separator_still_matches():
    assert _sin_values("sin: 123456789") == ["123456789"]
    assert _sin_values("sin=123456789") == ["123456789"]
    assert _sin_values("nas #123456789") == ["123456789"]


def test_long_label_matches_in_any_case():
    assert _sin_values("social insurance number 123456789") == ["123456789"]
    assert _sin_values("Social Insurance Number: 046454286") == ["046454286"]
