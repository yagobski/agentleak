#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Measure what the detectors actually find, and publish the misses.

AgentLeak scores. A scoring product lives on measured trust, and this one had
never published a precision or a recall figure — the gap was named in its own
2025-08 audit and stayed open for a year. In that year the deterministic tier
shipped a redactor that could not remove a SIN, a key-name capture that ran to
the end of the sentence, and a code scan that reported a bracket as a leaked
identifier. None of those needed clever analysis to find. They needed somebody
to count.

So this counts, against the labelled vaults bundled with the scenario packs,
and it prints the false positives next to the recall rather than under it.

Method
------
Every pack scenario carries a ``private_vault`` of typed records: the field
name is the label, the field value is the item. Each labelled value is placed
in a neutral carrier sentence and run through the deterministic detector chain
(the tier that runs for everyone by default — no Presidio, no semantic judge).

* **True positive** — the expected data type is among the types detected for
  that value.
* **Type confusion** — the value is detected, but only as something else. It is
  not counted as a hit; a phone number found as an account number is a wrong
  answer, not a partial one.
* **False negative** — nothing detected.
* **False positive** — a detection on the benign control corpus, which contains
  no personal data at all.

Fixture integrity
-----------------
Some bundled records carry values that contradict their own field name — an
``ssn`` field holding "has bipolar disorder managed with lithium", which is a
generation artefact in the upstream fixture, not a detector failure. Those are
excluded from recall and reported as their own number, so the exclusion is
visible instead of quietly flattering the result.

Usage
-----
    python scripts/detection_quality.py                  # table to stdout
    python scripts/detection_quality.py --json out.json  # machine readable
    python scripts/detection_quality.py --markdown out.md
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentleak import __version__  # noqa: E402
from agentleak.detectors import build_detectors  # noqa: E402

PACK_DIR = Path(__file__).resolve().parent.parent / "agentleak" / "scenarios" / "packs"

# Vault field name -> the data type a detector is expected to assign.
# Only fields with one unambiguous answer are labelled; everything else is
# counted as unlabelled and left out of the denominator rather than guessed at.
FIELD_LABELS: dict[str, str] = {
    "name": "person_name",
    "customer_name": "person_name",
    "patient_name": "person_name",
    "employee_name": "person_name",
    "full_name": "person_name",
    "email": "email",
    "email_address": "email",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "ssn": "ssn",
    "sin": "sin",
    "address": "address",
    "home_address": "address",
    "dob": "date_of_birth",
    "date_of_birth": "date_of_birth",
    "salary": "salary",
    "current_salary": "salary",
    "expected_salary": "salary",
    "credit_card": "credit_card",
    "card_number": "credit_card",
    "iban": "iban",
    "account_number": "account_number",
    "diagnosis": "health_condition",
    "chief_complaint": "health_condition",
    "medication": "medication",
    "medications": "medication",
    "mrn": "health_identifier",
    "health_id": "health_identifier",
    "credit_score": "credit_score",
}

# Shape checks, independent of the detectors, used only to spot fixture records
# whose value contradicts its field. Deliberately loose: the question is "could
# this plausibly be one of these at all", not "does a detector like it".
FIELD_SHAPES: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"),
    "phone_number": re.compile(r"^[\d\s()+.\-]{7,}$"),
    "ssn": re.compile(r"^[\d\s\-]{9,}$"),
    "sin": re.compile(r"^[\d\s\-]{9,}$"),
    "date_of_birth": re.compile(r"\d{4}|\d{1,2}[/-]\d{1,2}"),
    "salary": re.compile(r"\d"),
    "credit_score": re.compile(r"^\d{3}$"),
    "credit_card": re.compile(r"^[\d\s\-]{13,}$"),
}

# Benign control corpus: ordinary operational text with no personal data in it.
# A detection here is a false positive, full stop. These are independent
# negatives — not clean counterparts derived from the leaking fixtures — and
# the two must never be pooled into one number.
CONTROL_TEXTS: tuple[str, ...] = (
    "The order shipped on Tuesday and arrived Thursday afternoon.",
    "Deployment 4821 completed in 92 seconds with no failing checks.",
    "Please confirm whether the quarterly report is ready for review.",
    "The service returned a 503 and the retry succeeded on the second attempt.",
    "Ticket 88213 was closed after the customer confirmed the issue was resolved.",
    "Meeting moved to 3pm in room B; the agenda is unchanged.",
    "Cache hit ratio improved from 0.71 to 0.94 after the index was rebuilt.",
    "The invoice total came to 1420 units across three line items.",
    "Version 2.14.0 is available and the changelog lists eleven entries.",
    "Backup completed at 02:00 UTC and the checksum matched.",
    "The pipeline runs nightly and writes its summary to the shared bucket.",
    "Support hours are Monday to Friday, and the queue is currently empty.",
    "The migration touched 14 tables and took under four minutes.",
    "Reviewer feedback was addressed and the branch is ready to merge.",
    "Latency at the 95th percentile dropped below 200 milliseconds.",
)

# Two conditions, reported separately, because the deterministic tier reads
# field names as well as values and the two channels differ:
#
# * **structured** — the value arrives with the key that names it, which is how
#   tool_call, tool_response and shared_memory carry it.
# * **prose** — the value arrives in a sentence with no key, which is how
#   final_output, log and inter_agent_message carry it.
#
# Collapsing them into one figure would hide the finding that matters: what
# this tier can and cannot recognise once the field name is gone.
STRUCTURED_CARRIERS: tuple[str, ...] = (
    '{{"{field}": "{value}"}}',
    "{field}: {value}",
)

PROSE_CARRIERS: tuple[str, ...] = (
    "The record shows {value} for this case.",
    "Please note {value} in the file.",
    "{value}",
)


def wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. A proportion published without one invites the
    reader to treat 3/3 and 300/300 as the same claim."""
    if total == 0:
        return (0.0, 0.0)
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def load_labelled_values() -> tuple[
    list[tuple[str, str, str, str]], list[tuple[str, str, str, str]]
]:
    """Return ``(labelled, anomalous)`` as ``(pack, data_type, field, value)``."""
    labelled: list[tuple[str, str, str, str]] = []
    anomalous: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for path in sorted(PACK_DIR.glob("*.json")):
        pack = json.loads(path.read_text())
        pack_id = pack.get("id", path.stem)
        for scenario in pack.get("scenarios", []):
            for record in (scenario.get("private_vault") or {}).get("records", []):
                for field, value in (record.get("fields") or {}).items():
                    data_type = FIELD_LABELS.get(field)
                    if not data_type or not isinstance(value, str) or not value.strip():
                        continue
                    key = (data_type, value)
                    if key in seen:
                        continue
                    seen.add(key)
                    shape = FIELD_SHAPES.get(data_type)
                    if shape and not shape.match(value.strip()):
                        anomalous.append((pack_id, data_type, field, value))
                    else:
                        labelled.append((pack_id, data_type, field, value))
    return labelled, anomalous


def detect_types(detectors: list[Any], text: str) -> set[str]:
    return {raw.data_type for d in detectors for raw in d.detect(text)}


def _condition(
    detectors: list[Any],
    labelled: list[tuple[str, str, str, str]],
    carriers: tuple[str, ...],
) -> dict[str, Any]:
    """Recall for one carrier condition, broken down by data type."""
    per_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"hit": 0, "confused": 0, "missed": 0}
    )
    confusions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for _pack, expected, field, value in labelled:
        # A value counts as found if any carrier phrasing finds it: the
        # question is whether the detector can recognise the value, not whether
        # it survives one particular sentence.
        found: set[str] = set()
        for carrier in carriers:
            found |= detect_types(detectors, carrier.format(field=field, value=value))
        if expected in found:
            per_type[expected]["hit"] += 1
        elif found:
            per_type[expected]["confused"] += 1
            for other in sorted(found):
                confusions[expected][other] += 1
        else:
            per_type[expected]["missed"] += 1

    rows = []
    for data_type in sorted(per_type):
        counts = per_type[data_type]
        total = counts["hit"] + counts["confused"] + counts["missed"]
        low, high = wilson(counts["hit"], total)
        rows.append(
            {
                "data_type": data_type,
                "recall": round(counts["hit"] / total, 4) if total else 0.0,
                "ci95": [round(low, 4), round(high, 4)],
                "hit": counts["hit"],
                "type_confused": counts["confused"],
                "missed": counts["missed"],
                "labelled_values": total,
                "confused_as": dict(sorted(confusions[data_type].items())),
            }
        )

    hits = sum(r["hit"] for r in rows)
    total = sum(r["labelled_values"] for r in rows)
    low, high = wilson(hits, total)
    return {
        "recall": round(hits / total, 4) if total else 0.0,
        "ci95": [round(low, 4), round(high, 4)],
        "numerator": hits,
        "denominator": total,
        "by_data_type": rows,
    }


def evaluate() -> dict[str, Any]:
    detectors = build_detectors(None, None)
    labelled, anomalous = load_labelled_values()

    false_positives: list[dict[str, str]] = []
    for text in CONTROL_TEXTS:
        for detector in detectors:
            for raw in detector.detect(text):
                false_positives.append(
                    {
                        "data_type": raw.data_type,
                        "detector": detector.name,
                        "value": raw.matched_value,
                        "text": text,
                    }
                )

    return {
        "software_version": __version__,
        "detector_tier": "fast (deterministic: regex + dictionaries)",
        "tiers_not_run": ["presidio", "semantic judge"],
        "source": "private_vault records in the bundled scenario packs",
        "conditions": {
            "structured": _condition(detectors, labelled, STRUCTURED_CARRIERS),
            "prose": _condition(detectors, labelled, PROSE_CARRIERS),
        },
        "false_positives": {
            "control_texts": len(CONTROL_TEXTS),
            "detections": len(false_positives),
            "rate_per_text": round(len(false_positives) / len(CONTROL_TEXTS), 4),
            "detail": false_positives,
            "note": (
                "Independent negatives — ordinary operational text, not clean "
                "counterparts derived from the leaking fixtures. Never pool the two."
            ),
        },
        "fixture_integrity": {
            "excluded": len(anomalous),
            "note": (
                "Bundled records whose value contradicts its own field name "
                "(e.g. an 'ssn' field holding a sentence about a diagnosis). "
                "An upstream generation artefact, not a detector result; "
                "excluded from recall so the exclusion is visible."
            ),
            "examples": [
                {"data_type": t, "field": f, "value": v[:60], "pack": p}
                for p, t, f, v in anomalous[:5]
            ],
        },
    }


def to_markdown(report: dict[str, Any]) -> str:
    out = [
        "# Detection quality",
        "",
        f"AgentLeak {report['software_version']} · tier: {report['detector_tier']}",
        f"Not run: {', '.join(report['tiers_not_run'])}.",
        f"Ground truth: {report['source']}.",
        "",
        "Two conditions, because the deterministic tier reads field names as well",
        "as values. **Structured** is how `tool_call`, `tool_response` and",
        "`shared_memory` carry a value — with the key that names it. **Prose** is",
        "how `final_output`, `log` and `inter_agent_message` carry it — in a",
        "sentence, with the key gone.",
        "",
    ]

    for name in ("structured", "prose"):
        cond = report["conditions"][name]
        out += [
            f"## {name.capitalize()}",
            "",
            f"**Recall {cond['recall']:.3f}** ({cond['numerator']}/{cond['denominator']}, "
            f"95% CI {cond['ci95'][0]:.3f}–{cond['ci95'][1]:.3f})",
            "",
            "| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |",
            "|---|---:|---|---:|---:|---:|---:|",
        ]
        for row in cond["by_data_type"]:
            out.append(
                f"| `{row['data_type']}` | {row['recall']:.3f} | "
                f"{row['ci95'][0]:.3f}–{row['ci95'][1]:.3f} | {row['hit']} | "
                f"{row['type_confused']} | {row['missed']} | {row['labelled_values']} |"
            )
        out.append("")

    fp = report["false_positives"]
    out += [
        "## False positives",
        "",
        f"{fp['detections']} detection(s) across {fp['control_texts']} benign control "
        f"texts ({fp['rate_per_text']} per text). {fp['note']}",
    ]
    for item in fp["detail"][:20]:
        out.append(f"- `{item['data_type']}` matched `{item['value']}` in: {item['text']}")
    integrity = report["fixture_integrity"]
    out += [
        "",
        "## Fixture integrity",
        "",
        f"{integrity['excluded']} labelled value(s) excluded. {integrity['note']}",
        "",
        "Reproduce with `python scripts/detection_quality.py`.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="Write the full report as JSON.")
    parser.add_argument("--markdown", help="Write the report as Markdown.")
    args = parser.parse_args()

    report = evaluate()
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report))
        print(f"wrote {args.markdown}")
    if not args.json and not args.markdown:
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
