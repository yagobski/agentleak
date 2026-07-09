"""Integration tests for public-SaaS mode: quotas, per-IP throttle, BYOK,
readiness, and free-tier discovery. These build a fresh app with the public
knobs set so the local/self-hosted defaults elsewhere stay untouched."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web.app import create_app  # noqa: E402


def _app(tmp_path, **env) -> TestClient:
    # The TestClient talks http://, so a Secure cookie would never come back.
    # Public mode turns Secure on by default; force it off for the in-process
    # test client (real deployments run behind TLS where Secure is correct).
    import os

    os.environ.setdefault("AGENTLEAK_COOKIE_SECURE", "0")
    return TestClient(create_app(store=Store(str(tmp_path / "saas.db"))))


def _register(client, email="agent@x.io", password="agent-pass-123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


def _register_nonadmin(client, email="agent@x.io", password="agent-pass-123"):
    """The first account in a fresh DB is auto-promoted to admin (and admins
    bypass quotas). Burn a throwaway admin first so the returned session is a
    regular free-tier user."""
    client.post("/api/auth/register", json={"email": "root@x.io", "password": "root-pass-123"})
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


# -- readiness / discovery ------------------------------------------------
def test_readyz_ok(tmp_path):
    client = _app(tmp_path)
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_meta_advertises_free_tier(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    client = _app(tmp_path)
    ft = client.get("/api/meta").json()["free_tier"]
    assert ft["public"] is True
    assert ft["monthly_quota"] == 1000
    assert ft["byok"] is True


# -- free-tier quota ------------------------------------------------------
def test_quota_blocks_after_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    monkeypatch.setenv("AGENTLEAK_FREE_MONTHLY_QUOTA", "3")
    monkeypatch.setenv("AGENTLEAK_IP_RATE_LIMIT", "0")  # isolate quota from IP throttle
    monkeypatch.setenv("AGENTLEAK_REGISTER_IP_LIMIT", "0")
    client = _app(tmp_path)
    _register_nonadmin(client)

    trace = {"agent_name": "a", "events": [
        {"channel": "final_output", "content": "hi", "source": "agent", "target": "user"},
    ]}
    ok = [client.post("/api/analyze", json={"trace": trace}).status_code for _ in range(3)]
    assert ok == [200, 200, 200]

    blocked = client.post("/api/analyze", json={"trace": trace})
    assert blocked.status_code == 429
    assert "quota" in blocked.json()["detail"].lower()

    # /api/limits reports the exhausted window.
    lim = client.get("/api/limits").json()
    assert lim["limit"] == 3 and lim["used"] >= 3 and lim["remaining"] == 0


def test_admin_bypasses_quota(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    monkeypatch.setenv("AGENTLEAK_FREE_MONTHLY_QUOTA", "1")
    monkeypatch.setenv("AGENTLEAK_IP_RATE_LIMIT", "0")
    monkeypatch.setenv("AGENTLEAK_REGISTER_IP_LIMIT", "0")
    client = _app(tmp_path)
    _register(client, email="firstadmin@x.io")  # first account → admin

    trace = {"agent_name": "a", "events": [
        {"channel": "final_output", "content": "hi", "source": "agent", "target": "user"},
    ]}
    codes = [client.post("/api/analyze", json={"trace": trace}).status_code for _ in range(3)]
    assert codes == [200, 200, 200]  # never 429


def test_local_mode_has_no_quota(tmp_path, monkeypatch):
    for v in ("AGENTLEAK_PUBLIC_MODE", "AGENTLEAK_FREE_MONTHLY_QUOTA"):
        monkeypatch.delenv(v, raising=False)
    client = _app(tmp_path)
    _register(client)
    lim = client.get("/api/limits").json()
    assert lim["unlimited"] is True and lim["limit"] == 0


# -- per-IP registration throttle ----------------------------------------
def test_register_ip_throttle(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    monkeypatch.setenv("AGENTLEAK_REGISTER_IP_LIMIT", "2")
    monkeypatch.setenv("AGENTLEAK_IP_RATE_LIMIT", "0")
    client = _app(tmp_path)

    a = client.post("/api/auth/register", json={"email": "a@x.io", "password": "pw-123456"})
    b = client.post("/api/auth/register", json={"email": "b@x.io", "password": "pw-123456"})
    c = client.post("/api/auth/register", json={"email": "c@x.io", "password": "pw-123456"})
    assert a.status_code == 200 and b.status_code == 200
    assert c.status_code == 429
    assert "sign-up" in c.json()["detail"].lower()


# -- BYOK: no platform-funded LLM ----------------------------------------
def test_byok_blocks_env_key_fallback(monkeypatch):
    """In public mode, a live red-team with no tenant key must NOT fall back to
    the platform's process-level OPENROUTER_API_KEY."""
    from agentleak.web.app import _resolve_redteam_llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-platform-secret")
    project = {"config": {}}
    # force_byok on → returns None (scripted), never uses the platform key.
    assert _resolve_redteam_llm(project, {}, {}, force_byok=True) is None
    # force_byok off (self-hosted) → the env key is allowed.
    llm = _resolve_redteam_llm(project, {}, {}, force_byok=False)
    assert llm is not None and "openrouter" in llm.config.base_url


# -- frictionless agent onboarding ---------------------------------------
def test_agent_onboard_one_call(tmp_path, monkeypatch):
    for v in ("AGENTLEAK_PUBLIC_MODE", "AGENTLEAK_IP_RATE_LIMIT", "AGENTLEAK_REGISTER_IP_LIMIT"):
        monkeypatch.delenv(v, raising=False)
    client = _app(tmp_path)

    r = client.post("/api/agent/onboard", json={"email": "bot@x.io", "agent_name": "TicketBot"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["onboarded"] is True
    assert body["api_key"].startswith("ak_")
    assert body["password_generated"] is True and body["password"]
    assert body["agent_name"] == "TicketBot"

    # The returned key immediately drives the agent loop (no session cookie).
    key = body["api_key"]
    fresh = TestClient(client.app)
    reg = fresh.post(
        "/api/agent/register",
        json={"agent_card": {"name": "TicketBot", "description": "d", "capabilities": ["triage"]}},
        headers={"X-AgentLeak-Key": key},
    )
    assert reg.status_code == 200 and reg.json()["registered"] is True


def test_agent_onboard_rejects_duplicate_email(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTLEAK_REGISTER_IP_LIMIT", raising=False)
    client = _app(tmp_path)
    client.post("/api/agent/onboard", json={"email": "dup@x.io"})
    again = client.post("/api/agent/onboard", json={"email": "dup@x.io"})
    assert again.status_code == 409
