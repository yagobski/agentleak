"""Web GUI tests (skipped if the [gui] extra isn't installed)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.web import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path) -> TestClient:
    import os
    os.environ["AGENTLEAK_HOME"] = str(tmp_path)
    c = TestClient(create_app())
    from tests.conftest import authenticate
    return authenticate(c)


def test_spa_served(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    # The built React shell mounts on #root and links a hashed asset bundle.
    assert 'id="root"' in r.text
    assert "AgentLeak" in r.text


def test_public_route_is_prerendered_for_crawlers(client: TestClient):
    """A public page must arrive as HTML, not as an empty shell.

    The build renders these routes with the page components themselves, so this
    asserts the outcome (real markup, route-specific metadata) rather than one
    hard-coded string — the title now belongs to the page, not to a table in
    this repo that can drift from it.
    """
    r = client.get("/features/trace-analysis")
    assert r.status_code == 200
    assert '<link rel="canonical" href="https://www.agentleak.org/features/trace-analysis"' in r.text
    assert '<meta name="robots" content="index, follow, max-image-preview:large"' in r.text
    # Large-image cards need an image to point at.
    assert '<meta name="twitter:card" content="summary_large_image"' in r.text
    assert '<meta property="og:image"' in r.text
    # The page itself, not just <div id="root"></div>.
    assert "<h1" in r.text
    assert len(r.text) > 8000, "looks like the empty SPA shell, not a prerendered page"


def test_prerendered_page_carries_structured_data(client: TestClient):
    r = client.get("/research")
    assert r.status_code == 200
    assert 'application/ld+json' in r.text


def test_route_without_a_prerender_still_serves_the_shell(client: TestClient):
    """A new route must degrade to client-side rendering, never to a 404."""
    r = client.get("/features/does-not-exist-yet")
    assert r.status_code == 200
    assert 'id="root"' in r.text


def test_unknown_spa_route_is_not_indexable(client: TestClient):
    r = client.get("/private-or-missing")
    assert r.status_code == 200
    assert '<meta name="robots" content="noindex, nofollow"' in r.text


def test_public_spa_head_request(client: TestClient):
    r = client.head("/features")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_meta_endpoint(client: TestClient):
    m = client.get("/api/meta").json()
    assert {"version", "channels", "detectors", "agent_types"} <= set(m)
    assert "tool_call" in m["channels"]
    assert "pii" in m["detectors"]
    assert any(a["id"] == "generic" for a in m["agent_types"])


def test_scenarios_endpoint(client: TestClient):
    ids = {s["id"] for s in client.get("/api/scenarios").json()}
    assert "healthcare_patient_summary" in ids


def test_example_endpoint(client: TestClient):
    assert client.get("/api/example/healthcare_patient_summary").json()["events"]


def test_example_unknown_404(client: TestClient):
    assert client.get("/api/example/nope").status_code == 404


def test_analyze_scenario(client: TestClient):
    d = client.post("/api/analyze", json={"scenario_id": "healthcare_patient_summary"}).json()
    assert d["scoring"] == "agentrisk"
    assert d["verdict"] in {"High risk", "Fail"}
    assert d["blocked"] is True


def test_analyze_with_explicit_vault(client: TestClient):
    ex = client.get("/api/example/finance_loan_review").json()
    d = client.post("/api/analyze", json={
        "trace": ex,
        "vault": {"mode": "explicit", "levels": {1: 5, 2: 3, 3: 2, 4: 1}},
    }).json()
    assert d["rho_s"] == 21


def test_analyze_detector_toggles(client: TestClient):
    ex = client.get("/api/example/finance_loan_review").json()
    d = client.post("/api/analyze", json={
        "trace": ex,
        "detectors": {"pii": True, "secrets": False, "healthcare": False, "finance": False, "hr": False},
    }).json()
    assert {f["detector"] for f in d["findings"]} <= {"pii_detector"}


def test_analyze_custom_detector(client: TestClient):
    d = client.post("/api/analyze", json={
        "trace": {"run_id": "r", "events": [{"channel": "tool_call", "content": "ref PROJECT-ABC-1234"}]},
        "detectors": {"pii": False, "secrets": False, "healthcare": False, "finance": False, "hr": False},
        "custom_detectors": [{"name": "proj", "pattern": r"PROJECT-[A-Z]{3}-[0-9]{4}", "severity": "high"}],
    }).json()
    assert any(f["detector"] == "custom:proj" for f in d["findings"])


def test_analyze_bad_trace_400(client: TestClient):
    assert client.post("/api/analyze", json={"trace": "not json"}).status_code == 400


@pytest.mark.parametrize("fmt", ["json", "html", "markdown"])
def test_report_formats(client: TestClient, fmt: str):
    r = client.post(f"/api/report/{fmt}", json={"scenario_id": "healthcare_patient_summary"})
    assert r.status_code == 200
    assert len(r.text) > 0


def test_report_bad_format_400(client: TestClient):
    assert client.post("/api/report/pdf", json={"scenario_id": "healthcare_patient_summary"}).status_code == 400


# ---------------------------------------------------------------------------
# Run history & compare API endpoints
# ---------------------------------------------------------------------------

@pytest.fixture()
def project_with_runs(client: TestClient) -> dict:
    """Create a project and two stored runs (low score → high score)."""
    p = client.post("/api/projects", json={"name": "history-test-agent"}).json()
    pid = p["id"]
    # Run 1: vulnerable scenario
    r1 = client.post(f"/api/projects/{pid}/runs", json={
        "scenario_id": "healthcare_patient_summary",
        "label": "baseline",
    }).json()
    # Run 2: same scenario again (same score, just gives us two runs to compare)
    r2 = client.post(f"/api/projects/{pid}/runs", json={
        "scenario_id": "healthcare_patient_summary",
        "label": "second",
    }).json()
    return {"project": p, "run_1": r1, "run_2": r2}


def test_run_has_privacy_score_and_label(project_with_runs: dict):
    r = project_with_runs["run_1"]
    assert "privacy_score" in r
    assert isinstance(r["privacy_score"], int)
    assert r["label"] == "baseline"


def test_history_endpoint_returns_progression(client: TestClient, project_with_runs: dict):
    pid = project_with_runs["project"]["id"]
    r = client.get(f"/api/projects/{pid}/history").json()
    assert "runs" in r and "progression" in r
    assert len(r["runs"]) == 2
    # Ordered oldest-first
    assert r["runs"][0]["rank"] == 1
    assert r["runs"][1]["rank"] == 2
    # First run has no delta
    assert r["runs"][0]["delta_score"] is None
    # Progression aggregate keys present
    prog = r["progression"]
    assert {"first_score", "latest_score", "best_score", "total_runs"} <= set(prog)
    assert prog["total_runs"] == 2


def test_history_endpoint_limit(client: TestClient, project_with_runs: dict):
    pid = project_with_runs["project"]["id"]
    r = client.get(f"/api/projects/{pid}/history?limit=1").json()
    assert len(r["runs"]) == 1


def test_compare_endpoint(client: TestClient, project_with_runs: dict):
    pid = project_with_runs["project"]["id"]
    id_a = project_with_runs["run_1"]["id"]
    id_b = project_with_runs["run_2"]["id"]
    r = client.get(f"/api/projects/{pid}/compare?a={id_a}&b={id_b}").json()
    assert "run_a" in r and "run_b" in r and "diff" in r
    diff = r["diff"]
    assert "delta_score" in diff
    assert "delta_ri" in diff
    assert "score_direction" in diff
    assert isinstance(diff.get("frameworks"), list)


def test_compare_missing_run_404(client: TestClient, project_with_runs: dict):
    pid = project_with_runs["project"]["id"]
    r = client.get(f"/api/projects/{pid}/compare?a=run_missing&b=run_missing")
    assert r.status_code == 404


def test_history_wrong_project_403(client: TestClient):
    """Accessing another user's project returns 404 (ownership enforced)."""
    r = client.get("/api/projects/proj_nonexistent/history")
    assert r.status_code == 404
