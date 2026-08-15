# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The version has to be one number, not two that happen to agree.

`pyproject.toml` is what PyPI publishes and what the release workflow checks
against the git tag. `__version__` is what `agentleak version` prints and what
the API reports. Nothing connects them, so a bump that touches one and forgets
the other releases cleanly and then lies about which release it is — the sort of
error that only surfaces when someone is trying to reproduce a bug report.
"""

from __future__ import annotations

import pathlib
import re

from agentleak import __version__


def _declared_version(text: str) -> str:
    """Read `version` out of pyproject without needing a TOML parser.

    `tomllib` only arrives in 3.11 and this package supports 3.10, so a test
    that imports it does not run on the oldest Python we promise to work on —
    which is the one where a version mismatch is least likely to be noticed.
    """
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "no top-level `version` line found in pyproject.toml"
    return match.group(1)


def test_the_declared_version_matches_the_packaged_one() -> None:
    pyproject = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = _declared_version(pyproject.read_text())
    assert declared == __version__, (
        f"pyproject says {declared}, agentleak.__version__ says {__version__}. "
        "A release would publish one number and report the other."
    )
