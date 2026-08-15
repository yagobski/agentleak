# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Platform API: projects, runs, compare, stats (skipped without [gui])."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path, login) -> TestClient:
    return login(TestClient(create_app(store=Store(str(tmp_path / "api.db")))))


def test_meta_lists_agent_types(client: TestClient):
    types = client.get("/api/meta").json()["agent_types"]
    assert any(a["id"] == "generic" for a in types)
    assert any(a["id"] == "langchain" for a in types)


def test_connect_snippet(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P", "agent_type": "langchain"}).json()["id"]
    body = client.get(f"/api/projects/{pid}/connect").json()
    assert "agentleak.watch" in body["snippet"]
    assert "run.callback" in body["snippet"]
    assert body["framework"] == "LangChain"


def test_project_crud_via_api(client: TestClient):
    created = client.post("/api/projects", json={"name": "Support Bot", "agent_type": "crewai"}).json()
    pid = created["id"]
    assert created["agent_type"] == "crewai"

    assert any(p["id"] == pid for p in client.get("/api/projects").json())
    assert client.get(f"/api/projects/{pid}").json()["name"] == "Support Bot"

    patched = client.patch(f"/api/projects/{pid}", json={"description": "updated"}).json()
    assert patched["description"] == "updated"

    assert client.delete(f"/api/projects/{pid}").json()["deleted"] is True
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_create_project_requires_name(client: TestClient):
    assert client.post("/api/projects", json={"name": "  "}).status_code == 400


def test_run_creation_and_retrieval(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    run = client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "healthcare_patient_summary"}).json()
    assert run["id"].startswith("run_")
    assert run["report"]["scoring"] == "agentrisk"
    assert run["verdict"] in {"High risk", "Fail"}

    runs = client.get(f"/api/projects/{pid}/runs").json()
    assert len(runs) == 1


def test_project_run_enforces_declarative_privacy_policy(client: TestClient):
    project = client.post("/api/projects", json={
        "name": "No logs policy",
        "config": {"privacy_policy": {"forbid_channels": ["shared_memory"]}},
    }).json()
    run = client.post(
        f"/api/projects/{project['id']}/runs",
        json={"scenario_id": "healthcare_patient_summary"},
    ).json()
    policy = run["report"]["privacy_policy"]
    assert policy["enabled"] is True
    assert policy["passed"] is False
    assert policy["violations"][0]["rule"] == "forbid_channels"
    full = client.get(f"/api/runs/{run['id']}").json()
    assert full["report"]["risk_index"] == run["report"]["risk_index"]


def test_agent_crud_and_model(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Multi"}).json()["id"]
    created = client.post(f"/api/projects/{pid}/agents", json={
        "name": "Researcher", "framework": "langchain", "role": "researcher",
    }).json()
    agents = created["config"]["agents"]
    assert len(agents) == 1
    aid = agents[0]["id"]
    assert aid.startswith("agt_")

    listed = client.get(f"/api/projects/{pid}/agents").json()
    assert listed[0]["framework_label"] == "LangChain"
    assert listed[0]["name"] == "Researcher"

    client.post(f"/api/projects/{pid}/agents", json={"name": "Writer", "framework": "crewai"})

    # The model endpoint exposes the designed topology of the configured agents.
    model = client.get(f"/api/projects/{pid}/model").json()
    assert len(model["agents"]) == 2
    node_ids = {n["id"] for n in model["topology"]["nodes"]}
    assert "Researcher" in node_ids and "Writer" in node_ids
    assert model["last_run"] is None

    # Connect returns a per-agent snippet for each configured framework.
    connect = client.get(f"/api/projects/{pid}/connect").json()
    assert len(connect["agents"]) == 2
    frameworks = {a["framework"] for a in connect["agents"]}
    assert frameworks == {"langchain", "crewai"}

    patched = client.patch(f"/api/projects/{pid}/agents/{aid}", json={"role": "lead"}).json()
    assert next(a for a in patched["config"]["agents"] if a["id"] == aid)["role"] == "lead"

    client.delete(f"/api/projects/{pid}/agents/{aid}")
    assert len(client.get(f"/api/projects/{pid}/agents").json()) == 1


def test_agent_endpoint_key_redacted(client: TestClient):
    pid = client.post("/api/projects", json={"name": "M"}).json()["id"]
    proj = client.post(f"/api/projects/{pid}/agents", json={
        "name": "R", "endpoint": {"base_url": "http://x/v1", "model": "m", "api_key": "secret"},
    }).json()
    ep = proj["config"]["agents"][0]["endpoint"]
    assert ep["api_key"] == ""
    assert ep["api_key_set"] is True

    # A blank key on update keeps the stored secret (no accidental wipe).
    aid = proj["config"]["agents"][0]["id"]
    updated = client.patch(f"/api/projects/{pid}/agents/{aid}", json={
        "endpoint": {"base_url": "http://x/v1", "model": "m2", "api_key": ""},
    }).json()
    ep2 = next(a for a in updated["config"]["agents"] if a["id"] == aid)["endpoint"]
    assert ep2["api_key_set"] is True
    assert ep2["model"] == "m2"


def test_agent_tools_and_mcp_in_model(client: TestClient):
    pid = client.post("/api/projects", json={"name": "MCP"}).json()["id"]
    created = client.post(f"/api/projects/{pid}/agents", json={
        "name": "Researcher", "framework": "mcp",
        "tools": [
            {"name": "create_issue", "kind": "mcp", "server": "github-mcp"},
            {"name": "send_email", "kind": "function"},
        ],
    }).json()
    tools = created["config"]["agents"][0]["tools"]
    assert len(tools) == 2
    assert {t["kind"] for t in tools} == {"mcp", "function"}

    # The agent view exposes the tools, and the model adds sink nodes for them.
    listed = client.get(f"/api/projects/{pid}/agents").json()
    assert len(listed[0]["tools"]) == 2

    model = client.get(f"/api/projects/{pid}/model").json()
    node_ids = {n["id"] for n in model["topology"]["nodes"]}
    assert "mcp:github-mcp/create_issue" in node_ids
    assert "send_email" in node_ids
    kinds = {n["kind"] for n in model["topology"]["nodes"]}
    assert "mcp" in kinds

    # Running the pipeline leaks the records to the MCP server -> overlaid on the model.
    run = client.post(f"/api/projects/{pid}/execute", json={
        "scenario_id": "healthcare_patient_summary",
    }).json()
    assert run["report"]["scoring"] == "agentrisk"
    model2 = client.get(f"/api/projects/{pid}/model").json()
    mcp_node = next(n for n in model2["topology"]["nodes"] if n["id"] == "mcp:github-mcp/create_issue")
    assert mcp_node["leak_level"] > 0


def test_multi_agent_execute_produces_pipeline_run(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Multi"}).json()["id"]
    client.post(f"/api/projects/{pid}/agents", json={"name": "Researcher", "framework": "langchain"})
    client.post(f"/api/projects/{pid}/agents", json={"name": "Writer", "framework": "crewai"})

    run = client.post(f"/api/projects/{pid}/execute", json={
        "scenario_id": "healthcare_patient_summary",
    }).json()
    assert run["report"]["scoring"] == "agentrisk"
    assert "pipeline" in run["source"]

    # After a run, the model overlays where the leaks happened.
    model = client.get(f"/api/projects/{pid}/model").json()
    assert model["last_run"] is not None


def test_project_config_applies_to_runs(client: TestClient):
    # A project with only PII enabled should not report finance findings.
    pid = client.post("/api/projects", json={
        "name": "PiiOnly",
        "detectors": {"pii": True, "secrets": False, "healthcare": False, "finance": False, "hr": False},
    }).json()["id"]
    run = client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "finance_loan_review"}).json()
    detectors = {f["detector"] for f in run["report"]["findings"]}
    assert detectors <= {"pii_detector"}


def test_compare_dominance(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    a = client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "healthcare_patient_summary"}).json()
    b = client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "customer_support_crm"}).json()
    res = client.post("/api/compare", json={"a": a["id"], "b": b["id"]}).json()
    assert res["dominance"] in {"a", "b", "neither"}


def test_compare_incompatible_scopes_refuses_dominance(client: TestClient):
    # Two projects audited against different explicit vault sizes: same scope
    # label, different rho_s -> not a valid dominance comparison.
    pid_small = client.post("/api/projects", json={
        "name": "Small vault", "vault": {"mode": "explicit", "levels": {"4": 3}},
    }).json()["id"]
    pid_big = client.post("/api/projects", json={
        "name": "Big vault", "vault": {"mode": "explicit", "levels": {"1": 5, "2": 3, "3": 2, "4": 1}},
    }).json()["id"]
    a = client.post(f"/api/projects/{pid_small}/runs", json={"scenario_id": "healthcare_patient_summary"}).json()
    b = client.post(f"/api/projects/{pid_big}/runs", json={"scenario_id": "healthcare_patient_summary"}).json()
    assert a["report"]["rho_s"] != b["report"]["rho_s"]

    res = client.post("/api/compare", json={"a": a["id"], "b": b["id"]}).json()
    assert res["comparable"] is False
    assert res["dominance"] == "neither"
    assert "rho_s" in res["reason"] or "scope" in res["reason"]


def test_compare_matching_scopes_is_comparable(client: TestClient):
    # Two runs of the same scenario under the same project (identical scope
    # and rho_s) -> a valid, comparable dominance check.
    pid = client.post("/api/projects", json={
        "name": "Matching", "vault": {"mode": "explicit", "levels": {"1": 5, "2": 3, "3": 2, "4": 1}},
    }).json()["id"]
    a = client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "healthcare_patient_summary"}).json()
    b = client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "healthcare_patient_summary"}).json()
    assert a["report"]["scope_def"] == b["report"]["scope_def"]
    assert a["report"]["rho_s"] == b["report"]["rho_s"]

    res = client.post("/api/compare", json={"a": a["id"], "b": b["id"]}).json()
    assert res["comparable"] is True
    assert res["reason"] == ""
    assert res["dominance"] in {"a", "b", "neither"}


def test_stats_endpoint(client: TestClient):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "hr_employee_case"})
    s = client.get("/api/stats").json()
    assert s["projects"] == 1 and s["runs"] == 1


def test_run_unknown_project_404(client: TestClient):
    assert client.post("/api/projects/nope/runs", json={"scenario_id": "hr_employee_case"}).status_code == 404


# -- scenario management ------------------------------------------------
def test_scenarios_list_includes_builtin(client: TestClient):
    scs = client.get("/api/scenarios").json()
    assert all("builtin" in s for s in scs)
    assert any(s["builtin"] and s["id"] == "healthcare_patient_summary" for s in scs)


def test_scenario_packs_listed(client: TestClient):
    packs = client.get("/api/scenario-packs").json()
    ids = {p["id"] for p in packs}
    assert {"agentleak_bench", "privacylens_ci", "agentdojo_exfil"} <= ids
    assert all(p["imported_count"] == 0 for p in packs)


def test_import_pack_is_idempotent(client: TestClient):
    first = client.post("/api/scenario-packs/agentleak_bench/import").json()
    assert first["imported"] > 0 and first["skipped"] == 0
    again = client.post("/api/scenario-packs/agentleak_bench/import").json()
    assert again["imported"] == 0 and again["skipped"] == first["imported"]
    # now reflected in the library and pack listing
    imported = [s for s in client.get("/api/scenarios").json() if s["source"] == "imported"]
    assert len(imported) == first["imported"]
    pack = next(p for p in client.get("/api/scenario-packs").json() if p["id"] == "agentleak_bench")
    assert pack["imported_count"] == first["imported"]


def test_import_unknown_pack_404(client: TestClient):
    assert client.post("/api/scenario-packs/nope/import").status_code == 404


def test_upload_trace_then_run_and_delete(client: TestClient):
    trace = {"agent_name": "t", "events": [
        {"channel": "tool_response", "content": {"email": "a@b.com"}},
        {"channel": "shared_memory", "content": "memo a@b.com ssn 123-45-6789"},
    ]}
    created = client.post("/api/scenarios", json={"data": trace, "name": "Up"}).json()
    sid = created["id"]
    assert created["name"] == "Up" and created["source"] == "custom"

    detail = client.get(f"/api/scenarios/{sid}").json()
    assert detail["trace"]["events"]

    # analyze the stored scenario by id
    report = client.post("/api/analyze", json={"scenario_id": sid}).json()
    assert report["summary"]["leaked_secrets"] > 0

    assert client.delete(f"/api/scenarios/{sid}").json()["deleted"] is True
    assert client.get(f"/api/scenarios/{sid}").status_code == 404


def test_upload_pii_record_autodetected(client: TestClient):
    rec = {"id": "x", "category": "finance",
           "source_text": "Card 4111-1111-1111-1111 for john@x.com",
           "pii_annotations": [{"type": "CREDIT_CARD"}]}
    created = client.post("/api/scenarios", json={"data": rec}).json()
    assert created["domain"] == "finance"


def test_upload_junk_400(client: TestClient):
    assert client.post("/api/scenarios", json={"data": {"foo": "bar"}}).status_code == 400


def test_cannot_delete_builtin_scenario(client: TestClient):
    assert client.delete("/api/scenarios/healthcare_patient_summary").status_code == 400


def test_builtin_scenario_detail_has_trace(client: TestClient):
    detail = client.get("/api/scenarios/healthcare_patient_summary").json()
    assert detail["builtin"] is True
    assert detail["trace"]["events"]


def test_imported_scenarios_store_spec(client: TestClient):
    client.post("/api/scenario-packs/agentleak_bench/import")
    scs = client.get("/api/scenarios").json()
    assert any(s["source"] == "imported" and s.get("has_spec") for s in scs)


# -- live agent execution ----------------------------------------------
def test_execute_scripted_agent(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Bot"}).json()["id"]
    run = client.post(f"/api/projects/{pid}/execute", json={"scenario_id": "healthcare_patient_summary"}).json()
    assert run["source"] == "agent:scripted"
    assert run["report"]["summary"]["leaked_secrets"] > 0


def test_execute_live_without_config_400(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Bot"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/execute", json={"scenario_id": "healthcare_patient_summary", "mode": "live"})
    assert r.status_code == 400


def test_execute_unknown_scenario_404(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Bot"}).json()["id"]
    assert client.post(f"/api/projects/{pid}/execute", json={"scenario_id": "nope"}).status_code == 404


def test_agent_api_key_is_redacted(client: TestClient):
    pid = client.post("/api/projects", json={
        "name": "Bot",
        "agent": {"base_url": "https://openrouter.ai/api/v1", "model": "m", "api_key": "SECRET"},
    }).json()["id"]
    proj = client.get(f"/api/projects/{pid}").json()
    agent = proj["config"]["agent"]
    assert agent["api_key"] == "" and agent["api_key_set"] is True


def test_blank_api_key_preserves_stored_key(client: TestClient):
    pid = client.post("/api/projects", json={
        "name": "Bot",
        "agent": {"base_url": "https://openrouter.ai/api/v1", "model": "m1", "api_key": "SECRET"},
    }).json()["id"]
    # update the model with a blank key — the stored key must survive
    client.patch(f"/api/projects/{pid}", json={
        "config": {"agent": {"base_url": "https://openrouter.ai/api/v1", "model": "m2", "api_key": ""}},
    })
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["config"]["agent"]["model"] == "m2"
    assert proj["config"]["agent"]["api_key_set"] is True


# ---------------------------------------------------- self-test API key


def test_generate_and_fetch_api_key(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Self"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/api-key").json()["has_key"] is False

    gen = client.post(f"/api/projects/{pid}/api-key").json()
    assert gen["api_key"].startswith("ak_")
    assert gen["project_id"] == pid

    fetched = client.get(f"/api/projects/{pid}/api-key").json()
    assert fetched["has_key"] is True
    assert fetched["api_key"] == gen["api_key"]


def test_rotate_api_key_changes_value(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Self"}).json()["id"]
    first = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]
    second = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]
    assert first != second


def test_selftest_with_body_key_runs_and_saves(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Self"}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]

    resp = client.post("/api/selftest", json={
        "api_key": key,
        "scenario_id": "healthcare_patient_summary",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == pid
    assert body["run_id"].startswith("run_")
    assert "passed" in body
    assert "remediation_hints" in body

    # the run was auto-saved under the project
    runs = client.get(f"/api/projects/{pid}/runs").json()
    assert any(r["id"] == body["run_id"] for r in runs)


def test_selftest_returns_compliance_posture(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Self"}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]

    body = client.post("/api/selftest", json={
        "api_key": key,
        "scenario_id": "healthcare_patient_summary",
    }).json()
    assert body["compliant"] is False
    assert "hipaa" in body["failed_frameworks"]
    assert body["compliance"]["posture"]["status"] == "non_compliant"


def test_selftest_with_header_key(client: TestClient):
    pid = client.post("/api/projects", json={"name": "Self"}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]

    resp = client.post(
        "/api/selftest-header",
        json={"scenario_id": "healthcare_patient_summary"},
        headers={"X-AgentLeak-Key": key},
    )
    assert resp.status_code == 200
    assert resp.json()["project_id"] == pid


def test_selftest_rejects_invalid_key(client: TestClient):
    resp = client.post("/api/selftest", json={
        "api_key": "ak_not_a_real_key",
        "scenario_id": "healthcare_patient_summary",
    })
    assert resp.status_code == 401


def test_selftest_requires_key(client: TestClient):
    resp = client.post("/api/selftest", json={"scenario_id": "healthcare_patient_summary"})
    assert resp.status_code == 401


# ---------------------------------------------------- red-team endpoint

def test_redteam_returns_metrics(client: TestClient):
    pid = client.post("/api/projects", json={"name": "RT"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={
        "vertical": "healthcare",
        "n": 3,
        "adversary_level": "A1",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == pid
    assert body["vertical"] == "healthcare"
    assert body["scenarios_run"] >= 1
    metrics = body["metrics"]
    assert "mean_elr" in metrics
    assert "overall_asr" in metrics
    assert "clr_per_channel" in metrics
    assert "asr_by_family" in metrics
    assert len(body["attacks"]) == body["scenarios_run"]
    attack = body["attacks"][0]
    assert attack["run_id"] in body["run_ids"]
    assert attack["attack_class_id"].startswith("F")
    assert attack["attack_family_name"]
    assert attack["injection_surface"]
    assert attack["primary_channel"]
    assert attack["severity"] in {
        "critical", "high", "medium", "low", "informational",
    }
    assert isinstance(attack["success"], bool)
    # Report details contain types and channels only; raw matched values must
    # never be exposed by the red-team summary.
    assert "matched_value" not in attack


def test_redteam_saves_runs(client: TestClient):
    pid = client.post("/api/projects", json={"name": "RT2"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={"n": 2})
    body = resp.json()
    assert len(body["run_ids"]) >= 1
    runs = client.get(f"/api/projects/{pid}/runs").json()
    assert any(r["id"] in body["run_ids"] for r in runs)


def test_redteam_specific_attack_class(client: TestClient):
    pid = client.post("/api/projects", json={"name": "RT3"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={
        "attack_class": "F1.1",
        "n": 1,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenarios_run"] >= 1


def test_redteam_requires_login():
    """Unauthenticated redteam request should be 401."""
    from agentleak.core.store import Store
    from agentleak.web import create_app

    store = Store(":memory:")
    app = create_app(store=store, serve_ui=False)
    from fastapi.testclient import TestClient as TC
    anon = TC(app, raise_server_exceptions=True)
    resp = anon.post("/api/projects/nope/redteam", json={})
    assert resp.status_code in (401, 403, 404)


def _leaky_chat(self, messages, tools):
    """A fake LLM that retrieves records then leaks them in its final answer."""
    has_tool_result = any(m.get("role") == "tool" for m in messages)
    if not has_tool_result:
        return {
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "get_records", "arguments": "{}"}}],
        }
    leaked = " ".join(str(m.get("content", "")) for m in messages if m.get("role") == "tool")
    return {"content": f"Here is the full client record: {leaked}", "tool_calls": []}


def test_redteam_live_calls_real_agent(client: TestClient, monkeypatch):
    """Live mode must drive a real agent run (mocked LLM) and detect leaks."""
    from agentleak.agent.llm import OpenAICompatLLM
    monkeypatch.setattr(OpenAICompatLLM, "chat", _leaky_chat)

    pid = client.post("/api/projects", json={"name": "RT-live"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={
        "vertical": "finance",
        "n": 2,
        "mode": "live",
        "base_url": "https://example.test/v1",
        "model": "mock-model",
        "api_key": "test-key",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["live"] is True
    assert body["mode"] == "live"
    assert body["scenarios_run"] >= 1
    # The mocked agent leaks every record → detector must catch it.
    assert body["metrics"]["mean_elr"] > 0
    runs = client.get(f"/api/projects/{pid}/runs").json()
    assert any(r["id"] in body["run_ids"] for r in runs)
    assert any(r.get("source") == "redteam:live" for r in runs)


def test_redteam_live_without_endpoint_400(client: TestClient, monkeypatch):
    """mode=live with no endpoint and no env key returns a helpful 400."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTLEAK_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTLEAK_LLM_MODEL", raising=False)
    pid = client.post("/api/projects", json={"name": "RT-live-bad"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={"mode": "live", "n": 1})
    assert resp.status_code == 400


def test_redteam_auto_defaults_to_scripted(client: TestClient, monkeypatch):
    """auto mode without a configured endpoint stays scripted/deterministic."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTLEAK_LLM_BASE_URL", raising=False)
    pid = client.post("/api/projects", json={"name": "RT-auto"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={"n": 2})
    assert resp.status_code == 200
    assert resp.json()["live"] is False


def test_redteam_live_env_base_url(client: TestClient, monkeypatch):
    """AGENTLEAK_LLM_BASE_URL + AGENTLEAK_LLM_MODEL enables auto-live with a mocked LLM."""
    from agentleak.agent.llm import OpenAICompatLLM
    monkeypatch.setattr(OpenAICompatLLM, "chat", _leaky_chat)
    monkeypatch.setenv("AGENTLEAK_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("AGENTLEAK_LLM_MODEL", "llama3.2")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    pid = client.post("/api/projects", json={"name": "RT-ollama"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/redteam", json={"n": 1, "mode": "live"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["live"] is True
    assert body["scenarios_run"] >= 1
    # Local endpoints (localhost) need no API key — verify no LLMError was raised.
    assert body["metrics"]["mean_elr"] > 0





# -- leaderboard --------------------------------------------------------
def _leaky_trace() -> dict:
    return {
        "agent_name": "leaky", "events": [
            {"channel": "tool_response", "content": {"ssn": "123-45-6789"}, "source": "crm", "target": "agent"},
            {"channel": "log", "content": "ssn 123-45-6789 email a@b.io", "source": "agent", "target": "stdout"},
            {"channel": "final_output", "content": "Done.", "source": "agent", "target": "user"},
        ],
    }


def _clean_trace() -> dict:
    return {
        "agent_name": "clean", "events": [
            {"channel": "user_input", "content": "hello", "source": "user", "target": "agent"},
            {"channel": "final_output", "content": "Hi! How can I help?", "source": "agent", "target": "user"},
        ],
    }


def test_leaderboard_ranks_agents_by_agentrisk(client: TestClient):
    good = client.post("/api/projects", json={"name": "GoodBot"}).json()["id"]
    bad = client.post("/api/projects", json={"name": "LeakyBot"}).json()["id"]
    client.post(f"/api/projects/{good}/runs", json={"trace": _clean_trace()})
    client.post(f"/api/projects/{bad}/runs", json={"trace": _leaky_trace()})

    board = client.get("/api/leaderboard").json()
    assert [e["name"] for e in board["entries"]] == ["GoodBot", "LeakyBot"]
    top = board["entries"][0]
    assert top["rank"] == 1
    assert top["risk_index"] <= board["entries"][1]["risk_index"]
    assert set(top) >= {"project_id", "name", "rank", "risk_index", "privacy_score",
                        "verdict", "leaked_secrets", "runs", "last_run_at"}


def test_leaderboard_skips_projects_without_runs(client: TestClient):
    client.post("/api/projects", json={"name": "Idle"})
    board = client.get("/api/leaderboard").json()
    assert all(e["name"] != "Idle" for e in board["entries"])
