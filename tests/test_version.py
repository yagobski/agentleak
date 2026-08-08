"""The version has to be one number, not two that happen to agree.

`pyproject.toml` is what PyPI publishes and what the release workflow checks
against the git tag. `__version__` is what `agentleak version` prints and what
the API reports. Nothing connects them, so a bump that touches one and forgets
the other releases cleanly and then lies about which release it is — the sort of
error that only surfaces when someone is trying to reproduce a bug report.
"""

from __future__ import annotations

import pathlib

import tomllib

from agentleak import __version__


def test_the_declared_version_matches_the_packaged_one() -> None:
    pyproject = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert declared == __version__, (
        f"pyproject says {declared}, agentleak.__version__ says {__version__}. "
        "A release would publish one number and report the other."
    )
