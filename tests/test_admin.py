"""Tests for the admin console: roles, account management, platform stats,
health probe, and login rate limiting."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web.app import create_app  # noqa: E402
from agentleak.web.auth import LoginRateLimiter  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    return create_app(store=Store(str(tmp_path / "admin.db")))


def _register(client: TestClient, email: str, password: str = "test-pass-123") -> TestClient:
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


# -- roles ----------------------------------------------------------------
def test_first_user_becomes_admin(app):
    first = _register(TestClient(app), "owner@x.com")
    second = _register(TestClient(app), "member@x.com")
    assert first.get("/api/auth/me").json()["is_admin"] is True
    assert second.get("/api/auth/me").json()["is_admin"] is False


def test_admin_endpoints_forbidden_for_members(app):
    _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    assert member.get("/api/admin/overview").status_code == 403
    assert member.get("/api/admin/users").status_code == 403
    anon = TestClient(app)
    assert anon.get("/api/admin/overview").status_code == 401


# -- overview & users -------------------------------------------------------
def test_admin_overview_counts_all_accounts(app):
    admin = _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    member.post("/api/projects", json={"name": "Member Bot"})

    overview = admin.get("/api/admin/overview").json()
    assert overview["users"] == 2
    assert overview["admins"] == 1
    assert overview["projects"] == 1  # admin sees ALL projects, not just theirs
    assert overview["runs_24h"] == 0
    assert overview["active_projects_24h"] == 0
    assert overview["verdict_counts"] == {}

    users = admin.get("/api/admin/users").json()
    by_email = {u["email"]: u for u in users}
    assert by_email["member@x.com"]["project_count"] == 1
    assert by_email["owner@x.com"]["is_admin"] is True
    assert all("password" not in u and "password_hash" not in u for u in users)


# -- account management ------------------------------------------------------
def test_promote_and_disable_user(app):
    admin = _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    uid = member.get("/api/auth/me").json()["id"]

    # Promote to admin.
    r = admin.patch(f"/api/admin/users/{uid}", json={"is_admin": True})
    assert r.json()["is_admin"] is True

    # Disable: active session is revoked immediately + login refused.
    admin.patch(f"/api/admin/users/{uid}", json={"disabled": True, "is_admin": False})
    assert member.get("/api/auth/me").status_code == 401
    fresh = TestClient(app)
    r = fresh.post("/api/auth/login", json={"email": "member@x.com", "password": "test-pass-123"})
    assert r.status_code == 401

    # Re-enable: login works again.
    admin.patch(f"/api/admin/users/{uid}", json={"disabled": False})
    r = fresh.post("/api/auth/login", json={"email": "member@x.com", "password": "test-pass-123"})
    assert r.status_code == 200


def test_lockout_guards(app):
    admin = _register(TestClient(app), "owner@x.com")
    my_id = admin.get("/api/auth/me").json()["id"]
    # Cannot disable yourself.
    assert admin.patch(f"/api/admin/users/{my_id}", json={"disabled": True}).status_code == 400
    # The last admin cannot drop their own role.
    assert admin.patch(f"/api/admin/users/{my_id}", json={"is_admin": False}).status_code == 400
    # Cannot delete yourself.
    assert admin.delete(f"/api/admin/users/{my_id}").status_code == 400


def test_delete_user_cascades_their_data(app):
    admin = _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    uid = member.get("/api/auth/me").json()["id"]
    pid = member.post("/api/projects", json={"name": "Doomed"}).json()["id"]
    member.post(f"/api/projects/{pid}/runs", json={"scenario_id": "healthcare_patient_summary"})

    assert admin.delete(f"/api/admin/users/{uid}").json()["deleted"] is True
    assert admin.delete(f"/api/admin/users/{uid}").status_code == 404  # gone
    overview = admin.get("/api/admin/overview").json()
    assert overview["users"] == 1
    assert overview["projects"] == 0
    assert overview["runs"] == 0


# -- health & rate limiting ---------------------------------------------------
def test_health_probe_unauthenticated(app):
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"]


def test_login_rate_limited_after_failures(app):
    _register(TestClient(app), "owner@x.com")
    attacker = TestClient(app)
    for _ in range(10):
        r = attacker.post("/api/auth/login", json={"email": "owner@x.com", "password": "wrong-pass"})
        assert r.status_code == 401
    r = attacker.post("/api/auth/login", json={"email": "owner@x.com", "password": "wrong-pass"})
    assert r.status_code == 429
    # Even the CORRECT password is throttled while the window is hot.
    r = attacker.post("/api/auth/login", json={"email": "owner@x.com", "password": "test-pass-123"})
    assert r.status_code == 429


def test_rate_limiter_window_and_reset():
    limiter = LoginRateLimiter(max_attempts=3, window=60)
    for i in range(3):
        assert limiter.allow("a@x.com", now=100.0 + i)
        limiter.record_failure("a@x.com", now=100.0 + i)
    assert not limiter.allow("a@x.com", now=110.0)
    # Attempts age out of the window.
    assert limiter.allow("a@x.com", now=100.0 + 61)
    # Success resets immediately.
    limiter.record_failure("b@x.com", now=100.0)
    limiter.reset("b@x.com")
    assert limiter.allow("b@x.com", now=100.0)


# -- audit log ----------------------------------------------------------------
def test_audit_log_records_admin_actions(app):
    admin = _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    uid = member.get("/api/auth/me").json()["id"]

    admin.patch(f"/api/admin/users/{uid}", json={"is_admin": True})
    admin.patch(f"/api/admin/users/{uid}", json={"disabled": True})
    admin.delete(f"/api/admin/users/{uid}")

    log = admin.get("/api/admin/audit-log").json()
    actions = [entry["action"] for entry in log]
    # Most recent first.
    assert actions[:3] == ["user.delete", "user.update", "user.update"]
    assert all(entry["actor_email"] == "owner@x.com" for entry in log)
    assert all(entry["target_email"] == "member@x.com" for entry in log)
    update_entries = [e for e in log if e["action"] == "user.update"]
    assert any("is_admin=True" in e["detail"] for e in update_entries)
    assert any("disabled=True" in e["detail"] for e in update_entries)


def test_audit_log_forbidden_for_members(app):
    _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    assert member.get("/api/admin/audit-log").status_code == 403


def test_audit_log_empty_when_no_actions(app):
    admin = _register(TestClient(app), "owner@x.com")
    assert admin.get("/api/admin/audit-log").json() == []
