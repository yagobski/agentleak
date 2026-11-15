# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Score what red-team and evaluation tools already wrote.

promptfoo, garak, PyRIT and Inspect AI attack or benchmark an agent and keep a
log of what happened. This package turns those logs into AgentLeak traces, so
the same run can be audited channel by channel::

    agentleak import results.json --score

or from Python::

    from agentleak.interop import import_file
    imported = import_file("logs/2026-11-15_task.eval")
    for item in imported.traces:
        print(item.record_id, len(item.trace.events))

Each importer maps the tool's records to channels as faithfully as the format
allows, records where every trace came from (``trace.metadata["provenance"]``)
and what its source could observe (``trace.metadata["observation"]``). A
black-box tool sees only the prompt and the reply; its traces carry that, and
so does every report scored from them.

Imported files are data. Nothing in them is executed, fetched or followed.
"""

from __future__ import annotations

from .base import ImportedTrace, ImportResult, InteropError
from .importer import SOURCES, detect, import_file

__all__ = [
    "SOURCES",
    "ImportResult",
    "ImportedTrace",
    "InteropError",
    "detect",
    "import_file",
]
