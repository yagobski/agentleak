#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Detection quality in Spanish: the same count, in another language.

``scripts/detection_quality.py`` measures the deterministic tier against the
labelled vaults of the scenario packs, which are in English. The roadmap asks
for precision and recall by language; this is the Spanish half, measured the
same way so the two pages can be read side by side.

What is the same: the detector chain (deterministic tier only), the
structured carriers, the rule that a value counts as found if any carrier
finds it as the expected type, type confusion counted as a miss, Wilson
intervals, and false positives counted on independent benign controls,
never pooled with recall.

What is different, and why:

* **Ground truth** is ``scripts/detection_quality_es.json``: made-up values
  labelled by data type, because the packs carry no Spanish records.
  Identifiers carry valid check digits, so a detector that validates them can
  find them; no value belongs to a real person.
* **Field names are Spanish** (``telefono``, ``direccion``…). That is how a
  Spanish-language agent's tool calls look, so the structured condition also
  measures whether a Spanish key helps the way an English key does.
* **Prose carriers are Spanish sentences.**
* **Controls** are the English controls translated, plus a few ordinary
  sentences that use Spanish words the detectors could trip on ("sin").

Usage
-----
    python scripts/detection_quality_es.py                  # table to stdout
    python scripts/detection_quality_es.py --json out.json  # machine readable
    python scripts/detection_quality_es.py --markdown out.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import detection_quality as dq  # noqa: E402

LABELLED_SET = SCRIPTS / "detection_quality_es.json"

PROSE_CARRIERS: tuple[str, ...] = (
    "El expediente indica {value} para este caso.",
    "Por favor, anota {value} en la ficha.",
    "{value}",
)


def load_set() -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """Return ``(labelled, control_texts)``, labelled as
    ``(source, data_type, field, value)`` like ``dq.load_labelled_values``."""
    data = json.loads(LABELLED_SET.read_text(encoding="utf-8"))
    labelled = [
        ("es", item["data_type"], item["field"], item["value"]) for item in data["labelled"]
    ]
    return labelled, list(data["control_texts"])


def evaluate() -> dict[str, Any]:
    detectors = dq.build_detectors(None, None)
    labelled, controls = load_set()

    false_positives: list[dict[str, str]] = []
    for text in controls:
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
        "software_version": dq.__version__,
        "language": "es",
        "detector_tier": "fast (deterministic: regex + dictionaries)",
        "tiers_not_run": ["presidio", "semantic judge"],
        "source": f"made-up labelled Spanish values in scripts/{LABELLED_SET.name}",
        "conditions": {
            "structured": dq._condition(detectors, labelled, dq.STRUCTURED_CARRIERS),
            "prose": dq._condition(detectors, labelled, PROSE_CARRIERS),
        },
        "false_positives": {
            "control_texts": len(controls),
            "detections": len(false_positives),
            "rate_per_text": round(len(false_positives) / len(controls), 4),
            "detail": false_positives,
            "note": (
                "Independent negatives: the English controls translated, plus ordinary "
                "Spanish sentences. Never pool them with recall."
            ),
        },
    }


def to_markdown(report: dict[str, Any]) -> str:
    out = [
        f"AgentLeak {report['software_version']} · language: {report['language']} · "
        f"tier: {report['detector_tier']}",
        f"Not run: {', '.join(report['tiers_not_run'])}.",
        f"Ground truth: {report['source']}.",
        "",
    ]
    for name in ("structured", "prose"):
        cond = report["conditions"][name]
        out += [
            f"### {name.capitalize()}",
            "",
            f"**Recall {cond['recall']:.3f}** ({cond['numerator']}/{cond['denominator']}, "
            f"95% CI {cond['ci95'][0]:.3f}–{cond['ci95'][1]:.3f})",
            "",
            "| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |",
            "|---|---:|---|---:|---:|---:|---:|",
        ]
        for row in cond["by_data_type"]:
            confused = ", ".join(f"`{t}`" for t in row["confused_as"])
            out.append(
                f"| `{row['data_type']}` | {row['recall']:.3f} | "
                f"{row['ci95'][0]:.3f}–{row['ci95'][1]:.3f} | {row['hit']} | "
                f"{row['type_confused']}{' (' + confused + ')' if confused else ''} | "
                f"{row['missed']} | {row['labelled_values']} |"
            )
        out.append("")
    fp = report["false_positives"]
    out += [
        "### False positives",
        "",
        f"{fp['detections']} detection(s) across {fp['control_texts']} benign control "
        f"texts ({fp['rate_per_text']} per text). {fp['note']}",
    ]
    for item in fp["detail"][:20]:
        out.append(f"- `{item['data_type']}` matched `{item['value']}` in: {item['text']}")
    out += ["", "Reproduce with `python scripts/detection_quality_es.py`."]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="Write the full report as JSON.")
    parser.add_argument("--markdown", help="Write the report as Markdown.")
    args = parser.parse_args()

    report = evaluate()
    if args.json:
        Path(args.json).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.json}")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report), encoding="utf-8")
        print(f"wrote {args.markdown}")
    if not args.json and not args.markdown:
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
