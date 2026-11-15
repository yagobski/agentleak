# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AI-security framework mapping: a new key, nothing else moves.

The pinned report was written from the 0.19.0 code before the mapping
existed; the report of the same bundled scenario must still match it key for
key once ``security_frameworks`` is set aside.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from agentleak import AgentLeakRunner
from agentleak.core import security_frameworks as sf
from agentleak.core.attacks import ATTACK_INDEX
from agentleak.core.compliance import FRAMEWORKS
from agentleak.core.trace import CHANNELS
from agentleak.scenarios import load_example_trace
from agentleak.web.app import create_app

PIN = Path(__file__).parent / "fixtures" / "report_pin_healthcare_patient_summary.json"


def _report() -> dict:
    return AgentLeakRunner().analyze(load_example_trace("healthcare_patient_summary")).to_dict()


def test_existing_report_output_is_unchanged() -> None:
    report = _report()
    mapping = report.pop("security_frameworks")
    assert mapping["findings"]
    report.pop("generated_at")
    report["compliance"]["integrity"].pop("digest")
    pinned = json.loads(PIN.read_text("utf-8"))
    current = json.loads(json.dumps(report, sort_keys=True, default=str))
    assert current == pinned


def test_the_fourteen_privacy_frameworks_are_untouched() -> None:
    assert len(FRAMEWORKS) == 14
    meta = TestClient(create_app()).get("/api/meta").json()
    assert meta["compliance_frameworks"] == [f.id for f in FRAMEWORKS]
    assert meta["security_frameworks"]["identifiers"] == sf.IDENTIFIERS


def test_every_finding_is_mapped_by_its_channel() -> None:
    report = _report()
    mapped = {m["finding_id"]: m for m in report["security_frameworks"]["findings"]}
    assert len(mapped) == len(report["findings"])
    for finding in report["findings"]:
        assert mapped[finding["finding_id"]]["identifiers"] == sf.for_channel(finding["channel"])


def test_every_identifier_is_well_formed_and_known() -> None:
    patterns = {
        "owasp_asi_2026": r"ASI(0[1-9]|10)",
        "mitre_atlas": r"AML\.T\d{4}(\.\d{3})?",
        "nist_ai_100_2_e2025": r"NISTAML\.\d{2,3}",
    }
    for ident, entry in sf.IDENTIFIERS.items():
        assert re.fullmatch(patterns[entry["framework"]], ident), ident
        assert entry["framework"] in sf.SOURCES
    assert {i for i in sf.IDENTIFIERS if i.startswith("ASI")} == {f"ASI{n:02d}" for n in range(1, 11)}
    used = {i for ids in (*sf.CHANNEL_MAP.values(), *sf.ATTACK_CLASS_MAP.values()) for i in ids}
    assert used <= set(sf.IDENTIFIERS)


def test_owasp_entries_carry_our_summary_not_their_title() -> None:
    """OWASP text is CC BY-SA: identifiers only, in our own words."""
    for ident, entry in sf.IDENTIFIERS.items():
        if entry["framework"] == "owasp_asi_2026":
            assert "summary" in entry and "name" not in entry, ident


def test_mapped_channels_and_classes_exist() -> None:
    assert set(sf.CHANNEL_MAP) <= set(CHANNELS)
    assert set(sf.ATTACK_CLASS_MAP) <= set(ATTACK_INDEX)
    assert "user_input" not in sf.CHANNEL_MAP and "tool_response" not in sf.CHANNEL_MAP


def test_a_clean_run_maps_nothing() -> None:
    report = AgentLeakRunner().analyze(load_example_trace("healthcare_clean_referral")).to_dict()
    assert report["security_frameworks"]["findings"] == []
    assert report["security_frameworks"]["identifiers"] == {}
    assert "not a certification" in report["security_frameworks"]["note"]
