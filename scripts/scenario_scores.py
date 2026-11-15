#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Score every bundled scenario and, given a second file, list what moved.

A detector change moves scores: a value found for the first time grows the
vault, or becomes a leak. The project's rule is that every bundled scenario
whose risk index or verdict moves is named, with its pack, id, before and
after. This script produces both sides with one method:

    # before: an older source tree, e.g. the last release
    mkdir -p /tmp/al-before && git archive v0.19.0 src | tar -x -C /tmp/al-before
    PYTHONPATH=/tmp/al-before/src python scripts/scenario_scores.py --installed --json before.json
    # after: this tree
    python scripts/scenario_scores.py --json after.json
    python scripts/scenario_scores.py --compare before.json after.json

Per scenario it records the verdict, the risk index, the number of leaked
findings, the leaked data types, and the compliance controls at risk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if "--installed" not in sys.argv:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _row(report: dict[str, Any]) -> dict[str, Any]:
    at_risk = sorted(
        control["id"]
        for framework in report["compliance"]["frameworks"]
        for control in framework["controls"]
        if control.get("status") == "at_risk"
    )
    return {
        "verdict": report["verdict"],
        "risk_index": report["risk_index"],
        "leaked_findings": len(report["findings"]),
        "leaked_types": sorted({f["data_type"] for f in report["findings"]}),
        "controls_at_risk": at_risk,
    }


def score_all() -> dict[str, Any]:
    import agentleak
    from agentleak.core.runner import AgentLeakRunner
    from agentleak.scenarios import SCENARIOS, load_example_trace
    from agentleak.scenarios.packs import expand_pack, list_packs

    runner = AgentLeakRunner()
    rows: dict[str, Any] = {}
    for sid in SCENARIOS:
        rows[f"builtin/{sid}"] = _row(runner.analyze(load_example_trace(sid)).to_dict())
    for pack in sorted(p["id"] for p in list_packs()):
        for meta, trace in expand_pack(pack):
            sid = meta.get("origin_id") or trace.run_id
            rows[f"{pack}/{sid}"] = _row(runner.analyze(trace).to_dict())
    return {"software_version": agentleak.__version__, "scenarios": rows}


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    moved = []
    for key, b in before["scenarios"].items():
        a = after["scenarios"].get(key)
        if a is None:
            moved.append({"scenario": key, "change": "missing after"})
            continue
        changes = {
            field: [b[field], a[field]]
            for field in ("verdict", "risk_index", "leaked_findings", "leaked_types",
                          "controls_at_risk")
            if b[field] != a[field]
        }
        if changes:
            moved.append({"scenario": key, **changes})
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Write every scenario's scores as JSON.")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                        help="List the scenarios whose scores differ between two files.")
    parser.add_argument("--installed", action="store_true",
                        help="Score with whatever agentleak is importable instead of ../src.")
    args = parser.parse_args()
    if args.compare:
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.compare)
        moved = compare(before, after)
        print(f"{before['software_version']} -> {after['software_version']}: "
              f"{len(moved)} of {len(before['scenarios'])} scenarios moved")
        for row in moved:
            print(json.dumps(row, ensure_ascii=False))
        return 0
    result = score_all()
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"scored {len(result['scenarios'])} scenarios with AgentLeak {result['software_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
