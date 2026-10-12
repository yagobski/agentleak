# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Guards for the custom Presidio recognizers and the Presidio degradation path.

The recognizers are exercised directly (no spaCy model needed); the runner test
does not need Presidio at all.
"""

from __future__ import annotations

import pytest

from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner
from agentleak.detectors import presidio_detector

BENIGN = [
    "Public information about coastal erosion. Source comparison completed.",
    "Operation SOFTX26-0-000 completed; record contents omitted.",
    "Meeting moved to room 204 at 1530; ticket 48213 closed.",
    "Shopping spin class 2024 order shipped to the warehouse.",
    "Please transfer the information to the reviewer.",
]


def _hits(recognizer_cls: type, text: str) -> list[str]:
    rec = recognizer_cls()
    return [text[r.start:r.end] for r in rec.analyze(text, [rec.NAME])]


requires_presidio = pytest.mark.skipif(
    not presidio_detector._PRESIDIO_AVAILABLE, reason="presidio-analyzer not installed"
)


@requires_presidio
@pytest.mark.parametrize("text", BENIGN)
@pytest.mark.parametrize(
    "name", ["AgentLeakCVVRecognizer", "AgentLeakPINRecognizer", "AgentLeakBICRecognizer"]
)
def test_context_anchored_recognizers_ignore_ordinary_text(name: str, text: str) -> None:
    assert _hits(getattr(presidio_detector, name), text) == []


@requires_presidio
def test_context_anchored_recognizers_still_fire_next_to_context() -> None:
    assert _hits(presidio_detector.AgentLeakCVVRecognizer, "card CVV 123 expires") == ["123"]
    assert _hits(presidio_detector.AgentLeakPINRecognizer, "the atm pin is 4821") == ["4821"]
    assert _hits(
        presidio_detector.AgentLeakBICRecognizer, "wire it to SWIFT DEUTDEFF500 today"
    ) == ["DEUTDEFF500"]


@requires_presidio
def test_bic_is_case_sensitive() -> None:
    assert _hits(presidio_detector.AgentLeakBICRecognizer, "bank transfer deutdeff500") == []


@requires_presidio
def test_context_must_be_near_the_match() -> None:
    far = "PIN reset policy reviewed. " + "x " * 40 + "Order 4821 shipped."
    assert _hits(presidio_detector.AgentLeakPINRecognizer, far) == []


@requires_presidio
def test_custom_recognizer_names_do_not_shadow_presidio_builtins() -> None:
    from presidio_analyzer import EntityRecognizer

    def subclasses(cls: type) -> list[type]:
        out = []
        for sub in cls.__subclasses__():
            out.append(sub)
            out.extend(subclasses(sub))
        return out

    ours = {c.__name__ for c in presidio_detector._CUSTOM_RECOGNIZERS}
    theirs = {
        c.__name__
        for c in subclasses(EntityRecognizer)
        if not c.__module__.startswith("agentleak.")
    }
    assert ours.isdisjoint(theirs)


def test_unbuildable_analyzer_is_reported_as_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(score_threshold: float = 0.5) -> None:
        raise TypeError("registry exploded")

    monkeypatch.setattr(presidio_detector, "_PRESIDIO_AVAILABLE", True)
    monkeypatch.setattr(presidio_detector, "_build_analyzer", boom)
    cfg = Config.from_dict({"detection": {"mode": "standard", "presidio": {"enabled": True}}})
    runner = AgentLeakRunner(cfg)
    assert runner._pipeline._presidio is None
    assert any("registry exploded" in w for w in runner._warnings)
    assert "presidio" not in runner._pipeline.finding_tiers
