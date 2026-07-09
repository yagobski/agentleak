"""SQLite store: projects + runs persistence."""

from __future__ import annotations

import pytest

from agentleak import AgentLeakRunner
from agentleak.core.store import Store
from agentleak.scenarios import load_example_trace


@pytest.fixture()
def store(tmp_path) -> Store:
    return Store(str(tmp_path / "test.db"))


def _report():
    return AgentLeakRunner().analyze(load_example_trace("healthcare_patient_summary")).to_dict()


def test_project_crud(store: Store):
    p = store.create_project("My Agent", agent_type="langchain", description="d", config={"redact": True})
    assert p["id"].startswith("proj_")
    assert p["agent_type"] == "langchain"
    assert store.get_project(p["id"])["name"] == "My Agent"
    assert len(store.list_projects()) == 1

    updated = store.update_project(p["id"], name="Renamed")
    assert updated["name"] == "Renamed"
    assert store.delete_project(p["id"]) is True
    assert store.get_project(p["id"]) is None


def test_invalid_agent_type_falls_back(store: Store):
    p = store.create_project("x", agent_type="bogus")
    assert p["agent_type"] == "generic"


def test_get_project_by_name(store: Store):
    store.create_project("dup")
    assert store.get_project_by_name("dup") is not None
    assert store.get_project_by_name("missing") is None


def test_run_lifecycle_and_aggregates(store: Store):
    p = store.create_project("agent")
    run = store.create_run(p["id"], _report(), source="sdk")
    assert run["id"].startswith("run_")
    assert run["verdict"] in {"High risk", "Fail"}
    assert "report" in run and run["report"]["scoring"] == "agentrisk"

    runs = store.list_runs(p["id"])
    assert len(runs) == 1
    assert "report" not in runs[0]  # list is summary-only

    # project aggregates update
    proj = store.get_project(p["id"])
    assert proj["run_count"] == 1
    assert proj["avg_risk_index"] is not None
    assert proj["last_run"]["id"] == run["id"]

    assert store.delete_run(run["id"]) is True
    assert store.get_run(run["id"]) is None


def test_delete_project_cascades_runs(store: Store):
    p = store.create_project("agent")
    store.create_run(p["id"], _report())
    store.delete_project(p["id"])
    assert store.list_runs(p["id"]) == []


def test_stats(store: Store):
    p = store.create_project("agent")
    store.create_run(p["id"], _report())
    s = store.stats()
    assert s["projects"] == 1
    assert s["runs"] == 1
    assert s["avg_risk_index"] is not None
    assert len(s["recent_runs"]) == 1


# ---------------------------------------------------------------------------
# Run history & progression
# ---------------------------------------------------------------------------

def _fake_report(privacy_score: int, risk_index: float, *, blocked: bool = False) -> dict:
    """Minimal report dict that satisfies Store.create_run."""
    return {
        "agent_name": "test-agent",
        "privacy_score": privacy_score,
        "risk_index": risk_index,
        "verdict": "Fail" if blocked else "Pass",
        "blocked": blocked,
        "summary": {"leaked_secrets": 2 if blocked else 0, "total_findings": 4 if blocked else 0},
        "compliance": {
            "frameworks": [
                {"id": "hipaa", "status": "compliant" if not blocked else "non_compliant"},
                {"id": "gdpr", "status": "compliant"},
            ]
        },
        "channel_risk": [],
    }


def test_privacy_score_stored_in_column(store: Store):
    p = store.create_project("score-test")
    run = store.create_run(p["id"], _fake_report(77, 0.25))
    assert run["privacy_score"] == 77


def test_label_stored_and_returned(store: Store):
    p = store.create_project("label-test")
    run = store.create_run(p["id"], _fake_report(50, 0.5), label="before-defenses")
    assert run["label"] == "before-defenses"
    # label should also appear in list_runs summary
    summary = store.list_runs(p["id"])[0]
    assert summary["label"] == "before-defenses"


def test_run_history_empty(store: Store):
    p = store.create_project("empty-proj")
    assert store.run_history(p["id"]) == []


def test_run_history_single_run_no_delta(store: Store):
    p = store.create_project("single")
    store.create_run(p["id"], _fake_report(40, 0.8), label="v0")
    history = store.run_history(p["id"])
    assert len(history) == 1
    assert history[0]["rank"] == 1
    assert history[0]["delta_score"] is None
    assert history[0]["delta_ri"] is None
    assert history[0]["label"] == "v0"


def test_run_history_ordered_oldest_first_with_deltas(store: Store):
    p = store.create_project("multi")
    store.create_run(p["id"], _fake_report(30, 0.9), label="v1")
    store.create_run(p["id"], _fake_report(55, 0.6), label="v2")
    store.create_run(p["id"], _fake_report(80, 0.1), label="v3")

    history = store.run_history(p["id"])
    assert len(history) == 3
    # Ordered oldest-first
    assert [r["label"] for r in history] == ["v1", "v2", "v3"]
    # Ranks
    assert [r["rank"] for r in history] == [1, 2, 3]
    # First run has no delta
    assert history[0]["delta_score"] is None
    # v1→v2: score +25
    assert history[1]["delta_score"] == 25
    # v2→v3: score +25
    assert history[2]["delta_score"] == 25
    # RI deltas should be negative (improving)
    assert history[1]["delta_ri"] < 0
    assert history[2]["delta_ri"] < 0


def test_run_history_regression_shows_negative_delta(store: Store):
    p = store.create_project("regress")
    store.create_run(p["id"], _fake_report(90, 0.05), label="good")
    store.create_run(p["id"], _fake_report(40, 0.7), label="bad")

    history = store.run_history(p["id"])
    assert history[1]["delta_score"] == -50
    assert history[1]["delta_ri"] > 0  # RI got worse


def test_run_history_respects_limit(store: Store):
    p = store.create_project("limited")
    for i in range(10):
        store.create_run(p["id"], _fake_report(50 + i, 0.5))
    assert len(store.run_history(p["id"], limit=4)) == 4


def test_best_run(store: Store):
    p = store.create_project("best")
    store.create_run(p["id"], _fake_report(30, 0.9), label="low")
    store.create_run(p["id"], _fake_report(95, 0.02), label="high")
    store.create_run(p["id"], _fake_report(60, 0.4), label="mid")

    best = store.best_run(p["id"])
    assert best is not None
    assert best["privacy_score"] == 95
    assert best["label"] == "high"


def test_compare_runs_missing_returns_none(store: Store):
    assert store.compare_runs("run_missing_a", "run_missing_b") is None


def test_compare_runs_one_missing_returns_none(store: Store):
    p = store.create_project("cmp-one")
    r = store.create_run(p["id"], _fake_report(50, 0.5))
    assert store.compare_runs(r["id"], "run_missing") is None


def test_compare_runs_improvement(store: Store):
    p = store.create_project("cmp-improvement")
    r_a = store.create_run(p["id"], _fake_report(20, 0.9, blocked=True), label="before")
    r_b = store.create_run(p["id"], _fake_report(90, 0.05, blocked=False), label="after")

    result = store.compare_runs(r_a["id"], r_b["id"])
    assert result is not None

    diff = result["diff"]
    assert diff["delta_score"] == 70
    assert diff["delta_ri"] < 0
    assert diff["score_direction"] == "improved"
    assert diff["blocked_resolved"] is True


def test_compare_runs_regression(store: Store):
    p = store.create_project("cmp-regress")
    r_a = store.create_run(p["id"], _fake_report(80, 0.1))
    r_b = store.create_run(p["id"], _fake_report(30, 0.8))

    diff = store.compare_runs(r_a["id"], r_b["id"])["diff"]
    assert diff["delta_score"] == -50
    assert diff["score_direction"] == "regressed"
    assert diff["blocked_resolved"] is False


def test_compare_runs_framework_diff(store: Store):
    p = store.create_project("cmp-fw")
    r_a = store.create_run(p["id"], _fake_report(20, 0.9, blocked=True))
    r_b = store.create_run(p["id"], _fake_report(90, 0.05, blocked=False))

    fws = {fw["id"]: fw for fw in store.compare_runs(r_a["id"], r_b["id"])["diff"]["frameworks"]}
    assert fws["hipaa"]["before"] == "non_compliant"
    assert fws["hipaa"]["after"] == "compliant"
    assert fws["hipaa"]["change"] == "fixed"
    assert fws["gdpr"]["change"] == "same"


def test_stats_includes_avg_privacy_score(store: Store):
    p = store.create_project("stats-score")
    store.create_run(p["id"], _fake_report(60, 0.4))
    store.create_run(p["id"], _fake_report(80, 0.2))
    s = store.stats()
    assert s["avg_privacy_score"] == 70.0


def test_migration_adds_columns_to_existing_db(tmp_path):
    """Simulates an older DB without privacy_score/label — migration must add them."""
    import sqlite3
    db_path = str(tmp_path / "old.db")
    # Create a DB with the old schema (no privacy_score, no label)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE runs (
            id TEXT PRIMARY KEY, project_id TEXT, created_at REAL,
            source TEXT, agent_name TEXT, risk_index REAL,
            verdict TEXT, blocked INTEGER, leaked INTEGER, report TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE projects (
            id TEXT PRIMARY KEY, name TEXT, agent_type TEXT,
            description TEXT, config TEXT, created_at REAL, updated_at REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE scenarios (
            id TEXT PRIMARY KEY, name TEXT, domain TEXT,
            description TEXT, sensitive_data TEXT, tags TEXT,
            difficulty TEXT, source TEXT, pack_id TEXT, origin_id TEXT,
            trace TEXT, created_at REAL
        )"""
    )
    conn.commit()
    conn.close()

    # Opening via Store should run migration without errors
    store_new = Store(db_path)
    cols = {
        r[1]
        for r in store_new._conn().execute("PRAGMA table_info(runs)").fetchall()
    }
    assert "privacy_score" in cols
    assert "label" in cols



def _trace():
    return load_example_trace("healthcare_patient_summary").to_dict()


def test_scenario_crud(store: Store):
    sc = store.create_scenario(
        "My scenario", _trace(), domain="finance", description="d",
        sensitive_data=["ssn", "email"], tags=["t"], difficulty="hard",
    )
    assert sc["id"].startswith("sce_")
    assert sc["domain"] == "finance"
    assert sc["builtin"] is False
    assert "trace" in sc and sc["trace"]["events"]

    listed = store.list_scenarios()
    assert len(listed) == 1
    assert "trace" not in listed[0]  # list is summary-only

    assert store.get_scenario(sc["id"], with_trace=False).get("trace") is None
    assert store.delete_scenario(sc["id"]) is True
    assert store.get_scenario(sc["id"]) is None


def test_scenario_stores_and_returns_spec(store: Store):
    spec = {"scenario_id": "s1", "objective": {"user_request": "do it"}, "private_vault": {"records": []}}
    sc = store.create_scenario("S", _trace(), spec=spec)
    assert sc["has_spec"] is True
    assert store.get_scenario(sc["id"])["spec"] == spec
    # summaries advertise has_spec without carrying the body
    summary = store.list_scenarios()[0]
    assert summary["has_spec"] is True and "spec" not in summary


def test_scenario_without_spec_has_none(store: Store):
    sc = store.create_scenario("S", _trace())
    assert sc["has_spec"] is False
    assert store.get_scenario(sc["id"])["spec"] is None


def test_scenario_import_idempotency_helpers(store: Store):
    assert store.scenario_exists("pack_a", "origin_1") is False
    assert store.count_pack_scenarios("pack_a") == 0

    store.create_scenario("S", _trace(), source="imported", pack_id="pack_a", origin_id="origin_1")
    assert store.scenario_exists("pack_a", "origin_1") is True
    assert store.scenario_exists("pack_a", "origin_2") is False
    assert store.scenario_exists("pack_a", "") is False  # blank origin never matches
    assert store.count_pack_scenarios("pack_a") == 1


# -- per-owner metering & free-tier quota accounting --------------------
def test_meter_usage_counts_per_owner_within_window(store: Store):
    import time as _t

    now = _t.time()
    store.meter_usage("user_a", "/api/analyze")
    store.meter_usage("user_a", "/api/analyze")
    store.meter_usage("user_b", "/api/analyze")

    assert store.owner_usage_since("user_a", now - 60) == 2
    assert store.owner_usage_since("user_b", now - 60) == 1
    assert store.owner_usage_since("user_a", now + 60) == 0  # window excludes past rows
    assert store.owner_usage_since("", now - 60) == 0  # anonymous never counts


def test_record_api_usage_is_monitoring_only(store: Store):
    """record_api_usage logs for the admin console but does NOT meter quota."""
    import time as _t

    u = store.create_user("owner@x.io", "pw-123456")
    p = store.create_project("P", owner_id=u["id"])
    store.record_api_usage(p["id"], "/api/agent/improve")
    # Monitoring row exists, but quota is untouched (metered separately).
    assert store.owner_usage_since(u["id"], _t.time() - 60) == 0
