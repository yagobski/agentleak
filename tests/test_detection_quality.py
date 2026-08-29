# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The published detection-quality figures have to stay true.

``docs/detection-quality.md`` is the first precision/recall this project has
ever put in public, which makes it the easiest number to let rot. A detector
change that quietly drops structured recall, or starts firing on ordinary
operational text, has to fail here rather than be discovered by a reader
running the script themselves.

Thresholds are floors well under the measured values, not equality assertions:
the point is to catch a collapse, not to freeze every decimal and force a
churn commit on each detector improvement. When a change moves the numbers for
a good reason, regenerate the page in the same commit:

    python scripts/detection_quality.py --json docs/detection-quality.json
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "detection_quality.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("detection_quality", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["detection_quality"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report():
    return _load_module().evaluate()


def test_the_labelled_set_is_not_empty(report) -> None:
    """A harness that silently measures nothing reports a perfect score."""
    assert report["conditions"]["structured"]["denominator"] > 300


def test_structured_recall_holds(report) -> None:
    """0.926 when published. The internal channels the product is about carry
    values with their field names, so this is the number that supports the
    claim.
    """
    structured = report["conditions"]["structured"]
    assert structured["recall"] >= 0.85, (
        f"structured recall fell to {structured['recall']} "
        f"({structured['numerator']}/{structured['denominator']})"
    )


def test_prose_recall_is_reported_not_hidden(report) -> None:
    """0.275 when published, and it is meant to be low: without a field name
    the deterministic tier finds emails and SSNs and little else. The test
    guards the honesty of the split, not the size of the gap — if prose recall
    ever reaches structured recall, the two conditions have stopped being
    measured separately and the page is lying.
    """
    prose = report["conditions"]["prose"]
    structured = report["conditions"]["structured"]
    assert prose["denominator"] == structured["denominator"]
    assert prose["recall"] < structured["recall"]


def test_no_false_positives_on_benign_text(report) -> None:
    """Zero when published. A guardrail that fires on ordinary operational
    sentences gets switched off, and then it protects nothing.
    """
    false_positives = report["false_positives"]
    assert false_positives["detections"] == 0, (
        f"detector(s) fired on benign control text: "
        f"{[(d['data_type'], d['value']) for d in false_positives['detail']]}"
    )


def test_email_and_ssn_are_found_in_both_conditions(report) -> None:
    """The two types that carry their own shape must not depend on context."""
    for condition in ("structured", "prose"):
        rows = {
            row["data_type"]: row
            for row in report["conditions"][condition]["by_data_type"]
        }
        for data_type in ("email", "ssn"):
            assert rows[data_type]["recall"] == 1.0, (
                f"{data_type} recall dropped in the {condition} condition"
            )


def test_every_figure_carries_its_provenance(report) -> None:
    """A published number without its denominator, version and tier is a number
    nobody can check — the failure mode this whole page exists to close.
    """
    assert report["software_version"]
    assert "deterministic" in report["detector_tier"]
    assert report["tiers_not_run"]
    assert report["source"]
    for condition in report["conditions"].values():
        assert condition["numerator"] <= condition["denominator"]
        low, high = condition["ci95"]
        assert low <= condition["recall"] <= high


def test_fixture_anomalies_are_disclosed(report) -> None:
    """Excluding malformed fixtures is legitimate; excluding them quietly is
    not. The count and examples must be in the report.
    """
    integrity = report["fixture_integrity"]
    assert integrity["excluded"] > 0
    assert integrity["note"]
    assert integrity["examples"]
