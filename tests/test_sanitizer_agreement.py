# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""What the detectors find, the Sanitizer removes: checked on every bundled text.

The Sanitizer is built on the detector registry, so the two halves should
agree by construction. They did not, in three ways found by the self-test and
by this test: a postal-code-shaped run inside an email address won as the
inner span and left the rest of the address behind; a record number written
as one token (``MRN-12345678``) was not read at all; and a person name taken
across a possessive ("John Doe's Personal") was reported as a string that does
not occur in the text, so there was nothing to replace.

Property, over every event of every bundled scenario and every sentence of the
cued-prose fixture: for each value the detectors report (types the Sanitizer
deliberately keeps, ``DETECT_ONLY``, excluded), the sanitized text no longer
contains that value, and re-scanning it yields no finding with that value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agentleak.defenses.sanitizer import DETECT_ONLY, Sanitizer
from agentleak.detectors import build_detectors
from agentleak.scenarios import SCENARIOS, load_example_trace
from agentleak.scenarios.packs import expand_pack, list_packs

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _bundled_texts() -> list[str]:
    texts: set[str] = set()
    for sid in SCENARIOS:
        texts.update(e.searchable_text for e in load_example_trace(sid).events)
    for pack in list_packs():
        for _meta, trace in expand_pack(pack["id"]):
            texts.update(e.searchable_text for e in trace.events)
    return sorted(t for t in texts if t)


def _cued_texts() -> list[str]:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import detection_quality_cued as cued  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    fixture = json.loads(cued.CUED_SET.read_text(encoding="utf-8"))
    out: list[str] = []
    for language, (labelled, _controls) in cued.labelled_sets().items():
        templates = fixture["templates"][language]
        for _source, data_type, _field, value in labelled:
            for half in templates.get(data_type, {}).values():
                out.extend(t.replace("{value}", value) for t in half)
    return out


def _disagreements(texts: list[str]) -> list[tuple[str, str, str]]:
    detectors = build_detectors(None, None)
    sanitizer = Sanitizer()
    bad: list[tuple[str, str, str]] = []
    for text in texts:
        found = {
            (r.data_type, str(r.matched_value))
            for d in detectors for r in d.detect(text)
            if r.data_type not in DETECT_ONLY and str(r.matched_value).strip()
        }
        if not found:
            continue
        clean = sanitizer.sanitize(text)
        again = {str(r.matched_value) for d in detectors for r in d.detect(clean)}
        for data_type, value in found:
            if value in again or value in clean:
                bad.append((data_type, value, text[:120]))
    return bad


@pytest.mark.parametrize("corpus", ["bundled_scenarios", "cued_prose"])
def test_every_detected_value_is_removed(corpus: str) -> None:
    texts = _bundled_texts() if corpus == "bundled_scenarios" else _cued_texts()
    assert len(texts) > 1000
    assert _disagreements(texts) == []


@pytest.mark.parametrize("text, gone", [
    ("Contact dana.a1b2c3@example.com today", "dana"),
    ("write to j.diabetes.clinic@example.org now", "clinic@"),
    ("Record MRN-12345678 attached", "12345678"),
    ("Record MRN-12345678 attached", "MRN-"),
    ("John Doe's Personal Finance", "John Doe"),
])
def test_known_gaps_stay_closed(text: str, gone: str) -> None:
    assert gone not in Sanitizer().sanitize(text)


def test_a_record_label_keeps_the_rest_of_the_sentence() -> None:
    assert Sanitizer().sanitize("mrn: 12345678 for review") == (
        "mrn: [REDACTED_HEALTH_IDENTIFIER] for review"
    )
