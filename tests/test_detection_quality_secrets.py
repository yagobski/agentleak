# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The credential-coverage figures have to stay true.

Floors, not equality. Regenerate with
``python scripts/detection_quality_secrets.py --json docs/detection-quality-secrets.json``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "detection_quality_secrets.py"


@pytest.fixture(scope="module")
def report():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("detection_quality_secrets", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["detection_quality_secrets"] = module
    spec.loader.exec_module(module)
    return module.evaluate()


def test_every_generated_format_is_found(report) -> None:
    """159/159 when published (36/159 on 0.18.0)."""
    assert report["denominator"] >= 150
    missed = [r["format"] for r in report["by_format"] if r["hit"] < r["n"]]
    assert not missed, missed


def test_no_credential_type_on_hard_negatives(report) -> None:
    """0 of 82 when published (8 of 82 on 0.18.0)."""
    assert report["hard_negatives"]["flagged_with_a_credential_type"] == 0, report["hard_negatives"]["detail"]


def test_provenance(report) -> None:
    assert report["software_version"] and report["source"] and report["note"]
    assert report["numerator"] <= report["denominator"]
