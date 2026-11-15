#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Prose recall in three conditions, with a development and a held-out half.

``detection_quality.py`` and its Spanish and French siblings measure two
conditions: **structured** (the value under the key that names it) and
**prose** (the value in a sentence with no cue at all: "The record shows
555-0152 for this case."). The second is a floor no deterministic rule can or
should lift: a bare ``555-0152`` is also a part number.

Agents rarely write that way. They write "you can reach her at 555-0152",
"born on 3 March 1984", "her salary is $84,000". This script adds that third
condition, **cued prose**, from templates frozen in
``scripts/detection_quality_cued.json`` before any context-window rule was
written, and reports all three conditions for English, French and Spanish.

Honest measurement
------------------
Every labelled value is assigned to a development or a held-out half by a
seeded hash (seed and method in the fixture). Templates are split the same
way: development values meet development templates, held-out values meet
held-out templates. Rules were tuned by reading development misses only
(``--misses development``); held-out figures were only counted. Both halves
are reported side by side, and the whole set too.

The cued condition is stricter than the other two. A value counts as found
only when a finding of the expected type *overlaps the value's position* in
the sentence, and each (value, template) pair counts once: three templates
per value, three chances to miss. The structured and uncued prose conditions
keep the method of ``detection_quality.py`` unchanged (expected type among
the detected types, any carrier) so their numbers stay comparable with the
published ones.

False positives are counted on three negative sets, never pooled with recall:
the benign controls of the three quality scripts, the 82 hard negatives of
``detection_hard_negatives.json``, and the look-alikes written for the
context rules in ``detection_hard_negatives_context.json`` (development and
held-out halves reported apart).

Usage
-----
    python scripts/detection_quality_cued.py                    # Markdown to stdout
    python scripts/detection_quality_cued.py --json out.json
    python scripts/detection_quality_cued.py --misses development   # tuning aid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import detection_quality as dq  # noqa: E402
import detection_quality_es as dq_es  # noqa: E402
import detection_quality_fr as dq_fr  # noqa: E402

CUED_SET = SCRIPTS / "detection_quality_cued.json"
CONTEXT_NEGATIVES = SCRIPTS / "detection_hard_negatives_context.json"
SPLITS = ("development", "held_out")
LANGUAGES = ("en", "fr", "es")

Labelled = tuple[str, str, str, str]  # (source, data_type, field, value)


def fixture() -> dict[str, Any]:
    return json.loads(CUED_SET.read_text(encoding="utf-8"))


def labelled_sets() -> dict[str, tuple[list[Labelled], list[str]]]:
    """``{language: (labelled values, benign control texts)}``."""
    en, _anomalous = dq.load_labelled_values()
    return {
        "en": (en, list(dq.CONTROL_TEXTS)),
        "fr": dq_fr.load_set(),
        "es": dq_es.load_set(),
    }


def split_values(language: str, labelled: list[Labelled], seed: int) -> dict[str, list[Labelled]]:
    """Seeded, stratified 50/50 split: per data type, sort by a keyed hash and
    give the first ceil(n/2) to development. Stable across runs and machines."""
    by_type: dict[str, list[Labelled]] = defaultdict(list)
    for item in labelled:
        by_type[item[1]].append(item)
    out: dict[str, list[Labelled]] = {s: [] for s in SPLITS}
    for data_type in sorted(by_type):
        items = sorted(
            by_type[data_type],
            key=lambda it: hashlib.sha256(
                f"{seed}|{language}|{data_type}|{it[3]}".encode()
            ).hexdigest(),
        )
        cut = math.ceil(len(items) / 2)
        out["development"].extend(items[:cut])
        out["held_out"].extend(items[cut:])
    return out


def _overlaps(text: str, needle: str, span: tuple[int, int]) -> bool:
    start = text.find(needle)
    while start >= 0:
        if start < span[1] and span[0] < start + len(needle):
            return True
        start = text.find(needle, start + 1)
    return False


def cued_condition(
    detectors: list[Any],
    labelled: list[Labelled],
    templates: dict[str, list[str]],
    collect_misses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recall over (value, template) instances, value-position checked."""
    per_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"hit": 0, "confused": 0, "missed": 0}
    )
    rules: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for _source, expected, _field, value in labelled:
        for template in templates.get(expected, []):
            text = template.replace("{value}", value)
            pos = template.index("{value}")
            span = (pos, pos + len(value))
            raws = [r for d in detectors for r in d.detect(text)]
            on_value = [r for r in raws if r.matched_value and _overlaps(text, str(r.matched_value), span)]
            hits = [r for r in on_value if r.data_type == expected]
            if hits:
                per_type[expected]["hit"] += 1
                for r in hits:
                    rules[expected][r.rule or f"{r.detector}:default"] += 1
                continue
            outcome = "confused" if on_value else "missed"
            per_type[expected][outcome] += 1
            if collect_misses is not None:
                collect_misses.append({
                    "data_type": expected, "outcome": outcome, "text": text,
                    "found": sorted({f"{r.data_type}:{r.matched_value}" for r in raws}),
                })

    rows = []
    for data_type in sorted(per_type):
        c = per_type[data_type]
        total = c["hit"] + c["confused"] + c["missed"]
        low, high = dq.wilson(c["hit"], total)
        rows.append({
            "data_type": data_type,
            "recall": round(c["hit"] / total, 4) if total else 0.0,
            "ci95": [round(low, 4), round(high, 4)],
            "hit": c["hit"], "type_confused": c["confused"], "missed": c["missed"],
            "instances": total,
            "rules_fired": dict(sorted(rules[data_type].items())),
        })
    hits = sum(r["hit"] for r in rows)
    total = sum(r["instances"] for r in rows)
    low, high = dq.wilson(hits, total)
    return {
        "recall": round(hits / total, 4) if total else 0.0,
        "ci95": [round(low, 4), round(high, 4)],
        "numerator": hits, "denominator": total,
        "unit": "(value, template) instance",
        "by_data_type": rows,
    }


def _flagged(texts: list[str]) -> tuple[int, list[dict[str, str]]]:
    from agentleak.core.runner import analyze
    from agentleak.core.trace import Trace

    flagged = 0
    detail: list[dict[str, str]] = []
    for text in texts:
        trace = Trace.model_validate({
            "run_id": "hard-negative", "agent_name": "a",
            "events": [{"event_id": "e1", "channel": "log", "source": "a",
                        "target": "b", "content": text}],
        })
        findings = analyze(trace).findings
        if findings:
            flagged += 1
            for f in findings:
                detail.append({"data_type": f.data_type, "value": f.matched_value,
                               "rule": str(f.metadata.get("rule", "")), "text": text})
    return flagged, detail


def context_negatives() -> dict[str, Any]:
    data = json.loads(CONTEXT_NEGATIVES.read_text(encoding="utf-8"))
    out: dict[str, Any] = {"source": f"scripts/{CONTEXT_NEGATIVES.name}"}
    for split in SPLITS:
        rows = []
        detail: list[dict[str, str]] = []
        for category, texts in data[split].items():
            flagged, d = _flagged(texts)
            detail.extend({**x, "category": category} for x in d)
            rows.append({"category": category, "texts": len(texts), "flagged": flagged})
        total = sum(r["texts"] for r in rows)
        flagged = sum(r["flagged"] for r in rows)
        low, high = dq.wilson(flagged, total)
        out[split] = {
            "texts": total, "flagged": flagged,
            "rate": round(flagged / total, 4) if total else 0.0,
            "ci95": [round(low, 4), round(high, 4)],
            "by_category": rows, "detail": detail,
        }
    return out


def benign_controls(detectors: list[Any], controls: list[str]) -> dict[str, Any]:
    detail = [
        {"data_type": r.data_type, "value": r.matched_value, "rule": r.rule, "text": t}
        for t in controls for d in detectors for r in d.detect(t)
    ]
    return {"texts": len(controls), "detections": len(detail), "detail": detail}


def evaluate(misses_split: str | None = None) -> dict[str, Any]:
    detectors = dq.build_detectors(None, None)
    fx = fixture()
    seed = int(fx["split"]["seed"])
    languages: dict[str, Any] = {}
    misses: list[dict[str, Any]] = []
    for language, (labelled, controls) in labelled_sets().items():
        halves = split_values(language, labelled, seed)
        halves_all = {**halves, "all": labelled}
        tpl = fx["templates"][language]
        lang: dict[str, Any] = {"values": {k: len(v) for k, v in halves_all.items()}}
        for condition, carriers in (
            ("structured", dq.STRUCTURED_CARRIERS),
            ("prose_uncued", {"en": dq.PROSE_CARRIERS, "fr": dq_fr.PROSE_CARRIERS,
                              "es": dq_es.PROSE_CARRIERS}[language]),
        ):
            lang[condition] = {
                name: dq._condition(detectors, items, carriers)
                for name, items in halves_all.items()
            }
        cued: dict[str, Any] = {}
        for split in SPLITS:
            templates = {t: v[split] for t, v in tpl.items()}
            sink = misses if split == misses_split else None
            cued[split] = cued_condition(
                detectors, [(language, *it[1:]) for it in halves[split]], templates, sink
            )
        hits = sum(cued[s]["numerator"] for s in SPLITS)
        total = sum(cued[s]["denominator"] for s in SPLITS)
        low, high = dq.wilson(hits, total)
        cued["all"] = {"recall": round(hits / total, 4) if total else 0.0,
                       "ci95": [round(low, 4), round(high, 4)],
                       "numerator": hits, "denominator": total}
        lang["prose_cued"] = cued
        lang["benign_controls"] = benign_controls(detectors, controls)
        languages[language] = lang

    report: dict[str, Any] = {
        "software_version": dq.__version__,
        "detector_tier": "fast (deterministic: regex + dictionaries)",
        "tiers_not_run": ["presidio", "semantic judge"],
        "split": fx["split"],
        "conditions": {
            "structured": "value under the key that names it (detection_quality.py method)",
            "prose_uncued": "value in a sentence with no cue (detection_quality.py method); the honest floor",
            "prose_cued": "value in a sentence that says what it is; (value, template) instances, "
                          "value position checked",
        },
        "languages": languages,
        "hard_negatives": {
            k: v for k, v in dq.hard_negatives().items() if k != "detail"
        },
        "context_hard_negatives": context_negatives(),
    }
    if misses_split:
        report["misses"] = {"split": misses_split, "items": misses}
    return report


def _fmt(c: dict[str, Any]) -> str:
    return f"{c['recall']:.3f} ({c['numerator']}/{c['denominator']})"


def to_markdown(report: dict[str, Any]) -> str:
    out = [
        f"AgentLeak {report['software_version']} · tier: {report['detector_tier']}",
        f"Not run: {', '.join(report['tiers_not_run'])}. Split seed {report['split']['seed']}.",
        "",
        "| Language | Condition | Development | Held-out | All |",
        "|---|---|---:|---:|---:|",
    ]
    for language, lang in report["languages"].items():
        for cond in ("structured", "prose_uncued", "prose_cued"):
            c = lang[cond]
            out.append(f"| {language} | {cond} | {_fmt(c['development'])} | "
                       f"{_fmt(c['held_out'])} | {_fmt(c['all'])} |")
    out += ["", "### Cued prose by data type", "",
            "| Language | Data type | Development | Held-out |", "|---|---|---:|---:|"]
    for language, lang in report["languages"].items():
        dev = {r["data_type"]: r for r in lang["prose_cued"]["development"]["by_data_type"]}
        held = {r["data_type"]: r for r in lang["prose_cued"]["held_out"]["by_data_type"]}
        for t in sorted(dev):
            d, h = dev[t], held.get(t)
            hs = f"{h['recall']:.3f} ({h['hit']}/{h['instances']})" if h else "–"
            out.append(f"| {language} | `{t}` | {d['recall']:.3f} ({d['hit']}/{d['instances']}) | {hs} |")
    hn = report["hard_negatives"]
    ctx = report["context_hard_negatives"]
    out += [
        "", "### False positives", "",
        "| Negative set | Flagged |", "|---|---:|",
        *[f"| benign controls ({lang}) | {v['benign_controls']['detections']} detections / "
          f"{v['benign_controls']['texts']} texts |" for lang, v in report["languages"].items()],
        f"| hard negatives (82, round one) | {hn['flagged']}/{hn['texts']} |",
        f"| context look-alikes, development | {ctx['development']['flagged']}/{ctx['development']['texts']} |",
        f"| context look-alikes, held-out | {ctx['held_out']['flagged']}/{ctx['held_out']['texts']} |",
    ]
    for split in SPLITS:
        for item in ctx[split]["detail"]:
            out.append(f"- {split}: `{item['data_type']}` ({item['rule'] or 'default'}) matched "
                       f"`{item['value']}` in: {item['text']}")
    out += ["", "Reproduce with `python scripts/detection_quality_cued.py`."]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Write the full report as JSON.")
    parser.add_argument("--markdown", help="Write the report as Markdown.")
    parser.add_argument("--misses", choices=SPLITS,
                        help="List the cued misses of one half (tuning reads development only).")
    args = parser.parse_args()
    report = evaluate(args.misses)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        print(f"wrote {args.json}")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report), encoding="utf-8")
        print(f"wrote {args.markdown}")
    if args.misses:
        for m in report["misses"]["items"]:
            print(f"[{m['outcome']}] {m['data_type']}: {m['text']}  -> {m['found']}")
    if not args.json and not args.markdown and not args.misses:
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
