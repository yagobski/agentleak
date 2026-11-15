# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Local self-test history, so ``delta`` can say "better" or "worse".

The file is ``<state dir>/selftest-history.jsonl`` (state dir defaults to
``./.agentleak``, next to the preflight history). It is append-only, capped,
and holds only what is already in the printed document: fingerprints, channels,
data types, levels and *redacted* values. Never a raw value.

Each entry carries a ``target`` key (mode + what was tested) so that the delta
compares like with like: scoring ``trace_a.json`` and then running ``--cmd``
are two different targets, and one is not an improvement on the other.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from ..core.memory import write_private as _write_private

HISTORY_FILE = "selftest-history.jsonl"
SCENARIO_DIR = "selftest-scenarios"
DEFAULT_STATE_DIR = ".agentleak"
MAX_ENTRIES = 100


def default_state_dir() -> Path:
    """``$AGENTLEAK_STATE_DIR`` when set, else ``./.agentleak``."""
    raw = os.environ.get("AGENTLEAK_STATE_DIR", "").strip()
    return Path(raw) if raw else Path.cwd() / DEFAULT_STATE_DIR


def target_key(mode: str, labels: list[str]) -> str:
    """Identity of *what* was tested, independent of when."""
    joined = "\x00".join([mode, *sorted(labels)])
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


class SelftestHistory:
    """Read and append self-test entries for one state directory."""

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self.dir = Path(state_dir) if state_dir else default_state_dir()
        self.path = self.dir / HISTORY_FILE

    # -- reading ---------------------------------------------------------
    def entries(self) -> list[dict[str, Any]]:
        """All entries, oldest first. A corrupt line is skipped, never fatal."""
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

    def previous(self, target: str) -> dict[str, Any] | None:
        """The most recent entry for the same target."""
        for entry in reversed(self.entries()):
            if entry.get("target") == target:
                return entry
        return None

    def find_finding(self, fingerprint: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Newest ``(entry, finding)`` carrying ``fingerprint``."""
        for entry in reversed(self.entries()):
            for finding in entry.get("findings", []):
                if finding.get("fingerprint") == fingerprint:
                    return entry, finding
        return None

    # -- writing ---------------------------------------------------------
    def record(self, entry: dict[str, Any]) -> None:
        history = [*self.entries(), entry][-MAX_ENTRIES:]
        self.dir.mkdir(parents=True, exist_ok=True)
        _write_private(
            self.path,
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in history),
        )

    # -- issued scenarios (canary ground truth) -----------------------------
    def save_scenario(self, instance_id: str, payload: dict[str, Any]) -> Path:
        """Keep an issued scenario's synthetic canaries so a trace can be checked later."""
        folder = self.dir / SCENARIO_DIR
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{_safe_name(instance_id)}.json"
        _write_private(path, json.dumps(payload, ensure_ascii=False))
        return path

    def load_scenario(self, instance_id: str) -> dict[str, Any] | None:
        path = self.dir / SCENARIO_DIR / f"{_safe_name(instance_id)}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None


#: Flags a stored re-run command may carry. History files sit in the working
#: directory and can come with a cloned repository, so a stored command is
#: untrusted: one that runs a program (``--cmd``, ``--shell``) or loads a
#: config (``--config``, which can enable a network tier) is never handed back.
_RERUN_FLAGS = {"--trace", "--trace-format", "--scenarios", "--code", "--fail-on",
                "--fail-under", "--state-dir"}
_RERUN_SWITCHES = {"--json", "--human", "--no-history"}


def trusted_rerun(rerun: Any) -> dict[str, Any] | None:
    """A stored ``rerun`` rebuilt from its argv when it is a plain self-test, else ``None``."""
    import shlex

    if not isinstance(rerun, dict):
        return None
    argv = rerun.get("argv")
    if not isinstance(argv, list) or argv[:2] != ["agentleak", "selftest"]:
        return None
    if not all(isinstance(a, str) and "\n" not in a and "\r" not in a for a in argv):
        return None
    rest = argv[2:]
    i = 0
    while i < len(rest):
        flag = rest[i]
        if flag in _RERUN_SWITCHES:
            i += 1
        elif flag in _RERUN_FLAGS and i + 1 < len(rest) and not rest[i + 1].startswith("-"):
            i += 2
        else:
            return None
    return {"cli": shlex.join(argv), "argv": list(argv)}


def _safe_name(value: str) -> str:
    return "".join(c for c in value if c.isalnum() or c in "-_")[:80] or "scenario"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compute_delta(
    previous: dict[str, Any] | None,
    *,
    fingerprints: list[str],
    privacy_score: int | None,
    risk_index: float | None,
    passed: bool,
) -> dict[str, Any] | None:
    """Compare this self-test with the previous one of the same target.

    ``None`` on the first self-test of a target, as ``/api/agent/improve``
    returns ``null`` when there is no previous run. Field names that overlap
    with that endpoint (``previous_run_id``, ``delta_score``, ``delta_ri``,
    ``direction``) keep its meaning.
    """
    if previous is None:
        return None
    before = {f.get("fingerprint") for f in previous.get("findings", [])} - {None}
    now = set(fingerprints)
    prev_score = previous.get("privacy_score")
    prev_ri = previous.get("risk_index")
    delta_score = (
        privacy_score - prev_score
        if isinstance(privacy_score, int) and isinstance(prev_score, int)
        else None
    )
    delta_ri = (
        round(risk_index - prev_ri, 4)
        if isinstance(risk_index, (int, float)) and isinstance(prev_ri, (int, float))
        else None
    )
    new = sorted(now - before)
    fixed = sorted(before - now)
    if delta_score is not None and delta_score != 0:
        direction = "improved" if delta_score > 0 else "regressed"
    elif len(now) < len(before):
        direction = "improved"
    elif len(now) > len(before):
        direction = "regressed"
    elif passed and not previous.get("passed"):
        direction = "improved"
    elif previous.get("passed") and not passed:
        direction = "regressed"
    else:
        direction = "stable"
    return {
        "previous_run_id": previous.get("run_id"),
        "previous_at": previous.get("at"),
        "previous_passed": bool(previous.get("passed")),
        "delta_score": delta_score,
        "delta_ri": delta_ri,
        "direction": direction,
        "new": new,
        "fixed": fixed,
        "unchanged": len(now & before),
    }


__all__ = [
    "DEFAULT_STATE_DIR",
    "HISTORY_FILE",
    "SelftestHistory",
    "compute_delta",
    "default_state_dir",
    "now_iso",
    "target_key",
    "trusted_rerun",
]
