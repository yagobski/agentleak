#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Check that ``pii.EMAIL_RE`` is linear and finds what the plain pattern finds.

``EMAIL_RE`` carries a look-behind so that a match can only start where a run
of local-part characters starts. Without it, a long run with no usable ``@``
is rescanned from every position: quadratic. This script times the shipped
pattern against the plain one (same pattern, no look-behind) on adversarial
input, then runs both over every bundled scenario event, every labelled
quality value in its carriers and every cued-prose sentence, and lists every
text where the two return different matches.

    python scripts/email_regex_check.py
    python scripts/email_regex_check.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent / "src"))
sys.path.insert(0, str(SCRIPTS))

import agentleak  # noqa: E402
from agentleak.detectors.pii import EMAIL_RE  # noqa: E402

PLAIN_RE = re.compile(EMAIL_RE.pattern.replace(r"(?<![A-Za-z0-9_.+-])", "", 1))
N = 50_000
ADVERSARIAL = {
    "run_then_at": "a" * N + "@",
    "dotted_run_then_at": "a." * (N // 2) + "@",
    "run_then_at_no_dot": "a" * N + "@b",
    "runs_with_ats": ("a" * 1000 + "@") * (N // 1001),
    "alternating": "a@" * (N // 2),
    "long_domain": "a@" + "b" * N,
}


def _texts() -> list[str]:
    import detection_quality as dq
    import detection_quality_cued as cued

    from agentleak.scenarios import SCENARIOS, load_example_trace
    from agentleak.scenarios.packs import expand_pack, list_packs

    texts: set[str] = set()
    for sid in SCENARIOS:
        texts.update(e.searchable_text for e in load_example_trace(sid).events)
    for pack in list_packs():
        for _meta, trace in expand_pack(pack["id"]):
            texts.update(e.searchable_text for e in trace.events)
    fixture = cued.fixture()
    for language, (labelled, controls) in cued.labelled_sets().items():
        texts.update(controls)
        for _s, data_type, field, value in labelled:
            for carrier in dq.STRUCTURED_CARRIERS + dq.PROSE_CARRIERS:
                texts.add(carrier.format(field=field, value=value))
            for half in fixture["templates"][language].get(data_type, {}).values():
                texts.update(t.replace("{value}", value) for t in half)
    return sorted(texts)


def _time(pattern: re.Pattern[str], text: str) -> float:
    start = time.perf_counter()
    pattern.findall(text)
    return round(time.perf_counter() - start, 4)


def measure() -> dict[str, Any]:
    timings = {
        name: {"shipped_s": _time(EMAIL_RE, text), "plain_s": _time(PLAIN_RE, text)}
        for name, text in ADVERSARIAL.items()
    }
    texts = _texts()
    differences = [
        {"text": t[:200], "shipped": EMAIL_RE.findall(t), "plain": PLAIN_RE.findall(t)}
        for t in texts
        if "@" in t and EMAIL_RE.findall(t) != PLAIN_RE.findall(t)
    ]
    return {
        "software_version": agentleak.__version__,
        "pattern": EMAIL_RE.pattern,
        "adversarial_chars": N,
        "timings": timings,
        "texts_compared": len(texts),
        "texts_with_at": sum("@" in t for t in texts),
        "matches_shipped": sum(len(EMAIL_RE.findall(t)) for t in texts),
        "differences": differences,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Write the result as JSON.")
    args = parser.parse_args()
    result = measure()
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"AgentLeak {result['software_version']}: EMAIL_RE timings on {N:,} characters")
    for name, t in result["timings"].items():
        print(f"  {name}: shipped {t['shipped_s']} s, without look-behind {t['plain_s']} s")
    print(f"{result['texts_compared']} texts compared ({result['texts_with_at']} with '@'), "
          f"{result['matches_shipped']} matches, {len(result['differences'])} difference(s)")
    for d in result["differences"]:
        print(f"  {d['shipped']} vs {d['plain']}: {d['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
