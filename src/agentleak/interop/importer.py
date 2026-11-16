# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Choose the importer for a file, by name or by looking at it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import garak, inspect_ai, promptfoo, pyrit
from .base import ImportResult, InteropError
from .source import Source, load_source

_Sniff = Callable[[Source], tuple[bool, str]]
_Convert = Callable[[Source, str], ImportResult]

#: ``--from`` name -> (sniff, convert). Order is the auto-detection order.
SOURCES: dict[str, tuple[_Sniff, _Convert]] = {
    "promptfoo": (promptfoo.sniff, promptfoo.convert),
    "inspect": (inspect_ai.sniff, inspect_ai.convert),
    "garak": (garak.sniff, garak.convert),
    "pyrit": (pyrit.sniff, pyrit.convert),
}


def detect(src: Source) -> tuple[str, str]:
    """``(name, reason)`` of the importer that recognises ``src``.

    Raises :class:`InteropError` listing every format tried and why it did
    not match.
    """
    tried = []
    for name, (sniff, _convert) in SOURCES.items():
        matched, reason = sniff(src)
        if matched:
            return name, reason
        tried.append(f"{name}: {reason}")
    raise InteropError(
        f"{src.name} is not a format AgentLeak can import (read as {src.kind}). Tried "
        + "; ".join(tried)
        + ". For a trace AgentLeak already understands, use `agentleak run --trace` or "
        "`agentleak selftest --trace`."
    )


def import_file(path: str | Path, source: str = "auto") -> ImportResult:
    """Import one file. ``source`` is a key of :data:`SOURCES` or ``auto``."""
    src = load_source(path)
    if source in ("", "auto"):
        name, reason = detect(src)
    else:
        if source not in SOURCES:
            raise InteropError(f"unknown source {source!r}; use one of: auto, {', '.join(SOURCES)}")
        name = source
        matched, why = SOURCES[name][0](src)
        if not matched:
            raise InteropError(f"{src.name} does not look like {name} output: {why}")
        reason = f"--from {name} ({why})"
    result = SOURCES[name][1](src, reason)
    if not result.traces:
        raise InteropError(
            f"{src.name} was read as {name} output but produced no trace with events; an empty "
            "import cannot be scored, and scoring it would be a false pass"
            + (f" ({'; '.join(result.notes)})" if result.notes else "")
        )
    return result
