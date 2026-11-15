# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""`agentleak --version` prints the same line as `agentleak version`."""
from typer.testing import CliRunner

from agentleak import __version__
from agentleak.cli import app


def test_version_flag_matches_version_command() -> None:
    runner = CliRunner()
    flag = runner.invoke(app, ["--version"])
    command = runner.invoke(app, ["version"])
    assert flag.exit_code == 0
    assert flag.output.strip() == f"agentleak {__version__}"
    assert flag.output == command.output


def test_short_version_flag() -> None:
    result = CliRunner().invoke(app, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output
