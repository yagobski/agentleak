"""CLI tests via Typer's CliRunner."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from agentleak.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "agentleak" in result.stdout


def test_scenarios_lists_builtins():
    result = runner.invoke(app, ["scenarios"])
    assert result.exit_code == 0
    assert "healthcare_patient_summary" in result.stdout


def test_agent_card_prints_valid_a2a_card():
    result = runner.invoke(app, ["agent-card"])
    assert result.exit_code == 0
    card = json.loads(result.stdout)
    assert card["name"] == "agentleak"
    assert card["agent_protocol_version"] == "a2a-v1"
    assert "/api/selftest" in card["endpoints"]


def test_init_scaffolds_project(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "agentleak.yaml").exists()
    assert (tmp_path / "traces" / "example_trace.json").exists()
    assert (tmp_path / "reports").is_dir()


def test_validate_good_config(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    result = runner.invoke(app, ["validate", str(tmp_path / "agentleak.yaml")])
    assert result.exit_code == 0
    assert "valid" in result.stdout


def test_validate_missing_config():
    result = runner.invoke(app, ["validate", "/nonexistent/agentleak.yaml"])
    assert result.exit_code == 1


def test_run_scenario_blocks_on_critical(tmp_path):
    result = runner.invoke(app, [
        "run", "--scenario", "healthcare_patient_summary",
        "--output", str(tmp_path), "--format", "json",
    ])
    # Healthcare demo leaks Level-4 data -> blocked -> exit 1.
    assert result.exit_code == 1
    assert "Risk Index" in result.stdout
    assert "Key insight" in result.stdout
    files = list(tmp_path.glob("*.json"))
    assert files


def test_run_trace_file(tmp_path):
    trace = {
        "run_id": "clean_run",
        "events": [{"channel": "final_output", "content": "Nothing to see."}],
    }
    trace_path = tmp_path / "t.json"
    trace_path.write_text(json.dumps(trace))
    result = runner.invoke(app, [
        "run", "--trace", str(trace_path), "--output", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    assert "Pass" in result.stdout


def test_run_with_nothing_errors():
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 2


def test_report_rerenders_saved_json(tmp_path):
    # First produce a JSON report.
    runner.invoke(app, [
        "run", "--scenario", "finance_loan_review",
        "--output", str(tmp_path), "--format", "json",
    ])
    src = list(tmp_path.glob("*.json"))[0]
    result = runner.invoke(app, ["report", "--input", str(src), "--format", "html,markdown"])
    assert result.exit_code == 0
    assert src.with_suffix(".html").exists()
    assert src.with_suffix(".md").exists()


def test_run_fail_under_override(tmp_path):
    # A clean trace normally passes; --fail-under 101 forces a failure.
    trace = {"run_id": "r", "events": [{"channel": "final_output", "content": "clean"}]}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(trace))
    result = runner.invoke(app, [
        "run", "--trace", str(p), "--output", str(tmp_path),
        "--format", "json", "--fail-under", "101",
    ])
    assert result.exit_code == 1


def test_init_force_overwrites(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    # Without --force it warns and keeps the file.
    warned = runner.invoke(app, ["init", str(tmp_path)])
    assert "already exists" in warned.stdout
    # With --force it rewrites without warning.
    forced = runner.invoke(app, ["init", str(tmp_path), "--force"])
    assert forced.exit_code == 0
    assert "already exists" not in forced.stdout


def test_validate_invalid_trace(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json")
    result = runner.invoke(app, ["validate", str(tmp_path / "agentleak.yaml"), "--trace", str(bad)])
    assert result.exit_code == 1
    assert "invalid trace" in result.stdout


def test_run_from_config_scenarios(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    result = runner.invoke(app, [
        "run", "--config", str(tmp_path / "agentleak.yaml"),
        "--output", str(tmp_path / "out"), "--format", "json", "--quiet",
    ])
    # The scaffolded config enables one scenario (healthcare) -> blocked -> exit 1.
    assert result.exit_code in (0, 1)
    assert list((tmp_path / "out").glob("*.json"))


def test_run_bad_config_errors(tmp_path):
    bad = tmp_path / "agentleak.yaml"
    bad.write_text("detectors: [this is not valid structure")
    result = runner.invoke(app, ["run", "--config", str(bad), "--scenario", "hr_employee_case"])
    assert result.exit_code == 2


def test_report_missing_input_errors():
    result = runner.invoke(app, ["report", "--input", "/nonexistent/report.json"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# history & compare commands
# ---------------------------------------------------------------------------

def _make_db_with_runs(tmp_path):
    """Create a tmp DB, project, and 3 runs with improving scores."""
    from agentleak.core.store import Store
    db = Store(str(tmp_path / "agentleak.db"))
    p = db.create_project("my-agent")
    reports = [
        {"agent_name": "a", "privacy_score": 20, "risk_index": 0.9,
         "verdict": "Fail", "blocked": True,
         "summary": {"leaked_secrets": 4, "total_findings": 6}, "compliance": {}},
        {"agent_name": "a", "privacy_score": 60, "risk_index": 0.5,
         "verdict": "High risk", "blocked": False,
         "summary": {"leaked_secrets": 1, "total_findings": 3}, "compliance": {}},
        {"agent_name": "a", "privacy_score": 90, "risk_index": 0.05,
         "verdict": "Pass", "blocked": False,
         "summary": {"leaked_secrets": 0, "total_findings": 0}, "compliance": {}},
    ]
    for i, rep in enumerate(reports):
        db.create_run(p["id"], rep, label=f"v{i + 1}")
    runs = db.run_history(p["id"])
    return str(tmp_path / "agentleak.db"), runs


def test_history_shows_progression(tmp_path):
    db_path, _ = _make_db_with_runs(tmp_path)
    result = runner.invoke(app, ["history", "my-agent", "--db", db_path])
    assert result.exit_code == 0
    assert "my-agent" in result.stdout
    assert "v1" in result.stdout
    assert "v3" in result.stdout
    # Should show score deltas
    assert "+" in result.stdout


def test_history_missing_project_exits_1(tmp_path):
    from agentleak.core.store import Store
    db_path = str(tmp_path / "empty.db")
    Store(db_path)  # create empty DB
    result = runner.invoke(app, ["history", "nonexistent", "--db", db_path])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_history_no_runs_shows_message(tmp_path):
    from agentleak.core.store import Store
    db_path = str(tmp_path / "norun.db")
    db = Store(db_path)
    db.create_project("empty-agent")
    result = runner.invoke(app, ["history", "empty-agent", "--db", db_path])
    assert result.exit_code == 0
    assert "No runs" in result.stdout


def test_compare_improvement(tmp_path):
    db_path, runs = _make_db_with_runs(tmp_path)
    id_a, id_b = runs[0]["id"], runs[2]["id"]
    result = runner.invoke(app, ["compare", id_a, id_b, "--db", db_path])
    assert result.exit_code == 0
    assert "IMPROVED" in result.stdout
    assert "Blocker resolved" in result.stdout


def test_compare_regression(tmp_path):
    db_path, runs = _make_db_with_runs(tmp_path)
    id_a, id_b = runs[2]["id"], runs[0]["id"]  # reversed: good → bad
    result = runner.invoke(app, ["compare", id_a, id_b, "--db", db_path])
    assert result.exit_code == 0
    assert "REGRESSED" in result.stdout


def test_compare_missing_run_exits_1(tmp_path):
    from agentleak.core.store import Store
    db_path = str(tmp_path / "cmp.db")
    Store(db_path)
    result = runner.invoke(app, ["compare", "run_missing_a", "run_missing_b", "--db", db_path])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()
