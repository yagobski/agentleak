"""Help text has to survive the renderer that prints it.

Typer formats help through rich, and rich reads `[word]` as a style tag. So a
docstring saying "requires the [gui] extra" prints as "requires the  extra" —
the one word the reader needed is deleted, silently, with no error anywhere. It
happened to both `mcp` and `serve`, which are exactly the two commands a new
user hits before they have the extra installed.

Escaping is `\\[gui]`, which rich prints as `[gui]`.
"""

from __future__ import annotations

import re

from typer.testing import CliRunner

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


def test_no_help_text_has_a_hole_where_a_word_should_be() -> None:
    """A swallowed tag leaves a doubled space mid-sentence. Catch the shape."""
    offenders = []
    for command in [None, *COMMANDS]:
        text = _help(*( [] if command is None else [command] ))
        # Collapse the box-drawing padding rich uses to align the right border,
        # then look for a gap left mid-sentence between two lowercase words.
        for line in text.splitlines():
            body = re.sub(r"^[│|]\s?|\s*[│|]$", "", line)
            if re.search(r"[a-z],?\s{2}[a-z]", body.strip()):
                offenders.append((command or "<root>", body.strip()))
    assert not offenders, f"help text looks like a tag was eaten: {offenders[:4]}"
