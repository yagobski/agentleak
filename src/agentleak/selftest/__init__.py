# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Agent self-test: one local command, one stable JSON document, a loop to green.

An agent that wants to know whether it leaks has to be able to ask without a
human, a browser, an account, or a network. This package is that path:

* :func:`run_engine_check` — does the tool itself work here? (seconds, offline)
* :func:`selftest_traces` — score traces the agent recorded of itself
* :func:`selftest_command` — run the agent's own command against a built-in
  scenario battery with planted canaries, then score what it did
* :func:`selftest_code` — static scan of the agent's own source

Every mode returns the same versioned document (see :mod:`.document` and
:data:`.schema.SELFTEST_SCHEMA`), with ordered ``next_steps`` carrying concrete
``fix`` objects, a ``delta`` against the previous local self-test and the exact
``rerun`` command.

What a clean result means: no finding from the detection tiers that ran.
It is not a statement that the agent is safe or compliant.
"""

from __future__ import annotations

from .document import EXIT_CODES, SCHEMA_VERSION, build_document
from .runner import (
    SelftestOptions,
    run_engine_check,
    selftest_code,
    selftest_command,
    selftest_steps,
    selftest_traces,
)
from .schema import SELFTEST_SCHEMA

__all__ = [
    "EXIT_CODES",
    "SCHEMA_VERSION",
    "SELFTEST_SCHEMA",
    "SelftestOptions",
    "build_document",
    "run_engine_check",
    "selftest_code",
    "selftest_command",
    "selftest_steps",
    "selftest_traces",
]
