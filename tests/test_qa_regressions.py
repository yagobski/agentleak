# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Regression tests for defects found in the QA pass (see QA-REPORT.md).

Each test names the defect it pins. All data is synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentleak.cli import app
from agentleak.core.codescan import scan_files

_cli = CliRunner()

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


# ----------------------------------------------------------------------
# QA-02: `agentleak run` / `report` / `redact` / `scan -o` crashed with a
# traceback on bad input instead of a message and the documented exit code
# ----------------------------------------------------------------------



@pytest.mark.parametrize(
    "name, content",
    [
        ("empty.json", b""),
        ("bad.json", b"{bad"),
        ("nonutf8.json", b"\xff\xfe\x00bad"),
        ("array.json", b"[]"),
        ("bad_event.json", b'{"events": [{"channel": "nope"}]}'),
        ("events_not_list.json", b'{"events": 3}'),
    ],
)
def test_run_bad_trace_file_exits_2_without_traceback(
    tmp_path: Path, name: str, content: bytes
) -> None:
    p = tmp_path / name
    p.write_bytes(content)
    result = _cli.invoke(app, ["run", "--trace", str(p), "-o", str(tmp_path / "r")])
    assert result.exit_code == 2, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "✗" in result.output


def test_run_missing_trace_and_directory_exit_2(tmp_path: Path) -> None:
    for target in (tmp_path / "missing.json", tmp_path):
        result = _cli.invoke(app, ["run", "--trace", str(target)])
        assert result.exit_code == 2, result.output
        assert isinstance(result.exception, SystemExit)


def test_run_unknown_scenario_exits_2() -> None:
    result = _cli.invoke(app, ["run", "--scenario", "no_such_scenario"])
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    assert "no_such_scenario" in result.output


def test_run_unknown_format_exits_2_before_analysis(tmp_path: Path) -> None:
    out = tmp_path / "r"
    result = _cli.invoke(
        app, ["run", "--scenario", "healthcare_patient_summary", "-f", "pdf", "-o", str(out)]
    )
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    assert not out.exists()


def test_run_refuses_a_report_passed_as_a_trace(tmp_path: Path) -> None:
    # A report (or any JSON object without 'events') used to load as an empty
    # trace and pass the CI gate with exit 0.
    out = tmp_path / "r"
    first = _cli.invoke(
        app, ["run", "--scenario", "healthcare_patient_summary", "-f", "json", "-o", str(out)]
    )
    assert first.exit_code == 1
    report = next(out.glob("*.json"))
    result = _cli.invoke(app, ["run", "--trace", str(report), "-o", str(tmp_path / "r2")])
    assert result.exit_code == 2
    assert "events" in result.output


def test_run_empty_events_warns(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text('{"events": []}', encoding="utf-8")
    result = _cli.invoke(app, ["run", "--trace", str(p), "-o", str(tmp_path / "r")])
    assert result.exit_code == 0
    assert "no events" in result.output


@pytest.mark.parametrize("content", ["[]", "{}", '{"verdict": "Pass"}'])
def test_report_rejects_non_report_json(tmp_path: Path, content: str) -> None:
    p = tmp_path / "x.json"
    p.write_text(content, encoding="utf-8")
    result = _cli.invoke(app, ["report", "--input", str(p), "-f", "markdown"])
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)


def test_report_unknown_format_exits_2(tmp_path: Path) -> None:
    out = tmp_path / "r"
    _cli.invoke(app, ["run", "--scenario", "hr_clean_case", "-f", "json", "-o", str(out)])
    report = next(out.glob("*.json"))
    result = _cli.invoke(app, ["report", "--input", str(report), "-f", "pdf"])
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)


def test_redact_non_utf8_file_is_a_clear_error(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    p.write_bytes(b"\xff\xfe\x00 ssn 123-45-6789")
    result = _cli.invoke(app, ["redact", str(p)])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "UTF-8" in result.output


def test_scan_output_to_directory_is_a_clear_error(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("x = 1\n", encoding="utf-8")
    result = _cli.invoke(app, ["scan", str(src), "-o", str(tmp_path)])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "could not write" in result.output


def test_run_unwritable_output_is_a_clear_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    result = _cli.invoke(
        app, ["run", "--scenario", "hr_clean_case", "-f", "json", "-o", str(blocker / "sub")]
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "could not write reports" in result.output
