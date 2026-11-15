# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Regression tests for defects found in the QA pass (see QA-REPORT.md).

Each test names the defect it pins. All data is synthetic.
"""

from __future__ import annotations

import json

from agentleak.core.codescan import scan_files

# ----------------------------------------------------------------------
# QA-01: code-scan snippets printed other findings' raw values
# ----------------------------------------------------------------------


def test_codescan_snippet_redacts_every_value_on_the_line() -> None:
    src = 'print("Patient John Smith, SSN 123-45-6789")\n'
    result = scan_files({"agent.py": src})
    assert result.findings, "expected findings on a line with a name and an SSN"
    for f in result.findings:
        assert "123-45-6789" not in f.snippet, f
        assert "John Smith" not in f.snippet, f
    sarif = json.dumps(result.to_sarif())
    assert "123-45-6789" not in sarif
    assert "John Smith" not in sarif


def test_codescan_snippet_scrub_survives_truncation() -> None:
    # The secret sits across the 200-character cut: truncating before
    # scrubbing used to leave a raw prefix of it behind.
    pad = "x" * 180
    src = f'log.info("{pad} SSN 123-45-6789 email jane.doe@example.com")\n'
    result = scan_files({"agent.py": src})
    for f in result.findings:
        assert "123-4" not in f.snippet
        assert len(f.snippet) <= 200
