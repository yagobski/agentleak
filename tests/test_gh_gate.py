# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Tests for the GitHub Action entry point (scripts/gh_gate.py).

The Action is the artifact behind the "privacy is a required status check"
promise, so its contract is tested like product code: the right annotation
severity per finding level, a readable job summary, step outputs downstream
jobs can branch on, and an exit code that actually blocks a merge.

The CLI itself is stubbed here (a fake ``agentleak`` on PATH writing a known
report), so these tests assert the Action's own behavior rather than
re-testing detection.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1] / "scripts" / "gh_gate.py"

TRACE_REPORT = {
    "privacy_score": 62,
    "verdict": "High risk",
    "blocked": True,
    "agentrisk": {"risk_index": 0.3793},
    "compliance": {"failed_frameworks": ["gdpr.art5.1f", "hipaa.164.502b"]},
    "findings": [
        {
            "channel": "shared_memory", "data_type": "health_identifier", "level": 4,
            "level_label": "L4", "detector": "healthcare_detector", "confidence": 0.85,
            "recommendation": "Mask health identifiers before external tools.",
        },
        {
            "channel": "log", "data_type": "email", "level": 2, "level_label": "L2",
            "detector": "pii_detector", "confidence": 0.95,
            "recommendation": "Mask emails before logs.",
        },
        {
            "channel": "tool_call", "data_type": "person_name", "level": 1,
            "level_label": "L1", "detector": "pii_detector", "confidence": 0.55,
            "recommendation": "Prefer references over full names.",
        },
    ],
}

SCAN_REPORT = {
    "score": 48,
    "verdict": "Fail",
    "summary": {"files_scanned": 1, "total_findings": 2},
    "findings": [
        {
            "file": "bot.py", "line": 1, "level": 4, "rule": "hardcoded_secret",
            "data_type": "llm_api_key", "severity": "critical", "tier": "regex",
            "recommendation": "Rotate the key; inject it at the runtime boundary.",
        },
        {
            "file": "bot.py", "line": 3, "level": 2, "rule": "print_sensitive",
            "data_type": "ssn", "severity": "medium", "tier": "code_rule",
            "recommendation": "Do not print sensitive values.",
        },
    ],
}


@pytest.fixture()
def gate(tmp_path: Path):
    """Run the gate with a stubbed `agentleak` CLI and captured GitHub files."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    outputs = tmp_path / "outputs.txt"
    summary = tmp_path / "summary.md"
    outputs.touch()
    summary.touch()

    def _run(report: dict, *, exit_code: int = 0, is_scan: bool = False, **env: str):
        # A fake CLI: writes the report where the real one would, then exits
        # with the code a real gate failure would produce.
        if is_scan:
            # `scan` writes to the path given by --output.
            script = (
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                f"report = {report!r}\n"
                "args = sys.argv[1:]\n"
                "out = args[args.index('--output') + 1]\n"
                "open(out, 'w').write(json.dumps(report))\n"
                f"sys.exit({exit_code})\n"
            )
        else:
            # `run` writes <output-dir>/<run>.json.
            script = (
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                f"report = {report!r}\n"
                "args = sys.argv[1:]\n"
                "out = args[args.index('--output') + 1]\n"
                "os.makedirs(out, exist_ok=True)\n"
                "open(os.path.join(out, 'run_x.json'), 'w').write(json.dumps(report))\n"
                f"sys.exit({exit_code})\n"
            )
        stub = bin_dir / "agentleak"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

        proc = subprocess.run(
            [sys.executable, str(GATE)],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "GITHUB_OUTPUT": str(outputs),
                "GITHUB_STEP_SUMMARY": str(summary),
                **env,
            },
        )
        parsed = dict(
            line.split("=", 1)
            for line in outputs.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        return proc, parsed, summary.read_text(encoding="utf-8")

    return _run


# -- configuration ---------------------------------------------------------
def test_gate_refuses_to_run_with_nothing_to_analyze(gate) -> None:
    proc, _, _ = gate(TRACE_REPORT)
    assert proc.returncode == 2
    assert "Nothing to analyze" in proc.stdout


# -- trace mode ------------------------------------------------------------
def test_trace_annotations_are_graded_by_severity(gate) -> None:
    proc, _, _ = gate(TRACE_REPORT, exit_code=1, AL_SCENARIO="demo")

    # L4 -> error, L2 -> warning, L1 -> notice: a reviewer reads severity
    # from GitHub's own UI without opening the report.
    assert "::error title=AgentLeak L4: health_identifier in shared_memory::" in proc.stdout
    assert "::warning title=AgentLeak L2: email in log::" in proc.stdout
    assert "::notice title=AgentLeak L1: person_name in tool_call::" in proc.stdout


def test_trace_annotations_encode_newlines(gate) -> None:
    proc, _, _ = gate(TRACE_REPORT, exit_code=1, AL_SCENARIO="demo")
    # A raw newline would truncate the workflow command.
    annotation = next(ln for ln in proc.stdout.splitlines() if ln.startswith("::error title=AgentLeak L4"))
    assert "%0A" in annotation
    assert "Mask health identifiers" in annotation


def test_trace_outputs_and_blocking_exit_code(gate) -> None:
    proc, outputs, _ = gate(TRACE_REPORT, exit_code=1, AL_SCENARIO="demo", AL_FAIL_UNDER="80")

    assert proc.returncode == 1, "a failing gate must block the merge"
    assert outputs["score"] == "62"
    assert outputs["verdict"] == "High risk"
    assert outputs["risk-index"] == "0.3793"
    assert outputs["findings"] == "3"
    assert outputs["report"].endswith("run_x.json")


def test_trace_summary_is_readable(gate) -> None:
    _, _, summary = gate(TRACE_REPORT, exit_code=1, AL_SCENARIO="demo", AL_FAIL_UNDER="80")

    assert "## AgentLeak privacy gate" in summary
    assert "privacy score **62/100**" in summary
    assert "| `shared_memory` |" in summary and "L4" in summary
    assert "Compliance at risk:" in summary and "gdpr.art5.1f" in summary
    assert "blocks the merge" in summary


def test_clean_run_passes_and_says_so(gate) -> None:
    clean = {**TRACE_REPORT, "privacy_score": 100, "verdict": "Pass",
             "blocked": False, "findings": [], "compliance": {}}
    proc, outputs, summary = gate(clean, exit_code=0, AL_SCENARIO="clean")

    assert proc.returncode == 0
    assert outputs["verdict"] == "Pass"
    assert "No sensitive value crossed the boundary" in summary


def test_annotations_can_be_disabled(gate) -> None:
    proc, _, summary = gate(
        TRACE_REPORT, exit_code=1, AL_SCENARIO="demo", AL_ANNOTATE="false"
    )
    assert "::error title=AgentLeak L4" not in proc.stdout
    assert "## AgentLeak privacy gate" in summary  # summary still written


def test_summary_can_be_disabled(gate) -> None:
    _, _, summary = gate(TRACE_REPORT, exit_code=1, AL_SCENARIO="demo", AL_SUMMARY="false")
    assert summary == ""


# -- scan mode -------------------------------------------------------------
def test_scan_annotations_point_at_file_and_line(gate) -> None:
    proc, outputs, summary = gate(
        SCAN_REPORT, exit_code=1, is_scan=True, AL_SCAN="bot.py", AL_FAIL_UNDER="80"
    )

    assert "file=bot.py,line=1" in proc.stdout
    assert "::error title=AgentLeak L4: hardcoded_secret" in proc.stdout
    assert "::warning title=AgentLeak L2: print_sensitive" in proc.stdout
    assert outputs["score"] == "48"
    assert outputs["risk-index"] == "", "a code scan has no AgentRisk index"
    assert "across 1 file(s)" in summary


def test_missing_report_is_reported_not_silently_passed(gate, tmp_path: Path) -> None:
    # The CLI exits non-zero without writing anything (e.g. it crashed).
    bin_dir = tmp_path / "bin2"
    bin_dir.mkdir()
    stub = bin_dir / "agentleak"
    stub.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n", encoding="utf-8")
    stub.chmod(0o755)

    proc = subprocess.run(
        [sys.executable, str(GATE)],
        capture_output=True, text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
             "AL_SCENARIO": "demo"},
    )

    assert proc.returncode != 0
    assert "produced no report" in proc.stdout


def test_action_yml_matches_the_script_contract() -> None:
    """The Action's inputs/outputs must line up with what the script reads."""
    action = (Path(__file__).resolve().parents[1] / "action.yml").read_text(encoding="utf-8")
    script = GATE.read_text(encoding="utf-8")

    for env_var in ("AL_TRACE", "AL_SCENARIO", "AL_PACK", "AL_SCAN",
                    "AL_FAIL_UNDER", "AL_CONFIG", "AL_ANNOTATE", "AL_SUMMARY"):
        assert env_var in action, f"{env_var} must be wired in action.yml"
        assert env_var in script, f"{env_var} must be read by the gate script"

    for output in ("score", "risk-index", "verdict", "findings", "report"):
        assert f"{output}:" in action
        assert f'_set_output("{output}"' in script
