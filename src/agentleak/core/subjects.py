# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Whose data is this, and did it end up in somebody else's session?

Every other part of this project scores one trace against itself. That is a real
limit, and it is the one the 2026 literature spent the year on — PersistBench,
CIMemories, PiSAs all study the same thing: an agent with memory that outlives
the request, in a deployment that serves more than one person.

The failure is invisible to per-run analysis. Alice's diagnosis is written to
shared memory in one run; a later run answering Bob repeats it. Both runs are
scored independently, both may even score *well*, and nothing anywhere says the
second one disclosed the first one's data. The leak lives in the gap between two
traces, which is exactly where nobody was looking.

This module closes the gap with a per-project ledger of which subject each
secret belongs to. When a run discloses a secret first seen under a different
subject, that is a cross-subject disclosure, and it is reported as its own kind
of finding rather than folded into the Risk Index — the secret genuinely did
leak in this trace and is already scored there. What is new is the attribution,
and attribution is a different claim from severity.

**The ledger never stores a secret.** It stores a salted fingerprint, so it can
recognise the same value again without holding it. A file that records who owns
which secret is precisely the file you least want readable, and a privacy tool
that builds one would be making the leak it exists to find.

Runs that declare no subject are not judged. An undeclared subject cannot be
compared against anything, and guessing would invent an owner for data whose
owner nobody stated.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "SubjectLedger",
    "CrossSubjectDisclosure",
    "secret_fingerprint",
    "subject_of",
]

LEDGER_DIR = ".agentleak"
LEDGER_FILE = "subjects.jsonl"

# Baseline channels: where data legitimately *enters* the agent. A secret
# arriving here is attributed to the run's subject, but arriving is not
# disclosing, so it never raises a violation on its own.
_SOURCE_CHANNELS = frozenset({"user_input", "tool_response"})


def _salt(path: Path) -> str:
    """A per-ledger salt, created once beside it.

    Without it the fingerprints are a plain dictionary attack away from the
    values they stand for: the space of SINs is small enough to enumerate. The
    salt makes a stolen ledger useless anywhere but the deployment that wrote
    it, which is the most a local file can honestly offer.
    """
    salt_path = path.with_suffix(".salt")
    if salt_path.exists():
        return salt_path.read_text().strip()
    salt = os.urandom(32).hex()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt_path.write_text(salt)
    try:
        salt_path.chmod(0o600)
    except OSError:  # pragma: no cover - filesystem without chmod
        pass
    return salt


def secret_fingerprint(data_type: str, value: str, *, salt: str = "") -> str:
    """Recognise a secret again without keeping it."""
    normalized = " ".join(str(value).split()).casefold()
    digest = hashlib.sha256(f"{salt}\x00{data_type}\x00{normalized}".encode())
    return digest.hexdigest()[:24]


def subject_of(trace: Any, finding: Any = None) -> str:
    """Whose data this run is about.

    An event may name its own subject — one run can touch several people's
    records — and otherwise the run's subject applies. Empty when nobody said.
    """
    if finding is not None:
        metadata = getattr(finding, "metadata", None) or {}
        event_subject = str(metadata.get("subject") or "").strip()
        if event_subject:
            return event_subject
    return str(getattr(trace, "subject", "") or "").strip()


@dataclass
class CrossSubjectDisclosure:
    """One secret disclosed in a run belonging to a different subject."""

    data_type: str
    fingerprint: str
    owner: str
    disclosed_to: str
    channel: str
    finding_id: str = ""
    first_seen_run: str = ""
    first_seen_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_type": self.data_type,
            "fingerprint": self.fingerprint,
            "owner": self.owner,
            "disclosed_to": self.disclosed_to,
            "channel": self.channel,
            "finding_id": self.finding_id,
            "first_seen_run": self.first_seen_run,
            "first_seen_at": self.first_seen_at,
        }

    def describe(self) -> str:
        return (
            f"{self.data_type} belonging to '{self.owner}' was disclosed on "
            f"{self.channel} during a run for '{self.disclosed_to}' "
            f"(first seen in run {self.first_seen_run or 'an earlier run'})"
        )


@dataclass
class SubjectEvaluation:
    """What the ledger concluded about one run."""

    enabled: bool = False
    subject: str = ""
    disclosures: list[CrossSubjectDisclosure] = field(default_factory=list)
    secrets_attributed: int = 0
    reason: str = ""

    @property
    def passed(self) -> bool:
        return not self.disclosures

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "subject": self.subject,
            "passed": self.passed,
            "secrets_attributed": self.secrets_attributed,
            "cross_subject_disclosures": [d.to_dict() for d in self.disclosures],
            "reason": self.reason,
        }


class SubjectLedger:
    """Which subject each secret belongs to, remembered across runs."""

    def __init__(self, root: str | os.PathLike[str] | None = None, *,
                 path: str | os.PathLike[str] | None = None) -> None:
        if path is not None:
            self.path = Path(path)
        else:
            self.path = Path(root or ".").resolve() / LEDGER_DIR / LEDGER_FILE
        self._salt: str | None = None
        self._index: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    @property
    def salt(self) -> str:
        if self._salt is None:
            self._salt = _salt(self.path)
        return self._salt

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._index is not None:
            return self._index
        index: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        # A hand-edited or truncated ledger is a convenience
                        # that failed, never a reason to fail the analysis.
                        continue
                    fingerprint = record.get("fingerprint")
                    if fingerprint and fingerprint not in index:
                        index[fingerprint] = record
        self._index = index
        return index

    def _append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        index = self._load()
        index.setdefault(record["fingerprint"], record)

    # ------------------------------------------------------------------
    def evaluate(
        self,
        findings: Iterable[Any],
        *,
        trace: Any = None,
        run_id: str = "",
        subject: str = "",
        record: bool = True,
    ) -> SubjectEvaluation:
        """Attribute this run's secrets, and report any that belong elsewhere.

        Sightings are recorded from *every* channel, because a secret arriving
        on ``tool_response`` still tells us whose it is. Violations are raised
        only for disclosure channels: arriving is not disclosing.
        """
        run_subject = (subject or subject_of(trace)).strip()
        if not run_subject:
            return SubjectEvaluation(
                enabled=False,
                reason=(
                    "no subject declared for this run, so its secrets cannot be "
                    "attributed to anyone; set Trace.subject or an event's "
                    "metadata['subject'] to enable cross-session checking"
                ),
            )

        known = self._load()
        evaluation = SubjectEvaluation(
            enabled=True, subject=run_subject, reason="attributed against the project ledger"
        )
        seen_this_run: set[str] = set()
        # One disclosure per secret per channel. Coalescing unifies a secret's
        # *identity* but deliberately keeps every finding, so two detectors
        # agreeing about one value would otherwise be reported as two separate
        # cross-subject events — the same inflation this project fixed in
        # scoring, reappearing one layer up.
        reported: set[tuple[str, str]] = set()

        for finding in findings:
            data_type = str(getattr(finding, "data_type", ""))
            value = str(getattr(finding, "matched_value", ""))
            if not data_type or not value:
                continue
            owner = subject_of(trace, finding) or run_subject
            fingerprint = secret_fingerprint(data_type, value, salt=self.salt)
            prior = known.get(fingerprint)

            if prior is None:
                if fingerprint not in seen_this_run:
                    seen_this_run.add(fingerprint)
                    evaluation.secrets_attributed += 1
                    if record:
                        self._append({
                            "fingerprint": fingerprint,
                            "data_type": data_type,
                            "subject": owner,
                            "run_id": run_id or str(getattr(trace, "run_id", "")),
                            "first_seen_at": time.time(),
                        })
                continue

            prior_subject = str(prior.get("subject") or "")
            channel = str(getattr(finding, "channel", ""))
            if (
                prior_subject
                and prior_subject != owner
                and channel not in _SOURCE_CHANNELS
                and (fingerprint, channel) not in reported
            ):
                reported.add((fingerprint, channel))
                evaluation.disclosures.append(CrossSubjectDisclosure(
                    data_type=data_type,
                    fingerprint=fingerprint,
                    owner=prior_subject,
                    disclosed_to=owner,
                    channel=channel,
                    finding_id=str(getattr(finding, "finding_id", "")),
                    first_seen_run=str(prior.get("run_id") or ""),
                    first_seen_at=float(prior.get("first_seen_at") or 0.0),
                ))

        return evaluation

    # ------------------------------------------------------------------
    def subjects(self) -> list[str]:
        return sorted({str(r.get("subject") or "") for r in self._load().values()} - {""})

    def summary(self) -> dict[str, Any]:
        records = self._load()
        by_subject: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for record in records.values():
            by_subject[str(record.get("subject") or "?")] = (
                by_subject.get(str(record.get("subject") or "?"), 0) + 1
            )
            by_type[str(record.get("data_type") or "?")] = (
                by_type.get(str(record.get("data_type") or "?"), 0) + 1
            )
        return {
            "path": str(self.path),
            "secrets_tracked": len(records),
            "subjects": len(by_subject),
            "by_subject": dict(sorted(by_subject.items())),
            "by_data_type": dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))),
        }

    def forget(self, subject: str) -> int:
        """Drop every secret attributed to one subject, and say how many.

        Erasure is a right, not a feature request: GDPR Article 17 and Law 25's
        equivalent both mean a subject can require their data gone, and a
        fingerprint of their SIN is still about them. Rewrites the ledger
        without them.
        """
        records = [r for r in self._load().values()]
        keep = [r for r in records if str(r.get("subject") or "") != subject]
        removed = len(records) - len(keep)
        if removed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as handle:
                for record in keep:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._index = None
        return removed


def evaluate_subjects(
    ledger: SubjectLedger | None,
    findings: Sequence[Any],
    *,
    trace: Any = None,
    subject: str = "",
) -> SubjectEvaluation:
    """Convenience wrapper: no ledger configured means no opinion."""
    if ledger is None:
        return SubjectEvaluation(enabled=False, reason="no subject ledger configured")
    return ledger.evaluate(
        findings, trace=trace, run_id=str(getattr(trace, "run_id", "")), subject=subject
    )
