# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""An append-only, hash-chained record of what an agent was allowed to emit.

Since 2 August 2026 the Commission's enforcement powers over general-purpose AI
apply, and what supervisory review asks for is not a score. It is an
*attributable audit trail*: evidence that an agent's actions, and its tools'
actions, stayed inside approved risk bounds over the lifetime of the system.
A report generated on demand cannot answer that, because it is generated on
demand — nothing stops it being generated differently later.

This is the other kind of artefact. Every decision the runtime gateway makes is
appended as one line, and each line carries the hash of the line before it, so
the file is a chain:

    entry_n.previous == sha256(canonical_json(entry_{n-1}))

Editing any earlier entry breaks every hash after it, and :func:`verify` says
where. That is not tamper-*proof* — anyone who can write the file can rewrite
the whole chain — but it is tamper-*evident*, which is the property an auditor
actually needs and the one a plain log does not have. Pair it with append-only
storage or an external anchor for the stronger claim.

**No secret values are ever written.** An evidence log is exactly the file most
likely to be copied into a ticket, a bucket, or an email, so it records what was
found, where it was going and what was decided — never what the value was. The
one thing that would make this log the leak it exists to prevent is the one
thing it does not contain.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["EvidenceEntry", "EvidenceLog", "VerificationResult", "chain_hash", "verify"]

GENESIS = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    """Stable serialisation, so a hash depends on content and not key order."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chain_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass
class EvidenceEntry:
    """One decision, as it is written to the chain."""

    sequence: int
    timestamp: float
    previous: str
    action: str                      # allow | redact | block
    tool: str = ""
    recipient: str = ""
    purpose: str = ""
    data_types: tuple[str, ...] = ()
    reason: str = ""
    run_id: str = ""
    agent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        """The hashed body. Everything except the hash of this entry itself."""
        return {
            "sequence": self.sequence,
            "timestamp": round(self.timestamp, 6),
            "previous": self.previous,
            "action": self.action,
            "tool": self.tool,
            "recipient": self.recipient,
            "purpose": self.purpose,
            "data_types": sorted(self.data_types),
            "reason": self.reason,
            "run_id": self.run_id,
            "agent": self.agent,
            "metadata": self.metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        body = self.payload()
        return {**body, "hash": chain_hash(body)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EvidenceEntry:
        return cls(
            sequence=int(raw.get("sequence", 0)),
            timestamp=float(raw.get("timestamp", 0.0)),
            previous=str(raw.get("previous", GENESIS)),
            action=str(raw.get("action", "")),
            tool=str(raw.get("tool", "")),
            recipient=str(raw.get("recipient", "")),
            purpose=str(raw.get("purpose", "")),
            data_types=tuple(raw.get("data_types") or ()),
            reason=str(raw.get("reason", "")),
            run_id=str(raw.get("run_id", "")),
            agent=str(raw.get("agent", "")),
            metadata=dict(raw.get("metadata") or {}),
        )


@dataclass
class VerificationResult:
    ok: bool
    entries: int
    broken_at: int | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "entries": self.entries,
            "broken_at": self.broken_at,
            "detail": self.detail,
        }


class EvidenceLog:
    """Append-only JSONL, one decision per line, each chained to the last."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._last_hash = GENESIS
        self._sequence = 0
        if self.path.exists():
            self._resume()

    # ------------------------------------------------------------------
    def _resume(self) -> None:
        """Pick the chain up where it was left, so restarts do not fork it."""
        last: dict[str, Any] | None = None
        for raw in self._read_raw():
            last = raw
        if last is not None:
            self._sequence = int(last.get("sequence", 0)) + 1
            self._last_hash = str(last.get("hash") or chain_hash(
                EvidenceEntry.from_dict(last).payload()
            ))

    def _read_raw(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # A truncated final line is a crash, not a forgery. Stop
                    # reading rather than pretending the rest is intact.
                    return

    # ------------------------------------------------------------------
    def append(
        self,
        *,
        action: str,
        tool: str = "",
        recipient: str = "",
        purpose: str = "",
        data_types: Iterable[str] = (),
        reason: str = "",
        run_id: str = "",
        agent: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceEntry:
        """Record one decision and return the entry that was written."""
        entry = EvidenceEntry(
            sequence=self._sequence,
            timestamp=time.time(),
            previous=self._last_hash,
            action=action,
            tool=tool,
            recipient=recipient,
            purpose=purpose,
            data_types=tuple(sorted(set(data_types))),
            reason=reason,
            run_id=run_id,
            agent=agent,
            metadata=dict(metadata or {}),
        )
        record = entry.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Append and flush per line: a gateway that crashes mid-run must leave
        # the decisions it already made on disk, or the log proves nothing
        # about the interesting runs.
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._last_hash = record["hash"]
        self._sequence += 1
        return entry

    def entries(self) -> list[EvidenceEntry]:
        return [EvidenceEntry.from_dict(raw) for raw in self._read_raw()]

    def verify(self) -> VerificationResult:
        return verify(self.path)

    def summary(self) -> dict[str, Any]:
        """Counts by decision, for a report header or a CI summary."""
        counts: dict[str, int] = {}
        types: dict[str, int] = {}
        for entry in self.entries():
            counts[entry.action] = counts.get(entry.action, 0) + 1
            for data_type in entry.data_types:
                types[data_type] = types.get(data_type, 0) + 1
        return {
            "path": str(self.path),
            "entries": sum(counts.values()),
            "by_action": dict(sorted(counts.items())),
            "by_data_type": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
            "verified": self.verify().ok,
        }


def verify(path: str | os.PathLike[str]) -> VerificationResult:
    """Walk the chain and report the first link that does not hold."""
    file_path = Path(path)
    if not file_path.exists():
        return VerificationResult(ok=False, entries=0, detail=f"no evidence log at {file_path}")

    previous = GENESIS
    count = 0
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                return VerificationResult(
                    ok=False, entries=count, broken_at=line_number,
                    detail=f"line {line_number} is not valid JSON",
                )

            recorded = raw.get("hash")
            entry = EvidenceEntry.from_dict(raw)
            expected = chain_hash(entry.payload())
            if recorded != expected:
                return VerificationResult(
                    ok=False, entries=count, broken_at=line_number,
                    detail=(
                        f"entry {entry.sequence} (line {line_number}) was modified: "
                        f"its contents hash to {expected[:12]}…, not the {str(recorded)[:12]}… recorded"
                    ),
                )
            if entry.previous != previous:
                return VerificationResult(
                    ok=False, entries=count, broken_at=line_number,
                    detail=(
                        f"the chain breaks at entry {entry.sequence} (line {line_number}): "
                        f"it follows {entry.previous[:12]}…, but the previous entry hashes "
                        f"to {previous[:12]}… — an entry was inserted, removed or reordered"
                    ),
                )
            previous = expected
            count += 1

    return VerificationResult(ok=True, entries=count, detail=f"{count} entries, chain intact")
