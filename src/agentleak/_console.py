# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Console output for the CLIs: every line is printed through here.

The CLIs print strings taken from traces and imported files (agent names, run
ids, the imported tool's name, finding fields, file names). A terminal acts on
control characters in them: an escape sequence can recolour or hide text,
retitle the window, rewrite what was printed or, on some terminals, write to
the clipboard. :func:`clean` makes them inert before anything reaches the
terminal; :func:`echo` and :func:`secho` apply it to the whole message, and
``secho`` adds its own colours afterwards, so styling still works.

Neutralised: C0 controls except newline and tab, DEL and C1 controls. Each is
shown as ``\\uXXXX``, which is readable on a terminal and, inside a JSON
document printed with ``ensure_ascii=False``, the same character re-encoded
(JSON already escapes C0 itself), so ``--json`` output stays valid and equal.
Report files (JSON, SARIF, HTML, Markdown) are not written through here.
"""

from __future__ import annotations

import re
from typing import Any

import typer

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def clean(value: Any) -> str:
    """``value`` as text with every terminal control character made inert."""
    return _CONTROL_RE.sub(lambda m: f"\\u{ord(m.group(0)):04x}", str(value))


def _message(message: Any) -> Any:
    if message is None or isinstance(message, (bytes, bytearray)):
        return message
    return clean(message)


def echo(message: Any = None, *args: Any, **kwargs: Any) -> None:
    """:func:`typer.echo` with :func:`clean` applied to the message."""
    typer.echo(_message(message), *args, **kwargs)


def secho(message: Any = None, *args: Any, **kwargs: Any) -> None:
    """:func:`typer.secho`: the message is cleaned, then styled."""
    typer.secho(_message(message), *args, **kwargs)


__all__ = ["clean", "echo", "secho"]
