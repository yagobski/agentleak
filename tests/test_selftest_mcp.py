# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The self-test MCP tools, driven over stdio with real JSON-RPC."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp.server")

from agentleak.selftest import SELFTEST_SCHEMA  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "selftest"

SELFTEST_TOOL_NAMES = {
    "privacy_selftest", "privacy_selftest_status", "privacy_explain_finding",
    "privacy_list_scenarios", "privacy_get_scenario",
}


class Session:
    def __init__(self, cwd: Path) -> None:
        env = {**os.environ, "AGENTLEAK_MCP_ROOT": str(cwd)}
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "agentleak", "mcp"], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.next_id = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.next_id += 1
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next_id,
                                          "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            assert line, self.proc.stderr.read() if self.proc.stderr else "server closed"
            message = json.loads(line)
            if message.get("id") == self.next_id:
                return message

    def notify(self, method: str) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})["result"]
        assert not result.get("isError"), result
        structured: dict[str, Any] = result["structuredContent"]
        return structured

    def call_error(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """A call that must fail: ``isError`` true, the error document as JSON text."""
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})["result"]
        assert result.get("isError") is True, result
        text = result["content"][0]["text"]
        doc: dict[str, Any] = json.loads(text[text.index("{"):])
        return doc


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    s = Session(tmp_path)
    init = s.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "pytest", "version": "0"}})
    assert init["result"]["serverInfo"]["name"] == "agentleak"
    assert init["result"]["serverInfo"]["version"]
    s.notify("notifications/initialized")
    yield s
    s.proc.terminate()
    s.proc.wait(timeout=10)


def test_tools_are_listed_with_precise_schemas(session: Session):
    tools = {t["name"]: t for t in session.request("tools/list")["result"]["tools"]}
    assert SELFTEST_TOOL_NAMES <= set(tools)
    assert {"privacy_preflight", "privacy_scan_code", "privacy_check_trace", "privacy_redact"} <= set(tools)
    props = tools["privacy_selftest"]["inputSchema"]["properties"]
    for name in ("trace", "trace_path", "steps", "scenario_instance", "code_path", "fail_on"):
        assert props[name].get("description"), name
    assert tools["privacy_selftest_status"]["annotations"]["readOnlyHint"] is True
    assert tools["privacy_explain_finding"]["annotations"]["readOnlyHint"] is True
    assert tools["privacy_selftest"]["annotations"]["openWorldHint"] is False
    assert "next_steps" in tools["privacy_selftest"]["description"]


def test_selftest_tool_returns_the_same_document_as_the_cli(session: Session):
    jsonschema = pytest.importorskip("jsonschema")
    trace = json.loads((FIXTURES / "agents_sdk_items.json").read_text())
    doc = session.call("privacy_selftest", {"trace": trace})
    jsonschema.validate(doc, SELFTEST_SCHEMA)
    assert doc["inputs"][0]["format"] == "openai_responses"
    assert doc["outcome"] == "fail" and doc["next_steps"][0]["fix"]["defense"]
    assert doc["rerun"]["mcp"]["tool"] == "privacy_selftest"


def test_loop_over_mcp_delta_status_and_explain(session: Session):
    leaky = json.loads((ROOT / "examples" / "healthcare_trace.json").read_text())
    clean = json.loads((ROOT / "examples" / "healthcare_clean_trace.json").read_text())
    first = session.call("privacy_selftest", {"trace": leaky})
    fp = first["findings"][0]["fingerprint"]
    explained = session.call("privacy_explain_finding", {"fingerprint": fp})
    assert explained["found"] and explained["fix"]
    second = session.call("privacy_selftest", {"trace": clean})
    assert second["passed"] and second["delta"]["direction"] == "improved"
    st = session.call("privacy_selftest_status")
    assert st["latest"]["passed"] is True and st["targets"][0]["runs"] == 2


def test_get_scenario_then_submit_the_trace(session: Session):
    listed = session.call("privacy_list_scenarios")
    assert {s["id"] for s in listed["scenarios"]} >= {"coding_deploy", "support_refund"}
    issued = session.call("privacy_get_scenario", {"scenario_id": "coding_deploy"})
    env = issued["scenario"]["records"][0]["fields"]
    trace = {
        "scenario_id": issued["submit"]["trace_scenario_id"],
        "events": [*issued["submit"]["baseline_events"],
                   {"channel": "generated_file", "content": f"export KEY={env['AWS_ACCESS_KEY_ID']}",
                    "target": "deploy.sh"},
                   {"channel": "final_output", "content": "Fixed the region."}],
    }
    doc = session.call("privacy_selftest", {"trace": trace})
    assert doc["detection"]["canary"]
    assert any(f["tier"] == "canary" and f["channel"] == "generated_file" for f in doc["findings"])


def test_paths_outside_the_root_are_refused(session: Session, tmp_path: Path):
    outside = session.call_error("privacy_selftest", {"trace_path": "/etc/hosts"})
    assert outside["outcome"] == "usage" and "outside the server root" in outside["error"]
    (tmp_path / "run.json").write_text((ROOT / "examples" / "hr_trace.json").read_text())
    inside = session.call("privacy_selftest", {"trace_path": "run.json"})
    assert inside["kind"] == "agentleak.selftest"
    escape = session.call_error("privacy_selftest", {"trace_path": "../" * 12 + "etc/hosts"})
    assert escape["outcome"] == "usage"


def test_steps_are_scored(session: Session):
    steps = [
        {"action": "read_file", "path": ".env", "observation": "GITHUB_TOKEN=ghp_" + "a" * 36},
        {"action": "write_file", "path": "ci.yml", "content": "token: ghp_" + "a" * 36},
        {"action": "finish", "content": "CI fixed."},
    ]
    doc = session.call("privacy_selftest", {"steps": steps})
    assert doc["inputs"][0]["format"] == "agent_steps"
    assert any(c["channel"] == "generated_file" and c["status"] == "leak" for c in doc["channels"])


def test_errors_come_back_as_structured_usage_errors(session: Session):
    # A failure is reported as one (isError true) and still carries the document.
    assert session.call_error("privacy_selftest")["outcome"] == "usage"
    bad = session.call_error("privacy_selftest", {"trace": {"events": []}})
    assert bad["outcome"] == "usage"
    assert session.call_error("privacy_get_scenario", {"scenario_id": "nope"})["outcome"] == "usage"


# ----------------------------------------------------------------------
# Hardening review: the original four tools had no path confinement, and every
# tool reported a failure with isError false.
# ----------------------------------------------------------------------
@pytest.mark.parametrize("tool", ["privacy_preflight", "privacy_scan_code"])
def test_code_tools_are_confined_to_the_root(session: Session, tmp_path: Path, tool: str):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "notes.py").write_text('print("patient SSN 123-45-6789")\n')
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    for path in (str(outside), "../" + outside.name, "link"):
        err = session.call_error(tool, {"path": path})
        assert "outside the server root" in err["error"], path
    assert not (outside / ".agentleak").exists(), "preflight wrote its memory outside the root"
    (tmp_path / "agent.py").write_text('print("hello")\n')
    inside = session.call(tool, {"path": "."})
    assert inside["files_scanned"] >= 1


def test_failures_are_reported_with_is_error(session: Session):
    assert "error" in session.call_error("privacy_check_trace", {"trace": {"events": []}})
    assert "error" in session.call_error("privacy_redact", {"text": "x", "style": "nope"})
