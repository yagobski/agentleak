#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Count detections on text nobody wrote for AgentLeak: the Python standard library.

The labelled sets and the hard negatives were written by the people who wrote
the rules, so a zero on them shows the written cases are handled and nothing
more. Source code, docstrings and comments of the CPython standard library are
an outside corpus: names, e-mail addresses, IP addresses, dates, numbers and
English prose that no rule was tuned on. Almost every detection there is a
false positive or an incidental real value (an author's e-mail in a header),
so the count is read as "how much noise does a rule add on ordinary text".

Corpus: every top-level ``*.py`` module of the running interpreter's standard
library plus every ``<package>/__init__.py`` one level down, sorted by path,
each split into chunks on blank lines; every built-in detector runs on every
chunk. The interpreter's version is recorded, because the corpus is its
standard library.

    python scripts/detection_stdlib_check.py
    python scripts/detection_stdlib_check.py --json out.json
    PYTHONPATH=/tmp/al-before/src python scripts/detection_stdlib_check.py --installed
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import sysconfig
from collections import Counter
from pathlib import Path
from typing import Any

if "--installed" not in sys.argv:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agentleak  # noqa: E402
from agentleak.detectors import build_detectors  # noqa: E402

_CHUNK_RE = re.compile(r"\n\s*\n")


def corpus(stdlib: Path) -> list[Path]:
    return sorted(stdlib.glob("*.py")) + sorted(stdlib.glob("*/__init__.py"))


def measure(stdlib: Path) -> dict[str, Any]:
    files = corpus(stdlib)
    detectors = build_detectors(None, None)
    by_type: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    detail: list[dict[str, str]] = []
    chunks = 0
    size = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        size += len(text.encode("utf-8"))
        for chunk in _CHUNK_RE.split(text):
            chunks += 1
            for detector in detectors:
                for raw in detector.detect(chunk):
                    by_type[raw.data_type] += 1
                    by_rule[f"{raw.detector}:{raw.rule or 'default'}"] += 1
                    detail.append({
                        "file": path.relative_to(stdlib).as_posix(),
                        "data_type": raw.data_type, "rule": raw.rule,
                        "value": str(raw.matched_value)[:80],
                    })
    return {
        "software_version": agentleak.__version__,
        "detector_tier": "fast (deterministic: regex + dictionaries)",
        "python": platform.python_version(),
        "corpus": "top-level *.py and */__init__.py of the interpreter's standard library",
        "files": len(files),
        "bytes": size,
        "chunks": chunks,
        "detections": sum(by_type.values()),
        "by_data_type": dict(sorted(by_type.items())),
        "by_rule": dict(sorted(by_rule.items())),
        "detail": detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Write the full result as JSON.")
    parser.add_argument("--stdlib", default=sysconfig.get_paths()["stdlib"],
                        help="Standard library directory (default: this interpreter's).")
    parser.add_argument("--installed", action="store_true",
                        help="Measure whatever agentleak is importable instead of ../src.")
    args = parser.parse_args()
    result = measure(Path(args.stdlib))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"AgentLeak {result['software_version']} on Python {result['python']} stdlib: "
          f"{result['files']} files, {result['bytes']:,} bytes, {result['chunks']} chunks, "
          f"{result['detections']} detections")
    for data_type, count in result["by_data_type"].items():
        print(f"  {data_type}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
