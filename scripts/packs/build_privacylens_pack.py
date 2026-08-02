"""Curate a balanced PrivacyLens pack for AgentLeak.

Ships a subset rather than all 493: the pack travels inside the wheel, and a
balanced slice across the three provenance sources and the four outbound
channels tests more than a bigger unbalanced one would. Only the fields the
converter reads are kept (the long `vignette.story` prose is dropped).
"""

import json
import os
import re
from collections import Counter, defaultdict

SRC = "privacylens.json"
OUT = "privacylens_ci.json"
TARGET = 120

records = json.load(open(SRC))


def final_channel(record):
    return record["trajectory"].get("final_action", "unknown")


def trim(record):
    """Keep only what privacylens_to_trace() and normalize_upload() read."""
    seed, traj = record["seed"], record["trajectory"]
    return {
        "name": record["name"],
        "seed": {
            "data_type": seed.get("data_type", ""),
            "data_subject": seed.get("data_subject", ""),
            "data_sender": seed.get("data_sender", ""),
            "data_recipient": seed.get("data_recipient", ""),
            "transmission_principle": seed.get("transmission_principle", ""),
            "source": seed.get("source", ""),
        },
        "trajectory": {
            "user_name": traj.get("user_name", ""),
            "user_instruction": traj.get("user_instruction", ""),
            "toolkits": traj.get("toolkits", []),
            "executable_trajectory": traj.get("executable_trajectory", ""),
            "final_action": traj.get("final_action", ""),
            "sensitive_info_items": traj.get("sensitive_info_items", []),
        },
    }


# Round-robin across (source, outbound channel) buckets so the pack stays
# balanced instead of inheriting the raw dataset's skew toward Messenger.
buckets = defaultdict(list)
for r in records:
    buckets[(r["seed"].get("source", "?"), final_channel(r))].append(r)

# Prefer shorter trajectories inside each bucket: same coverage, smaller pack.
for key in buckets:
    buckets[key].sort(key=lambda r: len(r["trajectory"]["executable_trajectory"]))

picked, keys = [], sorted(buckets)
while len(picked) < TARGET:
    took = False
    for key in keys:
        if buckets[key] and len(picked) < TARGET:
            picked.append(buckets[key].pop(0))
            took = True
    if not took:
        break

# Deterministic order so re-running the build produces an identical file.
picked.sort(key=lambda r: int(re.sub(r"\D", "", r["name"]) or 0))

pack = {
    "id": "privacylens_ci",
    "name": "PrivacyLens (contextual integrity)",
    "description": (
        "Contextual-integrity scenarios: an agent pulls private context in through "
        "its tools, then acts toward a recipient the norm says must not receive it. "
        "Each ships the ground-truth facts that must not travel, wired as semantic "
        "canaries, so the scenario scores deterministically without an LLM tier."
    ),
    "source": "SALT-NLP/PrivacyLens (NeurIPS 2024 D&B, CC-BY-4.0)",
    "source_url": "https://huggingface.co/datasets/SALT-NLP/PrivacyLens",
    "license": "CC-BY-4.0",
    "attribution": (
        "Derived from PrivacyLens by Shao et al. (NeurIPS 2024 Datasets & Benchmarks), "
        "licensed CC-BY-4.0. Records were subset and reshaped into AgentLeak traces; "
        "the sensitive facts and trajectories are the authors' data."
    ),
    "format": "privacylens",
    "scenarios": [trim(r) for r in picked],
}

json.dump(pack, open(OUT, "w"), indent=1, ensure_ascii=False)

print(f"scenarios: {len(picked)}  ({os.path.getsize(OUT) / 1024:.0f} KB)")
print("par source:  ", dict(Counter(r['seed']['source'] for r in picked)))
print("par canal:   ", dict(Counter(final_channel(r) for r in picked)))
print("destinataires distincts:", len({r['seed']['data_recipient'] for r in picked}))
print("types de données distincts:", len({r['seed']['data_type'] for r in picked}))
