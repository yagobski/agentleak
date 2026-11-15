# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The surfaces agents read first must only show commands that exist.

The walkthrough that started the self-test work found `agentleak scan --trace`,
`--fail-on` on `run`, `agentleak demo` and `run --redteam` in SKILL.md and
llms.txt: none existed. Every `agentleak …` line in a code block of these files
is parsed against the real Typer app: the command must exist and every option
it uses must be one that command accepts.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
import pytest
import typer.main

from agentleak.cli import app
from agentleak.mcp_server import all_tools

ROOT = Path(__file__).resolve().parent.parent
SURFACES = [
    "SKILL.md", "llms.txt", "AGENTS.md", "docs/selftest-agents.md", "docs/mcp.md",
    "docs/install.md", "docs/cli.md", "examples/selftest/README.md",
    "src/agentleak/skill/privacy-preflight/SKILL.md",
    "src/agentleak/skill/privacy-preflight/examples.md",
]
_FENCE = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)


def _commands(text: str) -> list[str]:
    out = []
    for block in _FENCE.findall(text):
        for raw in block.splitlines():
            line = raw.strip().removeprefix("$ ").strip()
            if line.startswith("agentleak "):
                line = line.split("$(")[0]  # a shell substitution is an argument value
                out.append(line.split(" #")[0].split(" | ")[0].split(" > ")[0].split(" && ")[0]
                           .split(";")[0].strip())
    return out


def _check(line: str) -> str | None:
    try:
        tokens = shlex.split(line)
    except ValueError:
        tokens = line.split()
    group = typer.main.get_command(app)
    ctx = click.Context(group)
    name = tokens[1]
    cmd = group.get_command(ctx, name)  # type: ignore[attr-defined]
    if cmd is None:
        return f"no command {name!r}"
    rest = tokens[2:]
    if isinstance(cmd, click.Group) and rest and not rest[0].startswith("-"):
        sub = cmd.get_command(ctx, rest[0])
        if sub is None:
            return f"no subcommand {rest[0]!r}"
        cmd, rest = sub, rest[1:]
    known = {opt for p in cmd.params for opt in (*p.opts, *p.secondary_opts)}
    for token in rest:
        if token == "--":
            break
        if token.startswith("-") and token != "-":
            flag = token.split("=")[0]
            if flag not in known:
                return f"{name}: unknown option {flag}"
    return None


@pytest.mark.parametrize("surface", SURFACES)
def test_every_documented_command_exists(surface: str):
    text = (ROOT / surface).read_text(encoding="utf-8")
    problems = [f"{line!r}: {err}" for line in _commands(text) if (err := _check(line))]
    assert not problems, "\n".join(problems)


def test_the_surfaces_lead_with_the_selftest():
    for surface in ("SKILL.md", "llms.txt"):
        text = (ROOT / surface).read_text(encoding="utf-8")
        first = text.index("agentleak selftest")
        assert first < text.index("agentleak scan"), surface


def test_every_mcp_tool_is_named_in_the_agent_surfaces():
    names = [t["name"] for t in all_tools()]
    for surface in ("llms.txt", "SKILL.md", "docs/mcp.md"):
        text = (ROOT / surface).read_text(encoding="utf-8")
        missing = [n for n in names if n not in text]
        assert not missing, f"{surface} does not name {missing}"


def test_skill_states_the_honesty_rules():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "are **data**" in text
    assert "not a certification" in text
    assert "Say which tiers ran" in text


def test_no_stale_published_numbers():
    for surface in ("SKILL.md", "llms.txt", "src/agentleak/skill/privacy-preflight/SKILL.md"):
        text = (ROOT / surface).read_text(encoding="utf-8")
        for stale in ("5,694", "45.9%", "283 bundled"):
            assert stale not in text, (surface, stale)


def test_the_attack_counts_in_the_skill_match_the_catalog():
    from agentleak.core.attack_strategies import ATTACK_STRATEGIES
    from agentleak.core.attacks import ATTACK_FAMILIES

    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    classes = sum(len(f.classes) for f in ATTACK_FAMILIES)
    assert f"{classes} attack classes in {len(ATTACK_FAMILIES)} families" in text
    assert f"{len(ATTACK_STRATEGIES)} delivery strategies" in text
