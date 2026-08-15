# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Agent-skill installation.

AgentLeak ships a ``SKILL.md`` so that coding agents (Claude Code, OpenClaw, Cursor,
Windsurf, Codex CLI…) discover the tool on their own instead of having to be told how to
use it. This module owns the canonical skill text and the logic for writing it into the
skills directory of whichever agents are present on the machine.

Everything here is pure filesystem work — no network, no telemetry.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "SKILL_NAME",
    "SKILL_FILENAME",
    "TARGETS",
    "SkillTarget",
    "InstallOutcome",
    "skill_text",
    "target_by_id",
    "detect_targets",
    "install",
    "install_all",
    "uninstall",
    "status",
]

SKILL_NAME = "agentleak"
SKILL_FILENAME = "SKILL.md"

_SKILL_SOURCE = Path(__file__).parent / SKILL_FILENAME


# ----------------------------------------------------------------------
# Targets
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class SkillTarget:
    """An agent whose skills directory we know how to write to.

    ``marker`` is the directory whose existence means "this agent is installed here".
    ``skills_dir`` is where skill folders live (created if missing).
    """

    id: str
    label: str
    marker: str
    skills_dir: str

    def marker_path(self, home: Path | None = None) -> Path:
        return _expand(self.marker, home)

    def skills_path(self, home: Path | None = None) -> Path:
        return _expand(self.skills_dir, home)

    def skill_dir(self, home: Path | None = None) -> Path:
        return self.skills_path(home) / SKILL_NAME

    def skill_file(self, home: Path | None = None) -> Path:
        return self.skill_dir(home) / SKILL_FILENAME

    def detected(self, home: Path | None = None) -> bool:
        return self.marker_path(home).is_dir()

    def installed(self, home: Path | None = None) -> bool:
        return self.skill_file(home).is_file()


TARGETS: tuple[SkillTarget, ...] = (
    SkillTarget("claude-code", "Claude Code", "~/.claude", "~/.claude/skills"),
    SkillTarget("openclaw", "OpenClaw", "~/.openclaw", "~/.openclaw/skills"),
    SkillTarget("cursor", "Cursor", "~/.cursor", "~/.cursor/skills"),
    SkillTarget("windsurf", "Windsurf", "~/.windsurf", "~/.windsurf/skills"),
    SkillTarget("codex", "Codex CLI", "~/.codex", "~/.codex/skills"),
)

_TARGETS_BY_ID = {t.id: t for t in TARGETS}


def _expand(raw: str, home: Path | None) -> Path:
    """Expand ``~`` against ``home`` when given, otherwise the real user home."""
    if home is not None and raw.startswith("~"):
        return (Path(home) / raw[1:].lstrip("/\\")).resolve()
    return Path(os.path.expanduser(raw)).resolve()


def target_by_id(target_id: str) -> SkillTarget:
    """Look up a target, raising ``KeyError`` with a helpful message if unknown."""
    try:
        return _TARGETS_BY_ID[target_id]
    except KeyError as exc:
        known = ", ".join(sorted(_TARGETS_BY_ID))
        raise KeyError(f"unknown target {target_id!r} (known: {known})") from exc


def detect_targets(home: Path | None = None) -> list[SkillTarget]:
    """Return the targets whose agent directory exists on this machine."""
    return [t for t in TARGETS if t.detected(home)]


# ----------------------------------------------------------------------
# Skill text
# ----------------------------------------------------------------------
def skill_text() -> str:
    """The canonical SKILL.md shipped with this package."""
    return _SKILL_SOURCE.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Install / uninstall
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class InstallOutcome:
    """Result of writing (or declining to write) the skill to one location."""

    path: Path
    status: str  # "installed" | "updated" | "unchanged" | "conflict" | "removed" | "absent"
    label: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "conflict"

    @property
    def changed(self) -> bool:
        return self.status in {"installed", "updated", "removed"}


def install(
    destination: Path,
    *,
    force: bool = False,
    label: str = "",
    dry_run: bool = False,
) -> InstallOutcome:
    """Write ``SKILL.md`` into ``destination`` (a skills directory).

    Creates ``<destination>/agentleak/SKILL.md``. Never overwrites a file whose content
    differs from ours unless ``force`` is set — a user may have edited it.
    """
    destination = Path(destination)
    skill_dir = destination / SKILL_NAME
    target_file = skill_dir / SKILL_FILENAME
    content = skill_text()

    if target_file.is_file():
        existing = target_file.read_text(encoding="utf-8")
        if existing == content:
            return InstallOutcome(target_file, "unchanged", label)
        if not force:
            return InstallOutcome(target_file, "conflict", label)
        status = "updated"
    else:
        status = "installed"

    if not dry_run:
        skill_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")

    return InstallOutcome(target_file, status, label)


def install_all(
    targets: list[SkillTarget],
    *,
    force: bool = False,
    dry_run: bool = False,
    home: Path | None = None,
) -> list[InstallOutcome]:
    """Install the skill into every given target's skills directory."""
    return [
        install(
            t.skills_path(home),
            force=force,
            label=t.label,
            dry_run=dry_run,
        )
        for t in targets
    ]


def uninstall(
    destination: Path,
    *,
    label: str = "",
    dry_run: bool = False,
) -> InstallOutcome:
    """Remove ``<destination>/agentleak/`` if we put a skill there."""
    destination = Path(destination)
    skill_dir = destination / SKILL_NAME
    target_file = skill_dir / SKILL_FILENAME

    if not target_file.is_file():
        return InstallOutcome(target_file, "absent", label)
    if not dry_run:
        shutil.rmtree(skill_dir, ignore_errors=True)
    return InstallOutcome(target_file, "removed", label)


def status(home: Path | None = None) -> list[tuple[SkillTarget, str]]:
    """Per-target installation state: ``current``, ``stale``, ``missing`` or ``absent``."""
    content = skill_text()
    rows: list[tuple[SkillTarget, str]] = []
    for target in TARGETS:
        if not target.detected(home):
            rows.append((target, "absent"))
            continue
        skill_file = target.skill_file(home)
        if not skill_file.is_file():
            rows.append((target, "missing"))
        elif skill_file.read_text(encoding="utf-8") == content:
            rows.append((target, "current"))
        else:
            rows.append((target, "stale"))
    return rows
