# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Finding triage: identity of a finding across runs, and the triaged score view.

A reviewer marks a finding true positive, false positive, accepted risk or
needs review. Two properties matter more than the feature itself:

* **The measured result never changes.** Triage is stored beside the run, not
  in it. The Risk Index, privacy score, verdict and gate stay exactly what the
  detectors produced; :func:`triaged_score` computes a second, separately
  labelled figure that excludes findings triaged as false positive, with its
  own numerator and denominator.
* **A decision survives a re-run.** Finding ids are per run, so a decision is
  attached to an *identity*: the emission channel plus a keyed fingerprint of
  the secret (HMAC-SHA256 over project id, data type and the raw value, under
  a server key that is never stored in the database). The raw value is only
  in memory while the run is analysed; only the HMAC is kept. Runs stored
  before fingerprints existed fall back to the masked identity (channel, data
  type, level, masked value), which is what the comparison page matched on.

Everything here is pure except :func:`load_fingerprint_key`, which reads or
creates the key file.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets as _secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agentrisk import DEFAULT_WEIGHTS

# Decisions a reviewer can record. ``untriaged`` clears an earlier decision
# (and is itself kept in the audit trail).
STATES: tuple[str, ...] = ("true_positive", "false_positive", "accepted_risk", "needs_review")
CLEAR_STATE = "untriaged"
ALL_STATES: tuple[str, ...] = (*STATES, CLEAR_STATE)
# A short rationale is required for every state except a confirmed leak.
RATIONALE_REQUIRED: frozenset[str] = frozenset({"false_positive", "accepted_risk", "needs_review"})
RATIONALE_MAX = 1000
MAX_FINDINGS_PER_DECISION = 500
MAX_EXPIRY_DAYS = 3 * 366

FP_VERSION = "fp1"
KEY_ENV = "AGENTLEAK_FINGERPRINT_KEY"
KEY_FILE = "agentleak-fingerprint.key"
_MIN_ENV_KEY = 32


# ----------------------------------------------------------------------
# fingerprint key
# ----------------------------------------------------------------------
def load_fingerprint_key(db_path: str) -> tuple[bytes | None, str]:
    """Return ``(key, origin)`` for keyed finding fingerprints.

    ``AGENTLEAK_FINGERPRINT_KEY`` wins when set (at least 32 characters; a
    hosted deployment can keep it off the database volume). Otherwise a random
    256-bit key lives in ``agentleak-fingerprint.key`` next to the database,
    created once with mode 0600 and never written into the database itself.
    When neither is usable the key is ``None`` and runs use the masked identity.
    """
    env = os.environ.get(KEY_ENV, "").strip()
    if env:
        if len(env) < _MIN_ENV_KEY:
            return None, f"{KEY_ENV} is shorter than {_MIN_ENV_KEY} characters; keyed fingerprints are off"
        return hashlib.sha256(env.encode("utf-8")).digest(), "environment"
    if not db_path or db_path == ":memory:":
        return None, "in-memory database; keyed fingerprints are off"
    path = Path(db_path).resolve().parent / KEY_FILE
    try:
        return _read_key(path), "key file"
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        return None, f"key file unreadable ({exc.__class__.__name__}); keyed fingerprints are off"
    tmp = path.with_name(f".{KEY_FILE}.{os.getpid()}.{_secrets.token_hex(4)}")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(_secrets.token_hex(32) + "\n")
        try:
            # Atomic publish: a concurrent worker either wins the link or
            # reads the winner's complete file, never a half-written one.
            os.link(tmp, path)
        except FileExistsError:
            pass
        return _read_key(path), "key file"
    except (OSError, ValueError) as exc:
        return None, f"cannot create key file ({exc.__class__.__name__}); keyed fingerprints are off"
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _read_key(path: Path) -> bytes:
    text = path.read_text(encoding="ascii").strip()
    key = bytes.fromhex(text)
    if len(key) < 32:
        raise ValueError("key too short")
    return key


def secret_fingerprint(key: bytes, project_id: str, data_type: str, raw_value: str) -> str:
    """Keyed, project-scoped fingerprint of one secret (128 bits, hex).

    Same inputs as AgentRisk's distinct-secret rule (data type + exact value),
    so grouping by it reproduces the measured WSL. Scoped to the project, so
    the same value in two accounts never yields the same fingerprint.
    """
    msg = "\x1f".join((FP_VERSION, project_id, data_type, raw_value)).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:32]


def fingerprints_for(
    key: bytes, project_id: str, report_findings: Iterable[Mapping[str, Any]], raw_findings: Iterable[Any]
) -> dict[str, str]:
    """Map report finding ids to fingerprints, using the in-memory raw values.

    ``raw_findings`` are :class:`~agentleak.core.detector.Finding` objects from
    the analysis (they still hold ``matched_value``); nothing raw is returned.
    """
    raw_by_id = {getattr(f, "finding_id", ""): f for f in raw_findings}
    out: dict[str, str] = {}
    for f in report_findings:
        fid = str(f.get("finding_id", ""))
        raw = raw_by_id.get(fid)
        value = getattr(raw, "matched_value", None) if raw is not None else None
        if fid and isinstance(value, str):
            out[fid] = secret_fingerprint(key, project_id, str(f.get("data_type", "")), value)
    return out


# ----------------------------------------------------------------------
# identity
# ----------------------------------------------------------------------
def masked_key(f: Mapping[str, Any]) -> str:
    """Identity without a fingerprint: what the comparison page matches on."""
    return "m1|{}|{}|{}|{}".format(
        f.get("channel", ""), f.get("data_type", ""), f.get("level", ""), f.get("redacted_value", "")
    )


def identity_key(f: Mapping[str, Any], fingerprint: str | None) -> str:
    """Channel-scoped identity: a decision on one channel does not spread to another."""
    if fingerprint:
        return f"k1|{f.get('channel', '')}|{fingerprint}"
    return masked_key(f)


def _same_finding(decision: Mapping[str, Any], ident: str, masked: str) -> bool:
    d_ident = str(decision.get("identity_key", ""))
    if d_ident.startswith("k1|") and ident.startswith("k1|"):
        return d_ident == ident
    return str(decision.get("masked_key", "")) == masked


@dataclass(frozen=True)
class Resolved:
    finding_id: str
    identity_key: str
    masked_key: str
    state: str  # recorded state ("untriaged" when none)
    effective_state: str  # after expiry
    decision: dict[str, Any] | None
    carried: bool
    expired: bool

    def to_dict(self) -> dict[str, Any]:
        d = self.decision
        return {
            "finding_id": self.finding_id,
            "identity": "fingerprint" if self.identity_key.startswith("k1|") else "masked",
            "state": self.state,
            "effective_state": self.effective_state,
            "expired": self.expired,
            "carried": self.carried,
            "carried_from": (
                {"run_id": d["run_id"], "finding_id": d["finding_id"]} if d and self.carried else None
            ),
            "decision": d,
        }


def resolve(
    report_findings: Iterable[Mapping[str, Any]],
    fingerprints: Mapping[str, str],
    *,
    run_id: str,
    run_created_at: float,
    decisions: Iterable[Mapping[str, Any]],
    now: float,
) -> list[Resolved]:
    """The decision in force for each finding of one run.

    A decision recorded on this run for this finding wins. Otherwise the most
    recent decision on a matching finding of this or an earlier run of the
    same project is carried over. An accepted risk past its expiry is in force
    as *needs review*, and says so.
    """
    decs = list(decisions)
    out: list[Resolved] = []
    for f in report_findings:
        fid = str(f.get("finding_id", ""))
        ident = identity_key(f, fingerprints.get(fid))
        masked = masked_key(f)
        direct = [d for d in decs if d.get("run_id") == run_id and d.get("finding_id") == fid]
        carried = False
        chosen: Mapping[str, Any] | None = None
        if direct:
            chosen = max(direct, key=_order)
        else:
            cands = [
                d for d in decs
                if float(d.get("run_created_at") or 0) <= run_created_at and _same_finding(d, ident, masked)
            ]
            if cands:
                chosen = max(cands, key=_order)
                carried = True
        state = str(chosen["state"]) if chosen else CLEAR_STATE
        expires = chosen.get("expires_at") if chosen else None
        expired = bool(state == "accepted_risk" and expires and float(expires) <= now)
        out.append(
            Resolved(
                finding_id=fid,
                identity_key=ident,
                masked_key=masked,
                state=state,
                effective_state="needs_review" if expired else state,
                decision=dict(chosen) if chosen else None,
                carried=carried,
                expired=expired,
            )
        )
    return out


def _order(d: Mapping[str, Any]) -> tuple[float, str]:
    return (float(d.get("created_at") or 0), str(d.get("id", "")))


def history_for(
    finding: Mapping[str, Any], fingerprint: str | None, decisions: Iterable[Mapping[str, Any]], *, run_id: str
) -> list[dict[str, Any]]:
    """Every decision on this finding's identity in the project, newest first."""
    ident = identity_key(finding, fingerprint)
    masked = masked_key(finding)
    fid = str(finding.get("finding_id", ""))
    rows = [
        dict(d) for d in decisions
        if (d.get("run_id") == run_id and d.get("finding_id") == fid) or _same_finding(d, ident, masked)
    ]
    rows.sort(key=_order, reverse=True)
    return rows


# ----------------------------------------------------------------------
# triaged score view
# ----------------------------------------------------------------------
def summarize(resolved: list[Resolved]) -> dict[str, int]:
    """Counts per state in force, with the total as denominator."""
    counts = {s: 0 for s in ALL_STATES}
    for r in resolved:
        counts[r.effective_state] = counts.get(r.effective_state, 0) + 1
    counts["total"] = len(resolved)
    counts["triaged"] = len(resolved) - counts[CLEAR_STATE]
    counts["expired"] = sum(1 for r in resolved if r.expired)
    counts["carried"] = sum(1 for r in resolved if r.carried and r.state != CLEAR_STATE)
    return counts


def triaged_score(
    report: Mapping[str, Any], resolved: list[Resolved], fingerprints: Mapping[str, str]
) -> dict[str, Any]:
    """The measured score, and a second figure excluding false positives.

    Uses the run's own weights and ρ_S; the AgentRisk formula is unchanged
    (RI = WSL / ρ_S, privacy score = round(100 × (1 − RI))). A secret leaves
    the numerator only when *every* finding of it is triaged false positive;
    ρ_S is kept, because a false positive leaves the leaked set, not the vault
    the run was scored against. Accepted risks still count: they are leaks.
    """
    findings = list(report.get("findings") or [])
    agentrisk = report.get("agentrisk") or {}
    weights = list(agentrisk.get("weights") or DEFAULT_WEIGHTS)

    def w(level: Any) -> int:
        try:
            lvl = max(1, min(4, int(level)))
        except (TypeError, ValueError):
            lvl = 1
        return int(weights[lvl - 1])

    state_of = {r.finding_id: r.effective_state for r in resolved}
    groups: dict[str, dict[str, Any]] = {}
    for f in findings:
        fid = str(f.get("finding_id", ""))
        fp = fingerprints.get(fid)
        gid = f"k|{fp}" if fp else f"m|{f.get('data_type', '')}|{f.get('redacted_value', '')}"
        g = groups.setdefault(gid, {"level": f.get("level", 1), "all_fp": True})
        if state_of.get(fid) != "false_positive":
            g["all_fp"] = False

    wsl = int(report.get("wsl") or 0)
    rho_s = int(report.get("rho_s") or 0)
    leaked = int((report.get("summary") or {}).get("leaked_secrets") or 0)
    excluded = [g for g in groups.values() if g["all_fp"]]
    removed = sum(w(g["level"]) for g in excluded)
    group_wsl = sum(w(g["level"]) for g in groups.values())
    keyed = bool(findings) and all(fingerprints.get(str(f.get("finding_id", ""))) for f in findings)
    exact = keyed and group_wsl == wsl
    t_wsl = max(0, wsl - removed)
    t_ri = (t_wsl / rho_s) if rho_s > 0 else 0.0
    fp_findings = sum(1 for f in findings if state_of.get(str(f.get("finding_id", ""))) == "false_positive")
    return {
        "measured": {
            "risk_index": report.get("risk_index"),
            "privacy_score": report.get("privacy_score"),
            "verdict": report.get("verdict"),
            "blocked": report.get("blocked"),
            "wsl": wsl,
            "rho_s": rho_s,
            "leaked_secrets": leaked,
        },
        "triaged": {
            "label": "excluding findings triaged as false positive",
            "risk_index": round(t_ri, 4),
            "privacy_score": max(0, round(100.0 * (1.0 - t_ri))),
            "wsl": t_wsl,
            "rho_s": rho_s,
            "leaked_secrets": max(0, leaked - len(excluded)),
            "false_positive_findings": fp_findings,
            "total_findings": len(findings),
            "excluded_secrets": len(excluded),
            "exact": exact,
            "method": "fingerprint" if keyed else "masked value",
            "changed": removed > 0,
        },
    }
