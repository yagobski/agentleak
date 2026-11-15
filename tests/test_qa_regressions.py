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


# ----------------------------------------------------------------------
# QA-04: the HTML report did not escape trace-controlled strings (stored XSS)
# ----------------------------------------------------------------------


def test_html_report_escapes_trace_controlled_fields() -> None:
    from agentleak import AgentLeakRunner, Trace
    from agentleak.reporters import render

    payload = "<script>alert(1)</script>"
    trace = Trace.from_dict({
        "run_id": "r" + payload,
        "agent_name": "a" + payload,
        "scenario_id": "s" + payload,
        "events": [
            {"channel": "tool_response", "source": "db", "content": "SSN 123-45-6789"},
            {"channel": "log", "source": "x" + payload, "content": "SSN 123-45-6789"},
        ],
    })
    data = AgentLeakRunner().analyze(trace).to_dict()
    html = render(data, "html")
    assert payload not in html
    assert "&lt;script&gt;" in html
    # A crafted report posted to /api/render/html reaches the insight builder.
    data["channel_risks"] = [
        {"channel": "log<img src=x onerror=alert(1)>", "level": "high", "ri": 0.5,
         "level_label": "L4"},
    ]
    assert "<img src=x" not in render(data, "html")


def test_regex_safety_flags_nested_variable_repeats() -> None:
    from agentleak.core.regex_safety import UnsafeRegexError, check_regex

    for bad in [r"(a+)+$", r"(\w*\s?)*", r"(?:x+y?)+z"]:
        with pytest.raises(UnsafeRegexError):
            check_regex(bad)
    for good in [r"\bEMP-\d{6}\b", r"(\d{3}-)+", r"[A-Z]{2}\d+", r"(?:ab)+"]:
        check_regex(good)


@pytest.mark.parametrize("data", [[], {"events": 3}, {"events": ["x"]}])
def test_trace_from_dict_rejects_non_traces_with_value_error(data) -> None:
    from agentleak import Trace

    with pytest.raises(ValueError):
        Trace.from_dict(data)


# ----------------------------------------------------------------------
# QA-08: `validate --trace` failed when no agentleak.yaml was present
# ----------------------------------------------------------------------


def test_validate_trace_only_needs_no_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t.json").write_text('{"events": [{"channel": "log", "content": "hi"}]}', "utf-8")
    result = _cli.invoke(app, ["validate", "--trace", "t.json"])
    assert result.exit_code == 0, result.output
    assert "config not found" not in result.output
    # A config named explicitly is still required.
    assert _cli.invoke(app, ["validate", "missing.yaml", "--trace", "t.json"]).exit_code == 1
    # And a config check alone still reports the missing default file.
    assert _cli.invoke(app, ["validate"]).exit_code == 1


def test_validate_refuses_json_that_is_not_a_trace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "r.json").write_text('{"verdict": "Pass"}', "utf-8")
    assert _cli.invoke(app, ["validate", "--trace", "r.json"]).exit_code == 1


# ----------------------------------------------------------------------
# QA-09: quadratic regex scans in the built-in detectors
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["1-" * 25_000, "a." * 25_000, "QUFB" * 12_500],
    ids=["dash-run", "dot-run", "base64-run"],
)
def test_builtin_detectors_stay_fast_on_long_runs(text: str) -> None:
    import time

    from agentleak.detectors import build_detectors

    for detector in build_detectors(None, None):
        start = time.perf_counter()
        detector.detect(text)
        elapsed = time.perf_counter() - start
        # Before the fix: secrets 23 s on the dash run, pii about 3 s on each.
        assert elapsed < 1.5, f"{detector.name} took {elapsed:.1f}s"


def test_secret_assignment_still_matches_prefixed_keys() -> None:
    from agentleak.detectors.secrets import SecretsDetector

    text = "DB_PASSWORD=hunter2hunter OPENAI_API_KEY: zz9ab7cd aws_secret_access_key = q1w2e3r4t5"
    values = {m.matched_value for m in SecretsDetector().detect(text)}
    assert {"hunter2hunter", "zz9ab7cd", "q1w2e3r4t5"} <= values


# ----------------------------------------------------------------------
# QA-11: deeply nested event content raised RecursionError (500 on selftest)
# ----------------------------------------------------------------------


def test_deeply_nested_content_is_a_value_error() -> None:
    from agentleak import Trace

    content: object = "x"
    for _ in range(3000):
        content = {"k": content}
    with pytest.raises(ValueError, match="nested"):
        Trace.from_dict({"events": [{"channel": "log", "content": content}]})
    shallow: object = "x"
    for _ in range(50):
        shallow = {"k": shallow}
    assert Trace.from_dict({"events": [{"channel": "log", "content": shallow}]}).events


# ----------------------------------------------------------------------
# QA-12: AgentLeakClient against a platform with accounts said only
# "401 Not authenticated"; docs/platform.md never mentioned --local
# ----------------------------------------------------------------------


def test_client_401_explains_how_to_connect(monkeypatch) -> None:
    import io
    import urllib.error
    import urllib.request

    from agentleak.client import AgentLeakClient, AgentLeakError

    def deny(req, timeout=0):  # noqa: ANN001, ANN202
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"detail": "Not authenticated"}')
        )

    monkeypatch.setattr(urllib.request, "urlopen", deny)
    with pytest.raises(AgentLeakError, match="serve --local"):
        AgentLeakClient("support-bot", base_url="http://127.0.0.1:1")
    doc = (Path(__file__).parents[1] / "docs" / "platform.md").read_text("utf-8")
    assert "serve --local" in doc


def test_run_ingest_accepts_a_trace_dict() -> None:
    import agentleak

    with agentleak.watch(print_summary=False) as run:
        run.ingest({"events": [{"channel": "log", "content": "SSN 123-45-6789"}]})
    assert len(run.trace.events) == 1
    assert run.report is not None and run.report.findings


# ----------------------------------------------------------------------
# QA-13: GitHub Action gate (scripts/gh_gate.py)
# ----------------------------------------------------------------------


def _run_gate(tmp_path: Path, reports: dict[str, dict], **env: str):
    import os
    import subprocess
    import sys

    gate = Path(__file__).resolve().parents[1] / "scripts" / "gh_gate.py"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "agentleak"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"reports = {reports!r}\n"
        "args = sys.argv[1:]\n"
        "out = args[args.index('--output') + 1]\n"
        "os.makedirs(out, exist_ok=True)\n"
        "for name, rep in reports.items():\n"
        "    open(os.path.join(out, name), 'w').write(json.dumps(rep))\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    outputs, summary = tmp_path / "out.txt", tmp_path / "sum.md"
    outputs.touch()
    summary.touch()
    proc = subprocess.run(
        [sys.executable, str(gate)], capture_output=True, text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
             "GITHUB_OUTPUT": str(outputs), "GITHUB_STEP_SUMMARY": str(summary), **env},
    )
    parsed = dict(ln.split("=", 1) for ln in outputs.read_text().splitlines() if "=" in ln)
    return proc, parsed, summary.read_text()


def test_gate_headlines_the_worst_of_several_runs(tmp_path: Path) -> None:
    clean = {"run_id": "a_clean", "privacy_score": 100, "verdict": "Pass", "blocked": False,
             "findings": []}
    leaky = {"run_id": "b_leaky", "privacy_score": 20, "verdict": "Fail", "blocked": True,
             "findings": [{"channel": "log", "data_type": "ssn", "level": 4}]}
    proc, out, summary = _run_gate(
        tmp_path, {"a_clean.json": clean, "b_leaky.json": leaky}, AL_SCENARIO="all"
    )
    assert proc.returncode == 1
    assert out["verdict"] == "Fail" and out["score"] == "20"
    assert out["findings"] == "1"
    assert "2 runs analyzed, 1 blocked" in summary


def test_gate_escapes_workflow_commands_and_reads_posture(tmp_path: Path) -> None:
    evil = {"run_id": "r", "privacy_score": 10, "verdict": "Fail", "blocked": True,
            "compliance": {"posture": {"failed_frameworks": ["gdpr"]}},
            "findings": [{"channel": "log", "level": 4,
                          "data_type": "x,file=evil.py\n::warning::injected 100%0A"}]}
    proc, _, summary = _run_gate(tmp_path, {"r.json": evil}, AL_TRACE="t.json")
    lines = proc.stdout.splitlines()
    assert not any(ln.startswith("::warning::injected") for ln in lines)
    annotation = next(ln for ln in lines if ln.startswith("::error "))
    properties = annotation[len("::error "):].split("::", 1)[0]
    assert ",file=" not in properties  # the comma could not start a new property
    assert "100%250A" in proc.stdout
    assert "Compliance at risk:** gdpr" in summary


def test_action_never_pastes_inputs_into_shell_source() -> None:
    import re

    import yaml

    action = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "action.yml").read_text(encoding="utf-8")
    )
    for step in action["runs"]["steps"]:
        script = step.get("run", "")
        assert not re.search(r"\$\{\{\s*inputs\.", script), step.get("name")


# ----------------------------------------------------------------------
# QA-14: `redact --style hash` was an unkeyed SHA-256, reversible by brute force
# ----------------------------------------------------------------------


def test_hash_redaction_is_not_a_plain_sha256() -> None:
    import hashlib

    from agentleak.defenses import sanitize_text

    ssn = "412-55-9087"
    out = sanitize_text(f"SSN: {ssn}", style="hash")
    assert hashlib.sha256(ssn.encode()).hexdigest()[:16] not in out
    # Still stable within a process, so equal values stay linkable in one log.
    assert out == sanitize_text(f"SSN: {ssn}", style="hash")
