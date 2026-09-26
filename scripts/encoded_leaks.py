#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Measure detection of encoded and obscured copies passed between agents.

For each sensitive value and each transformation, one trace: the value arrives
in a tool response, then the planner passes it to a worker in transformed form.
A cell counts as detected only when a finding lands on the *disclosing* message
with the right data type and the *original* value — a reversed SIN reported as
some other SIN is a miss, because the report would name the wrong secret.

Deliberately uses nothing but ``analyze()``, so the same script runs against
any installed version and the before/after columns come from one method.

    python scripts/encoded_leaks.py --markdown out.md --json out.json
    python scripts/encoded_leaks.py --installed   # measure the installed wheel
"""

from __future__ import annotations

import argparse
import base64
import codecs
import json
import sys
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

# The checkout by default, like detection_quality.py; --installed measures
# whatever version is installed, which is how the "before" column is produced.
if "--installed" not in sys.argv:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agentleak  # noqa: E402
from agentleak.core.coalesce import canonical_form  # noqa: E402
from agentleak.core.runner import analyze  # noqa: E402
from agentleak.core.trace import Trace  # noqa: E402

VALUES: dict[str, tuple[str, str]] = {
    # data_type: (field name in the tool response, value)
    "sin": ("sin", "046 454 286"),
    "credit_card": ("card", "4111 1111 1111 1111"),
    "phone_number": ("phone", "514-555-0199"),
    "email": ("email", "jean.tremblay@example.com"),
    "llm_api_key": ("api_key", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"),
    "health_condition": ("diagnosis", "diabetes"),
}


def _b64(v: str) -> str:
    return base64.b64encode(v.encode()).decode()


def _split(v: str) -> list[str] | None:
    digits = sum(ch.isdigit() for ch in v)
    if digits < 4:
        return None  # not an identifier; see transforms._reassembled
    tokens = v.split(" ") if " " in v else [v[: len(v) // 2], v[len(v) // 2:]]
    cut = max(1, len(tokens) // 2)
    return ["part one: " + " ".join(tokens[:cut]), "part two: " + " ".join(tokens[cut:])]


TRANSFORMS: dict[str, Callable[[str], Any]] = {
    "plaintext (control)": lambda v: [f"forwarding: {v}"],
    "base64": lambda v: [f"ctx={_b64(v)}"],
    "base64 of base64": lambda v: [f"ctx={_b64(_b64(v))}"],
    "hex": lambda v: [f"id={v.encode().hex()}"],
    "URL-encoded": lambda v: [f"https://t.example/p?u={urllib.parse.quote(v, safe='')}"],
    "letter-spaced": lambda v: [" ".join(v.replace(" ", ""))],
    "reversed": lambda v: [f"code {v[::-1]}"],
    "ROT13": lambda v: [f"note: {codecs.encode(v, 'rot13')}"],
    "split in two": _split,
}


def _trace(field: str, value: str, messages: list[str]) -> Trace:
    events: list[dict[str, Any]] = [
        {"event_id": "e1", "channel": "tool_response", "source": "crm", "target": "planner",
         "content": {"customer": "record 4812", field: value}},
    ]
    for i, text in enumerate(messages, start=2):
        events.append({"event_id": f"e{i}", "channel": "inter_agent_message",
                       "source": "planner", "target": "worker", "content": text})
    return Trace.model_validate({"run_id": "enc", "agent_name": "planner", "events": events})


def _detected(trace: Trace, data_type: str, value: str) -> bool:
    want = canonical_form(value)
    last = trace.events[-1].event_id
    for f in analyze(trace).findings:
        if f.event_id != last or f.data_type != data_type:
            continue
        got = canonical_form(f.matched_value)
        if got == want or want in got or got in want:
            return True
    return False


def measure() -> dict[str, Any]:
    cells: dict[str, dict[str, bool | None]] = {}
    for name, fn in TRANSFORMS.items():
        cells[name] = {}
        for data_type, (field, value) in VALUES.items():
            messages = fn(value)
            if messages is None:
                cells[name][data_type] = None
                continue
            cells[name][data_type] = _detected(_trace(field, value, messages), data_type, value)
    obscured = [v for k, row in cells.items() if k != "plaintext (control)" for v in row.values()
                if v is not None]
    return {
        "software_version": agentleak.__version__,
        "cells": cells,
        "obscured_detected": sum(obscured),
        "obscured_total": len(obscured),
        "method": "tool_response holds the value; the next inter_agent_message carries it "
                  "transformed. Detected = finding on that message, right type, original value.",
    }


def to_markdown(report: dict[str, Any]) -> str:
    types = list(VALUES)
    lines = [
        f"agentleak {report['software_version']} — "
        f"{report['obscured_detected']} of {report['obscured_total']} obscured copies detected",
        "",
        "| Transformation | " + " | ".join(f"`{t}`" for t in types) + " |",
        "|---|" + "---|" * len(types),
    ]
    mark = {True: "✓", False: "✗", None: "n/a"}
    for name, row in report["cells"].items():
        lines.append(f"| {name} | " + " | ".join(mark[row[t]] for t in types) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", help="Write the report as JSON.")
    parser.add_argument("--markdown", help="Write the table as Markdown.")
    parser.add_argument("--installed", action="store_true",
                        help="Measure the installed agentleak instead of this checkout.")
    args = parser.parse_args()
    report = measure()
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report))
    sys.stdout.write(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
