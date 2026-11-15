# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The French detection-quality figures have to stay true.

Same contract as ``test_detection_quality_es.py``: floors under the measured
values, not equality. When a change moves the numbers for a good reason,
regenerate in the same commit:

    python scripts/detection_quality_fr.py --json docs/detection-quality-fr.json

The labelled set is checked on its own too: its identifiers must carry valid
check digits, or a miss would be the fixture's fault and not the detector's.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from agentleak.detectors import checksums

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "detection_quality_fr.py"
LABELLED_SET = REPO_ROOT / "scripts" / "detection_quality_fr.json"


def _load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("detection_quality_fr", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["detection_quality_fr"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report():
    return _load_module().evaluate()


def _values(data_type):
    data = json.loads(LABELLED_SET.read_text(encoding="utf-8"))
    return [item["value"] for item in data["labelled"] if item["data_type"] == data_type]


def test_the_labelled_set_is_not_empty(report) -> None:
    assert report["conditions"]["structured"]["denominator"] >= 100
    assert report["false_positives"]["control_texts"] >= 20


def test_fixture_identifiers_carry_valid_check_digits() -> None:
    for value in _values("national_id"):
        assert checksums.fr_nir(value), value
    for value in _values("sin"):
        assert checksums.ca_sin(value), value
    for value in _values("iban"):
        assert checksums.iban(value), value
    for value in _values("credit_card"):
        assert checksums.payment_card(value), value


def test_recall_holds(report) -> None:
    """Structured 1.000 and prose 0.860 when published."""
    assert report["conditions"]["structured"]["recall"] >= 0.9
    assert report["conditions"]["prose"]["recall"] >= 0.7
    assert report["conditions"]["prose"]["recall"] < report["conditions"]["structured"]["recall"]


def test_no_false_positives_on_benign_french_text(report) -> None:
    fp = report["false_positives"]
    assert fp["detections"] == 0, [(d["data_type"], d["value"]) for d in fp["detail"]]


def test_self_validating_types_are_found_in_both_conditions(report) -> None:
    for condition in ("structured", "prose"):
        rows = {r["data_type"]: r for r in report["conditions"][condition]["by_data_type"]}
        for data_type in ("email", "credit_card", "iban", "national_id", "sin"):
            assert rows[data_type]["recall"] == 1.0, (condition, data_type)


def test_every_figure_carries_its_provenance(report) -> None:
    assert report["software_version"]
    assert report["language"] == "fr"
    assert "deterministic" in report["detector_tier"]
    assert report["source"]
    for condition in report["conditions"].values():
        assert condition["numerator"] <= condition["denominator"]
