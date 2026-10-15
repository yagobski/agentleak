# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Spanish social security number (NUSS), validated by its control (issue #4).

Two digits of province, eight of number, two of control: the control is the
province and number modulo 97, so a match is checked, not guessed from the
shape. The values below are made up; only the arithmetic is real.
"""
from agentleak.core.agentrisk import DATA_TYPE_LEVELS
from agentleak.core.contextual_integrity import BUILTIN_TYPE_GROUPS
from agentleak.detectors.pii import PIIDetector, _nuss_ok

NUSS = "spanish_social_security_number"


def _values(text):
    return [m.matched_value for m in PIIDetector().detect(text) if m.data_type == NUSS]


def test_control_digits():
    assert _nuss_ok("28", "12345678", "40")      # 2812345678 % 97
    assert not _nuss_ok("28", "12345678", "41")
    # A number below ten million counts as number + province * 10^7.
    assert _nuss_ok("08", "01234567", "74")
    assert not _nuss_ok("08", "01234567", "17")  # the plain concatenation


def test_grouped_forms_match_on_their_own():
    for text in ["28/12345678/40", "28 12345678 40", "28-12345678-40",
                 "Afiliación: 08/01234567/74."]:
        assert len(_values(text)) == 1, text


def test_bare_run_needs_the_label():
    assert _values("NUSS 281234567840") == ["281234567840"]
    assert _values("Número de afiliación a la Seguridad Social: 281234567840") == ["281234567840"]
    assert _values("Pedido 281234567840 enviado.") == []


def test_wrong_control_or_mixed_separators_are_not_matched():
    assert _values("28/12345678/41") == []
    assert _values("NUSS 281234567841") == []
    assert _values("28/12345678 40") == []
    assert _values("ref 128/12345678/40") == []


def test_registered_like_the_other_government_ids():
    assert DATA_TYPE_LEVELS[NUSS] == 4
    assert NUSS in BUILTIN_TYPE_GROUPS["government_ids"]
