# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Measure the bundled corpus and emit the public benchmark.

Two questions, answered by running the analyzer over every scenario that ships
in the package:

1. **Where does a leak actually travel?** Per-channel leakage rates. The point
   of the product is that internal channels carry what the final answer does
   not, and this is that claim reduced to a number anyone can reproduce.

2. **What does each detection tier actually catch?** Every scenario is scored
   twice — with its ground-truth canaries and without — so the gap between
   "no pattern matched" and "nothing leaked" is measured rather than asserted.

Honesty constraints, because a benchmark that overstates is worth less than no
benchmark: this measures the *corpus*, not live models. The scenarios are built
to exercise internal channels, so a high internal-leak rate is partly by
construction; the output is labelled accordingly. Nothing here involves a model
call, so the numbers are deterministic and reproduce exactly.

Usage: python scripts/build_benchmark.py
"""

from __future__ import annotations

import importlib.resources as resources
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from agentleak import AgentLeakRunner, __version__
from agentleak.core.canary import CanarySet
from agentleak.core.trace import Trace
from agentleak.scenarios import SCENARIOS, get_scenario
from agentleak.scenarios.packs import expand_pack, list_packs

OUT = Path(__file__).resolve().parents[1] / "agentleak/web/frontend/src/data/benchmark.json"

INTERNAL_CHANNELS = (
    "tool_call",
    "tool_response",
    "shared_memory",
    "inter_agent_message",
    "log",
    "generated_file",
)

# Which of the three leak modes each source exercises. Kept here rather than in
# the packs because it is an editorial claim about coverage, not pack metadata.
LEAK_MODE = {
    "builtin": "pattern",
    "agentleak_bench": "pattern",
    "privacylens_ci": "norm",
    "agentdojo_exfil": "hijack",
}


def builtin_traces() -> list[tuple[str, Trace]]:
    out: list[tuple[str, Trace]] = []
    for sid in SCENARIOS:
        name = get_scenario(sid).example_trace
        if not name:
            continue
        raw = resources.files("agentleak.examples").joinpath(name).read_text(encoding="utf-8")
        out.append((sid, Trace.from_dict(json.loads(raw))))
    return out


def main() -> None:
    runner = AgentLeakRunner()
    records: list[dict[str, Any]] = []

    for sid, trace in builtin_traces():
        report = runner.analyze(trace).to_dict()
        records.append({"source": "builtin", "id": sid, "with_gt": report, "bare": report})

    for pack in list_packs():
        for meta, trace in expand_pack(pack["id"]):
            canaries = meta.get("canaries")
            bare = runner.analyze(trace).to_dict()
            with_gt = (
                runner.analyze(trace, canary_set=CanarySet.from_dict(canaries)).to_dict()
                if canaries
                else bare
            )
            records.append(
                {"source": pack["id"], "id": meta["name"], "with_gt": with_gt, "bare": bare}
            )

    leaky = [r for r in records if r["with_gt"]["summary"]["leaked_secrets"] > 0]

    channels: Counter[str] = Counter()
    internal_only = mixed = output_only = 0
    for record in leaky:
        hit = {f["channel"] for f in record["with_gt"]["findings"] if f.get("level", 0) > 0}
        channels.update(hit)
        on_output = "final_output" in hit
        on_internal = bool(hit & set(INTERNAL_CHANNELS))
        if on_output and on_internal:
            mixed += 1
        elif on_output:
            output_only += 1
        else:
            internal_only += 1

    # Per-source: what the pattern tier alone concludes, versus the truth.
    by_source: list[dict[str, Any]] = []
    for source in ["builtin", *[p["id"] for p in list_packs()]]:
        group = [r for r in records if r["source"] == source]
        if not group:
            continue
        unblocked = sum(
            r["bare"]["verdict"] in ("Pass", "Conditional pass") for r in group
        )
        by_source.append(
            {
                "source": source,
                "leak_mode": LEAK_MODE.get(source, "pattern"),
                "scenarios": len(group),
                "clean_pass_without_ground_truth": sum(
                    r["bare"]["privacy_score"] == 100 for r in group
                ),
                "would_not_block_a_gate": unblocked,
                "fails_with_ground_truth": sum(
                    r["with_gt"]["verdict"] in ("Fail", "High risk") for r in group
                ),
            }
        )

    document = {
        "generated_on": date.today().isoformat(),
        "agentleak_version": __version__,
        "method": (
            "Every scenario bundled in the package, analyzed by the deterministic "
            "pipeline in fast mode (regex tier). Scenarios carrying ground-truth "
            "canaries are scored twice: once with them and once without, so the gap "
            "between 'no pattern matched' and 'nothing leaked' is measured. No model "
            "is called, so re-running this reproduces the numbers exactly."
        ),
        "caveat": (
            "This measures the bundled corpus, not live agents. These scenarios are "
            "built to exercise internal channels, so the internal-leak rate is partly "
            "by construction — it is the shape of the failure that matters, not the "
            "rate as a prediction about your agent."
        ),
        "corpus": {
            "scenarios": len(records),
            "leaking": len(leaky),
            "channels": [
                {
                    "channel": channel,
                    "scenarios": count,
                    "share": round(100 * count / len(leaky), 1),
                }
                for channel, count in channels.most_common()
            ],
            "internal_only": internal_only,
            "internal_and_output": mixed,
            "output_only": output_only,
        },
        "by_source": by_source,
        "reproduce": "python scripts/build_benchmark.py",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    print(f"{OUT.relative_to(Path.cwd())}  ({OUT.stat().st_size / 1024:.1f} KB)")
    print(f"  {len(records)} scenarios, {len(leaky)} leaking")
    print(f"  internal-only leaks: {internal_only}  mixed: {mixed}  output-only: {output_only}")
    for row in by_source:
        print(
            f"  {row['source']:20} {row['scenarios']:>4}  "
            f"clean-pass-without-gt={row['clean_pass_without_ground_truth']:>3}  "
            f"unblocked={row['would_not_block_a_gate']:>3}"
        )


if __name__ == "__main__":
    main()
