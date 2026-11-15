# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""HTTP parity, the end-to-end "agent fixes itself" loop, and the hook recipes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from agentleak.selftest import SELFTEST_SCHEMA
from agentleak.selftest.runner import SelftestOptions, selftest_traces

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
FIXTURES = ROOT / "tests" / "fixtures" / "selftest"
HOOKS = EXAMPLES / "selftest" / "hooks"


# ----------------------------------------------------------------------
# HTTP: same document shape as the CLI
# ----------------------------------------------------------------------
@pytest.fixture()
def api(tmp_path: Path, monkeypatch) -> Any:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from agentleak.core.store import Store
    from agentleak.web.app import create_app

    monkeypatch.setenv("AGENTLEAK_LOCAL_MODE", "1")
    client = TestClient(create_app(store=Store(str(tmp_path / "t.db"))))
    pid = client.post("/api/projects", json={"name": "bot"}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]
    client.headers.update({"X-AgentLeak-Key": key})
    return client


def test_http_selftest_returns_the_cli_document(api: Any, tmp_path: Path):
    jsonschema = pytest.importorskip("jsonschema")
    trace = json.loads((EXAMPLES / "healthcare_trace.json").read_text())
    http_doc = api.post("/api/agent/selftest", json={"trace": trace}).json()
    jsonschema.validate(http_doc, SELFTEST_SCHEMA)
    cli_doc = selftest_traces([str(EXAMPLES / "healthcare_trace.json")],
                              SelftestOptions(state_dir=str(tmp_path / "s")))
    for key in ("passed", "outcome", "verdict", "risk_index", "privacy_score", "findings_total"):
        assert http_doc[key] == cli_doc[key], key
    assert [c["status"] for c in http_doc["channels"]] == [c["status"] for c in cli_doc["channels"]]
    assert {f["fingerprint"] for f in http_doc["findings"]} == {f["fingerprint"] for f in cli_doc["findings"]}
    assert [s["kind"] for s in http_doc["next_steps"]][:3] == [s["kind"] for s in cli_doc["next_steps"]][:3]
    assert http_doc["mode"] == "http" and http_doc["platform_run_id"].startswith("run_")


def test_http_delta_and_any_trace_format(api: Any):
    first = api.post("/api/agent/selftest", json={"trace": json.loads(
        (FIXTURES / "agents_sdk_items.json").read_text())}).json()
    assert first["inputs"][0]["format"] == "openai_responses" and first["delta"] is None
    clean = json.loads((EXAMPLES / "healthcare_clean_trace.json").read_text())
    second = api.post("/api/agent/selftest", json={"trace": clean}).json()
    assert second["delta"]["previous_run_id"] == first["platform_run_id"]
    assert second["delta"]["direction"] == "improved"


def test_http_rejects_bad_input_and_missing_key(api: Any):
    assert api.post("/api/agent/selftest", json={"trace": {"events": []}}).status_code == 400
    api.headers.pop("X-AgentLeak-Key")
    assert api.post("/api/agent/selftest", json={"scenario_id": "hr_employee_case"}).status_code == 401


def test_improve_is_unchanged(api: Any):
    trace = json.loads((EXAMPLES / "healthcare_trace.json").read_text())
    body = api.post("/api/agent/improve", json={"trace": trace}).json()
    assert {"passed", "delta", "next_steps", "risk_index", "privacy_score", "verdict"} <= set(body)


def test_client_document_mode_and_local_helper(monkeypatch):
    from agentleak import client as client_mod

    calls: list[tuple[str, str, Any]] = []

    def fake(base: str, method: str, path: str, body: Any = None, **kw: Any) -> Any:
        calls.append((method, path, body))
        if path == "/api/projects" and method == "GET":
            return []
        if path == "/api/projects":
            return {"id": "proj_1"}
        if path.endswith("/api-key"):
            return {"api_key": "ak_test"}
        return {"kind": "agentleak.selftest"}

    monkeypatch.setattr(client_mod, "_http_request", fake)
    me = client_mod.AgentSelfClient.for_local_server("bot", base_url="http://127.0.0.1:9")
    assert me.api_key == "ak_test"
    assert me.selftest({"events": []}, document=True)["kind"] == "agentleak.selftest"
    assert calls[-1][1] == "/api/agent/selftest" and calls[-1][2]["fail_on"] == "L3"
    with pytest.raises(client_mod.AgentLeakError):
        client_mod.AgentSelfClient.for_local_server(base_url="http://example.com")


# ----------------------------------------------------------------------
# The loop: a leaky toy agent fixes itself until green
# ----------------------------------------------------------------------
def test_the_leaky_agent_reaches_green_by_applying_next_steps(tmp_path: Path):
    sys.path.insert(0, str(EXAMPLES / "selftest"))
    try:
        import fix_loop  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    transcript = fix_loop.run_loop(tmp_path, agentleak=[sys.executable, "-m", "agentleak"])
    first, last = transcript[0], transcript[-1]
    assert first["passed"] is False and first["exit_code"] == 1
    assert set(first["leaking_channels"]) >= {"tool_call", "log", "shared_memory"}
    assert last["passed"] is True and last["exit_code"] == 0
    assert len(transcript) <= 7
    # Every step after the first reports a delta, and the run ends improved.
    assert all(row["delta"] is not None for row in transcript[1:])
    assert last["delta"]["direction"] == "improved"
    applied = [row["applied"] for row in transcript if row["applied"]]
    assert all(a.startswith("Sanitizer on ") for a in applied)
    config = json.loads((tmp_path / "agent_config.json").read_text())
    assert set(config["sanitize"]) == {"tool_call", "log", "generated_file",
                                       "inter_agent_message", "shared_memory"}


# ----------------------------------------------------------------------
# Hooks
# ----------------------------------------------------------------------
def _hook_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def test_claude_code_stop_hook_blocks_on_an_l4_leak(tmp_path: Path):
    event = {
        "session_id": "abc123",
        "transcript_path": str(FIXTURES / "claude_code_session.jsonl"),
        "cwd": str(tmp_path),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": "Fixed.",
    }
    proc = subprocess.run([sys.executable, str(HOOKS / "agentleak_stop_hook.py")],
                          input=json.dumps(event), capture_output=True, text=True,
                          env=_hook_env(), timeout=120, check=False)
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["decision"] == "block"
    assert "aws_access_key" in out["reason"] and "AKIAIOSFODNN7EXAMPLE" not in out["reason"]


def test_claude_code_stop_hook_never_loops(tmp_path: Path):
    event = {"transcript_path": str(FIXTURES / "claude_code_session.jsonl"),
             "cwd": str(tmp_path), "stop_hook_active": True}
    proc = subprocess.run([sys.executable, str(HOOKS / "agentleak_stop_hook.py")],
                          input=json.dumps(event), capture_output=True, text=True,
                          env=_hook_env(), timeout=120, check=False)
    assert proc.returncode == 0 and proc.stdout.strip() == ""
    assert "AgentLeak self-test" in proc.stderr


def test_claude_code_stop_hook_lets_a_clean_session_stop(tmp_path: Path):
    clean = tmp_path / "clean.jsonl"
    clean.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n"
                     + json.dumps({"type": "assistant", "message": {"role": "assistant",
                                   "content": [{"type": "text", "text": "Hello."}]}}) + "\n")
    proc = subprocess.run([sys.executable, str(HOOKS / "agentleak_stop_hook.py")],
                          input=json.dumps({"transcript_path": str(clean), "cwd": str(tmp_path)}),
                          capture_output=True, text=True, env=_hook_env(), timeout=120, check=False)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


@pytest.mark.skipif(shutil.which("git") is None or os.name == "nt", reason="needs git and sh")
def test_pre_commit_hook_refuses_a_secret(tmp_path: Path):
    env = _hook_env()
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=tmp_path, env=env, capture_output=True,
                              text=True, check=False, timeout=120)

    git("init", "-q")
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    shutil.copy(HOOKS / "pre-commit", hook)
    hook.chmod(0o755)
    (tmp_path / "agent.py").write_text("def run():\n    return 1\n")
    git("add", "agent.py")
    assert git("commit", "-qm", "clean").returncode == 0
    (tmp_path / "leak.py").write_text('AWS = "AKIAIOSFODNN7EXAMPLE"\n')
    git("add", "leak.py")
    refused = git("commit", "-qm", "leak")
    assert refused.returncode != 0 and "commit refused" in refused.stderr
