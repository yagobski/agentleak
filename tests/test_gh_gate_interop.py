# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The Action's SARIF output and sticky pull-request comment, and the escaping
of everything a report can carry into GitHub (summary, comment, outputs, log).

Report values are attacker-influenced: a trace comes from the pull request
under test, a custom rule can name a data type, a file can be called anything.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1] / "scripts" / "gh_gate.py"

HOSTILE = "evil`|<img src=x onerror=alert(1)>[link](https://attacker.example)@octocat\n::error::pwned\r%0A"


@pytest.fixture()
def gh_gate():
    spec = importlib.util.spec_from_file_location("gh_gate_under_test", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _report(run_id="run_a", data_type="ssn", channel="tool_call", **extra):
    return {"run_id": run_id, "privacy_score": 40, "verdict": "Fail", "blocked": True,
            "findings": [{"channel": channel, "data_type": data_type, "level": 4,
                          "detector": "pii_detector", "recommendation": "Mask it."}], **extra}


def _assert_inert(text: str) -> None:
    for bad in ("<img", "](", "@octocat", "`|", "\n::error::", "|<"):
        assert bad not in text, bad


def test_md_and_code_neutralise_markup(gh_gate):
    assert gh_gate._md(HOSTILE).count("\n") == 0
    _assert_inert(gh_gate._md(HOSTILE))
    code = gh_gate._code(HOSTILE)
    assert code.startswith("`") and code.endswith("`") and code.count("`") == 2
    assert "<" not in code and "|" not in code and "\n" not in code


def test_summary_escapes_hostile_report_values(gh_gate):
    report = _report(run_id=HOSTILE, data_type=HOSTILE, channel=HOSTILE,
                     verdict=HOSTILE, detection={"mode": HOSTILE, "tiers": [HOSTILE]},
                     compliance={"failed_frameworks": [HOSTILE]})
    report["findings"][0]["recommendation"] = HOSTILE
    text = gh_gate._summarize_trace(report, 80, True)
    _assert_inert(text)
    # one table row per channel: the hostile channel cannot add rows or columns
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "Worst level" not in ln
            and "---" not in ln]
    assert len(rows) == 1 and rows[0].count("|") == 4


def test_scan_summary_escapes_hostile_file_names(gh_gate):
    report = {"score": 10, "summary": {"files_scanned": 1}, "findings": [
        {"file": "a`|b<script>.py\n## pwned", "line": "3\n", "level": 4, "rule": HOSTILE}]}
    text = gh_gate._summarize_scan(report, 80)
    _assert_inert(text)
    assert "## pwned" not in text and "<script>" not in text


def test_outputs_cannot_inject_another_output(gh_gate, tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    gh_gate._set_output("verdict", "Fail\nscore=100\r\nx<<EOF")
    lines = out.read_text().splitlines()
    assert lines == ["verdict=Fail score=100  x<<EOF"]


def test_comment_body_with_baseline(gh_gate):
    base = [_report(), _report(data_type="email", channel="log")]
    head = [_report(), _report(data_type=HOSTILE, channel="shared_memory", run_id=HOSTILE)]
    body = gh_gate._comment_body(head, 80, base)
    assert body.startswith(gh_gate.COMMENT_MARKER)
    assert "1 new, 1 resolved" in body
    assert "| new |" in body and "| resolved |" in body
    _assert_inert(body)
    assert "Values are never shown" in body


def test_comment_body_says_what_a_black_box_import_did_not_see(gh_gate):
    report = _report(observation={"source": "garak", "observable_channels": ["user_input",
                                                                           "final_output"],
                                  "unobserved_channels": ["tool_call", "log"]})
    body = gh_gate._comment_body([report], 80, None)
    assert "Not observed, so not audited: tool&#95;call" not in body  # underscores kept readable
    assert "Not observed, so not audited: tool_call, log" in body


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _event(tmp_path, number=7):
    path = tmp_path / "event.json"
    path.write_text(json.dumps({"pull_request": {"number": number}}))
    return path


def test_sticky_comment_updates_the_existing_one(gh_gate, tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(request, timeout=0):
        calls.append((request.get_method(), request.full_url, request.data))
        if request.get_method() == "GET":
            return _FakeResponse([
                {"id": 1, "body": "unrelated", "user": {"type": "User"}},
                {"id": 2, "body": gh_gate.COMMENT_MARKER + " spoofed", "user": {"type": "User"}},
                {"id": 3, "body": gh_gate.COMMENT_MARKER + " old", "user": {"type": "Bot"}},
            ])
        return _FakeResponse({})

    monkeypatch.setattr(gh_gate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("AL_GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(_event(tmp_path)))
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert gh_gate._post_sticky_comment("body") == "updated"
    method, url, data = calls[-1]
    assert method == "PATCH" and url.endswith("/repos/owner/repo/issues/comments/3")
    assert json.loads(data) == {"body": "body"}


def test_sticky_comment_creates_and_never_fails_the_gate(gh_gate, tmp_path, monkeypatch):
    monkeypatch.setenv("AL_GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(_event(tmp_path)))
    posted = []

    def ok(request, timeout=0):
        posted.append(request.get_method())
        return _FakeResponse([] if request.get_method() == "GET" else {})

    monkeypatch.setattr(gh_gate.urllib.request, "urlopen", ok)
    assert gh_gate._post_sticky_comment("b") == "created" and posted == ["GET", "POST"]

    def denied(request, timeout=0):
        raise gh_gate.urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)

    monkeypatch.setattr(gh_gate.urllib.request, "urlopen", denied)
    assert gh_gate._post_sticky_comment("b") == "failed"


def test_sticky_comment_refuses_odd_settings(gh_gate, tmp_path, monkeypatch):
    monkeypatch.setenv("AL_GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(_event(tmp_path)))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo/../../x")
    assert gh_gate._post_sticky_comment("b").startswith("skipped")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_API_URL", "http://insecure.example")
    assert gh_gate._post_sticky_comment("b").startswith("skipped")
    monkeypatch.delenv("GITHUB_API_URL")
    (tmp_path / "event.json").write_text(json.dumps({"push": {}}))
    assert gh_gate._post_sticky_comment("b") == "skipped: not a pull_request event"


# -- end to end with a stub CLI ----------------------------------------------
def _stub(bin_dir: Path, report: dict, *, sarif: bool) -> None:
    sarif_log = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "AgentLeak"}},
                                               "results": [{"message": {"text": "x"}}]}]}
    bin_dir.mkdir()
    stub = bin_dir / "agentleak"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"report = {report!r}\n"
        f"sarif = {sarif_log!r}\n"
        "args = sys.argv[1:]\n"
        "print('Agent: x\\n::error::injected-by-trace')\n"
        "out = args[args.index('--output') + 1]\n"
        "os.makedirs(out, exist_ok=True)\n"
        "open(os.path.join(out, 'r1.json'), 'w').write(json.dumps(report))\n"
        f"if {sarif!r} and 'sarif' in args[args.index('--format') + 1]:\n"
        "    open(os.path.join(out, 'r1.sarif'), 'w').write(json.dumps(sarif))\n"
        "    open(os.path.join(out, 'r2.sarif'), 'w').write(json.dumps(sarif))\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def test_gate_writes_merged_sarif_and_fences_cli_output(tmp_path):
    _stub(tmp_path / "bin", _report(), sarif=True)
    outputs = tmp_path / "out.txt"
    outputs.touch()
    proc = subprocess.run(
        [sys.executable, str(GATE)], capture_output=True, text=True,
        env={**os.environ, "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
             "GITHUB_OUTPUT": str(outputs), "AL_TRACE": "t\n::error::from-file-name.json",
             "AL_SARIF": str(tmp_path / "agentleak.sarif"), "AL_PR_COMMENT": "true"},
    )
    assert proc.returncode == 1
    lines = proc.stdout.splitlines()
    # The CLI's own output is fenced by stop-commands; the echoed command line
    # cannot start a workflow command.
    start = next(i for i, ln in enumerate(lines) if ln.startswith("::stop-commands::"))
    token = lines[start].split("::")[2]
    end = lines.index(f"::{token}::")
    assert start < lines.index("::error::injected-by-trace") < end
    assert not any(ln.startswith("::error::from-file-name") for ln in lines)
    merged = json.loads((tmp_path / "agentleak.sarif").read_text())
    assert len(merged["runs"]) == 2
    parsed = dict(ln.split("=", 1) for ln in outputs.read_text().splitlines())
    assert parsed["sarif"].endswith("agentleak.sarif")
    assert parsed["comment"].startswith("skipped")   # no token, no PR event: never fatal


def test_action_wires_the_new_inputs():
    import yaml

    action = yaml.safe_load((GATE.parents[1] / "action.yml").read_text(encoding="utf-8"))
    for name in ("sarif", "pr-comment", "baseline", "github-token"):
        assert name in action["inputs"]
    assert action["inputs"]["pr-comment"]["default"] == "false"
    assert action["inputs"]["sarif"]["default"] == ""
    for name in ("sarif", "comment"):
        assert name in action["outputs"]
    env = next(s for s in action["runs"]["steps"] if s.get("id") == "gate")["env"]
    for var in ("AL_SARIF", "AL_PR_COMMENT", "AL_BASELINE", "AL_GITHUB_TOKEN"):
        assert var in env
