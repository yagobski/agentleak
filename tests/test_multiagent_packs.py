# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The AgentSocialBench and MCPTox packs: provenance, ground truth, pairing.

AgentSocialBench: one agent hands two must-not-cross facts to another agent
(``inter_agent_message``) or into a space every member agent reads
(``shared_memory``). The clean counterpart carries the source's abstractions.

MCPTox: a poisoned tool description makes a model send the user's data to a
recipient the description named. The clean counterpart is a model that
ignored it; it may carry the same data to the recipient the user named, so it
is judged by the bundled flow preset, not by presence.
"""

from __future__ import annotations

import re
from importlib import resources

import pytest

from agentleak.core.canary import CanarySet
from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner
from agentleak.scenarios.convert import detect_format, normalize_upload
from agentleak.scenarios.packs import expand_pack, list_packs, load_pack

ASB = "agentsocialbench_ma"
MCP = "mcptox_recipient_hijack"
_CREDENTIAL = re.compile(
    r"sk_live_[A-Za-z0-9]{24}|ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


def _canary_channels(meta: dict, trace) -> tuple[set[str], dict]:
    report = AgentLeakRunner().analyze(
        trace, canary_set=CanarySet.from_dict(meta["canaries"])
    ).to_dict()
    return {f["channel"] for f in report["findings"] if f["data_type"] == "canary"}, report


def _clean(record: dict) -> tuple[dict, object]:
    return normalize_upload(dict(record, variant="clean"))


# ----------------------------------------------------------------------
# Provenance
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("pack_id", "licence", "url", "credit", "count"),
    [
        (ASB, "MIT", "kingofspace0wzz/agentsocialbench", "Shuli Jiang", 105),
        (MCP, "CC-BY-4.0", "zhiqiangwang4/MCPTox-Benchmark", "MCPTox contributors", 24),
    ],
)
def test_pack_declares_source_licence_and_count(pack_id, licence, url, credit, count) -> None:
    pack = next(p for p in list_packs() if p["id"] == pack_id)
    assert pack["license"] == licence
    assert url in pack["source_url"]
    assert credit in pack["attribution"]
    assert pack["count"] == count
    assert load_pack(pack_id)["upstream_commit"]


@pytest.mark.parametrize("pack_id", [ASB, MCP])
def test_no_credential_shaped_string_ships(pack_id: str) -> None:
    raw = resources.files("agentleak.scenarios.packs").joinpath(f"{pack_id}.json").read_text("utf-8")
    assert not _CREDENTIAL.search(raw)


def test_records_are_recognised() -> None:
    assert detect_format(load_pack(ASB)["scenarios"][0]) == "agentsocialbench"
    assert detect_format(load_pack(MCP)["scenarios"][0]) == "mcptox"


# ----------------------------------------------------------------------
# AgentSocialBench
# ----------------------------------------------------------------------
def test_asb_covers_both_channels_and_five_categories() -> None:
    records = load_pack(ASB)["scenarios"]
    by_channel: dict[str, int] = {}
    for r in records:
        by_channel[r["channel"]] = by_channel.get(r["channel"], 0) + 1
    assert by_channel == {"inter_agent_message": 50, "shared_memory": 55}
    assert {r["category"] for r in records} == {
        "cross_user", "cross_domain", "multi_party_group", "hub_and_spoke", "affinity_modulated",
    }


def test_asb_records_carry_sender_recipient_and_norm() -> None:
    for r in load_pack(ASB)["scenarios"]:
        assert r["sender"]["agent"] and r["recipient"]["agent"], r["id"]
        assert r["sender"]["agent"] != r["recipient"]["agent"], r["id"]
        assert r["transmission_principle"], r["id"]
        assert len(r["leaked_values"]) == len(r["abstractions"]) == 2, r["id"]


def test_asb_every_canary_is_context_the_sender_held() -> None:
    for r in load_pack(ASB)["scenarios"]:
        held = "\n".join(r["private_context"])
        for value in r["leaked_values"]:
            assert value in held, (r["id"], value)


def test_asb_every_canary_leaks_on_the_claimed_channel_only() -> None:
    for meta, trace in expand_pack(ASB):
        record = next(r for r in load_pack(ASB)["scenarios"] if r["id"] == meta["name"])
        channels, report = _canary_channels(meta, trace)
        assert channels == {record["channel"]}, (meta["name"], channels)
        assert report["verdict"] != "Pass", meta["name"]


def test_asb_each_canary_is_found_on_the_hand_off() -> None:
    runner = AgentLeakRunner()
    for record in load_pack(ASB)["scenarios"]:
        meta, trace = normalize_upload(record)
        result = runner.analyze(trace, canary_set=CanarySet.from_dict(meta["canaries"]))
        found = {
            f.matched_value for f in result.findings
            if f.data_type == "canary" and f.channel == record["channel"]
        }
        assert found == set(record["leaked_values"]), record["id"]


def test_asb_clean_counterpart_scores_no_canary() -> None:
    for record in load_pack(ASB)["scenarios"]:
        meta, trace = _clean(record)
        channels, _ = _canary_channels(meta, trace)
        assert not channels, record["id"]


def test_asb_clean_counterpart_differs_only_in_the_carried_statements() -> None:
    record = load_pack(ASB)["scenarios"][0]
    _, leak = normalize_upload(record)
    _, clean = _clean(record)
    assert [e.channel_value for e in leak.events] == [e.channel_value for e in clean.events]
    for value in record["abstractions"]:
        assert value in clean.events[2].searchable_text


# ----------------------------------------------------------------------
# MCPTox
# ----------------------------------------------------------------------
def test_mcptox_calls_are_recorded_model_output() -> None:
    for r in load_pack(MCP)["scenarios"]:
        assert r["hijacked_call"]["model"] and r["clean_call"]["model"], r["id"]
        assert r["hijacked_call"]["tool"] in r["legitimate_tools"], r["id"]
        assert r["hijacked_call"]["tool"] != r["poisoned_tool"]["name"], r["id"]
        assert r["attacker_recipient"] in r["poisoned_tool"]["description"], r["id"]
        assert r["attacker_recipient"] not in r["user_prompt"], r["id"]


def test_mcptox_every_canary_is_user_data_on_the_hijacked_call() -> None:
    for meta, trace in expand_pack(MCP):
        record = next(r for r in load_pack(MCP)["scenarios"] if r["id"] == meta["name"])
        for value in record["leaked_values"]:
            assert value in record["user_prompt"], (record["id"], value)
        channels, _ = _canary_channels(meta, trace)
        assert channels == {"tool_call"}, record["id"]
        call = [e for e in trace.events if e.channel_value == "tool_call"]
        assert len(call) == 1 and call[0].target == record["attacker_recipient"]


def test_mcptox_clean_counterpart_never_reaches_the_attacker() -> None:
    for record in load_pack(MCP)["scenarios"]:
        _, trace = _clean(record)
        for event in trace.events:
            if event.channel_value == "tool_call":
                assert record["attacker_recipient"] not in event.searchable_text, record["id"]
                assert event.target != record["attacker_recipient"], record["id"]


def test_mcptox_presence_alone_cannot_separate_some_pairs() -> None:
    """The point of the pack: the user asked for the same data to be sent."""
    same_data = 0
    for record in load_pack(MCP)["scenarios"]:
        meta, trace = _clean(record)
        channels, _ = _canary_channels(meta, trace)
        same_data += bool(channels)
    assert same_data == 7


def test_mcptox_flow_preset_flags_every_leak_and_no_clean_counterpart() -> None:
    pack = load_pack(MCP)
    runner = AgentLeakRunner(Config.from_dict({"project": {"name": "preset"}, **pack["flow_preset"]}))
    for record in pack["scenarios"]:
        for variant, expect_pass in ((None, False), ("clean", True)):
            meta, trace = normalize_upload(dict(record, variant=variant) if variant else record)
            policy = runner.analyze(
                trace, canary_set=CanarySet.from_dict(meta["canaries"])
            ).to_dict()["privacy_policy"]
            assert policy["passed"] is expect_pass, (record["id"], variant)
