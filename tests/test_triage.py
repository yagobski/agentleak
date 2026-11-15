# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Finding triage, the triaged score view, paged run listing (synthetic data only)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from agentleak.core import triage as tri
from agentleak.core.store import Store

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.web import create_app  # noqa: E402

SSN = "123-45-6789"
_TRACE = {
    "run_id": "tri-trace",
    "agent_name": "tri-agent",
    "events": [
        {"channel": "tool_response", "content": {"patient": "Ada Quill", "ssn": SSN, "email": "ada@example.test"}},
        {"channel": "log", "content": f"Patient Ada Quill SSN {SSN}"},
        {"channel": "tool_call", "content": {"to": "crm", "email": "ada@example.test"}},
        {"channel": "final_output", "content": "Done."},
    ],
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.delenv(tri.KEY_ENV, raising=False)
    store = Store(str(tmp_path / "t.db"))
    app = create_app(store=store)
    alice, bob, anon = TestClient(app), TestClient(app), TestClient(app)
    alice.post("/api/auth/register", json={"email": "alice@example.test", "password": "alice-pass-123"})
    bob.post("/api/auth/register", json={"email": "bob@example.test", "password": "bob-pass-12345"})
    pid = alice.post("/api/projects", json={"name": "A"}).json()["id"]
    pid_b = bob.post("/api/projects", json={"name": "B"}).json()["id"]
    return {"store": store, "path": tmp_path / "t.db", "alice": alice, "bob": bob, "anon": anon,
            "pid": pid, "pid_b": pid_b}


def _run(client: TestClient, pid: str, **extra: Any) -> dict[str, Any]:
    r = client.post(f"/api/projects/{pid}/runs", json={"trace": _TRACE, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _decide(client: TestClient, rid: str, ids: list[str], state: str, rationale: str = "synthetic reason",
            **extra: Any):
    return client.post(f"/api/runs/{rid}/triage", json={"finding_ids": ids, "state": state,
                                                         "rationale": rationale, **extra})


# ----------------------------------------------------------------------
# fingerprints
# ----------------------------------------------------------------------
def test_fingerprints_are_keyed_and_no_raw_value_is_stored(env) -> None:
    run = _run(env["alice"], env["pid"])
    fps = env["store"].finding_fingerprints(run["id"])
    assert fps and set(fps) == {f["finding_id"] for f in run["report"]["findings"]}
    assert all(len(v) == 32 for v in fps.values())
    key_file = Path(env["path"]).parent / tri.KEY_FILE
    assert key_file.exists() and (key_file.stat().st_mode & 0o077) == 0
    _decide(env["alice"], run["id"], [run["report"]["findings"][0]["finding_id"]], "false_positive")
    blob = b"".join(p.read_bytes() for p in Path(env["path"]).parent.glob("t.db*"))
    assert SSN.encode() not in blob
    assert key_file.read_text().strip().encode() not in blob


def test_fingerprint_is_project_scoped_and_needs_the_key() -> None:
    k1, k2 = b"k" * 32, b"j" * 32
    a = tri.secret_fingerprint(k1, "proj_a", "ssn", SSN)
    assert a == tri.secret_fingerprint(k1, "proj_a", "ssn", SSN)
    assert a != tri.secret_fingerprint(k1, "proj_b", "ssn", SSN)
    assert a != tri.secret_fingerprint(k2, "proj_a", "ssn", SSN)
    assert a != tri.secret_fingerprint(k1, "proj_a", "ssn", "123-45-6780")


def test_key_from_environment_and_short_key_refused(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(tri.KEY_ENV, "x" * 40)
    key, origin = tri.load_fingerprint_key(str(tmp_path / "a.db"))
    assert key and origin == "environment" and not (tmp_path / tri.KEY_FILE).exists()
    monkeypatch.setenv(tri.KEY_ENV, "short")
    key, origin = tri.load_fingerprint_key(str(tmp_path / "a.db"))
    assert key is None and "shorter" in origin


def test_key_file_is_stable_across_restarts(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(tri.KEY_ENV, raising=False)
    k1, _ = tri.load_fingerprint_key(str(tmp_path / "a.db"))
    k2, _ = tri.load_fingerprint_key(str(tmp_path / "a.db"))
    assert k1 and k1 == k2


# ----------------------------------------------------------------------
# decisions, carry-over, expiry, audit trail
# ----------------------------------------------------------------------
def test_decision_carries_over_to_a_later_run_not_an_earlier_one(env) -> None:
    a = env["alice"]
    earlier = _run(a, env["pid"])
    time.sleep(0.01)
    first = _run(a, env["pid"])
    fid = first["report"]["findings"][0]["finding_id"]
    r = _decide(a, first["id"], [fid], "false_positive", "test fixture value, not a real SSN")
    assert r.status_code == 200
    item = next(x for x in r.json()["findings"] if x["finding_id"] == fid)
    assert item["state"] == "false_positive" and not item["carried"]
    assert item["decision"]["reviewer_email"] == "alice@example.test"
    assert "identity_key" not in item["decision"] and "masked_key" not in item["decision"]

    time.sleep(0.01)
    later = _run(a, env["pid"])
    view = a.get(f"/api/runs/{later['id']}/triage").json()
    assert view["identity"]["method"] == "fingerprint"
    carried = [x for x in view["findings"] if x["carried"]]
    assert len(carried) == 1 and carried[0]["state"] == "false_positive"
    assert carried[0]["carried_from"] == {
        "run_id": first["id"], "finding_id": fid, "run_exists": True, "same_run": False,
    }
    # earlier runs are not rewritten by a later decision
    assert a.get(f"/api/runs/{earlier['id']}/triage").json()["summary"]["triaged"] == 0
    # a direct decision on the later run wins over the carried one
    lfid = carried[0]["finding_id"]
    _decide(a, later["id"], [lfid], "true_positive", "")
    again = a.get(f"/api/runs/{later['id']}/triage").json()
    assert next(x for x in again["findings"] if x["finding_id"] == lfid)["state"] == "true_positive"
    hist = a.get(f"/api/runs/{later['id']}/triage/history", params={"finding_id": lfid}).json()
    assert [d["state"] for d in hist["decisions"]] == ["true_positive", "false_positive"]
    assert hist["decisions"][0]["in_force"] and not hist["decisions"][1]["in_force"]


def test_deleted_source_run_is_reported(env) -> None:
    a = env["alice"]
    first = _run(a, env["pid"])
    fid = first["report"]["findings"][0]["finding_id"]
    _decide(a, first["id"], [fid], "accepted_risk", "logged on purpose for the audit")
    time.sleep(0.01)
    later = _run(a, env["pid"])
    a.delete(f"/api/runs/{first['id']}")
    view = a.get(f"/api/runs/{later['id']}/triage").json()
    carried = [x for x in view["findings"] if x["carried"]]
    assert carried and carried[0]["carried_from"]["run_exists"] is False


def test_expired_accepted_risk_is_needs_review_and_says_why(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    f = run["report"]["findings"][0]
    fps = env["store"].finding_fingerprints(run["id"])
    env["store"].add_triage_decisions(
        project_id=env["pid"], run_id=run["id"], run_created_at=run["created_at"],
        items=[(f["finding_id"], tri.identity_key(f, fps.get(f["finding_id"])), tri.masked_key(f))],
        state="accepted_risk", rationale="accepted until the fix ships", expires_at=time.time() - 60,
        reviewer_id="x", reviewer_email="alice@example.test",
    )
    view = a.get(f"/api/runs/{run['id']}/triage").json()
    item = next(x for x in view["findings"] if x["finding_id"] == f["finding_id"])
    assert item["state"] == "accepted_risk" and item["effective_state"] == "needs_review"
    assert item["expired"] and "expired on" in item["expiry_note"]
    assert view["summary"]["needs_review"] == 1 and view["summary"]["expired"] == 1


def test_accepted_risk_with_future_expiry(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    fid = run["report"]["findings"][0]["finding_id"]
    day = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 30 * 86400))
    r = _decide(a, run["id"], [fid], "accepted_risk", "until the vendor fix", expires_on=day)
    assert r.status_code == 200
    item = next(x for x in r.json()["findings"] if x["finding_id"] == fid)
    assert item["effective_state"] == "accepted_risk" and item["decision"]["expires_on"] == day


def test_bulk_decision(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    ids = [f["finding_id"] for f in run["report"]["findings"]]
    assert len(ids) >= 2
    r = _decide(a, run["id"], ids, "needs_review", "check with the data owner")
    assert r.json()["summary"]["needs_review"] == len(ids)
    assert r.json()["summary"]["triaged"] == len(ids) == r.json()["summary"]["total"]


# ----------------------------------------------------------------------
# the measured score does not move; the triaged view is separate
# ----------------------------------------------------------------------
def test_measured_score_is_unchanged_and_triaged_view_is_labelled(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    before = a.get(f"/api/runs/{run['id']}").json()
    findings = run["report"]["findings"]
    ssn_ids = [f["finding_id"] for f in findings if "ssn" in f["data_type"].lower()]
    assert ssn_ids
    view = _decide(a, run["id"], ssn_ids, "false_positive", "fixture value").json()
    after = a.get(f"/api/runs/{run['id']}").json()
    assert after == before  # the stored run, its report, RI, verdict and gate are untouched
    projects = a.get(f"/api/projects/{env['pid']}/runs").json()
    assert projects[0]["risk_index"] == before["risk_index"]

    s = view["score"]
    assert s["measured"]["risk_index"] == before["risk_index"]
    assert s["measured"]["wsl"] == before["report"]["wsl"]
    t = s["triaged"]
    assert t["label"].startswith("excluding findings triaged as false positive")
    assert t["false_positive_findings"] == len(ssn_ids) and t["total_findings"] == len(findings)
    assert t["rho_s"] == before["report"]["rho_s"]  # denominator kept
    assert t["exact"] is True and t["changed"] is True
    assert t["wsl"] < s["measured"]["wsl"]
    assert t["risk_index"] == round(t["wsl"] / t["rho_s"], 4)
    assert t["privacy_score"] == max(0, round(100 * (1 - t["wsl"] / t["rho_s"])))
    assert t["leaked_secrets"] == before["leaked_secrets"] - t["excluded_secrets"]


def test_accepted_risk_still_counts_in_the_triaged_score(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    ids = [f["finding_id"] for f in run["report"]["findings"]]
    t = _decide(a, run["id"], ids, "accepted_risk", "known and tracked").json()["score"]["triaged"]
    assert t["changed"] is False and t["wsl"] == run["report"]["wsl"]


def test_secret_leaves_numerator_only_when_every_finding_is_false_positive() -> None:
    report = {
        "wsl": 4, "rho_s": 8, "risk_index": 0.5, "summary": {"leaked_secrets": 1},
        "agentrisk": {"weights": [1, 2, 3, 4]},
        "findings": [
            {"finding_id": "f1", "channel": "log", "data_type": "ssn", "level": 4, "redacted_value": "12*****89"},
            {"finding_id": "f2", "channel": "tool_call", "data_type": "ssn", "level": 4, "redacted_value": "12*****89"},
        ],
    }
    fps = {"f1": "a" * 32, "f2": "a" * 32}
    res = tri.resolve(report["findings"], fps, run_id="r", run_created_at=1.0,
                      decisions=[{"id": "d1", "run_id": "r", "finding_id": "f1", "state": "false_positive",
                                  "created_at": 2.0, "run_created_at": 1.0, "identity_key": "", "masked_key": ""}],
                      now=3.0)
    assert tri.triaged_score(report, res, fps)["triaged"]["wsl"] == 4  # f2 still leaks it
    res2 = tri.resolve(report["findings"], fps, run_id="r", run_created_at=1.0,
                       decisions=[{"id": f"d{i}", "run_id": "r", "finding_id": f, "state": "false_positive",
                                   "created_at": 2.0, "run_created_at": 1.0, "identity_key": "",
                                   "masked_key": ""} for i, f in enumerate(("f1", "f2"))], now=3.0)
    t = tri.triaged_score(report, res2, fps)["triaged"]
    assert t["wsl"] == 0 and t["risk_index"] == 0 and t["privacy_score"] == 100 and t["exact"]


def test_ci_facing_responses_are_unchanged(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    assert "triage" not in run and "triaged" not in run["report"]
    assert set(run) == set(a.get(f"/api/runs/{run['id']}").json())


# ----------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "body, status",
    [
        ({"finding_ids": ["F"], "state": "maybe"}, 400),
        ({"finding_ids": [], "state": "true_positive"}, 400),
        ({"finding_ids": "F", "state": "true_positive"}, 400),
        ({"finding_ids": [1], "state": "true_positive"}, 400),
        ({"finding_ids": ["x" * 65], "state": "true_positive"}, 400),
        ({"finding_ids": ["F"] * 501, "state": "true_positive"}, 400),
        ({"finding_ids": ["nope"], "state": "true_positive"}, 400),
        ({"finding_ids": ["F"], "state": "false_positive"}, 400),  # rationale required
        ({"finding_ids": ["F"], "state": "false_positive", "rationale": "ok"}, 400),  # too short
        ({"finding_ids": ["F"], "state": "false_positive", "rationale": "x" * 1001}, 400),
        ({"finding_ids": ["F"], "state": "false_positive", "rationale": "bell\x07here"}, 400),
        ({"finding_ids": ["F"], "state": "false_positive", "rationale": 12}, 400),
        ({"finding_ids": ["F"], "state": "true_positive", "expires_on": "2099-01-01"}, 400),
        ({"finding_ids": ["F"], "state": "accepted_risk", "rationale": "abc", "expires_on": "2020-01-01"}, 400),
        ({"finding_ids": ["F"], "state": "accepted_risk", "rationale": "abc", "expires_on": "2099-01-01"}, 400),
        ({"finding_ids": ["F"], "state": "accepted_risk", "rationale": "abc", "expires_on": "2026-02-30"}, 400),
        ({"finding_ids": ["F"], "state": "accepted_risk", "rationale": "abc", "expires_on": "tomorrow"}, 400),
        (["not", "an", "object"], 400),
    ],
)
def test_bad_triage_input_is_4xx(env, body, status) -> None:
    run = _run(env["alice"], env["pid"])
    fid = run["report"]["findings"][0]["finding_id"]
    if isinstance(body, dict):
        body = {**body, "finding_ids": [fid if i == "F" else i for i in body["finding_ids"]]} \
            if isinstance(body.get("finding_ids"), list) else body
    r = env["alice"].post(f"/api/runs/{run['id']}/triage", json=body)
    assert r.status_code == status, r.text


def test_oversized_triage_body_is_413(env) -> None:
    run = _run(env["alice"], env["pid"])
    r = env["alice"].post(
        f"/api/runs/{run['id']}/triage",
        content=b'{"finding_ids": ["a"], "state": "true_positive", "pad": "' + b"x" * 70_000 + b'"}',
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413


def test_rationale_is_stored_as_text(env) -> None:
    a = env["alice"]
    run = _run(a, env["pid"])
    fid = run["report"]["findings"][0]["finding_id"]
    note = '<img src=x onerror="alert(1)"> =HYPERLINK("x")'
    view = _decide(a, run["id"], [fid], "false_positive", note).json()
    assert next(x for x in view["findings"] if x["finding_id"] == fid)["decision"]["rationale"] == note


# ----------------------------------------------------------------------
# isolation and authentication
# ----------------------------------------------------------------------
def test_two_account_isolation(env) -> None:
    a, b = env["alice"], env["bob"]
    run = _run(a, env["pid"])
    rid, fid = run["id"], run["report"]["findings"][0]["finding_id"]
    _decide(a, rid, [fid], "false_positive", "alice's private note")
    _run(b, env["pid_b"])
    assert b.get(f"/api/runs/{rid}/triage").status_code == 404
    assert _decide(b, rid, [fid], "true_positive", "").status_code == 404
    assert b.get(f"/api/runs/{rid}/triage/history", params={"finding_id": fid}).status_code == 404
    assert b.get("/api/runs", params={"project": env["pid"]}).status_code == 404
    assert b.get("/api/runs/export", params={"project": env["pid"]}).status_code == 404
    listed = b.get("/api/runs").json()
    assert listed["total"] == 1 and all(r["project_id"] == env["pid_b"] for r in listed["items"])
    exported = b.get("/api/runs/export", params={"format": "csv"}).text
    assert rid not in exported and "alice" not in exported
    assert b.get("/api/runs", params={"q": rid}).json()["total"] == 0
    # alice's decision did not leak into bob's run, even for the same value
    bob_run = b.get("/api/runs").json()["items"][0]["id"]
    assert b.get(f"/api/runs/{bob_run}/triage").json()["summary"]["triaged"] == 0


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/api/runs"),
        ("get", "/api/runs/export"),
        ("get", "/api/runs/run_x/triage"),
        ("post", "/api/runs/run_x/triage"),
        ("get", "/api/runs/run_x/triage/history?finding_id=f"),
    ],
)
def test_anonymous_is_401(env, method, url) -> None:
    r = getattr(env["anon"], method)(url, **({"json": {}} if method == "post" else {}))
    assert r.status_code == 401


def test_session_probe(env) -> None:
    assert env["anon"].get("/api/auth/session").json() == {"authenticated": False, "user": None}
    me = env["alice"].get("/api/auth/session").json()
    assert me["authenticated"] and me["user"]["email"] == "alice@example.test"
    assert "password_hash" not in me["user"]


# ----------------------------------------------------------------------
# paged listing and export
# ----------------------------------------------------------------------
def test_paging_is_stable_and_complete(env) -> None:
    a = env["alice"]
    pid2 = a.post("/api/projects", json={"name": "Second"}).json()["id"]
    ids = {_run(a, env["pid"], label=f"r{i}")["id"] for i in range(5)}
    ids |= {_run(a, pid2, source="selftest")["id"] for _ in range(2)}
    seen: list[str] = []
    for offset in range(0, 9, 3):
        page = a.get("/api/runs", params={"limit": 3, "offset": offset, "sort": "risk_index"}).json()
        assert page["total"] == 7
        seen += [r["id"] for r in page["items"]]
    assert len(seen) == 7 and set(seen) == ids
    first = a.get("/api/runs", params={"limit": 50}).json()["items"]
    assert [r["created_at"] for r in first] == sorted((r["created_at"] for r in first), reverse=True)
    assert all(r["project_name"] in ("A", "Second") for r in first)
    assert a.get("/api/runs", params={"project": pid2}).json()["total"] == 2
    assert a.get("/api/runs", params={"source": "selftest"}).json()["total"] == 2
    assert set(a.get("/api/runs").json()["sources"]) == {"manual", "selftest"}
    assert a.get("/api/runs", params={"q": "r3"}).json()["total"] == 1
    assert a.get("/api/runs", params={"q": "%"}).json()["total"] == 0  # LIKE wildcards are literal
    verdict = first[0]["verdict"]
    assert a.get("/api/runs", params={"verdict": verdict}).json()["total"] == 7
    now = time.time()
    assert a.get("/api/runs", params={"since": now - 3600, "until": now + 60}).json()["total"] == 7
    assert a.get("/api/runs", params={"since": now + 60}).json()["total"] == 0


@pytest.mark.parametrize(
    "params, status",
    [
        ({"limit": 0}, 422), ({"limit": 201}, 422), ({"offset": -1}, 422), ({"limit": "x"}, 422),
        ({"verdict": "Safe"}, 400), ({"gate": "maybe"}, 400), ({"source": "a b"}, 400),
        ({"sort": "report"}, 400), ({"dir": "up"}, 400), ({"since": -5}, 400),
        ({"since": 10, "until": 5}, 400), ({"q": "x" * 201}, 422), ({"project": "../etc"}, 404),
    ],
)
def test_bad_listing_input_is_4xx(env, params, status) -> None:
    assert env["alice"].get("/api/runs", params=params).status_code == status


def test_export_honours_filter_and_neutralises_formulas(env) -> None:
    a = env["alice"]
    _run(a, env["pid"], label="=cmd|' /C calc'!A0")
    _run(a, env["pid"], label="plain")
    r = a.get("/api/runs/export", params={"format": "csv", "q": "cmd"})
    assert r.status_code == 200 and r.headers["x-total-count"] == "1" and r.headers["x-exported-count"] == "1"
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("run_id,project,agent,label,verdict") and len(lines) == 2
    assert ",'=cmd" in lines[1]
    j = a.get("/api/runs/export", params={"format": "json"}).json()
    assert j["total"] == 2 and len(j["rows"]) == 2 and j["rows"][0]["gate"] in ("blocked", "passed")
    assert a.get("/api/runs/export", params={"format": "xml"}).status_code == 400


# ----------------------------------------------------------------------
# backend issues from round one
# ----------------------------------------------------------------------
def test_b7_gate_sent_with_a_run_is_applied(env) -> None:
    run = _run(env["alice"], env["pid"], privacy_policy={"forbid_channels": ["log"]})
    assert run["report"]["privacy_policy"]["enabled"] is True and run["blocked"] is True


def test_b7_project_gate_is_not_replaced(env) -> None:
    a = env["alice"]
    a.patch(f"/api/projects/{env['pid']}", json={"config": {"privacy_policy": {"forbid_channels": ["log"]}}})
    run = _run(a, env["pid"], privacy_policy={"max_findings": 1000})
    assert run["report"]["privacy_policy"]["enabled"] is True and run["blocked"] is True


def test_b6_index_is_reread_after_a_rebuild(tmp_path, monkeypatch) -> None:
    from agentleak.web import app as app_module

    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    index = static / "index.html"
    index.write_text("<html><head><title>x</title></head><body>build-one</body></html>")
    monkeypatch.setattr(app_module, "_STATIC_DIR", static)
    client = TestClient(app_module.create_app(store=Store(str(tmp_path / "s.db")), serve_ui=True))
    assert "build-one" in client.get("/app/").text
    index.write_text("<html><head><title>x</title></head><body>build-two</body></html>")
    import os

    st = index.stat()
    os.utime(index, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert "build-two" in client.get("/app/runs").text
