"""Tests for the agent-skill installer (`agentleak skill`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentleak import skill as skill_mod
from agentleak.cli import app

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# canonical text
# ----------------------------------------------------------------------
def test_skill_text_is_non_empty_and_has_frontmatter():
    text = skill_mod.skill_text()
    assert text.startswith("---\n")
    assert "name: agentleak" in text
    assert "description:" in text


def test_repo_root_skill_matches_packaged_skill():
    """The repo-root SKILL.md (used by `npx skills add`) must not drift from the shipped one."""
    root_skill = REPO_ROOT / "SKILL.md"
    assert root_skill.is_file(), "SKILL.md must exist at the repository root"
    assert root_skill.read_text(encoding="utf-8") == skill_mod.skill_text()


def test_skill_documents_core_commands():
    text = skill_mod.skill_text()
    for command in ("agentleak scan", "agentleak run", "agentleak serve", "agentleak.watch"):
        assert command in text


# ----------------------------------------------------------------------
# targets
# ----------------------------------------------------------------------
def test_target_ids_are_unique_and_resolvable():
    ids = [t.id for t in skill_mod.TARGETS]
    assert len(ids) == len(set(ids))
    for target_id in ids:
        assert skill_mod.target_by_id(target_id).id == target_id


def test_unknown_target_raises_with_known_ids():
    with pytest.raises(KeyError) as exc:
        skill_mod.target_by_id("emacs")
    assert "claude-code" in str(exc.value)


def test_detect_targets_uses_supplied_home(tmp_path):
    assert skill_mod.detect_targets(home=tmp_path) == []
    (tmp_path / ".claude").mkdir()
    detected = skill_mod.detect_targets(home=tmp_path)
    assert [t.id for t in detected] == ["claude-code"]


# ----------------------------------------------------------------------
# install / uninstall
# ----------------------------------------------------------------------
def test_install_writes_skill_file(tmp_path):
    outcome = skill_mod.install(tmp_path)
    assert outcome.status == "installed"
    assert outcome.changed
    written = tmp_path / "agentleak" / "SKILL.md"
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == skill_mod.skill_text()


def test_install_is_idempotent(tmp_path):
    skill_mod.install(tmp_path)
    second = skill_mod.install(tmp_path)
    assert second.status == "unchanged"
    assert not second.changed
    assert second.ok


def test_install_refuses_to_clobber_edited_file(tmp_path):
    skill_mod.install(tmp_path)
    edited = tmp_path / "agentleak" / "SKILL.md"
    edited.write_text("# my own notes\n", encoding="utf-8")

    blocked = skill_mod.install(tmp_path)
    assert blocked.status == "conflict"
    assert not blocked.ok
    assert edited.read_text(encoding="utf-8") == "# my own notes\n"

    forced = skill_mod.install(tmp_path, force=True)
    assert forced.status == "updated"
    assert edited.read_text(encoding="utf-8") == skill_mod.skill_text()


def test_dry_run_writes_nothing(tmp_path):
    outcome = skill_mod.install(tmp_path, dry_run=True)
    assert outcome.status == "installed"
    assert not (tmp_path / "agentleak" / "SKILL.md").exists()


def test_uninstall_removes_and_is_safe_when_absent(tmp_path):
    assert skill_mod.uninstall(tmp_path).status == "absent"
    skill_mod.install(tmp_path)
    assert skill_mod.uninstall(tmp_path).status == "removed"
    assert not (tmp_path / "agentleak").exists()


def test_uninstall_dry_run_keeps_the_file(tmp_path):
    skill_mod.install(tmp_path)
    outcome = skill_mod.uninstall(tmp_path, dry_run=True)
    assert outcome.status == "removed"
    assert (tmp_path / "agentleak" / "SKILL.md").is_file()


def test_install_all_covers_every_detected_target(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    targets = skill_mod.detect_targets(home=tmp_path)
    outcomes = skill_mod.install_all(targets, home=tmp_path)

    assert {o.status for o in outcomes} == {"installed"}
    assert (tmp_path / ".claude" / "skills" / "agentleak" / "SKILL.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "agentleak" / "SKILL.md").is_file()


# ----------------------------------------------------------------------
# status
# ----------------------------------------------------------------------
def test_status_reports_absent_missing_current_and_stale(tmp_path):
    def state_for(target_id: str) -> str:
        return {t.id: s for t, s in skill_mod.status(home=tmp_path)}[target_id]

    assert state_for("claude-code") == "absent"

    (tmp_path / ".claude").mkdir()
    assert state_for("claude-code") == "missing"

    claude = skill_mod.target_by_id("claude-code")
    skill_mod.install(claude.skills_path(tmp_path))
    assert state_for("claude-code") == "current"

    claude.skill_file(tmp_path).write_text("edited\n", encoding="utf-8")
    assert state_for("claude-code") == "stale"


# ----------------------------------------------------------------------
# CLI surface
# ----------------------------------------------------------------------
def test_cli_print_dumps_the_skill():
    result = runner.invoke(app, ["skill", "--print"])
    assert result.exit_code == 0
    assert "name: agentleak" in result.stdout


def test_cli_install_to_explicit_path(tmp_path):
    result = runner.invoke(app, ["skill", "--install", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "agentleak" / "SKILL.md").is_file()


def test_cli_install_conflict_exits_nonzero(tmp_path):
    runner.invoke(app, ["skill", "--install", "--path", str(tmp_path)])
    (tmp_path / "agentleak" / "SKILL.md").write_text("mine\n", encoding="utf-8")

    blocked = runner.invoke(app, ["skill", "--install", "--path", str(tmp_path)])
    assert blocked.exit_code == 1
    assert "--force" in blocked.stdout

    forced = runner.invoke(app, ["skill", "--install", "--path", str(tmp_path), "--force"])
    assert forced.exit_code == 0


def test_cli_dry_run_writes_nothing(tmp_path):
    result = runner.invoke(app, ["skill", "--install", "--path", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.stdout
    assert not (tmp_path / "agentleak").exists()


def test_cli_uninstall_explicit_path(tmp_path):
    runner.invoke(app, ["skill", "--install", "--path", str(tmp_path)])
    result = runner.invoke(app, ["skill", "--uninstall", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert not (tmp_path / "agentleak").exists()


def test_cli_rejects_install_and_uninstall_together(tmp_path):
    result = runner.invoke(
        app, ["skill", "--install", "--uninstall", "--path", str(tmp_path)]
    )
    assert result.exit_code == 2


def test_cli_rejects_unknown_target():
    result = runner.invoke(app, ["skill", "--install", "--target", "emacs"])
    assert result.exit_code == 2
    assert "emacs" in result.stdout


def test_cli_status_runs_without_flags():
    result = runner.invoke(app, ["skill"])
    assert result.exit_code == 0
    assert "AgentLeak skill" in result.stdout


def test_cli_install_with_no_detected_agent_fails_cleanly(monkeypatch):
    monkeypatch.setattr(skill_mod, "detect_targets", lambda home=None: [])
    result = runner.invoke(app, ["skill", "--install"])
    assert result.exit_code == 1
    assert "--path" in result.stdout
