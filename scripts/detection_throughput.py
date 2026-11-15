#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Measure how fast the deterministic tier scans the bundled scenarios.

Detection runs on every event of every trace, so a new rule is paid for on
every event anyone ever analyses. This script times two things over the
built-in scenarios and every bundled pack:

* **detectors** — every built-in detector over every event's searchable text,
  the raw cost of the regex and dictionary rules;
* **analyze** — ``analyze()`` on every trace, which adds decoding, obscured-copy
  matching, coalescing and scoring.

Each is run ``--repeat`` times and the fastest run is reported (the least
disturbed by other work on the machine). Numbers depend on the machine; compare
two versions on the same machine in the same session.

    python scripts/detection_throughput.py
    python scripts/detection_throughput.py --installed   # whatever is importable
    python scripts/detection_throughput.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

if "--installed" not in sys.argv:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agentleak  # noqa: E402
from agentleak.core.runner import analyze  # noqa: E402
from agentleak.core.trace import Trace  # noqa: E402
from agentleak.detectors import build_detectors  # noqa: E402
from agentleak.scenarios import SCENARIOS, load_example_trace  # noqa: E402
from agentleak.scenarios.packs import expand_pack, list_packs  # noqa: E402

# The packs that ship with 0.18.0. A pack added later is timed too when
# ``--all-packs`` is given, but the default corpus stays fixed so that two
# versions are compared on the same input.
BASELINE_PACKS = ("agentdojo_exfil", "agentleak_bench", "privacylens_ci")


def _corpus(all_packs: bool) -> list[Trace]:
    traces = [load_example_trace(s) for s in SCENARIOS]
    available = {p["id"] for p in list_packs()}
    packs = sorted(available) if all_packs else [p for p in BASELINE_PACKS if p in available]
    for pack in packs:
        traces.extend(trace for _meta, trace in expand_pack(pack))
    return traces


def measure(repeat: int = 5, all_packs: bool = False) -> dict[str, Any]:
    traces = _corpus(all_packs)
    texts = [e.searchable_text for t in traces for e in t.events if e.searchable_text]
    chars = sum(len(t) for t in texts)
    detectors = build_detectors(None, None)

    best_det = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        for text in texts:
            for d in detectors:
                d.detect(text)
        best_det = min(best_det, time.perf_counter() - start)

    best_an = float("inf")
    for _ in range(max(1, repeat // 2)):
        start = time.perf_counter()
        for trace in traces:
            analyze(trace)
        best_an = min(best_an, time.perf_counter() - start)

    return {
        "software_version": agentleak.__version__,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "corpus": {
            "traces": len(traces),
            "events": len(texts),
            "characters": chars,
            "packs": "all bundled" if all_packs else list(BASELINE_PACKS) + ["built-in scenarios"],
        },
        "detectors": {
            "seconds": round(best_det, 4),
            "events_per_second": round(len(texts) / best_det),
            "mb_per_second": round(chars / best_det / 1e6, 3),
        },
        "analyze": {
            "seconds": round(best_an, 4),
            "traces_per_second": round(len(traces) / best_an, 1),
        },
        "repeat": repeat,
        "method": "best of N wall-clock runs, time.perf_counter, single process",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--all-packs", action="store_true")
    parser.add_argument("--json", help="Write the result as JSON.")
    parser.add_argument("--installed", action="store_true",
                        help="Measure the importable agentleak instead of this checkout.")
    args = parser.parse_args()
    result = measure(args.repeat, args.all_packs)
    text = json.dumps(result, indent=2)
    if args.json:
        Path(args.json).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
