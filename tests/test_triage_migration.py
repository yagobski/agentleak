# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The triage tables must not endanger a database created by 0.18.0 or 0.19.0.

Two independent checks, synthetic data only:

* the 0.19.0 schema (``fixtures/store_schema_v0_19_0.sql``, dumped from
  ``sqlite_master`` of a database the tagged code created; 0.18.0's is
  identical) is filled by raw SQL, opened twice by this version, and every
  pre-existing row, table definition and index must be byte-identical; every
  existing endpoint must still answer;
* when the git tags are available, the tagged ``core/store.py`` itself
  creates and fills the database (upgrade), and opens it again after this
  version wrote triage rows (downgrade): reads, deletes and cascades work.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import time
import types
from pathlib import Path
from typing import Any

import pytest

from agentleak.core.store import TRIAGE_DDL, Store

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.web import create_app  # noqa: E402
from agentleak.web.auth import COOKIE_NAME  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "store_schema_v0_19_0.sql"
NEW_TABLES = {"finding_fingerprints", "finding_triage"}
_TRACE = {
    "run_id": "mig-trace",
    "agent_name": "mig-agent",
    "events": [
        {"channel": "tool_response", "content": {"patient": "Ada Quill", "ssn": "123-45-6789"}},
        {"channel": "log", "content": "Patient Ada Quill SSN 123-45-6789"},
        {"channel": "final_output", "content": "Done."},
    ],
}


def _report() -> dict[str, Any]:
    from agentleak import AgentLeakRunner, Trace

    return AgentLeakRunner().analyze(Trace.from_dict(_TRACE)).to_dict()


def _snapshot(path: str) -> dict[str, Any]:
    """Every row of every table, and the DDL of every schema object."""
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    out: dict[str, Any] = {"schema": {}, "rows": {}}
    for r in c.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL"):
        out["schema"][f"{r['type']}:{r['name']}"] = r["sql"]
    for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        out["rows"][name] = [tuple(row) for row in c.execute(f"SELECT * FROM {name} ORDER BY rowid")]
    c.close()
    return out


def _fill_019_schema(path: str) -> dict[str, str]:
    """A 0.19.0-shaped database with one row in every table (raw SQL)."""
    report = _report()
    now = time.time()
    c = sqlite3.connect(path)
    c.executescript(FIXTURE.read_text(encoding="utf-8"))
    c.execute(
        "INSERT INTO users (id, email, name, password_hash, created_at, is_admin, disabled)"
        " VALUES ('usr_a', 'alice@example.test', 'Alice', 'x$y', ?, 1, 0)", (now,),
    )
    c.execute("INSERT INTO sessions VALUES ('tok-alice', 'usr_a', ?, ?)", (now, now + 3600))
    c.execute(
        "INSERT INTO projects (id, name, agent_type, description, config, created_at, updated_at,"
        " owner_id, agent_card, public_slug) VALUES ('proj_a', 'Legacy', 'generic', 'd',"
        " '{\"detectors\": {\"pii\": true}}', ?, ?, 'usr_a', '', '')", (now, now),
    )
    for i, rid in enumerate(("run_old1", "run_old2")):
        c.execute(
            "INSERT INTO runs (id, project_id, created_at, source, agent_name, risk_index, privacy_score,"
            " verdict, blocked, leaked, label, report) VALUES (?, 'proj_a', ?, 'manual', 'mig-agent', ?, ?,"
            " ?, ?, ?, '', ?)",
            (rid, now - 100 + i, report["risk_index"], report["privacy_score"], report["verdict"],
             int(report["blocked"]), report["summary"]["leaked_secrets"], json.dumps(report)),
        )
    c.execute(
        "INSERT INTO scenarios (id, name, domain, trace, created_at, owner_id) VALUES"
        " ('sce_a', 'mine', 'custom', ?, ?, 'usr_a')", (json.dumps(_TRACE), now),
    )
    c.execute(
        "INSERT INTO code_scans (id, project_id, created_at, result) VALUES ('scan_a', 'proj_a', ?, '{}')", (now,)
    )
    c.execute("INSERT INTO audit_log (id, created_at, actor_id, action) VALUES ('aud_a', ?, 'usr_a', 'x')", (now,))
    c.execute("INSERT INTO api_usage VALUES ('use_a', ?, 'proj_a', '/api/selftest')", (now,))
    c.execute("INSERT INTO usage_meter VALUES ('met_a', ?, 'usr_a', '/api/analyze')", (now,))
    c.execute("INSERT INTO user_settings VALUES ('usr_a', 'k', 'v', ?)", (now,))
    c.commit()
    c.close()
    return {"pid": "proj_a", "run1": "run_old1", "run2": "run_old2"}


def test_new_tables_are_the_only_schema_change(tmp_path) -> None:
    path = str(tmp_path / "v019.db")
    ids = _fill_019_schema(path)
    before = _snapshot(path)
    Store(path)
    Store(path)  # idempotent: a second start changes nothing
    after = _snapshot(path)

    for key, sql in before["schema"].items():
        assert after["schema"][key] == sql, f"{key} changed"
    added = {k.split(":", 1)[1] for k in set(after["schema"]) - set(before["schema"])}
    assert added == NEW_TABLES | {"idx_triage_project", "idx_triage_run"}
    for table, rows in before["rows"].items():
        assert after["rows"][table] == rows, f"rows of {table} changed"
    assert after["rows"]["finding_triage"] == [] and after["rows"]["finding_fingerprints"] == []
    assert len(TRIAGE_DDL) == 4
    assert ids["pid"]


def test_existing_endpoints_answer_on_a_019_database(tmp_path) -> None:
    path = str(tmp_path / "v019.db")
    ids = _fill_019_schema(path)
    before = _snapshot(path)
    client = TestClient(create_app(store=Store(path)))
    client.cookies.set(COOKIE_NAME, "tok-alice")
    pid, r1, r2 = ids["pid"], ids["run1"], ids["run2"]
    for url in (
        "/api/auth/me", "/api/projects", f"/api/projects/{pid}", f"/api/projects/{pid}/runs",
        f"/api/projects/{pid}/history", f"/api/runs/{r1}", "/api/stats", "/api/leaderboard",
        "/api/scenarios", "/api/scenarios/sce_a", f"/api/projects/{pid}/code-scans",
        f"/api/projects/{pid}/model", f"/api/projects/{pid}/compare?a={r1}&b={r2}",
        "/api/admin/overview", "/api/admin/users", "/api/meta",
        # new in this version, on old rows
        "/api/runs", f"/api/runs/{r1}/triage",
    ):
        assert client.get(url).status_code == 200, url
    assert client.post("/api/compare", json={"a": r1, "b": r2}).status_code == 200
    # Old runs have no fingerprint: triage falls back to the masked identity.
    tri = client.get(f"/api/runs/{r1}/triage").json()
    assert tri["identity"]["method"] == "masked value"
    assert tri["score"]["measured"]["risk_index"] == client.get(f"/api/runs/{r1}").json()["risk_index"]
    # B3: list carries run statistics
    listed = client.get("/api/projects").json()[0]
    assert listed["run_count"] == 2 and listed["last_run"]["id"] == r2
    # Reads did not alter a single pre-existing row.
    after = _snapshot(path)
    for table, rows in before["rows"].items():
        if table == "sessions":
            continue
        assert after["rows"][table] == rows, table


# ----------------------------------------------------------------------
# the tagged code itself (skipped when the tags are not in the checkout)
# ----------------------------------------------------------------------
def _tagged_store(tag: str) -> Any:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    try:
        src = subprocess.run(
            ["git", "show", f"{tag}:src/agentleak/core/store.py"],
            cwd=REPO, capture_output=True, text=True, check=True, timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pytest.skip(f"tag {tag} not available in this checkout")
    mod = types.ModuleType(f"agentleak.core._store_{tag.replace('.', '_')}")
    mod.__package__ = "agentleak.core"
    exec(compile(src, f"store.py@{tag}", "exec"), mod.__dict__)  # noqa: S102 - our own tagged source
    return mod.Store


@pytest.mark.parametrize("tag", ["v0.18.0", "v0.19.0"])
def test_upgrade_then_downgrade_with_tagged_store(tmp_path, tag) -> None:
    OldStore = _tagged_store(tag)
    path = str(tmp_path / f"{tag}.db")
    old = OldStore(path)
    user = old.create_user("alice@example.test", "alice-pass-123")
    other = old.create_user("bob@example.test", "bob-pass-12345")
    pid = old.create_project("Legacy", owner_id=user["id"])["id"]
    pid_b = old.create_project("Other", owner_id=other["id"])["id"]
    runs = [old.create_run(pid, _report(), label=f"r{i}")["id"] for i in range(3)]
    old.create_run(pid_b, _report())
    old.create_scenario("mine", _TRACE, owner_id=user["id"])
    token = old.create_session(user["id"])
    before = _snapshot(path)

    # upgrade: open with this version, use it, write triage
    client = TestClient(create_app(store=Store(path)))
    client.cookies.set(COOKIE_NAME, token)
    assert client.get(f"/api/runs/{runs[0]}").json()["report"] == old.get_run(runs[0])["report"]
    new_run = client.post(f"/api/projects/{pid}/runs", json={"trace": _TRACE}).json()["id"]
    fid = client.get(f"/api/runs/{new_run}").json()["report"]["findings"][0]["finding_id"]
    r = client.post(
        f"/api/runs/{new_run}/triage",
        json={"finding_ids": [fid], "state": "false_positive", "rationale": "synthetic test value"},
    )
    assert r.status_code == 200
    after = _snapshot(path)
    for table, rows in before["rows"].items():
        if table in ("runs", "usage_meter"):
            # the run stored through the API (and its meter row) are additions
            assert set(rows) <= set(after["rows"][table]), table
        elif table == "projects":
            # storing a run touches updated_at (column 6); nothing else moves
            strip = [tuple(v for i, v in enumerate(row) if i != 6) for row in rows]
            assert strip == [tuple(v for i, v in enumerate(row) if i != 6) for row in after["rows"][table]]
        else:
            assert after["rows"][table] == rows, table
    for key, sql in before["schema"].items():
        assert after["schema"][key] == sql, key

    # downgrade: the tagged code opens the database and works on it
    old2 = OldStore(path)
    assert {p["id"] for p in old2.list_projects(owner_id=user["id"])} == {pid}
    assert len(old2.list_runs(pid)) == 4
    assert old2.get_run(new_run)["report"]["findings"]
    assert old2.stats(owner_id=user["id"])["runs"] == 4
    assert old2.delete_run(new_run)
    c = sqlite3.connect(path)
    assert c.execute("SELECT COUNT(*) FROM finding_fingerprints WHERE run_id=?", (new_run,)).fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM finding_triage").fetchone()[0] == 1  # audit trail kept
    c.close()
    assert old2.delete_project(pid)
    c = sqlite3.connect(path)
    assert c.execute("SELECT COUNT(*) FROM finding_triage").fetchone()[0] == 0  # cascaded with the project
    assert c.execute("SELECT COUNT(*) FROM runs WHERE project_id=?", (pid_b,)).fetchone()[0] == 1
    c.close()
    # and this version opens it once more
    assert Store(path).get_project(pid_b)["run_count"] == 1
