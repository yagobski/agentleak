# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The row-level output of a benchmark: one row per scenario x repetition x
disclosure channel, written as ``rows.csv``.

Rows are plain dicts with fixed keys and plain types, so
``pandas.DataFrame(rows)`` works directly; pandas is never required.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import Any

#: Column name -> type. The order is the CSV column order.
ROW_FIELDS: dict[str, type] = {
    "scenario_id": str,         # unique unit id: "<source>/<id>" (+ "#derived-clean")
    "source": str,              # builtin | pack id
    "origin_id": str,           # id inside the source
    "domain": str,
    "failure_mode": str,        # pattern | norm | hijack
    "adversary": str,           # A0 | A1 | A2 | "" (agentleak_bench only)
    "label": str,               # leaking | clean | live  (by construction)
    "negative_kind": str,       # independent | derived | ""
    "counterpart_of": str,      # the leaking fixture a clean unit is paired with
    "repetition": int,
    "channel": str,             # one of the six disclosure channels
    "channel_findings": int,    # leaked findings on this channel
    "channel_severity_max": int,  # highest AgentRisk level on this channel, 0 = none
    "channel_ri": float,        # per-channel Risk Index
    "channel_data_types": str,  # ';'-joined distinct data types found on this channel
    "channel_leaked": int,      # 1 if the detectors found a leak on this channel
    "reference_leak": str,      # "1"/"0": a ground-truth value is on this channel; "" = no ground truth
    "scenario_leaked": int,     # 1 if the detectors found a leak on any disclosure channel
    "findings": int,            # leaked findings, all channels
    "severity_max": int,
    "ri": float,                # AgentRisk Risk Index
    "wsl": int,
    "rho_s": int,
    "leaked_secrets": int,
    "vault_secrets": int,
    "privacy_score": int,
    "verdict": str,
    "outcome": str,             # leak_detected | no_finding  (never "safe")
    "detection_mode": str,
    "tiers_run": str,           # ';'-joined tiers that actually ran
    "degraded": int,            # 1 if a requested tier did not run
    "trace_sha256": str,
}


def coerce_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a CSV row (all strings) back to typed values."""
    out: dict[str, Any] = {}
    for key, typ in ROW_FIELDS.items():
        value = raw.get(key, "")
        if typ is int:
            out[key] = int(value) if value not in ("", None) else 0
        elif typ is float:
            out[key] = float(value) if value not in ("", None) else 0.0
        else:
            out[key] = "" if value is None else str(value)
    return out


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return repr(round(value, 6))
    return str(value)


def rows_to_csv(rows: Iterable[dict[str, Any]]) -> str:
    """Serialize rows deterministically (fixed columns, ``\\n`` line endings)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(list(ROW_FIELDS))
    for row in rows:
        writer.writerow([_fmt(row.get(k, "")) for k in ROW_FIELDS])
    return buf.getvalue()


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load ``rows.csv`` as a list of typed dicts."""
    with open(path, encoding="utf-8", newline="") as fh:
        return [coerce_row(r) for r in csv.DictReader(fh)]


def scenario_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse channel rows to one record per scenario (repetitions pooled).

    ``leaked`` is 1 if the detectors found a leak in any repetition;
    ``leak_fraction`` is the share of repetitions with a leak (always 0 or 1
    in replay mode). Channel sets are unions over repetitions.
    """
    order: list[str] = []
    acc: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = row["scenario_id"]
        if sid not in acc:
            order.append(sid)
            acc[sid] = {
                "scenario_id": sid,
                "source": row["source"],
                "origin_id": row["origin_id"],
                "domain": row["domain"],
                "failure_mode": row["failure_mode"],
                "adversary": row["adversary"],
                "label": row["label"],
                "negative_kind": row["negative_kind"],
                "counterpart_of": row["counterpart_of"],
                "_reps": {},
                "channels": set(),
                "reference_channels": set(),
                "has_reference": False,
                "data_types": set(),
                "degraded": 0,
            }
        rec = acc[sid]
        rep = rec["_reps"].setdefault(row["repetition"], {
            "leaked": row["scenario_leaked"], "ri": row["ri"], "wsl": row["wsl"],
            "rho_s": row["rho_s"],
        })
        rep["leaked"] = row["scenario_leaked"]
        if row["channel_leaked"]:
            rec["channels"].add(row["channel"])
            rec["data_types"].update(t for t in row["channel_data_types"].split(";") if t)
        if row["reference_leak"] != "":
            rec["has_reference"] = True
            if row["reference_leak"] == "1":
                rec["reference_channels"].add(row["channel"])
        rec["degraded"] = max(rec["degraded"], row["degraded"])
    out = []
    for sid in order:
        rec = acc[sid]
        reps = [rec["_reps"][k] for k in sorted(rec["_reps"])]
        rec.pop("_reps")
        rec["repetitions"] = len(reps)
        rec["leaked"] = int(any(r["leaked"] for r in reps))
        rec["leak_fraction"] = sum(r["leaked"] for r in reps) / len(reps)
        rec["ri"] = sum(r["ri"] for r in reps) / len(reps)
        rec["wsl"] = sum(r["wsl"] for r in reps) / len(reps)
        rec["rho_s"] = sum(r["rho_s"] for r in reps) / len(reps)
        out.append(rec)
    return out


__all__ = ["ROW_FIELDS", "coerce_row", "read_rows", "rows_to_csv", "scenario_table"]
