"""Tests for self-service account management: profile update, password
change (with session revocation), and account self-deletion."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web.app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    return create_app(store=Store(str(tmp_path / "account.db")))


def _register(client: TestClient, email: str, password: str = "test-pass-123") -> TestClient:
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


# -- profile ----------------------------------------------------------------
def test_update_own_name(app):
    client = _register(TestClient(app), "a@x.com")
    r = client.patch("/api/auth/me", json={"name": "Alice"})
    assert r.status_code == 200
    assert r.json()["name"] == "Alice"
    assert client.get("/api/auth/me").json()["name"] == "Alice"


def test_update_name_rejects_blank(app):
    client = _register(TestClient(app), "a@x.com")
    assert client.patch("/api/auth/me", json={"name": "   "}).status_code == 400


def test_update_me_requires_auth(app):
    assert TestClient(app).patch("/api/auth/me", json={"name": "X"}).status_code == 401


# -- password change ---------------------------------------------------------
def test_change_password_success_revokes_session(app):
    client = _register(TestClient(app), "a@x.com", "old-pass-123")
    r = client.post("/api/auth/change-password", json={
        "current_password": "old-pass-123", "new_password": "new-pass-456",
    })
    assert r.status_code == 200
    # The old session is revoked by the password change itself.
    assert client.get("/api/auth/me").status_code == 401

    # Old password no longer works; new one does.
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "a@x.com", "password": "old-pass-123"}).status_code == 401
    r = fresh.post("/api/auth/login", json={"email": "a@x.com", "password": "new-pass-456"})
    assert r.status_code == 200


def test_change_password_wrong_current_rejected(app):
    client = _register(TestClient(app), "a@x.com", "old-pass-123")
    r = client.post("/api/auth/change-password", json={
        "current_password": "totally-wrong", "new_password": "new-pass-456",
    })
    assert r.status_code == 401
    # Session survives a rejected attempt.
    assert client.get("/api/auth/me").status_code == 200


def test_change_password_enforces_min_length(app):
    client = _register(TestClient(app), "a@x.com", "old-pass-123")
    r = client.post("/api/auth/change-password", json={
        "current_password": "old-pass-123", "new_password": "short",
    })
    assert r.status_code == 400


# -- self-deletion ------------------------------------------------------------
def test_delete_own_account_requires_password(app):
    # Two accounts so the deleting one isn't the last admin.
    _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com", "member-pass-1")

    r = member.post("/api/auth/delete-account", json={"password": "wrong"})
    assert r.status_code == 401

    r = member.post("/api/auth/delete-account", json={"password": "member-pass-1"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert member.get("/api/auth/me").status_code == 401

    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "member@x.com", "password": "member-pass-1"}).status_code == 401


def test_last_admin_cannot_self_delete(app):
    admin = _register(TestClient(app), "owner@x.com")
    r = admin.post("/api/auth/delete-account", json={"password": "test-pass-123"})
    assert r.status_code == 400
    assert admin.get("/api/auth/me").status_code == 200  # nothing happened


def test_delete_own_account_removes_owned_data(app):
    admin = _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com", "member-pass-1")
    member.post("/api/projects", json={"name": "Mine"})

    member.post("/api/auth/delete-account", json={"password": "member-pass-1"})
    overview = admin.get("/api/admin/overview").json()
    assert overview["users"] == 1
    assert overview["projects"] == 0


# -- default model key (OpenRouter etc.) --------------------------------------
def test_model_key_roundtrip_never_returns_key(app):
    client = _register(TestClient(app), "keys@x.com")
    # Nothing configured yet.
    r = client.get("/api/auth/model-key")
    assert r.status_code == 200
    assert r.json() == {"base_url": "", "model": "", "api_key_set": False}

    # Save a key — OpenRouter defaults fill base_url/model.
    r = client.post("/api/auth/model-key", json={"api_key": "sk-or-v1-secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["api_key_set"] is True
    assert "openrouter.ai" in body["base_url"]
    assert body["model"]
    assert "sk-or" not in str(body)  # the key itself never comes back

    # Blank key on update preserves the stored key.
    r = client.post("/api/auth/model-key", json={"model": "openai/gpt-4o", "api_key": ""})
    assert r.json()["model"] == "openai/gpt-4o"
    assert r.json()["api_key_set"] is True


def test_model_key_delete_clears(app):
    client = _register(TestClient(app), "keys2@x.com")
    client.post("/api/auth/model-key", json={"api_key": "sk-or-v1-x"})
    r = client.delete("/api/auth/model-key")
    assert r.status_code == 200
    assert client.get("/api/auth/model-key").json()["api_key_set"] is False


def test_model_key_requires_auth(app):
    assert TestClient(app).get("/api/auth/model-key").status_code == 401


def test_execute_live_falls_back_to_user_model_key(app, monkeypatch):
    """A project with no endpoint can still run live using the account key."""
    client = _register(TestClient(app), "runner@x.com")
    client.post("/api/auth/model-key", json={"api_key": "sk-or-v1-abc"})
    pid = client.post("/api/projects", json={"name": "NoEndpoint"}).json()["id"]

    captured: dict = {}

    class FakeLLM:
        model = "openai/gpt-4o-mini"

        def __init__(self, cfg):
            captured["base_url"] = cfg.base_url
            captured["api_key"] = cfg.api_key

        def chat(self, messages, tools=None):
            return {"content": "done", "tool_calls": []}

    monkeypatch.setattr("agentleak.web.app.OpenAICompatLLM", lambda cfg: FakeLLM(cfg))
    r = client.post(f"/api/projects/{pid}/execute", json={
        "scenario_id": "healthcare_patient_summary", "mode": "live",
    })
    assert r.status_code == 200, r.text
    assert "openrouter.ai" in captured["base_url"]
    assert captured["api_key"] == "sk-or-v1-abc"
