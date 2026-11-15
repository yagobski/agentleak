# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Turn the real tool outputs into the small fixtures committed next to this file.

Run with the Inspect AI virtual environment's Python (it can read and write the
zstd-compressed members of an ``.eval`` log)::

    python trim_fixtures.py <scratch-dir> <fixtures-dir>

Trimming only removes bulk (token counters, Inspect ``events``, garak's
configuration dump, the long DAN prompt body) and local absolute paths; every
key an importer reads is kept exactly as the tool wrote it.
"""

from __future__ import annotations

import glob
import json
import sys
import zipfile
from pathlib import Path

scratch, out = Path(sys.argv[1]), Path(sys.argv[2])


def dump(name: str, data: object) -> None:
    (out / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# promptfoo 0.125.1 ------------------------------------------------------
for run, name in (("run1", "promptfoo_0.125.1_plain.json"), ("run2", "promptfoo_0.125.1_traced.json")):
    data = json.loads((scratch / "promptfoo" / run / "results.json").read_text())
    data["config"].pop("basePath", None)
    for row in data["results"]["results"]:
        for key in ("tokenUsage",):
            row.pop(key, None)
        if isinstance(row.get("response"), dict):
            row["response"].pop("tokenUsage", None)
        if isinstance(row.get("gradingResult"), dict):
            row["gradingResult"].pop("tokensUsed", None)
    for prompt in data["results"].get("prompts", []):
        prompt.pop("metrics", None)
    dump(name, data)

# Inspect AI 0.3.290 -----------------------------------------------------
import inspect_ai._util.zipfile  # noqa: E402,F401  (registers zstd on Python < 3.14)

src = Path(glob.glob(str(scratch / "inspect" / "run" / "logs2" / "*.eval"))[0])
(out / "inspect_0.3.290.eval").write_bytes(src.read_bytes())     # untouched, zstd members
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out / "inspect_0.3.290_deflate.eval", "w",
                                                  compression=zipfile.ZIP_DEFLATED) as zout:
    for info in zin.infolist():                                  # same members, deflate
        zout.writestr(info.filename, zin.read(info.filename))
log = json.loads(Path(glob.glob(str(scratch / "inspect" / "run" / "logs2_json" / "*.json"))[0]).read_text())
log["eval"]["model_args"] = {}
for sample in log.get("samples", []):
    for key in ("events", "events_data", "model_usage", "role_usage"):
        sample.pop(key, None)
dump("inspect_0.3.290.json", log)

# garak 0.17.1 -----------------------------------------------------------
rows = [json.loads(line) for line in
        (scratch / "garak" / "run" / "xdg_data" / "garak" / "garak_runs" / "sample.report.jsonl")
        .read_text().splitlines() if line.strip()]
kept = []
for row in rows:
    kind = row.get("entry_type")
    if kind == "start_run setup":
        row = {k: v for k, v in row.items()
               if k in ("entry_type", "_config.version", "transient.run_id", "plugins.target_type",
                        "plugins.target_name", "plugins.probe_spec", "run.generations")}
    elif kind in ("digest", "plugin_cache", "probe_summary"):
        continue
    elif kind == "attempt" and row["probe_classname"] == "test.Test" and row["seq"] > 1:
        continue
    elif kind == "attempt":
        for holder in [row["prompt"], *row.get("conversations", []),
                       row.get("notes", {}).get("pre_translation_prompt") or {"turns": []}]:
            for turn in holder["turns"]:
                text = turn["content"]["text"]
                if len(text) > 300:
                    turn["content"]["text"] = text[:300] + " [trimmed]"
    kept.append(row)
(out / "garak_0.17.1.report.jsonl").write_text(
    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")

# PyRIT 1.2.0 ------------------------------------------------------------
for name in ("scenario_conversations.json", "conversation.json"):
    data = json.loads((scratch / "pyrit" / "run" / name).read_text())
    dump(f"pyrit_1.2.0_{name}", data)
