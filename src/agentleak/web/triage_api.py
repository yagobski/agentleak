# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""GUI endpoints added in 0.20: finding triage, paged run listing, session probe.

Kept out of ``app.py`` so that file only gains one registration call and the
fingerprint hook after each stored run. Every route here authenticates with
the app's own ``require_user`` and resolves projects through its owner-scoped
helper: another account's run or project answers exactly like an unknown one.

Nothing here changes a measured result. Triage is stored beside a run; the
run's report, Risk Index, verdict and gate are returned untouched, and the
triaged score is a second figure that only this API's triage view returns.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Body, Cookie, Depends, Header, HTTPException, Query
from fastapi.responses import Response

from ..core import triage as tri
from ..core.store import RUN_SORT_COLUMNS, Store
from .auth import COOKIE_NAME, public_user

VERDICTS = ("Pass", "Conditional pass", "High risk", "Fail")
PAGE_MAX = 200
EXPORT_MAX = 10_000
OFFSET_MAX = 1_000_000
TRIAGE_BODY_MAX = 64 * 1024
PROJECT_DECISIONS_MAX = 50_000
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SOURCE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Printable text plus newline and tab; everything else is refused, not stripped.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_PUBLIC_DECISION_KEYS = (
    "id", "run_id", "finding_id", "state", "rationale", "expires_at", "expires_on",
    "reviewer_email", "created_at",
)


def _public_decision(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if not d:
        return None
    return {k: d.get(k) for k in _PUBLIC_DECISION_KEYS}


def record_fingerprints(db: Store, run: dict[str, Any], raw_findings: Any) -> None:
    """Store keyed fingerprints for a just-stored run's findings.

    Called with the analysis result's in-memory findings (which still hold the
    raw values); only HMACs are written. Never fails the run: without a key or
    on any error the run simply uses the masked identity for triage.
    """
    try:
        key, _origin = db.fingerprint_key()
        if key is None:
            return
        findings = (run.get("report") or {}).get("findings") or []
        db.set_finding_fingerprints(
            run["id"], tri.fingerprints_for(key, str(run["project_id"]), findings, raw_findings or [])
        )
    except Exception:  # noqa: BLE001 - fingerprints are an optimisation, never a failure
        return


def register_triage_routes(
    app: Any,
    *,
    db: Store,
    require_user: Callable[..., dict[str, Any]],
    owned_project: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> None:
    """Attach the routes. Must run before ``GET /api/runs/{rid}`` is registered."""

    def owned_run(rid: str, user: dict[str, Any]) -> dict[str, Any]:
        if not _ID_RE.match(rid or ""):
            raise HTTPException(status_code=404, detail="Run not found")
        run = db.get_run(rid)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        project = db.get_project(run["project_id"])
        if not project or project.get("owner_id") != user["id"]:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    # -- session probe (B5) ---------------------------------------------
    @app.get("/api/auth/session")
    def auth_session(token: str = Cookie(default="", alias=COOKIE_NAME)) -> dict[str, Any]:
        """Who is signed in, without a 401 when nobody is (the sign-in page asks)."""
        try:
            user = require_user(token)
        except HTTPException:
            return {"authenticated": False, "user": None}
        return {"authenticated": True, "user": public_user(user)}

    # -- paged run listing ------------------------------------------------
    def run_filters(
        user: dict[str, Any],
        project: str | None,
        verdict: str | None,
        gate: str | None,
        source: str | None,
        since: float | None,
        until: float | None,
        q: str | None,
        sort: str,
        direction: str,
    ) -> dict[str, Any]:
        if project:
            if not _ID_RE.match(project):
                raise HTTPException(status_code=404, detail="Project not found")
            owned_project(project, user)
        if verdict and verdict not in VERDICTS:
            raise HTTPException(status_code=400, detail=f"'verdict' must be one of: {', '.join(VERDICTS)}.")
        if gate and gate not in ("blocked", "passed"):
            raise HTTPException(status_code=400, detail="'gate' must be 'blocked' or 'passed'.")
        if source and not _SOURCE_RE.match(source):
            raise HTTPException(status_code=400, detail="'source' must be a source kind such as 'manual' or 'agent'.")
        for name, value in (("since", since), ("until", until)):
            if value is not None and not (0 <= value <= 4_102_444_800):  # 2100-01-01
                raise HTTPException(status_code=400, detail=f"'{name}' must be a Unix time in seconds.")
        if since is not None and until is not None and since >= until:
            raise HTTPException(status_code=400, detail="'since' must be before 'until'.")
        if sort not in RUN_SORT_COLUMNS:
            raise HTTPException(status_code=400, detail=f"'sort' must be one of: {', '.join(RUN_SORT_COLUMNS)}.")
        if direction not in ("asc", "desc"):
            raise HTTPException(status_code=400, detail="'dir' must be 'asc' or 'desc'.")
        return {
            "project_id": project or None, "verdict": verdict or None, "gate": gate or None,
            "source": source or None, "since": since, "until": until,
            "q": (q or "").strip() or None, "sort": sort, "direction": direction,
        }

    @app.get("/api/runs")
    def list_all_runs(
        project: str | None = Query(None, max_length=64),
        verdict: str | None = Query(None, max_length=32),
        gate: str | None = Query(None, max_length=16),
        source: str | None = Query(None, max_length=64),
        since: float | None = Query(None),
        until: float | None = Query(None),
        q: str | None = Query(None, max_length=200),
        sort: str = Query("created_at", max_length=32),
        dir: str = Query("desc", max_length=4),  # noqa: A002 - query parameter name
        limit: int = Query(50, ge=1, le=PAGE_MAX),
        offset: int = Query(0, ge=0, le=OFFSET_MAX),
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        """Every run the caller owns, across projects: filtered, sorted, paged."""
        f = run_filters(user, project, verdict, gate, source, since, until, q, sort, dir)
        items, total = db.query_runs(user["id"], **f, limit=limit, offset=offset)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "sort": f["sort"],
            "dir": f["direction"],
            "sources": db.run_source_kinds(user["id"]),
        }

    @app.get("/api/runs/export")
    def export_runs(
        format: str = Query("csv", max_length=4),  # noqa: A002 - query parameter name
        project: str | None = Query(None, max_length=64),
        verdict: str | None = Query(None, max_length=32),
        gate: str | None = Query(None, max_length=16),
        source: str | None = Query(None, max_length=64),
        since: float | None = Query(None),
        until: float | None = Query(None),
        q: str | None = Query(None, max_length=200),
        sort: str = Query("created_at", max_length=32),
        dir: str = Query("desc", max_length=4),  # noqa: A002
        user: dict[str, Any] = Depends(require_user),
    ) -> Response:
        """Every row matching the filter (not one page), up to EXPORT_MAX."""
        if format not in ("csv", "json"):
            raise HTTPException(status_code=400, detail="'format' must be 'csv' or 'json'.")
        f = run_filters(user, project, verdict, gate, source, since, until, q, sort, dir)
        items, total = db.query_runs(user["id"], **f, limit=EXPORT_MAX, offset=0)
        headers = {
            "X-Total-Count": str(total),
            "X-Exported-Count": str(len(items)),
            "Content-Disposition": f'attachment; filename="runs.{format}"',
            "Cache-Control": "no-store",
        }
        cols = ("run_id", "project", "agent", "label", "verdict", "risk_index", "privacy_score",
                "leaked_secrets", "gate", "source", "stored_at_utc")
        rows = [
            (
                r["id"], r.get("project_name", ""), r["agent_name"], r["label"], r["verdict"],
                r["risk_index"], r["privacy_score"], r["leaked_secrets"],
                "blocked" if r["blocked"] else "passed", r["source"],
                datetime.fromtimestamp(float(r["created_at"]), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            for r in items
        ]
        if format == "json":
            body = json.dumps(
                {"total": total, "exported": len(items), "rows": [dict(zip(cols, r, strict=True)) for r in rows]},
                ensure_ascii=False,
            )
            return Response(body, media_type="application/json", headers=headers)
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(cols)
        writer.writerows([[_csv_safe(v) for v in r] for r in rows])
        return Response(buf.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)

    # -- triage -----------------------------------------------------------
    def triage_view(run: dict[str, Any]) -> dict[str, Any]:
        report = run.get("report") or {}
        findings = report.get("findings") or []
        fps = db.finding_fingerprints(run["id"])
        decisions = db.list_triage_decisions(run["project_id"])
        resolved = tri.resolve(
            findings, fps, run_id=run["id"], run_created_at=float(run["created_at"]),
            decisions=decisions, now=time.time(),
        )
        live_runs = {r["id"] for r in db.list_runs(run["project_id"], limit=100_000)}
        items = []
        for r in resolved:
            d = r.to_dict()
            d["decision"] = _public_decision(r.decision)
            if d["carried_from"]:
                d["carried_from"]["run_exists"] = d["carried_from"]["run_id"] in live_runs
                d["carried_from"]["same_run"] = d["carried_from"]["run_id"] == run["id"]
            if r.expired and r.decision:
                d["expiry_note"] = f"Accepted risk expired on {r.decision.get('expires_on')}; review it again."
            items.append(d)
        key, origin = db.fingerprint_key()
        keyed = bool(findings) and all(fps.get(str(f.get("finding_id", ""))) for f in findings)
        return {
            "run_id": run["id"],
            "project_id": run["project_id"],
            "identity": {
                "method": "fingerprint" if keyed else "masked value",
                "detail": (
                    "Keyed HMAC of the value, scoped to the project, plus the channel."
                    if keyed else
                    "Channel, data type, level and masked value: this run was stored without fingerprints."
                ),
                "key": origin if key is not None else "unavailable",
            },
            "findings": items,
            "summary": tri.summarize(resolved),
            "score": tri.triaged_score(report, resolved, fps),
            "states": list(tri.STATES),
        }

    @app.get("/api/runs/{rid}/triage")
    def get_triage(rid: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        """Triage in force for each finding, the audit counts, and both scores."""
        return triage_view(owned_run(rid, user))

    @app.post("/api/runs/{rid}/triage")
    def post_triage(
        rid: str,
        payload: Any = Body(...),
        content_length: str | None = Header(default=None),
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        """Record one decision for one or more findings of a run (bulk)."""
        if content_length and content_length.isdigit() and int(content_length) > TRIAGE_BODY_MAX:
            raise HTTPException(status_code=413, detail=f"Triage request over {TRIAGE_BODY_MAX} bytes.")
        run = owned_run(rid, user)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        state = payload.get("state")
        if state not in tri.ALL_STATES:
            raise HTTPException(status_code=400, detail=f"'state' must be one of: {', '.join(tri.ALL_STATES)}.")
        ids = payload.get("finding_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            raise HTTPException(status_code=400, detail="'finding_ids' must be a non-empty list of strings.")
        if len(ids) > tri.MAX_FINDINGS_PER_DECISION:
            raise HTTPException(
                status_code=400, detail=f"At most {tri.MAX_FINDINGS_PER_DECISION} findings per decision."
            )
        if any(not _ID_RE.match(i) for i in ids):
            raise HTTPException(status_code=400, detail="A finding id has an invalid format.")
        rationale = payload.get("rationale", "")
        if rationale is None:
            rationale = ""
        if not isinstance(rationale, str):
            raise HTTPException(status_code=400, detail="'rationale' must be a string.")
        rationale = rationale.replace("\r\n", "\n").strip()
        if len(rationale) > tri.RATIONALE_MAX:
            raise HTTPException(status_code=400, detail=f"'rationale' is limited to {tri.RATIONALE_MAX} characters.")
        if _CONTROL_RE.search(rationale):
            raise HTTPException(status_code=400, detail="'rationale' contains control characters.")
        if state in tri.RATIONALE_REQUIRED and len(rationale) < 3:
            raise HTTPException(status_code=400, detail="A short rationale is required for this decision.")
        expires_at = _expiry(payload.get("expires_on"), state)

        report = run.get("report") or {}
        by_id = {str(f.get("finding_id", "")): f for f in report.get("findings") or []}
        unique = list(dict.fromkeys(ids))
        unknown = [i for i in unique if i not in by_id]
        if unknown:
            raise HTTPException(
                status_code=400, detail=f"{len(unknown)} finding id(s) are not findings of this run."
            )
        existing = len(db.list_triage_decisions(run["project_id"], limit=PROJECT_DECISIONS_MAX))
        if existing + len(unique) > PROJECT_DECISIONS_MAX:
            raise HTTPException(
                status_code=409, detail=f"This project holds the maximum of {PROJECT_DECISIONS_MAX} triage decisions."
            )
        fps = db.finding_fingerprints(run["id"])
        items = [
            (fid, tri.identity_key(by_id[fid], fps.get(fid)), tri.masked_key(by_id[fid])) for fid in unique
        ]
        db.add_triage_decisions(
            project_id=run["project_id"], run_id=run["id"], run_created_at=float(run["created_at"]),
            items=items, state=str(state), rationale=rationale, expires_at=expires_at,
            reviewer_id=user["id"], reviewer_email=str(user.get("email", "")),
        )
        return triage_view(run)

    @app.get("/api/runs/{rid}/triage/history")
    def triage_history(
        rid: str,
        finding_id: str = Query(..., max_length=64),
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        """The audit trail of one finding: every decision on its identity in the project."""
        run = owned_run(rid, user)
        findings = (run.get("report") or {}).get("findings") or []
        finding = next((f for f in findings if str(f.get("finding_id", "")) == finding_id), None)
        if finding is None:
            raise HTTPException(status_code=404, detail="Finding not found in this run")
        fps = db.finding_fingerprints(run["id"])
        decisions = db.list_triage_decisions(run["project_id"])
        in_force = tri.resolve(
            [finding], fps, run_id=run["id"], run_created_at=float(run["created_at"]),
            decisions=decisions, now=time.time(),
        )[0]
        live_runs = {r["id"] for r in db.list_runs(run["project_id"], limit=100_000)}
        rows = []
        for d in tri.history_for(finding, fps.get(finding_id), decisions, run_id=run["id"]):
            pub = _public_decision(d) or {}
            pub["in_force"] = bool(in_force.decision and in_force.decision.get("id") == d["id"])
            pub["run_exists"] = d["run_id"] in live_runs
            rows.append(pub)
        return {"run_id": run["id"], "finding_id": finding_id, "decisions": rows}


def _expiry(raw: Any, state: Any) -> float | None:
    """``expires_on`` (YYYY-MM-DD, UTC) → end of that day as epoch seconds."""
    if raw in (None, ""):
        return None
    if state != "accepted_risk":
        raise HTTPException(status_code=400, detail="'expires_on' applies to accepted risk only.")
    if not isinstance(raw, str) or not _DATE_RE.match(raw):
        raise HTTPException(status_code=400, detail="'expires_on' must be a date, YYYY-MM-DD.")
    try:
        day = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="'expires_on' is not a valid date.") from exc
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if day <= today:
        raise HTTPException(status_code=400, detail="'expires_on' must be after today (UTC).")
    if day > today + timedelta(days=tri.MAX_EXPIRY_DAYS):
        raise HTTPException(status_code=400, detail="'expires_on' is limited to three years ahead.")
    return (day + timedelta(days=1)).timestamp()


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formulas in text cells (same rule as the GUI export)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value
