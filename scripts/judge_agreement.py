#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Agreement between the LLM-judge tier and the PrivacyLens labels.

AgentLeak's semantic judge (``detectors/llm_judge.py``) is optional and, until
this harness, unmeasured. This script measures it: it asks a judge endpoint
about each labelled statement of the PrivacyLens-derived pack and reports
Cohen's kappa against the labels, with a confidence interval, the confusion
table, the judge model and a hash of the prompt.

**No number exists yet.** No model key is available where this harness was
written, so it has only been run against the fake local judge in
``tests/test_judge_agreement.py``, which checks the arithmetic. The command that
would produce the first published figure is::

    export JUDGE_KEY=...            # your key; never passed on the command line
    python scripts/judge_agreement.py \\
        --endpoint https://api.openai.com/v1 --model gpt-4o-mini \\
        --api-key-env JUDGE_KEY --json judge-agreement.json

Off by default and bring-your-own-key: without ``--endpoint`` nothing is sent
anywhere. With it, the statements below (synthetic PrivacyLens text, CC-BY-4.0)
are sent to that endpoint and nowhere else.

Items and labels
----------------
* **Positive (label 1)**: every ``sensitive_info_items`` fact of every scenario
  in ``scenarios/packs/privacylens_ci.json``: the facts PrivacyLens says must
  not travel.
* **Negative (label 0)**: sentences of the same scenario's tool observations
  that share little with every listed fact (content-word Jaccard below 0.2,
  at least six words), at most as many as the scenario has positives, chosen
  with a fixed seed. PrivacyLens does not label negatives; these are derived,
  and some may still be personal. That is label noise against the judge, and it
  is stated here rather than hidden.

Decision rule
-------------
The judge sees the statement alone, with the shipping judge's system prompt
(``llm_judge._SYSTEM_PROMPT``), and says "sensitive" when it returns at least
one hit at or above the shipping threshold (0.72 unless ``--threshold``). A
call that fails or returns unparseable output is counted as an error and left
out of kappa, never scored as "not sensitive".

Statistics
----------
Cohen's kappa, with a 95% interval from a cluster bootstrap over scenarios
(items of one scenario are not independent), seeded. Observed agreement, the
confusion table and per-class counts are reported with it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent / "src"))

import agentleak  # noqa: E402
from agentleak.detectors.llm_judge import _SYSTEM_PROMPT  # noqa: E402

PACK = SCRIPTS.parent / "src" / "agentleak" / "scenarios" / "packs" / "privacylens_ci.json"
SEED = 20261115
_WORD_RE = re.compile(r"[a-z0-9']+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_STOP = frozenset(
    "a an the and or of to in on for with at by from is are was were be been this that "
    "these those it its as he she they his her their our we you your i my me".split()
)

Item = dict[str, Any]  # {"scenario", "text", "label"}
Judge = Callable[[str], list[dict[str, Any]]]


def prompt_hash() -> str:
    return hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _observation_sentences(trajectory: str) -> list[str]:
    """Sentences of the string values inside each ``Observation:`` JSON."""
    out: list[str] = []
    decoder = json.JSONDecoder()
    for m in re.finditer(r"Observation:\s*", trajectory):
        try:
            data, _end = decoder.raw_decode(trajectory, m.end())
        except json.JSONDecodeError:
            continue
        stack: list[Any] = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, str):
                out.extend(s.strip() for s in _SENTENCE_RE.split(node) if s.strip())
    return out


def load_items(pack: Path = PACK, seed: int = SEED) -> list[Item]:
    data = json.loads(pack.read_text(encoding="utf-8"))
    rng = random.Random(seed)
    items: list[Item] = []
    for scenario in data["scenarios"]:
        traj = scenario.get("trajectory") or {}
        facts = [f for f in traj.get("sensitive_info_items") or [] if isinstance(f, str)]
        if not facts:
            continue
        name = scenario.get("name", "")
        items.extend({"scenario": name, "text": f, "label": 1} for f in facts)
        fact_words = [_content_words(f) for f in facts]
        candidates = sorted({
            s for s in _observation_sentences(traj.get("executable_trajectory", ""))
            if len(s.split()) >= 6
            and all(_jaccard(_content_words(s), fw) < 0.2 for fw in fact_words)
        })
        rng.shuffle(candidates)
        items.extend({"scenario": name, "text": s, "label": 0} for s in candidates[:len(facts)])
    return items


def endpoint_judge(endpoint: str, model: str, api_key: str, timeout: float = 60.0) -> tuple[Judge, dict[str, str]]:
    """A judge over an OpenAI-compatible endpoint, same request shape as the
    shipping judge. Raises on transport or parse errors so they are counted."""
    seen: dict[str, str] = {"model_requested": model}

    def judge(text: str) -> list[dict[str, Any]]:
        body = json.dumps({
            "model": model, "temperature": 0.0,
            "messages": [{"role": "system", "content": _SYSTEM_PROMPT},
                         {"role": "user", "content": text[:4000]}],
        }).encode()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(f"{endpoint.rstrip('/')}/chat/completions", data=body,
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (user-given endpoint)
            payload = json.loads(resp.read().decode())
        if payload.get("model"):
            seen["model_reported"] = str(payload["model"])
        content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        clean = content.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(clean)
        if not isinstance(result, list):
            raise ValueError("judge did not return a JSON array")
        return result

    return judge, seen


def cohen_kappa(table: dict[str, int]) -> float:
    """Kappa from a 2x2 table keyed tp, fp, fn, tn (judge vs label)."""
    n = sum(table.values())
    if n == 0:
        return float("nan")
    po = (table["tp"] + table["tn"]) / n
    judge_yes = (table["tp"] + table["fp"]) / n
    label_yes = (table["tp"] + table["fn"]) / n
    pe = judge_yes * label_yes + (1 - judge_yes) * (1 - label_yes)
    if pe == 1:
        return 1.0 if po == 1 else float("nan")
    return (po - pe) / (1 - pe)


def _table(pairs: list[tuple[int, int]]) -> dict[str, int]:
    t = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for judged, label in pairs:
        t[("t" if judged == label else "f") + ("p" if judged else "n")] += 1
    return t


def bootstrap_ci(by_scenario: dict[str, list[tuple[int, int]]], *, resamples: int = 2000,
                 seed: int = SEED) -> tuple[float, float]:
    """95% percentile interval of kappa, resampling whole scenarios."""
    keys = sorted(by_scenario)
    if not keys:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(resamples):
        pairs = [p for _ in keys for p in by_scenario[rng.choice(keys)]]
        k = cohen_kappa(_table(pairs))
        if not math.isnan(k):
            stats.append(k)
    if not stats:
        return (float("nan"), float("nan"))
    stats.sort()
    return (stats[int(0.025 * (len(stats) - 1))], stats[int(0.975 * (len(stats) - 1))])


def evaluate(items: list[Item], judge: Judge, *, threshold: float = 0.72,
             model: dict[str, str] | None = None, resamples: int = 2000) -> dict[str, Any]:
    by_scenario: dict[str, list[tuple[int, int]]] = {}
    errors: list[dict[str, str]] = []
    for item in items:
        try:
            hits = judge(item["text"])
        except Exception as exc:  # counted, never scored as "not sensitive"
            errors.append({"scenario": item["scenario"], "error": type(exc).__name__})
            continue
        judged = int(any(
            isinstance(h, dict) and float(h.get("confidence", 0.0)) >= threshold for h in hits
        ))
        by_scenario.setdefault(item["scenario"], []).append((judged, item["label"]))
    pairs = [p for ps in by_scenario.values() for p in ps]
    table = _table(pairs)
    n = len(pairs)
    low, high = bootstrap_ci(by_scenario, resamples=resamples)
    kappa = cohen_kappa(table)
    return {
        "software_version": agentleak.__version__,
        "tier": "semantic judge (LLM), decision: >=1 hit at or above threshold",
        "judge_model": model or {},
        "prompt": "agentleak.detectors.llm_judge._SYSTEM_PROMPT",
        "prompt_sha256": prompt_hash(),
        "threshold": threshold,
        "source": f"{PACK.name}: sensitive_info_items (label 1) and derived negatives (label 0)",
        "items": len(items),
        "scored": n,
        "errors": len(errors),
        "error_detail": errors[:20],
        "positives": table["tp"] + table["fn"],
        "negatives": table["fp"] + table["tn"],
        "confusion": table,
        "observed_agreement": round((table["tp"] + table["tn"]) / n, 4) if n else None,
        "kappa": None if math.isnan(kappa) else round(kappa, 4),
        "kappa_ci95": [None if math.isnan(low) else round(low, 4),
                       None if math.isnan(high) else round(high, 4)],
        "ci_method": f"cluster bootstrap over {len(by_scenario)} scenarios, "
                     f"{resamples} resamples, seed {SEED}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", help="OpenAI-compatible base URL (BYOK). Off when absent.")
    parser.add_argument("--model", help="Judge model name sent to the endpoint.")
    parser.add_argument("--api-key-env", default="",
                        help="Name of the environment variable holding the key.")
    parser.add_argument("--threshold", type=float, default=0.72)
    parser.add_argument("--limit", type=int, default=0, help="Score only the first N items.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List the item counts and prompt hash; call nothing.")
    parser.add_argument("--json", help="Write the result as JSON.")
    args = parser.parse_args()

    items = load_items()
    if args.limit:
        items = items[:args.limit]
    positives = sum(i["label"] for i in items)
    if args.dry_run or not args.endpoint:
        print(f"{len(items)} items ({positives} labelled sensitive, {len(items) - positives} "
              f"derived negatives) from {PACK.name}; prompt sha256 {prompt_hash()}")
        if not args.endpoint and not args.dry_run:
            print("No --endpoint given: nothing was sent. See --help for the command.")
            return 2
        return 0
    if not args.model:
        parser.error("--model is required with --endpoint")
    api_key = os.environ.get(args.api_key_env, "") if args.api_key_env else ""
    judge, seen = endpoint_judge(args.endpoint, args.model, api_key)
    result = evaluate(items, judge, threshold=args.threshold, model=seen)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "error_detail"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
