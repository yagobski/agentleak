#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Build ``agentsocialbench_ma.json`` from AgentSocialBench's multi-agent scenarios.

AgentSocialBench (Wang and Jiang, 2026; MIT,
https://github.com/kingofspace0wzz/agentsocialbench) describes teams of agents
that each serve one person. Every scenario says which agent holds which
private facts, which facts must not cross to another agent or into a group
space (``must_not_cross``), and the abstraction that may cross instead
(``acceptable_abstractions``). The scenarios are model-generated personas;
the repository ships no recorded agent conversations.

Each pack scenario is one hand-off:

* the sender agent receives its task (``user_input``) and reads its user's
  private context (``tool_response``, a source, not a leak);
* it then sends its contribution to another agent (``inter_agent_message``)
  or posts it to a space every member agent reads (``shared_memory``). The
  leaking hand-off carries two of the source's ``must_not_cross`` statements
  verbatim; those statements are the canaries.

The clean counterpart is the same hand-off with each leaked statement replaced
by the abstraction the source gives for it. Set ``"variant": "clean"`` on a
record to get it; the tests check that it scores no canary.

The hand-off text is modelled, not recorded: AgentSocialBench publishes the
norms, not transcripts. The ground truth (which fact, from which agent, to
which recipient, under which norm) is the source's.

Selection
---------
Five of the seven categories, the ones whose leak happens between agents:

=====================  ======================  ===================  ===
category               channel                 recipient            n
=====================  ======================  ===================  ===
``cross_user``         inter_agent_message     the other user's     25
                                               agent (A2A)
``cross_domain``       inter_agent_message     the same user's      25
                                               agent in another
                                               domain
``multi_party_group``  shared_memory           the group chat       20
``hub_and_spoke``      shared_memory           the shared plan the  15
                                               coordinator posts
``affinity_modulated`` shared_memory           the group chat, with 20
                                               per-tier norms
=====================  ======================  ===================  ===

Left out: ``mediated_comm`` (the agent talks to a human, not to another
agent; PrivacyLens already covers that shape) and ``competitive`` (the leak
is self-disclosure under pressure, and 92 of its 100 participant boundaries
lack an abstraction for every item, so no clean counterpart can be built).

Within a category, scenario files are ordered by the SHA-256 of their
``scenario_id`` (a seedless shuffle that spreads the sub-types), files that
fail to parse or repeat an id are skipped, and the first scenarios that pass
the checks below are kept. A scenario is kept only if its sender has at least
two ``must_not_cross`` statements, each at least 20 characters long, absent
from everything the clean counterpart emits, and none shaped like a
credential.

Usage
-----
    python -I scripts/packs/build_agentsocialbench_pack.py PATH/TO/agentsocialbench

Reads ``prism/data/scenarios/`` from a checkout of the repository (commit
6d8497c05dbab812714b2545a563e6fe7d4160ec was used). Plain JSON, no upstream
code is run. Deterministic: the same inputs give a byte-identical pack.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

OUT = (
    Path(__file__).resolve().parents[2]
    / "src" / "agentleak" / "scenarios" / "packs" / "agentsocialbench_ma.json"
)
COMMIT = "6d8497c05dbab812714b2545a563e6fe7d4160ec"
LEAKS_PER_SCENARIO = 2
MIN_FACT_LEN = 20
PER_CATEGORY = {
    "cross_user": 25,
    "cross_domain": 25,
    "multi_party_group": 20,
    "hub_and_spoke": 15,
    "affinity_modulated": 20,
}
CHANNEL = {
    "cross_user": "inter_agent_message",
    "cross_domain": "inter_agent_message",
    "multi_party_group": "shared_memory",
    "hub_and_spoke": "shared_memory",
    "affinity_modulated": "shared_memory",
}
# Closest first: a fact forbidden at a tier is forbidden at every tier after it.
AFFINITY_ORDER = ("close", "friend", "acquaintance", "stranger")
# Provider key prefixes. A statement shaped like a live credential never ships.
_CREDENTIAL = re.compile(
    r"(sk_live_|sk-[A-Za-z0-9]{20}|ghp_[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|xox[abp]-|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) and data.get("scenario_id") else None


def _fact(item: str) -> str:
    """The statement as it crosses: ``That X has Y.`` becomes ``X has Y``."""
    text = " ".join(str(item).split()).rstrip(".")
    return text[5:] if text.startswith("That ") else text


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "agent"


def _pairs(items: list[str], abstractions: dict[str, str]) -> list[tuple[str, str]]:
    """``(fact, abstraction)`` for each item, pairing by key when the source
    keys its abstractions by the item and in order when it does not."""
    keyed = [(i, abstractions[i]) for i in items if i in abstractions]
    if keyed:
        return keyed
    return list(zip(items, list(abstractions.values()), strict=False))


def _choose(
    pairs: list[tuple[str, str]], clean_text: str,
) -> list[tuple[str, str]] | None:
    chosen: list[tuple[str, str]] = []
    for item, abstraction in pairs:
        fact = _fact(item)
        if len(fact) < MIN_FACT_LEN or _CREDENTIAL.search(fact):
            continue
        if fact in clean_text or fact in abstraction or any(fact == c for c, _ in chosen):
            continue
        chosen.append((fact, " ".join(abstraction.split())))
        if len(chosen) == LEAKS_PER_SCENARIO:
            return chosen
    return None


def _boundary_for(scenario: dict[str, Any], user: str) -> dict[str, Any]:
    """cross_user keys each user's boundary by a lower-case first name."""
    boundary = scenario.get("privacy_boundary") or {}
    first = user.split()[0].lower()
    for key, value in boundary.items():
        if isinstance(value, dict) and key.lower() in (first, _slug(user)):
            return value
    return {}


def _two_agent(scenario: dict[str, Any], category: str) -> dict[str, Any] | None:
    agents = scenario.get("agents") or []
    if len(agents) < 2:
        return None
    sender, recipient = agents[0], agents[1]
    if category == "cross_user":
        boundary = _boundary_for(scenario, str(sender.get("user") or ""))
        subject = str(sender.get("user") or "")
        recipient_user = str(recipient.get("user") or "")
    else:
        boundary = scenario.get("privacy_boundary") or {}
        profiles = scenario.get("user_profiles") or [{}]
        subject = str(profiles[0].get("name") or "the user")
        recipient_user = subject
    items = [str(i) for i in boundary.get("must_not_cross") or []]
    shared = [" ".join(str(s).split()) for s in sender.get("should_share") or []]
    pairs = _pairs(items, dict(boundary.get("acceptable_abstractions") or {}))
    chosen = _choose(pairs, " ".join([scenario.get("task", ""), *shared]))
    if chosen is None:
        return None
    return {
        "sender": {"agent": sender["role"], "user": subject, "domain": sender.get("domain", "")},
        "recipient": {
            "agent": recipient["role"], "user": recipient_user,
            "domain": recipient.get("domain", ""),
        },
        "data_subject": subject,
        "private_context": [" ".join(str(k).split()) for k in sender.get("knows") or []],
        "shared_content": shared,
        "chosen": chosen,
    }


def _least_close(scenario: dict[str, Any], sender_key: str, members: list[str]) -> list[str]:
    """The sender's affinity to each other member, closest first."""
    tiers: list[str] = []
    for edge in (scenario.get("social_graph") or {}).get("edges") or []:
        if str(edge.get("from", "")).lower() == sender_key and str(edge.get("to", "")).lower() in members:
            tier = str(edge.get("affinity") or "")
            if tier in AFFINITY_ORDER:
                tiers.append(tier)
    return sorted(set(tiers), key=AFFINITY_ORDER.index)


def _group(scenario: dict[str, Any], category: str) -> dict[str, Any] | None:
    participants = scenario.get("participants") or []
    if category == "hub_and_spoke":
        participants = [p for p in participants if p.get("task_role") == "coordinator"]
    others_all = scenario.get("participants") or []
    for sender in participants:
        boundary = sender.get("privacy_boundary") or {}
        raw = boundary.get("must_not_cross")
        abstractions = dict(boundary.get("acceptable_abstractions") or {})
        affinity: dict[str, Any] = {}
        sender_key = str(sender.get("agent_name", "")).removesuffix("_agent").lower()
        members = [
            str(p.get("agent_name", "")).removesuffix("_agent").lower()
            for p in others_all if p is not sender
        ]
        if isinstance(raw, dict):
            tiers = _least_close(scenario, sender_key, members)
            if not tiers:
                continue
            closest, least = tiers[0], tiers[-1]
            forbidden = [str(i) for i in raw.get(least) or []]
            allowed_close = set(raw.get(closest) or [])
            # The contextual-integrity case: a fact the norm lets the sender
            # tell a close contact privately, but not post to this group.
            items = [i for i in forbidden if i not in allowed_close] + [
                i for i in forbidden if i in allowed_close
            ]
            affinity = {"least_close_tier_present": least, "closest_tier_present": closest}
        else:
            items = [str(i) for i in raw or []]
        chosen = _choose(_pairs(items, abstractions), scenario.get("task", ""))
        if chosen is None:
            continue
        profile = sender.get("user_profile") or {}
        context = [" ".join(str(sender.get("system_prompt_context", "")).split())]
        if category == "hub_and_spoke":
            subject = "the team members who confided in the coordinator"
        else:
            subject = str(sender.get("user_name") or profile.get("name") or "")
        return {
            "sender": {"agent": sender["agent_name"], "user": str(sender.get("user_name") or "")},
            "recipient": {
                "agent": "group_chat" if category != "hub_and_spoke" else "team_plan",
                "audience": [str(p.get("agent_name")) for p in others_all if p is not sender],
            },
            "data_subject": subject,
            "private_context": context,
            "shared_content": [],
            "chosen": chosen,
            "affinity": affinity,
        }
    return None


def _ordered(directory: Path) -> list[dict[str, Any]]:
    seen: set[str] = set()
    scenarios = []
    for path in sorted(directory.glob("*.json")):
        data = _load(path)
        if data is None or data["scenario_id"] in seen:
            continue
        seen.add(data["scenario_id"])
        scenarios.append(data)
    return sorted(scenarios, key=lambda d: hashlib.sha256(d["scenario_id"].encode()).hexdigest())


def build(repo: Path) -> dict[str, Any]:
    root = repo / "prism" / "data" / "scenarios"
    records: list[dict[str, Any]] = []
    considered: dict[str, int] = {}
    for category, quota in PER_CATEGORY.items():
        kept = 0
        considered[category] = 0
        for scenario in _ordered(root / category):
            if kept == quota:
                break
            considered[category] += 1
            shape = (
                _two_agent(scenario, category)
                if category in ("cross_user", "cross_domain")
                else _group(scenario, category)
            )
            if shape is None:
                continue
            chosen = shape.pop("chosen")
            # The agent holds every fact it later passes on: the source lists
            # them as what this agent knows about its user.
            context = shape["private_context"]
            context += [f for f, _ in chosen if not any(f in line for line in context)]
            criteria = scenario.get("success_criteria") or {}
            records.append({
                "id": f"asb__{scenario['scenario_id']}",
                "benchmark": "agentsocialbench",
                "category": category,
                "sub_type": str((scenario.get("metadata") or {}).get("sub_type") or ""),
                "scenario_id": scenario["scenario_id"],
                "channel": CHANNEL[category],
                "task": " ".join(str(scenario.get("task", "")).split()),
                **shape,
                "transmission_principle": " ".join(
                    str(criteria.get("privacy_preserved") or "").split()
                ),
                "leaked_values": [fact for fact, _ in chosen],
                "abstractions": [abstraction for _, abstraction in chosen],
            })
            kept += 1
    return {
        "id": "agentsocialbench_ma",
        "name": "AgentSocialBench (private facts crossing between agents)",
        "description": (
            "Teams of agents that each serve one person hand work to each other. Each "
            "scenario is one hand-off in which the sender passes on two facts the source "
            "says must not cross: agent to agent (another user's agent, or the same user's "
            "agent in another domain) on inter_agent_message, or into a group chat or a "
            "shared plan every member agent reads, on shared_memory. The facts ship as "
            "canaries; the clean counterpart uses the source's acceptable abstraction "
            "instead. A regex tier sees few of these: they are facts, not identifiers."
        ),
        "source": "kingofspace0wzz/agentsocialbench (AgentSocialBench, 2026, MIT)",
        "source_url": "https://github.com/kingofspace0wzz/agentsocialbench",
        "license": "MIT",
        "attribution": (
            "Derived from AgentSocialBench by Prince Zizhuang Wang and Shuli Jiang "
            "(arXiv:2604.01487), MIT-licensed, Copyright (c) 2026 Prince Zizhuang Wang, "
            f"Shuli Jiang, commit {COMMIT}. Tasks, private context, must-not-cross statements, "
            "abstractions and norms are the authors' (model-generated personas); "
            f"{len(records)} scenarios from five categories were selected and reshaped into "
            "AgentLeak traces; the hand-off text that carries the statements is modelled by "
            "AgentLeak, not recorded."
        ),
        "format": "agentsocialbench",
        "upstream_commit": COMMIT,
        "selection": {
            "per_category": PER_CATEGORY,
            "considered": considered,
            "leaks_per_scenario": LEAKS_PER_SCENARIO,
            "order": "sha256(scenario_id)",
        },
        "scenarios": records,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    pack = build(Path(sys.argv[1]))
    OUT.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(pack['scenarios'])} scenarios, considered {pack['selection']['considered']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
