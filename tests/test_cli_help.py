"""Help text has to survive the renderer that prints it.

Typer formats help through rich, and rich reads `[word]` as a style tag. So a
docstring saying "requires the [gui] extra" prints as "requires the  extra" —
the one word the reader needed is deleted, silently, with no error anywhere. It
happened to both `mcp` and `serve`, which are exactly the two commands a new
user hits before they have the extra installed.

Escaping is `\\[gui]`, which rich prints as `[gui]`.
"""

from __future__ import annotations

import pathlib
import re

from typer.testing import CliRunner

from agentleak import cli
from agentleak.cli import app

runner = CliRunner()

COMMANDS = [
    "version", "init", "validate", "scenarios", "agent-card", "schema", "skill",
    "scan", "redact", "mcp", "serve", "run", "report", "history", "compare", "admin",
]


def _help(*args: str) -> str:
    result = runner.invoke(app, [*args, "--help"])
    assert result.exit_code == 0, f"`{' '.join(args)} --help` exited {result.exit_code}"
    return result.output


def test_no_extra_is_named_only_to_be_swallowed() -> None:
    """The install hint must reach the reader, not the markup parser."""
    for command in ("mcp", "serve"):
        text = _help(command)
        assert "agentleak[" in text, f"`{command} --help` lost the name of its extra"
        assert not re.search(r"requires the\s+extra", text)


def test_every_command_renders_its_help() -> None:
    for command in COMMANDS:
        assert _help(command).strip(), f"`{command} --help` printed nothing"


def test_no_help_string_contains_an_unescaped_markup_tag() -> None:
    """Check the cause, not the shape of the damage.

    The first version of this matched rendered output for a gap mid-sentence.
    That passed locally and failed on CI, where rich emits ANSI colour and pads
    option tables with runs of spaces — a false failure, which is worse than no
    test. The invariant is in the source: a `[word]` in help text is a rich tag
    unless it is escaped, so look for that directly.
    """
    source = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    offenders = [
        match.group(0)
        for match in re.finditer(r'(?<!\\)\[[a-z][a-z0-9_-]*\]', source)
        if _inside_help_text(source, match.start())
    ]
    assert not offenders, (
        f"rich will silently delete these from the help output: {sorted(set(offenders))}. "
        "Escape them as \\\\[gui]."
    )


def _inside_help_text(source: str, index: int) -> bool:
    """Whether this offset sits in a docstring or a `help=` string.

    A `[str]` in a type annotation is fine; only text that reaches rich matters.
    """
    line_start = source.rfind("\n", 0, index) + 1
    line = source[line_start : source.find("\n", index)]
    stripped = line.lstrip()
    return stripped.startswith('"""') or 'help="' in line or stripped.startswith(('"', "'"))
