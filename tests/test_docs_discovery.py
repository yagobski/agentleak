# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Public documentation and autonomous-agent discovery surfaces."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web.app import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path) -> TestClient:
    return TestClient(create_app(store=Store(str(tmp_path / "docs.db"))))


def test_llms_txt_is_a_linked_machine_readable_index(client: TestClient):
    response = client.get("/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.startswith("# AgentLeak")
    assert "http://testserver/docs/agents" in response.text
    assert "http://testserver/docs/api" in response.text
    assert "http://testserver/openapi.json" in response.text
    assert "http://testserver/agents.md" in response.text


def test_full_context_contains_working_agent_loop(client: TestClient):
    response = client.get("/llms-full.txt")
    assert response.status_code == 200
    assert "/api/agent/onboard" in response.text
    assert "/api/agent/improve" in response.text
    assert "/docs/api" in response.text
    assert "X-AgentLeak-Key" in response.text
    assert "synthetic" in response.text.lower()


def test_agents_md_defines_safety_and_error_rules(client: TestClient):
    response = client.get("/agents.md")
    assert response.status_code == 200
    assert "MUST NOT submit production credentials" in response.text
    assert "On `429`" in response.text
    assert "X-Quota-Reset" in response.text
    assert "Completion report" in response.text


def test_agent_card_uses_explicit_custom_binding(client: TestClient):
    card = client.get("/.well-known/agent-card.json").json()
    assert card["version"]
    assert card["documentationUrl"] == "http://testserver/docs/agents"
    interface = card["supportedInterfaces"][0]
    assert interface["url"] == "http://testserver/api"
    assert interface["protocolBinding"].endswith("#agentleak-rest-binding")
    assert "standard A2A" in card["extensions"]["bindingNotice"]
    assert card["securitySchemes"]["agentLeakKey"]["apiKeySecurityScheme"]["name"] == "X-AgentLeak-Key"


def test_interactive_api_moved_below_api_namespace(client: TestClient):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["version"]


def test_meta_links_every_documentation_surface(client: TestClient):
    docs = client.get("/api/meta").json()["documentation"]
    assert docs == {
        "humans": "/docs",
        "developers": "/docs/developers",
        "agents": "/docs/agents",
        "api_reference": "/docs/api",
        "agent_instructions": "/agents.md",
        "llms": "/llms.txt",
        "llms_full": "/llms-full.txt",
        "openapi": "/openapi.json",
        "interactive_api": "/api/docs",
        "schemas": "/api/schemas",
    }


def test_public_schema_catalog_and_documents(client: TestClient):
    catalog = client.get("/api/schemas")
    assert catalog.status_code == 200
    names = {item["name"] for item in catalog.json()["schemas"]}
    assert {"config", "trace", "analysis-report", "privacy-policy", "code-scan"} <= names

    schema = client.get("/api/schemas/privacy-policy")
    assert schema.status_code == 200
    assert schema.json()["$schema"].endswith("2020-12/schema")
    assert "max_risk_index" in schema.json()["properties"]

    assert client.get("/api/schemas/not-real").status_code == 404


def test_public_mode_emits_https_behind_an_http_reverse_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    public = TestClient(create_app(store=Store(str(tmp_path / "public-docs.db"))))
    response = public.get("/llms.txt", headers={"host": "agentleak.org"})
    assert "https://www.agentleak.org/docs/agents" in response.text
    card = public.get("/.well-known/agent-card.json", headers={"host": "agentleak.org"}).json()
    assert card["documentationUrl"] == "https://www.agentleak.org/docs/agents"
