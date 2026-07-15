"""Tests for the agent-first platform API: agent cards, code scans, and the
autonomous self-improvement loop (register → scan → improve → status)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web.app import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path, login) -> TestClient:
    return login(TestClient(create_app(store=Store(str(tmp_path / "api.db")))))


CARD = {
    "name": "support-bot",
    "description": "Handles support tickets",
    "capabilities": ["ticket_triage", "crm_lookup"],
    "tags": ["support"],
    "examples": ["triage this ticket"],
    "agent_protocol_version": "a2a-v1",
    "endpoints": {"/chat": "Chat endpoint", "/health": "Health check"},
    "source": {"type": "github", "repo": "acme/support-bot", "branch": "main"},
}

LEAKY_FILE = {
    "path": "agent.py",
    "content": 'import logging\nlogger = logging.getLogger()\n'
               'password = "hunter2secret99"\n'
               'logger.info(f"ssn={user_ssn}")\n',
}

LEAKY_TRACE = {
    "run_id": "run_x",
    "agent_name": "support-bot",
    "events": [
        {"channel": "tool_call", "source": "agent", "target": "crm",
         "content": {"customer_email": "jane@acme.com", "ssn": "123-45-6789"}},
        {"channel": "final_output", "content": "All set!"},
    ],
}

CLEAN_TRACE = {
    "run_id": "run_y",
    "agent_name": "support-bot",
    "events": [
        {"channel": "tool_call", "source": "agent", "target": "crm",
         "content": {"ticket": "TCK-1", "status": "resolved"}},
        {"channel": "final_output", "content": "All set!"},
    ],
}


def _project_with_key(client: TestClient) -> tuple[str, str]:
    pid = client.post("/api/projects", json={"name": "Support Bot"}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]
    return pid, key


# -- session-authenticated agent-card management ------------------------
def test_agent_card_crud(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]

    # No card yet.
    assert client.get(f"/api/projects/{pid}/agent-card").json()["agent_card"] is None

    # Attach.
    r = client.put(f"/api/projects/{pid}/agent-card", json={"agent_card": CARD})
    assert r.status_code == 200
    assert r.json()["agent_card"]["name"] == "support-bot"

    # Visible on the project itself.
    assert client.get(f"/api/projects/{pid}").json()["agent_card"]["name"] == "support-bot"

    # Invalid card rejected.
    bad = client.put(f"/api/projects/{pid}/agent-card", json={"agent_card": {"name": ""}})
    assert bad.status_code == 400

    # Delete.
    assert client.delete(f"/api/projects/{pid}/agent-card").json()["deleted"] is True
    assert client.get(f"/api/projects/{pid}/agent-card").json()["agent_card"] is None


def test_agent_card_requires_auth(tmp_path):
    anon = TestClient(create_app(store=Store(str(tmp_path / "anon.db"))))
    assert anon.get("/api/projects/x/agent-card").status_code == 401


# -- code scans ----------------------------------------------------------
def test_code_scan_with_inline_files(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    r = client.post(
        f"/api/projects/{pid}/code-scan",
        json={"source": "files", "files": [LEAKY_FILE]},
    )
    assert r.status_code == 200
    scan = r.json()
    assert scan["id"].startswith("scan_")
    assert scan["findings_count"] > 0
    assert scan["score"] < 100
    assert scan["result"]["findings"][0]["file"] == "agent.py"

    # Listed + retrievable.
    scans = client.get(f"/api/projects/{pid}/code-scans").json()
    assert len(scans) == 1
    full = client.get(f"/api/code-scans/{scan['id']}").json()
    assert full["result"]["summary"]["total_findings"] == scan["findings_count"]


def test_code_scan_bad_payload(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/code-scan", json={"source": "files", "files": []})
    assert r.status_code == 400
    # Empty body with no card source is also a 400.
    r = client.post(f"/api/projects/{pid}/code-scan", json={})
    assert r.status_code == 400


def test_code_scan_other_users_project_hidden(client: TestClient, login):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    scan = client.post(
        f"/api/projects/{pid}/code-scan",
        json={"source": "files", "files": [LEAKY_FILE]},
    ).json()
    other = login(
        TestClient(client.app), email="other@agentleak.local", password="other-pass-123"
    )
    assert other.get(f"/api/code-scans/{scan['id']}").status_code == 404


# -- autonomous agent API (X-AgentLeak-Key) -------------------------------
def test_agent_register_and_card(client: TestClient):
    _, key = _project_with_key(client)
    fresh = TestClient(client.app)  # no session cookie — key only

    r = fresh.post("/api/agent/register", json={"agent_card": CARD},
                   headers={"X-AgentLeak-Key": key})
    assert r.status_code == 200
    body = r.json()
    assert body["registered"] is True
    assert body["agent_card"]["source"]["repo"] == "acme/support-bot"

    got = fresh.get("/api/agent/card", headers={"X-AgentLeak-Key": key}).json()
    assert got["agent_card"]["name"] == "support-bot"


def test_agent_register_rejects_bad_key(client: TestClient):
    fresh = TestClient(client.app)
    r = fresh.post("/api/agent/register", json={"agent_card": CARD},
                   headers={"X-AgentLeak-Key": "ak_wrong"})
    assert r.status_code == 401
    r = fresh.post("/api/agent/register", json={"agent_card": CARD})
    assert r.status_code == 401


def test_agent_code_scan_uses_card_source(client: TestClient, monkeypatch):
    """POST /api/agent/code with an empty body re-scans the card's repo."""
    import agentleak.core.codescan as codescan
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("support-bot-main/agent.py", LEAKY_FILE["content"])
    monkeypatch.setattr(codescan, "fetch_github_repo", lambda repo, **kw: buf.getvalue())

    _, key = _project_with_key(client)
    fresh = TestClient(client.app)
    fresh.post("/api/agent/register", json={"agent_card": CARD},
               headers={"X-AgentLeak-Key": key})

    r = fresh.post("/api/agent/code", json={}, headers={"X-AgentLeak-Key": key})
    assert r.status_code == 200
    scan = r.json()
    assert scan["source_type"] == "github"
    assert scan["source_ref"] == "acme/support-bot@main"
    assert scan["findings_count"] > 0


def test_agent_improve_loop_and_status(client: TestClient):
    """The full self-improvement loop: leaky run → hints → clean run → delta."""
    _, key = _project_with_key(client)
    fresh = TestClient(client.app)
    headers = {"X-AgentLeak-Key": key}

    # Step 1 — leaky trace: low score, actionable next steps, no delta yet.
    r1 = fresh.post("/api/agent/improve", json={"trace": LEAKY_TRACE}, headers=headers)
    assert r1.status_code == 200
    step1 = r1.json()
    assert step1["delta"] is None
    assert step1["next_steps"], "leaky run must produce next steps"
    kinds = {s["kind"] for s in step1["next_steps"]}
    assert "runtime_leak" in kinds
    assert all("action" in s and "priority" in s for s in step1["next_steps"])

    # Step 2 — the agent "fixed" its leaks: score improves, delta says so.
    r2 = fresh.post("/api/agent/improve", json={"trace": CLEAN_TRACE}, headers=headers)
    step2 = r2.json()
    assert step2["delta"]["previous_run_id"] == step1["run_id"]
    assert step2["delta"]["direction"] == "improved"
    assert step2["delta"]["delta_score"] > 0
    assert step2["privacy_score"] > step1["privacy_score"]

    # Status reflects the progression.
    status = fresh.get("/api/agent/status", headers=headers).json()
    assert status["progression"]["total_runs"] == 2
    assert status["progression"]["total_delta"] > 0
    assert status["latest_run"]["id"] == step2["run_id"]


def test_agent_status_empty_project(client: TestClient):
    _, key = _project_with_key(client)
    fresh = TestClient(client.app)
    status = fresh.get("/api/agent/status", headers={"X-AgentLeak-Key": key}).json()
    assert status["latest_run"] is None
    assert status["progression"] == {}
    assert status["next_steps"] == []
    assert status["compliant"] is None


# -- _next_steps unit behaviour -------------------------------------------
def test_next_steps_priority_ordering():
    """Steps merge three sources and come back critical-first."""
    from agentleak.web.app import _next_steps

    report = {
        "remediation_hints": [
            {"priority": "medium", "channel": "log", "advice": "Mask logs.", "data_types": ["email"]},
            {"priority": "critical", "channel": "tool_call", "advice": "Strip SSN.", "data_types": ["ssn"]},
        ],
        "compliance": {"posture": {"failed": [
            {"id": "gdpr", "name": "GDPR (EU 2016/679)", "at_risk": 2},
        ]}},
    }
    scan = {"id": "scan_x", "findings_count": 4, "score": 55}
    steps = _next_steps(report, scan)
    assert [s["kind"] for s in steps[:1]] == ["runtime_leak"]
    assert steps[0]["priority"] == "critical"
    priorities = [ {"critical": 0, "high": 1, "medium": 2, "low": 3}[s["priority"]] for s in steps ]
    assert priorities == sorted(priorities), "steps must be priority-sorted"
    kinds = {s["kind"] for s in steps}
    assert kinds == {"runtime_leak", "compliance", "code_scan"}
    code_step = next(s for s in steps if s["kind"] == "code_scan")
    assert code_step["priority"] == "high"  # score 55 < 70


def test_next_steps_empty_report():
    from agentleak.web.app import _next_steps

    assert _next_steps({}, None) == []
    # A clean code scan adds no step.
    assert _next_steps({}, {"id": "s", "findings_count": 0, "score": 100}) == []


def test_agent_self_client_against_app(client: TestClient, monkeypatch):
    """AgentSelfClient drives the loop end-to-end through the HTTP surface."""
    import json as _json
    from agentleak.client import AgentSelfClient

    _, key = _project_with_key(client)
    fresh = TestClient(client.app)

    me = AgentSelfClient(api_key=key, base_url="http://testserver")

    def fake_request(method: str, path: str, body=None):
        headers = {"X-AgentLeak-Key": key}
        if method == "GET":
            resp = fresh.get(path, headers=headers)
        else:
            resp = fresh.request(method, path, json=body, headers=headers)
        assert resp.status_code < 400, resp.text
        return resp.json()

    monkeypatch.setattr(me, "_request", fake_request)

    assert me.register(CARD)["registered"] is True
    scan = me.scan_code(source="files", files=[LEAKY_FILE])
    assert scan["findings_count"] > 0
    step = me.improve(LEAKY_TRACE)
    assert step["next_steps"]
    assert any(s["kind"] == "code_scan" for s in step["next_steps"])
    assert me.status()["progression"]["total_runs"] == 1
    # Guard: improve() needs a trace or scenario.
    with pytest.raises(Exception):
        me.improve()
