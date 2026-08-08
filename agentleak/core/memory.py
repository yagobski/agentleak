"""Local, per-project memory of what a previous check already found.

A score on its own tells an agent almost nothing: it reads the number, files it
away, and moves on. What makes an agent iterate is knowing that *this finding is
new since you last looked* — or that the one it fixed has stayed fixed. That is
the whole reason this module exists.

Everything here is local. The history lives in `.agentleak/history.jsonl` inside
the project being checked, so a coding agent gets continuity across sessions
without an account, a network call, or anything leaving the machine.

## Why identity is the hard part

To say "new" or "fixed", you have to recognise the *same* finding across two
runs. The obvious key is `file:line` — and it is wrong. Reformat a file, add an
import, and every known finding shifts a line and reappears as new. A tool that
cries wolf on every commit gets muted within a day, which is worse than not
reporting deltas at all.

So identity is `(file, rule, fingerprint-of-the-matched-value)` with the line
number deliberately excluded. The trade: moving a secret from one file to
another reads as one fixed finding plus one new finding rather than a move. That
is the rarer event, and the honest reading of it — the secret really is
somewhere new.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HISTORY_DIR = ".agentleak"
HISTORY_FILE = "history.jsonl"

# Enough runs to see a trend, few enough that the file stays hand-readable.
MAX_ENTRIES = 50


def finding_id(file: str, rule: str, snippet: str) -> str:
    """A stable identity for one finding, unchanged by moving it up or down.

    The snippet is already redacted by the scanner, which is what makes it safe
    to hash and keep: the history file never holds a raw secret.
    """
    digest = hashlib.sha256(f"{file}\x00{rule}\x00{snippet.strip()}".encode()).hexdigest()
    return digest[:16]


@dataclass(frozen=True)
class Delta:
    """What changed since the previous check of this project."""

    new: list[dict[str, Any]] = field(default_factory=list)
    fixed: list[dict[str, Any]] = field(default_factory=list)
    unchanged: int = 0
    previous_at: str = ""
    is_first_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "new": self.new,
            "fixed": self.fixed,
            "unchanged": self.unchanged,
            "previous_at": self.previous_at,
            "is_first_run": self.is_first_run,
        }

    def summary(self) -> str:
        """One line an agent can repeat to a human without reformatting it."""
        if self.is_first_run:
            return "First check of this project; nothing to compare against yet."
        parts = []
        if self.new:
            parts.append(f"{len(self.new)} new")
        if self.fixed:
            parts.append(f"{len(self.fixed)} fixed since last check")
        if self.unchanged:
            parts.append(f"{self.unchanged} still open")
        return ", ".join(parts) if parts else "No findings, and none last time either."


class ProjectMemory:
    """Append-only history of checks for one project directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / HISTORY_DIR / HISTORY_FILE

    # -- reading ---------------------------------------------------------
    def entries(self) -> list[dict[str, Any]]:
        """Every recorded check, oldest first. A corrupt line is skipped.

        A history file is a convenience, never a source of truth — if it has
        been hand-edited into something unparseable, the check still has to
        run. Losing the delta is acceptable; refusing to scan is not.
        """
        if not self.path.is_file():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                out.append(parsed)
        return out

    def last(self) -> dict[str, Any] | None:
        entries = self.entries()
        return entries[-1] if entries else None

    # -- comparing -------------------------------------------------------
    def compare(self, findings: list[dict[str, Any]]) -> Delta:
        """Classify the current findings against the previous check."""
        previous = self.last()
        if previous is None:
            return Delta(new=list(findings), is_first_run=True)

        before = {f["id"]: f for f in previous.get("findings", []) if "id" in f}
        now = {f["id"]: f for f in findings if "id" in f}

        return Delta(
            new=[f for fid, f in now.items() if fid not in before],
            fixed=[f for fid, f in before.items() if fid not in now],
            unchanged=sum(1 for fid in now if fid in before),
            previous_at=str(previous.get("at", "")),
        )

    # -- writing ---------------------------------------------------------
    def record(self, findings: list[dict[str, Any]], **extra: Any) -> None:
        """Append this check, keeping the file bounded and readable."""
        entry = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "findings": findings,
            **extra,
        }
        history = [*self.entries(), entry][-MAX_ENTRIES:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in history),
            encoding="utf-8",
        )
