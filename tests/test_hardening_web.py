# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Web regressions from the hardening review (docs/reports/next/HARDENING-REPORT.md).

Every test runs against an in-process app with a temporary database. Values that
look like credentials are built at run time and are synthetic.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web import create_app  # noqa: E402

_TRACE = {
    "events": [
        {"channel": "tool_response", "content": {"patient": "Ada Quill", "diagnosis": "asthma"}},
        {"channel": "log", "content": "Patient Ada Quill has asthma, SSN 123-45-6789"},
    ]
}


def _client(tmp_path, monkeypatch, *, public: bool = False) -> TestClient:
    if public:
        monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    else:
        monkeypatch.delenv("AGENTLEAK_PUBLIC_MODE", raising=False)
    app = create_app(store=Store(str(tmp_path / "h.db")))
    client = TestClient(app, base_url="https://testserver")
    r = client.post("/api/auth/register",
                    json={"email": "eve@example.test", "password": "eve-pass-12345"})
    assert r.status_code in (200, 201), r.text
    return client


# ----------------------------------------------------------------------
# H-01: request-supplied LLM-judge settings chose the env var and the host
# ----------------------------------------------------------------------
@pytest.mark.parametrize("public", [False, True])
def test_request_cannot_send_a_server_env_var_to_its_own_host(tmp_path, monkeypatch, public) -> None:
    import agentleak.detectors.llm_judge as judge_mod

    secret = "synthetic-" + "x" * 24
    monkeypatch.setenv("AGENTLEAK_TEST_SERVER_SECRET", secret)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-operator-key")
    sent: list[tuple[str, str]] = []

    def _capture(request, *, timeout):  # noqa: ANN001, ANN202
        sent.append((request.full_url, request.get_header("Authorization") or ""))
        raise OSError("no network in tests")

    monkeypatch.setattr(judge_mod, "open_model_url", _capture)
    client = _client(tmp_path, monkeypatch, public=public)
    body = {
        "trace": _TRACE,
        "detection": {
            "mode": "hybrid",
            "llm_judge": {
                "enabled": True,
                "base_url": "https://attacker.example/v1",
                "api_key_env": "AGENTLEAK_TEST_SERVER_SECRET",
                "model": "m",
            },
        },
    }
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200, r.text
    assert not any("attacker.example" in url for url, _ in sent), sent
    assert not any(secret in auth for _, auth in sent), sent
    if public:
        # A hosted deployment never spends the operator's key on a tenant's run.
        assert sent == []


# ----------------------------------------------------------------------
# H-02: a tenant's model URL received the operator's API key from the env
# ----------------------------------------------------------------------
def test_unit_key_resolution_matches_hosts_not_substrings(monkeypatch) -> None:
    from agentleak.agent.llm import resolve_api_key

    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-or")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-oa")
    assert resolve_api_key("https://openrouter.ai/api/v1") == "synthetic-or"
    assert resolve_api_key("https://evil.example/openrouter.ai/v1") != "synthetic-or"
    assert resolve_api_key("https://openrouter.ai.evil.example/v1") != "synthetic-or"


def test_hosted_execute_never_sends_operator_key_to_tenant_url(tmp_path, monkeypatch) -> None:
    from agentleak.core import netguard

    operator_key = "synthetic-operator-" + "k" * 20
    monkeypatch.setenv("OPENAI_API_KEY", operator_key)
    monkeypatch.setenv("OPENROUTER_API_KEY", operator_key)
    seen: list[str] = []

    def _capture(request, timeout):  # noqa: ANN001, ANN202
        import urllib.error

        seen.append(request.get_header("Authorization") or "")
        raise urllib.error.URLError("no network in tests")

    monkeypatch.setattr(netguard._SAFE_OPENER, "open", _capture)
    monkeypatch.setattr(netguard, "_assert_safe_http_url", lambda url: None)
    client = _client(tmp_path, monkeypatch, public=True)
    pid = client.post("/api/projects", json={"name": "p", "config": {"agent": {
        "base_url": "https://tenant.example/openrouter.ai/v1", "model": "m", "api_key": ""}}}).json()["id"]
    sid = client.get("/api/scenarios").json()
    sid = (sid.get("scenarios") if isinstance(sid, dict) else sid)[0]["id"]
    client.post(f"/api/projects/{pid}/execute", json={"scenario_id": sid, "mode": "live"})
    assert seen, "the live run should have tried the tenant endpoint"
    assert all(operator_key not in h for h in seen), seen
