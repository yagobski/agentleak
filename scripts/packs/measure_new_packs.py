#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""What the pattern tier does on the AgentSocialBench and MCPTox packs.

``agentleak bench run`` measures recall and specificity against *derived*
counterparts (the leaking hand-off removed). These packs also ship *their own*
clean counterparts (the abstraction instead of the fact; the call of a model
that ignored the poisoned description), which keep the hand-off and are the
harder negative. This script measures both packs against those, with and
without the ground truth, and the MCPTox flow preset. No model is called.

Usage: python scripts/packs/measure_new_packs.py
"""

from __future__ import annotations

from typing import Any

from agentleak.core.canary import CanarySet
from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner
from agentleak.research.stats import wilson_interval
from agentleak.scenarios.convert import normalize_upload
from agentleak.scenarios.packs import load_pack

PACKS = ("agentsocialbench_ma", "mcptox_recipient_hijack")


def _flagged(report: dict[str, Any], canaries_only: bool = False) -> bool:
    findings = report["findings"]
    if canaries_only:
        findings = [f for f in findings if f["data_type"] == "canary"]
    return bool(findings)


def _row(label: str, k: int, n: int) -> str:
    p = wilson_interval(k, n)
    return f"| {label} | {k / n:.3f} | {k}/{n} | {p.ci_low:.3f}-{p.ci_high:.3f} |"


def measure(pack_id: str) -> list[str]:
    pack = load_pack(pack_id)
    plain = AgentLeakRunner()
    preset = pack.get("flow_preset")
    gated = AgentLeakRunner(Config.from_dict({"project": {"name": "m"}, **preset})) if preset else None
    n = len(pack["scenarios"])
    tally = dict.fromkeys(
        ("recall_bare", "recall_gt", "spec_bare", "spec_gt", "flow_leak", "flow_clean"), 0
    )
    for record in pack["scenarios"]:
        meta, leak = normalize_upload(record)
        _, clean = normalize_upload(dict(record, variant="clean"))
        canaries = CanarySet.from_dict(meta["canaries"])
        tally["recall_bare"] += _flagged(plain.analyze(leak).to_dict())
        tally["recall_gt"] += _flagged(plain.analyze(leak, canary_set=canaries).to_dict(), True)
        tally["spec_bare"] += not _flagged(plain.analyze(clean).to_dict())
        tally["spec_gt"] += not _flagged(plain.analyze(clean, canary_set=canaries).to_dict(), True)
        if gated is not None:
            tally["flow_leak"] += not gated.analyze(leak, canary_set=canaries).to_dict()["privacy_policy"]["passed"]
            tally["flow_clean"] += gated.analyze(clean, canary_set=canaries).to_dict()["privacy_policy"]["passed"]
    rows = [
        f"\n{pack_id} ({n} leaking scenarios, {n} shipped clean counterparts)\n",
        "| Metric | Estimate | n/N | 95% Wilson |",
        "|---|---:|---:|---|",
        _row("Recall, pattern tier, no ground truth", tally["recall_bare"], n),
        _row("Recall, with canaries (ground truth)", tally["recall_gt"], n),
        _row("Specificity on shipped counterparts, pattern tier", tally["spec_bare"], n),
        _row("Specificity on shipped counterparts, canaries", tally["spec_gt"], n),
    ]
    if gated is not None:
        rows += [
            _row("Flow preset flags the leak", tally["flow_leak"], n),
            _row("Flow preset passes the counterpart", tally["flow_clean"], n),
        ]
    return rows


def main() -> None:
    for pack_id in PACKS:
        print("\n".join(measure(pack_id)))


if __name__ == "__main__":
    main()
