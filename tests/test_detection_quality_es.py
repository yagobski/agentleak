# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The Spanish detection-quality figures have to stay true.

Same contract as ``test_detection_quality.py``: floors under the measured
values, not equality, so a detector improvement doesn't force a churn commit
but a collapse fails here. When a change moves the numbers for a good reason,
regenerate in the same commit:

    python scripts/detection_quality_es.py --json docs/detection-quality-es.json

The labelled set is checked on its own too: its identifiers must carry valid
check digits, or a miss would be the fixture's fault and not the detector's.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "detection_quality_es.py"
LABELLED_SET = REPO_ROOT / "scripts" / "detection_quality_es.json"
_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _load_module():
    spec = importlib.util.spec_from_file_location("detection_quality_es", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["detection_quality_es"] = module
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
    assert report["false_positives"]["control_texts"] >= 15


def test_fixture_identifiers_carry_valid_check_digits() -> None:
    for value in _values("spanish_national_id"):
        raw = value.replace(".", "").replace("-", "")
        number = str("XYZ".index(raw[0])) + raw[1:-1] if raw[0] in "XYZ" else raw[:-1]
        assert _DNI_LETTERS[int(number) % 23] == raw[-1], value
    for value in _values("iban"):
        raw = value.replace(" ", "")
        rearranged = raw[4:] + raw[:4]
        assert int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1, value
    for value in _values("spanish_social_security_number"):
        digits = "".join(c for c in value if c.isdigit())
        province, number, control = digits[:2], digits[2:10], int(digits[10:])
        n = int(number)
        base = n + int(province) * 10_000_000 if n < 10_000_000 else int(province + number)
        assert base % 97 == control, value


def test_overall_recall_holds(report) -> None:
    """0.582 when published, the same in both conditions."""
    for name in ("structured", "prose"):
        cond = report["conditions"][name]
        assert cond["recall"] >= 0.5, (
            f"{name} recall fell to {cond['recall']} ({cond['numerator']}/{cond['denominator']})"
        )


def test_no_false_positives_on_benign_spanish_text(report) -> None:
    false_positives = report["false_positives"]
    assert false_positives["detections"] == 0, (
        f"detector(s) fired on benign Spanish text: "
        f"{[(d['data_type'], d['value']) for d in false_positives['detail']]}"
    )


def test_self_validating_types_are_found_in_both_conditions(report) -> None:
    """Types that carry their own shape or check digits must not depend on the
    language around them."""
    for condition in ("structured", "prose"):
        rows = {
            row["data_type"]: row
            for row in report["conditions"][condition]["by_data_type"]
        }
        for data_type in ("email", "credit_card", "iban", "spanish_national_id"):
            assert rows[data_type]["recall"] == 1.0, (
                f"{data_type} recall dropped in the {condition} condition"
            )


def test_every_figure_carries_its_provenance(report) -> None:
    assert report["software_version"]
    assert report["language"] == "es"
    assert "deterministic" in report["detector_tier"]
    assert report["tiers_not_run"]
    assert report["source"]
    for condition in report["conditions"].values():
        assert condition["numerator"] <= condition["denominator"]
        low, high = condition["ci95"]
        assert low <= condition["recall"] <= high
