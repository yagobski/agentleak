# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Authentication & per-user scoping for the platform API."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web import create_app  # noqa: E402


@pytest.fixture()
def app_client(tmp_path) -> TestClient:
    """An *unauthenticated* client against a fresh store."""
    return TestClient(create_app(store=Store(str(tmp_path / "auth.db"))))


def _register(client: TestClient, email: str, password: str = "s3cret-pass") -> None:
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def test_protected_endpoints_require_auth(app_client: TestClient):
    for path in ("/api/projects", "/api/scenarios", "/api/stats", "/api/auth/me"):
        assert app_client.get(path).status_code == 401


def test_meta_is_public(app_client: TestClient):
    assert app_client.get("/api/meta").status_code == 200


def test_register_login_logout_flow(app_client: TestClient):
    me = app_client.post("/api/auth/register", json={"email": "a@b.com", "password": "longenough"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"
    # session cookie now lets us reach a protected route
    assert app_client.get("/api/auth/me").json()["email"] == "a@b.com"

    app_client.post("/api/auth/logout")
    assert app_client.get("/api/auth/me").status_code == 401

    bad = app_client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert bad.status_code == 401
    ok = app_client.post("/api/auth/login", json={"email": "a@b.com", "password": "longenough"})
    assert ok.status_code == 200


def test_register_validates_input(app_client: TestClient):
    assert app_client.post("/api/auth/register", json={"email": "nope", "password": "longenough"}).status_code == 400
    assert app_client.post("/api/auth/register", json={"email": "a@b.com", "password": "short"}).status_code == 400


def test_duplicate_email_rejected(app_client: TestClient):
    _register(app_client, "dup@b.com")
    assert app_client.post("/api/auth/register", json={"email": "dup@b.com", "password": "longenough"}).status_code == 409


def test_projects_are_isolated_per_user(tmp_path):
    app = create_app(store=Store(str(tmp_path / "shared.db")))
    alice = TestClient(app)
    bob = TestClient(app)
    _register(alice, "alice@x.com")
    _register(bob, "bob@x.com")

    pid = alice.post("/api/projects", json={"name": "Alice project"}).json()["id"]

    # Bob cannot see or touch Alice's project.
    assert bob.get("/api/projects").json() == []
    assert bob.get(f"/api/projects/{pid}").status_code == 404
    assert bob.delete(f"/api/projects/{pid}").status_code == 404

    # Alice still owns it.
    assert any(p["id"] == pid for p in alice.get("/api/projects").json())


def test_scenarios_are_isolated_per_user(tmp_path):
    app = create_app(store=Store(str(tmp_path / "shared2.db")))
    alice = TestClient(app)
    bob = TestClient(app)
    _register(alice, "alice2@x.com")
    _register(bob, "bob2@x.com")

    trace = {"agent_name": "t", "events": [{"channel": "shared_memory", "content": "ssn 123-45-6789"}]}
    sid = alice.post("/api/scenarios", json={"data": trace, "name": "Mine"}).json()["id"]

    bob_custom = [s for s in bob.get("/api/scenarios").json() if not s["builtin"]]
    assert bob_custom == []
    assert bob.get(f"/api/scenarios/{sid}").status_code == 404
    assert bob.delete(f"/api/scenarios/{sid}").status_code == 404

    alice_custom = [s for s in alice.get("/api/scenarios").json() if not s["builtin"]]
    assert any(s["id"] == sid for s in alice_custom)


def test_security_headers_present(app_client: TestClient):
    r = app_client.get("/api/meta")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    # HSTS only when secure cookies are enabled (HTTPS deployments).
    assert "Strict-Transport-Security" not in r.headers


def test_cookie_secure_flag_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_COOKIE_SECURE", "1")
    client = TestClient(create_app(store=Store(str(tmp_path / "secure.db"))))
    r = client.post("/api/auth/register", json={"email": "s@b.com", "password": "longenough"})
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"].lower()
    assert "secure" in set_cookie
    assert "httponly" in set_cookie
    assert r.headers["Strict-Transport-Security"].startswith("max-age=")
