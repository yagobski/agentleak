# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Where the database goes, and why guessing wrong is expensive.

A deployment mounts a volume and points the app at it. If the app quietly
ignores that setting and falls back to a path inside the container, everything
works — until the next rebuild recreates the container and takes every account,
run and published page with it. Nothing fails loudly at the time.
"""

from __future__ import annotations

import pathlib

from agentleak.core.store import Store


def test_the_named_database_file_is_the_one_used(tmp_path: pathlib.Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTLEAK_DB", str(tmp_path / "mounted" / "agentleak.db"))
    db = Store()
    db.create_project("a", owner_id="")
    assert (tmp_path / "mounted" / "agentleak.db").is_file(), (
        "AGENTLEAK_DB was ignored — the data landed somewhere the deployment did not mount"
    )


def test_an_explicit_path_still_wins_over_the_environment(tmp_path: pathlib.Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AGENTLEAK_DB", str(tmp_path / "env.db"))
    db = Store(str(tmp_path / "explicit.db"))
    db.create_project("a", owner_id="")
    assert (tmp_path / "explicit.db").is_file()
    assert not (tmp_path / "env.db").exists()


def test_home_still_works_on_its_own(tmp_path: pathlib.Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("AGENTLEAK_DB", raising=False)
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path / "home"))
    db = Store()
    db.create_project("a", owner_id="")
    assert (tmp_path / "home" / "agentleak.db").is_file()
