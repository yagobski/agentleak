# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The InjecAgent data-stealing pack: provenance, ground truth and pairing.

Each scenario is a compromised run: an instruction in a tool response makes
the agent read private data with a second tool and e-mail it to the attacker.
The clean counterpart is the same run without the two attacker steps — the
agent ignored the injection — and must score no canary at all.
"""

from __future__ import annotations

import copy

from agentleak.core.canary import CanarySet
from agentleak.core.runner import AgentLeakRunner
from agentleak.scenarios.convert import detect_format, normalize_upload
from agentleak.scenarios.packs import expand_pack, list_packs, load_pack

PACK_ID = "injecagent_ds"


def test_pack_declares_its_source_and_licence() -> None:
    pack = next(p for p in list_packs() if p["id"] == PACK_ID)
    assert pack["license"] == "MIT"
    assert "uiuc-kang-lab/InjecAgent" in pack["source_url"]
    assert "Zhan" in pack["attribution"]
    assert pack["count"] == 96


def test_records_are_recognised_as_injecagent_not_agentdojo() -> None:
    record = load_pack(PACK_ID)["scenarios"][0]
    assert detect_format(record) == "injecagent"
    meta, _trace = normalize_upload(record)
    assert "injecagent" in meta["tags"] and "agentdojo" not in meta["tags"]


def test_every_canary_is_data_the_agent_read_before_sending_it() -> None:
    for record in load_pack(PACK_ID)["scenarios"]:
        read = record["exfiltration"][0]["observation"]
        body = record["exfiltration"][1]["args"]["body"]
        assert record["leaked_values"], record["id"]
        for value in record["leaked_values"]:
            assert value in read or value.replace("\\", "\\\\") in read, (record["id"], value)
            assert value in body or value.replace("\\", "\\\\") in body, (record["id"], value)


def test_no_canary_is_filler() -> None:
    for record in load_pack(PACK_ID)["scenarios"]:
        for value in record["leaked_values"]:
            assert len(value) >= 5
            assert value.lower() not in {"active", "checking", "confirmed", "delivered", "limit"}


def test_every_scenario_leaks_its_canaries_on_a_tool_call() -> None:
    runner = AgentLeakRunner()
    for meta, trace in expand_pack(PACK_ID):
        report = runner.analyze(trace, canary_set=CanarySet.from_dict(meta["canaries"])).to_dict()
        canary_channels = {f["channel"] for f in report["findings"] if f["data_type"] == "canary"}
        assert canary_channels == {"tool_call"}, (meta["name"], canary_channels)
        assert report["verdict"] != "Pass", meta["name"]


def test_clean_counterpart_scores_no_canary() -> None:
    """The same run where the agent ignored the injection."""
    runner = AgentLeakRunner()
    for record in load_pack(PACK_ID)["scenarios"]:
        clean = copy.deepcopy(record)
        clean["exfiltration"] = []
        meta, trace = normalize_upload(clean)
        report = runner.analyze(
            trace, canary_set=CanarySet.from_dict(normalize_upload(record)[0]["canaries"])
        ).to_dict()
        assert not [f for f in report["findings"] if f["data_type"] == "canary"], record["id"]


def test_covers_every_attacker_goal_and_both_settings() -> None:
    records = load_pack(PACK_ID)["scenarios"]
    assert len({r["injection_task"] for r in records}) == 32
    assert len({r["user_task"] for r in records}) == 17
    assert {r["setting"] for r in records} == {"base", "enhanced"}
