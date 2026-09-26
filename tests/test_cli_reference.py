# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""docs/cli.md names every command the CLI actually has.

``proxy``, ``evidence`` and ``subjects`` shipped in 0.13–0.14 and were missing
from the reference for two releases. The command list comes from the running
Typer app, so a new command cannot land without a line in the table.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer.main

from agentleak.cli import app

CLI_DOC = Path(__file__).resolve().parent.parent / "docs" / "cli.md"


def _commands() -> set[str]:
    group = typer.main.get_command(app)
    return set(group.commands)  # type: ignore[attr-defined]


def test_every_command_is_in_the_reference_table():
    doc = CLI_DOC.read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([a-z-]+)", doc, flags=re.MULTILINE))
    missing = _commands() - documented
    assert not missing, f"docs/cli.md does not list: {sorted(missing)}"
