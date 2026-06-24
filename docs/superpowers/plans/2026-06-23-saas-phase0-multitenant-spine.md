# SaaS Phase 0 — Multi-Tenant Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AgentLeak's per-user account model into a multi-tenant one — Organizations, Memberships, and role-based access control (RBAC) — so several organizations can share one instance with full data isolation.

**Architecture:** Add `organizations` and `memberships` tables to the existing SQLite `Store`. Every user gets a personal org on first use; projects, scenarios, and runs are authorized by **org membership + role**, not by `owner_id` alone. The active org is carried on the server-side session. Authorization moves into a single `require_member(min_role)` FastAPI dependency. The `Store` interface is unchanged in shape, so a later Postgres swap stays behind the same seam.

**Tech Stack:** Python 3.10+, FastAPI, SQLite (stdlib `sqlite3`), pytest + FastAPI `TestClient`, React/Vite + shadcn (frontend).

**Scope notes (decided during planning):**
- **Postgres is deferred.** Phase 0 ships on the current SQLite store; the migration is a separate infra task behind the same `Store` API.
- **Teams are deferred.** Org + roles is the isolation spine; teams (intra-org grouping) come once a team-scoped feature needs them.
- `owner_id` (resource creator) is **kept** for attribution; authorization switches to `org_id` + role.

**Role model:** `viewer < member < admin < owner`.
- `viewer` — read-only (GET endpoints).
- `member` — create/update/run/delete projects, scenarios, runs in the org.
- `admin` — everything `member` can, plus manage members (add/remove, change role up to `admin`).
- `owner` — everything, plus assign the `owner` role, remove admins, delete the org.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `agentleak/core/store.py` | Org/membership tables, role helpers, ownership backfill, session active-org | Modify |
| `agentleak/web/auth.py` | `ROLES`, `role_at_least`, `public_org`, `public_member` helpers | Modify |
| `agentleak/web/app.py` | `require_member` dependency, org + member endpoints, switch resource authz to org | Modify |
| `tests/test_store.py` | Store-level org/membership/role/backfill tests | Modify |
| `tests/test_orgs.py` | API-level org/member/RBAC/isolation tests | Create |
| `agentleak/web/frontend/src/lib/api.ts` | `Org`, `Member`, org API client methods | Modify |
| `agentleak/web/frontend/src/features/OrgSwitcher.tsx` | Sidebar org switcher | Create |
| `agentleak/web/frontend/src/pages/Members.tsx` | Org members settings page | Create |
| `agentleak/web/frontend/src/layout/AppShell.tsx` | Mount `OrgSwitcher` in sidebar header | Modify |

---

## Task 1: Org + membership schema and store methods

**Files:**
- Modify: `agentleak/core/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_store.py`:

```python
def test_create_org_makes_creator_owner(store: Store):
    user = store.create_user("a@x.io", "password123")
    org = store.create_org("Acme", owner_user_id=user["id"])
    assert org["id"].startswith("org_")
    assert org["name"] == "Acme"
    m = store.get_membership(org["id"], user["id"])
    assert m is not None and m["role"] == "owner"


def test_list_orgs_for_user_includes_role(store: Store):
    user = store.create_user("b@x.io", "password123")
    org = store.create_org("Beta", owner_user_id=user["id"])
    orgs = store.list_orgs_for_user(user["id"])
    assert [o["id"] for o in orgs] == [org["id"]]
    assert orgs[0]["role"] == "owner"


def test_add_and_update_and_remove_member(store: Store):
    owner = store.create_user("o@x.io", "password123")
    member = store.create_user("m@x.io", "password123")
    org = store.create_org("Gamma", owner_user_id=owner["id"])

    store.add_member(org["id"], member["id"], "member")
    assert store.get_membership(org["id"], member["id"])["role"] == "member"

    members = store.list_members(org["id"])
    emails = {m["email"] for m in members}
    assert emails == {"o@x.io", "m@x.io"}

    store.update_member_role(org["id"], member["id"], "admin")
    assert store.get_membership(org["id"], member["id"])["role"] == "admin"

    assert store.remove_member(org["id"], member["id"]) is True
    assert store.get_membership(org["id"], member["id"]) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_store.py -k "org or member" -v`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'create_org'`.

- [ ] **Step 3: Add the schema**

In `agentleak/core/store.py`, inside `Store._init`, immediately **before** the final `self._migrate(c)` call (currently at line 147), add the two tables:

```python
            c.execute(
                """CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at REAL NOT NULL
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS memberships (
                    org_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (org_id, user_id),
                    FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)")
```

- [ ] **Step 4: Add the role constant and store methods**

In `agentleak/core/store.py`, add a module-level constant after `SESSION_TTL` (line 66):

```python
# Org roles, ordered from least to most privileged.
ROLES = ("viewer", "member", "admin", "owner")
```

Then add these methods inside class `Store`, after `_user_row` (line 232), before the `# -- projects` section:

```python
    # -- organizations & memberships -----------------------------------
    def create_org(self, name: str, *, owner_user_id: str) -> dict[str, Any]:
        oid = _new_id("org")
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO organizations (id, name, created_at) VALUES (?,?,?)",
                (oid, name.strip() or "My organization", now),
            )
            c.execute(
                "INSERT INTO memberships (org_id, user_id, role, created_at) VALUES (?,?,?,?)",
                (oid, owner_user_id, "owner", now),
            )
        return self.get_org(oid)  # type: ignore[return-value]

    def get_org(self, oid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM organizations WHERE id=?", (oid,)).fetchone()
        return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]} if row else None

    def list_orgs_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT o.id, o.name, o.created_at, m.role FROM organizations o "
                "JOIN memberships m ON m.org_id = o.id WHERE m.user_id=? ORDER BY o.created_at",
                (user_id,),
            ).fetchall()
        return [{"id": r["id"], "name": r["name"], "created_at": r["created_at"], "role": r["role"]} for r in rows]

    def add_member(self, org_id: str, user_id: str, role: str = "member") -> dict[str, Any]:
        if role not in ROLES:
            role = "member"
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO memberships (org_id, user_id, role, created_at) VALUES (?,?,?,?)",
                (org_id, user_id, role, _now()),
            )
        return self.get_membership(org_id, user_id)  # type: ignore[return-value]

    def get_membership(self, org_id: str, user_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM memberships WHERE org_id=? AND user_id=?", (org_id, user_id)
            ).fetchone()
        return {"org_id": row["org_id"], "user_id": row["user_id"], "role": row["role"]} if row else None

    def list_members(self, org_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT u.id, u.email, u.name, m.role, m.created_at FROM memberships m "
                "JOIN users u ON u.id = m.user_id WHERE m.org_id=? ORDER BY m.created_at",
                (org_id,),
            ).fetchall()
        return [
            {"user_id": r["id"], "email": r["email"], "name": r["name"], "role": r["role"], "created_at": r["created_at"]}
            for r in rows
        ]

    def update_member_role(self, org_id: str, user_id: str, role: str) -> dict[str, Any] | None:
        if role not in ROLES:
            return None
        with self._conn() as c:
            cur = c.execute(
                "UPDATE memberships SET role=? WHERE org_id=? AND user_id=?", (role, org_id, user_id)
            )
            if cur.rowcount == 0:
                return None
        return self.get_membership(org_id, user_id)

    def remove_member(self, org_id: str, user_id: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM memberships WHERE org_id=? AND user_id=?", (org_id, user_id))
            return cur.rowcount > 0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_store.py -k "org or member" -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add agentleak/core/store.py tests/test_store.py
git commit -m "feat(store): organizations, memberships and role helpers"
```

---

## Task 2: Personal-org bootstrap and ownership backfill

**Files:**
- Modify: `agentleak/core/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_store.py`:

```python
def test_personal_org_is_created_once(store: Store):
    user = store.create_user("solo@x.io", "password123")
    org1 = store.personal_org_for(user["id"])
    org2 = store.personal_org_for(user["id"])
    assert org1["id"] == org2["id"]
    assert store.get_membership(org1["id"], user["id"])["role"] == "owner"


def test_backfill_assigns_org_to_legacy_resources(store: Store):
    user = store.create_user("legacy@x.io", "password123")
    # Simulate a pre-org project owned only by user.
    proj = store.create_project("Legacy", owner_id=user["id"])
    # Force the legacy state: blank org_id.
    with store._conn() as c:
        c.execute("UPDATE projects SET org_id='' WHERE id=?", (proj["id"],))
    store.backfill_orgs()
    refreshed = store.get_project(proj["id"])
    assert refreshed["org_id"]
    assert store.get_membership(refreshed["org_id"], user["id"]) is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_store.py -k "personal_org or backfill" -v`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'personal_org_for'`.

- [ ] **Step 3: Add `org_id` columns and backfill wiring**

In `agentleak/core/store.py`, extend `_migrate` (after the existing scenario/owner_id blocks, currently ending line 163) with:

```python
        # Org ownership of projects and scenarios (added in Phase 0 / SaaS).
        if "org_id" not in proj_cols:
            c.execute("ALTER TABLE projects ADD COLUMN org_id TEXT DEFAULT ''")
        if "org_id" not in sce_cols:
            c.execute("ALTER TABLE scenarios ADD COLUMN org_id TEXT DEFAULT ''")
        sess_cols = {r["name"] for r in c.execute("PRAGMA table_info(sessions)")}
        if "org_id" not in sess_cols:
            c.execute("ALTER TABLE sessions ADD COLUMN org_id TEXT DEFAULT ''")
```

Then in `_init`, change the final line from `self._migrate(c)` to:

```python
            self._migrate(c)
        self.backfill_orgs()
```

(Note: `backfill_orgs` opens its own connection, so it runs after the `with self._conn() as c` block closes.)

- [ ] **Step 4: Add the bootstrap and backfill methods**

In `agentleak/core/store.py`, add inside class `Store`, right after `remove_member`:

```python
    def personal_org_for(self, user_id: str) -> dict[str, Any]:
        """Return the user's first owned org, creating a personal one if none."""
        for org in self.list_orgs_for_user(user_id):
            if org["role"] == "owner":
                return {"id": org["id"], "name": org["name"], "created_at": org["created_at"]}
        user = self.get_user(user_id)
        label = (user or {}).get("name") or (user or {}).get("email", "My organization")
        return self.create_org(f"{label}'s org", owner_user_id=user_id)

    def backfill_orgs(self) -> None:
        """Give every user a personal org and assign org_id to legacy resources."""
        with self._conn() as c:
            user_ids = [r["id"] for r in c.execute("SELECT id FROM users").fetchall()]
        org_by_user: dict[str, str] = {}
        for uid in user_ids:
            org_by_user[uid] = self.personal_org_for(uid)["id"]
        with self._conn() as c:
            for table in ("projects", "scenarios"):
                rows = c.execute(
                    f"SELECT id, owner_id FROM {table} WHERE org_id IS NULL OR org_id=''"
                ).fetchall()
                for row in rows:
                    oid = org_by_user.get(row["owner_id"])
                    if oid:
                        c.execute(f"UPDATE {table} SET org_id=? WHERE id=?", (oid, row["id"]))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_store.py -k "personal_org or backfill" -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full store suite for regressions**

Run: `pytest tests/test_store.py -v`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add agentleak/core/store.py tests/test_store.py
git commit -m "feat(store): personal-org bootstrap and legacy ownership backfill"
```

---

## Task 3: Active org on the session

**Files:**
- Modify: `agentleak/core/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_store.py`:

```python
def test_session_carries_active_org(store: Store):
    user = store.create_user("sess@x.io", "password123")
    org = store.personal_org_for(user["id"])
    token = store.create_session(user["id"], org_id=org["id"])
    ctx = store.session_context(token)
    assert ctx["user"]["id"] == user["id"]
    assert ctx["org_id"] == org["id"]
    assert ctx["role"] == "owner"

    other = store.create_org("Other", owner_user_id=user["id"])
    store.set_session_org(token, other["id"])
    assert store.session_context(token)["org_id"] == other["id"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_store.py -k "active_org" -v`
Expected: FAIL — `create_session() got an unexpected keyword argument 'org_id'`.

- [ ] **Step 3: Update `create_session` to store the active org**

In `agentleak/core/store.py`, replace the existing `create_session` (lines 197-205) with:

```python
    def create_session(self, user_id: str, *, org_id: str = "") -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        if not org_id:
            org_id = self.personal_org_for(user_id)["id"]
        with self._conn() as c:
            c.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at, org_id) VALUES (?,?,?,?,?)",
                (token, user_id, now, now + SESSION_TTL, org_id),
            )
        return token
```

- [ ] **Step 4: Add `set_session_org` and `session_context`**

In `agentleak/core/store.py`, add after the existing `session_user` method (ends line 219):

```python
    def set_session_org(self, token: str, org_id: str) -> bool:
        with self._conn() as c:
            cur = c.execute("UPDATE sessions SET org_id=? WHERE token=?", (org_id, token))
            return cur.rowcount > 0

    def session_context(self, token: str) -> dict[str, Any] | None:
        """Resolve a session token to its user, active org id, and role."""
        if not token:
            return None
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
            if not row:
                return None
            if row["expires_at"] < _now():
                c.execute("DELETE FROM sessions WHERE token=?", (token,))
                return None
            user_row = c.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        if not user_row:
            return None
        user = self._user_row(user_row)
        org_id = row["org_id"] if "org_id" in row.keys() else ""
        if not org_id:
            org_id = self.personal_org_for(user["id"])["id"]
            self.set_session_org(token, org_id)
        membership = self.get_membership(org_id, user["id"])
        if membership is None:
            # Active org no longer accessible — fall back to the personal org.
            org_id = self.personal_org_for(user["id"])["id"]
            self.set_session_org(token, org_id)
            membership = self.get_membership(org_id, user["id"])
        return {"user": user, "org_id": org_id, "role": membership["role"] if membership else "viewer"}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_store.py -k "active_org" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agentleak/core/store.py tests/test_store.py
git commit -m "feat(store): carry active org and role on the session"
```

---

## Task 4: Auth helpers + `require_member` dependency + org endpoints

**Files:**
- Modify: `agentleak/web/auth.py`
- Modify: `agentleak/web/app.py`
- Test: `tests/test_orgs.py` (create)

- [ ] **Step 1: Add role + projection helpers to `auth.py`**

In `agentleak/web/auth.py`, add at the end of the file:

```python
# Org roles, ordered least → most privileged (mirrors store.ROLES).
ROLES = ("viewer", "member", "admin", "owner")
_ROLE_RANK = {r: i for i, r in enumerate(ROLES)}


def role_at_least(role: str, minimum: str) -> bool:
    """True when ``role`` is at least as privileged as ``minimum``."""
    return _ROLE_RANK.get(role, -1) >= _ROLE_RANK.get(minimum, len(ROLES))


def public_org(org: dict[str, Any], *, role: str | None = None) -> dict[str, Any]:
    out = {"id": org["id"], "name": org["name"], "created_at": org.get("created_at")}
    if role is not None:
        out["role"] = role
    return out


def public_member(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": member["user_id"],
        "email": member["email"],
        "name": member.get("name") or member["email"].split("@")[0],
        "role": member["role"],
        "created_at": member.get("created_at"),
    }
```

- [ ] **Step 2: Write the failing API tests**

Create `tests/test_orgs.py`:

```python
"""Org, membership and RBAC API behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentleak.web.app import create_app
from tests.conftest import authenticate


@pytest.fixture()
def client(tmp_path):
    from agentleak.core.store import Store

    app = create_app(store=Store(str(tmp_path / "api.db")))
    return TestClient(app)


def _signup(client, email):
    c = TestClient(client.app)
    authenticate(c, email=email, password="password123")
    return c


def test_new_user_has_a_personal_org(tmp_path):
    from agentleak.core.store import Store

    app = create_app(store=Store(str(tmp_path / "a.db")))
    c = TestClient(app)
    authenticate(c, email="solo@x.io", password="password123")
    orgs = c.get("/api/orgs").json()
    assert len(orgs) == 1
    assert orgs[0]["role"] == "owner"


def test_create_and_switch_org(tmp_path):
    from agentleak.core.store import Store

    app = create_app(store=Store(str(tmp_path / "b.db")))
    c = TestClient(app)
    authenticate(c, email="multi@x.io", password="password123")
    created = c.post("/api/orgs", json={"name": "Second"}).json()
    assert created["name"] == "Second"
    assert len(c.get("/api/orgs").json()) == 2

    assert c.post(f"/api/orgs/{created['id']}/switch").status_code == 200
    assert c.get("/api/auth/me").json()["org"]["id"] == created["id"]


def test_isolation_between_orgs(tmp_path):
    from agentleak.core.store import Store

    app = create_app(store=Store(str(tmp_path / "c.db")))
    c = TestClient(app)
    authenticate(c, email="iso@x.io", password="password123")
    # Project in the personal org.
    p = c.post("/api/projects", json={"name": "P1"}).json()
    # Switch to a new org — the project must not be visible.
    org2 = c.post("/api/orgs", json={"name": "Org2"}).json()
    c.post(f"/api/orgs/{org2['id']}/switch")
    assert c.get("/api/projects").json() == []
    assert c.get(f"/api/projects/{p['id']}").status_code == 404
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_orgs.py -v`
Expected: FAIL — `/api/orgs` returns 404 (route not defined).

- [ ] **Step 4: Replace `require_user` with an org-aware context dependency**

In `agentleak/web/app.py`, update the auth import block (lines 353-360) to also import the new helpers:

```python
    from .auth import (
        COOKIE_MAX_AGE,
        COOKIE_NAME,
        MIN_PASSWORD_LEN,
        normalize_email,
        public_member,
        public_org,
        public_user,
        role_at_least,
        valid_email,
    )
```

Then replace the `require_user` function (lines 370-375) with the context resolver plus a role-gated factory:

```python
    def require_ctx(token: str = Cookie(default="", alias=COOKIE_NAME)) -> dict[str, Any]:
        """Resolve {user, org_id, role} from the session cookie or raise 401."""
        ctx = db.session_context(token)
        if not ctx:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return ctx

    def require_user(ctx: dict[str, Any] = Depends(require_ctx)) -> dict[str, Any]:
        """Back-compat shim: hand existing routes the user dict."""
        return ctx["user"]

    def require_member(minimum: str):
        """Dependency factory: require the active-org role to be >= ``minimum``."""

        def _dep(ctx: dict[str, Any] = Depends(require_ctx)) -> dict[str, Any]:
            if not role_at_least(ctx["role"], minimum):
                raise HTTPException(status_code=403, detail=f"Requires {minimum} role")
            return ctx

        return _dep
```

- [ ] **Step 5: Make `/api/auth/me` and session creation org-aware**

In `agentleak/web/app.py`, replace `_session_response` (lines 377-384) with:

```python
    def _session_response(user: dict[str, Any]) -> Any:
        """JSON response for ``user`` that also plants a fresh session cookie."""
        org = db.personal_org_for(user["id"])
        resp = JSONResponse({**public_user(user), "org": public_org(org, role="owner")})
        resp.set_cookie(
            COOKIE_NAME, db.create_session(user["id"], org_id=org["id"]),
            max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", path="/",
        )
        return resp
```

Replace the `me` endpoint (lines 421-423) with:

```python
    @app.get("/api/auth/me")
    def me(ctx: dict[str, Any] = Depends(require_ctx)) -> dict[str, Any]:
        org = db.get_org(ctx["org_id"]) or {}
        return {**public_user(ctx["user"]), "org": public_org(org, role=ctx["role"])}
```

- [ ] **Step 6: Add the org endpoints**

In `agentleak/web/app.py`, add immediately after the `me` endpoint:

```python
    @app.get("/api/orgs")
    def list_orgs(ctx: dict[str, Any] = Depends(require_ctx)) -> list[dict[str, Any]]:
        return [
            public_org({"id": o["id"], "name": o["name"], "created_at": o["created_at"]}, role=o["role"])
            for o in db.list_orgs_for_user(ctx["user"]["id"])
        ]

    @app.post("/api/orgs")
    def create_org(payload: dict[str, Any] = Body(...), ctx: dict[str, Any] = Depends(require_ctx)) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="An organization name is required.")
        org = db.create_org(name, owner_user_id=ctx["user"]["id"])
        return public_org(org, role="owner")

    @app.post("/api/orgs/{org_id}/switch")
    def switch_org(org_id: str, token: str = Cookie(default="", alias=COOKIE_NAME),
                   ctx: dict[str, Any] = Depends(require_ctx)) -> dict[str, Any]:
        if db.get_membership(org_id, ctx["user"]["id"]) is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        db.set_session_org(token, org_id)
        org = db.get_org(org_id) or {}
        role = db.get_membership(org_id, ctx["user"]["id"])["role"]
        return public_org(org, role=role)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/test_orgs.py -v`
Expected: `test_new_user_has_a_personal_org`, `test_create_and_switch_org` PASS. `test_isolation_between_orgs` still FAILS (projects not yet org-scoped) — fixed in Task 6.

- [ ] **Step 8: Commit**

```bash
git add agentleak/web/auth.py agentleak/web/app.py tests/test_orgs.py
git commit -m "feat(api): org-aware session context, require_member, org endpoints"
```

---

## Task 5: Member-management endpoints with RBAC

**Files:**
- Modify: `agentleak/web/app.py`
- Test: `tests/test_orgs.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_orgs.py`:

```python
def test_admin_can_add_member_viewer_cannot(tmp_path):
    from agentleak.core.store import Store

    store = Store(str(tmp_path / "d.db"))
    app = create_app(store=store)
    owner = TestClient(app)
    authenticate(owner, email="owner@x.io", password="password123")
    org_id = owner.get("/api/orgs").json()[0]["id"]

    # A second user exists (registers their own personal org).
    invitee = TestClient(app)
    authenticate(invitee, email="invitee@x.io", password="password123")

    # Owner adds the invitee as a viewer.
    r = owner.post(f"/api/orgs/{org_id}/members", json={"email": "invitee@x.io", "role": "viewer"})
    assert r.status_code == 200
    members = owner.get(f"/api/orgs/{org_id}/members").json()
    assert {m["email"] for m in members} == {"owner@x.io", "invitee@x.io"}

    # Invitee switches into the org and is read-only.
    invitee.post(f"/api/orgs/{org_id}/switch")
    assert invitee.post("/api/projects", json={"name": "Nope"}).status_code == 403
    # Viewer cannot manage members.
    assert invitee.post(f"/api/orgs/{org_id}/members", json={"email": "x@x.io"}).status_code == 403


def test_only_owner_assigns_owner_role(tmp_path):
    from agentleak.core.store import Store

    app = create_app(store=Store(str(tmp_path / "e.db")))
    owner = TestClient(app)
    authenticate(owner, email="boss@x.io", password="password123")
    org_id = owner.get("/api/orgs").json()[0]["id"]

    admin = TestClient(app)
    authenticate(admin, email="admin@x.io", password="password123")
    owner.post(f"/api/orgs/{org_id}/members", json={"email": "admin@x.io", "role": "admin"})

    member = TestClient(app)
    authenticate(member, email="reg@x.io", password="password123")
    owner.post(f"/api/orgs/{org_id}/members", json={"email": "reg@x.io", "role": "member"})

    # Admin promotes member to admin — allowed.
    member_uid = next(m["user_id"] for m in owner.get(f"/api/orgs/{org_id}/members").json() if m["email"] == "reg@x.io")
    admin.post(f"/api/orgs/{org_id}/switch")
    assert admin.patch(f"/api/orgs/{org_id}/members/{member_uid}", json={"role": "admin"}).status_code == 200
    # Admin tries to grant owner — forbidden.
    assert admin.patch(f"/api/orgs/{org_id}/members/{member_uid}", json={"role": "owner"}).status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_orgs.py -k "member" -v`
Expected: FAIL — member routes return 404/405.

- [ ] **Step 3: Add the member-management endpoints**

In `agentleak/web/app.py`, add after the `switch_org` endpoint:

```python
    @app.get("/api/orgs/{org_id}/members")
    def list_org_members(org_id: str, ctx: dict[str, Any] = Depends(require_member("member"))) -> list[dict[str, Any]]:
        if ctx["org_id"] != org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        return [public_member(m) for m in db.list_members(org_id)]

    @app.post("/api/orgs/{org_id}/members")
    def add_org_member(org_id: str, payload: dict[str, Any] = Body(...),
                       ctx: dict[str, Any] = Depends(require_member("admin"))) -> dict[str, Any]:
        if ctx["org_id"] != org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        role = str(payload.get("role") or "member")
        if role == "owner" and ctx["role"] != "owner":
            raise HTTPException(status_code=403, detail="Only an owner can grant the owner role")
        target = db.get_user_by_email(normalize_email(payload.get("email")))
        if not target:
            raise HTTPException(status_code=404, detail="No user with that email")
        return public_member({**db.add_member(org_id, target["id"], role),
                              "email": target["email"], "name": target.get("name", ""),
                              "created_at": None})

    @app.patch("/api/orgs/{org_id}/members/{user_id}")
    def update_org_member(org_id: str, user_id: str, payload: dict[str, Any] = Body(...),
                          ctx: dict[str, Any] = Depends(require_member("admin"))) -> dict[str, Any]:
        if ctx["org_id"] != org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        role = str(payload.get("role") or "")
        if role == "owner" and ctx["role"] != "owner":
            raise HTTPException(status_code=403, detail="Only an owner can grant the owner role")
        updated = db.update_member_role(org_id, user_id, role)
        if not updated:
            raise HTTPException(status_code=404, detail="Member not found")
        u = db.get_user(user_id) or {}
        return public_member({**updated, "email": u.get("email", ""), "name": u.get("name", ""), "created_at": None})

    @app.delete("/api/orgs/{org_id}/members/{user_id}")
    def remove_org_member(org_id: str, user_id: str,
                          ctx: dict[str, Any] = Depends(require_member("admin"))) -> dict[str, bool]:
        if ctx["org_id"] != org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        if user_id == ctx["user"]["id"]:
            raise HTTPException(status_code=400, detail="Use leave-org to remove yourself")
        return {"deleted": db.remove_member(org_id, user_id)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_orgs.py -k "member" -v`
Expected: PASS (2 tests). `test_admin_can_add_member_viewer_cannot` asserts a 403 on `POST /api/projects` for a viewer — this passes only once Task 6 gates project creation with `require_member("member")`. **If it fails on that line, complete Task 6 then re-run.**

- [ ] **Step 5: Commit**

```bash
git add agentleak/web/app.py tests/test_orgs.py
git commit -m "feat(api): org member management with RBAC"
```

---

## Task 6: Switch resource authorization from user to org

**Files:**
- Modify: `agentleak/core/store.py` (org-scoped queries)
- Modify: `agentleak/web/app.py` (route authz + scoping)
- Test: `tests/test_orgs.py`, `tests/test_platform.py`

- [ ] **Step 1: Add org-scoped variants in the store**

In `agentleak/core/store.py`, change the `owner_id` filter parameters to also accept org scoping. Update `list_projects` (lines 256-264) to:

```python
    def list_projects(self, *, org_id: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as c:
            if org_id is not None:
                rows = c.execute(
                    "SELECT * FROM projects WHERE org_id=? ORDER BY updated_at DESC", (org_id,)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [self._project_row(r) for r in rows]
```

Update `create_project` signature (lines 235-243) to accept `org_id` and persist it. Replace the method body's INSERT (lines 248-253) so the column list includes `org_id`:

```python
    def create_project(
        self,
        name: str,
        *,
        agent_type: str = "generic",
        description: str = "",
        config: dict[str, Any] | None = None,
        owner_id: str = "",
        org_id: str = "",
    ) -> dict[str, Any]:
        pid = _new_id("proj")
        now = _now()
        if agent_type not in AGENT_TYPES:
            agent_type = "generic"
        with self._conn() as c:
            c.execute(
                "INSERT INTO projects (id, name, agent_type, description, config, owner_id, org_id, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (pid, name.strip() or "Untitled", agent_type, description, json.dumps(config or {}),
                 owner_id, org_id, now, now),
            )
        return self.get_project(pid)  # type: ignore[return-value]
```

Add `"org_id"` to `_project_row` (after the `owner_id` line, ~line 479):

```python
            "org_id": row["org_id"] if "org_id" in keys else "",
```

Mirror the same three changes for scenarios: `list_scenarios(*, org_id=None)` filtering on `org_id`, `create_scenario(..., org_id="")` persisting `org_id` (add it to the column list and values tuple), and `"org_id"` in `_scenario_row`. Also update `stats`, `scenario_exists`, and `count_pack_scenarios` to filter on `org_id` instead of `owner_id` (same query shape, swap the column name).

- [ ] **Step 2: Update the store tests that pass `owner_id` filters**

In `tests/test_store.py`, any test calling `list_projects(owner_id=...)`, `list_scenarios(owner_id=...)`, `stats(owner_id=...)`, `scenario_exists(..., owner_id=...)`, or `count_pack_scenarios(..., owner_id=...)` must switch to `org_id=...`. Update each call site to pass an org id created via `create_org`. Run `pytest tests/test_store.py -v` and fix any remaining `owner_id=` filter call.

- [ ] **Step 3: Switch the project/scenario/run routes to org scope + RBAC**

In `agentleak/web/app.py`:

Replace `_owned_project` (lines 386-391) with an org-scoped check that takes the context:

```python
    def _org_project(pid: str, ctx: dict[str, Any]) -> dict[str, Any]:
        """Fetch a project and ensure it belongs to the active org."""
        project = db.get_project(pid)
        if not project or project.get("org_id") != ctx["org_id"]:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
```

Then update the resource routes so reads require `viewer` and writes require `member`, scoping by `ctx["org_id"]`. Concretely:

- `GET /api/projects` (line 576-578):
```python
    @app.get("/api/projects")
    def list_projects(ctx: dict[str, Any] = Depends(require_member("viewer"))) -> list[dict[str, Any]]:
        return [_safe_project(p) for p in db.list_projects(org_id=ctx["org_id"])]  # type: ignore[misc]
```

- `POST /api/projects` (line 580-...): change the dependency to `ctx: dict[str, Any] = Depends(require_member("member"))`, and pass `owner_id=ctx["user"]["id"], org_id=ctx["org_id"]` to `db.create_project(...)`.

- `GET /api/projects/{pid}` (line 601-603): dependency `require_member("viewer")`; replace the body with `return _safe_project(_org_project(pid, ctx))`.

- `PATCH`/`DELETE /api/projects/{pid}` and all `/api/projects/{pid}/...` sub-routes (agents, runs, execute, model, connect, api-key): change the dependency to `require_member("member")` for writes / `require_member("viewer")` for reads, and replace every `_owned_project(pid, user)` call with `_org_project(pid, ctx)`. Where a handler previously used `user["id"]`, read `ctx["user"]["id"]`.

- `GET /api/scenarios` (line 435-439): dependency `require_member("viewer")`; `db.list_scenarios(org_id=ctx["org_id"])`.
- `POST /api/scenarios`, `DELETE /api/scenarios/{id}`, `POST /api/scenario-packs/{id}/import`: writes → `require_member("member")`, pass/scope `org_id=ctx["org_id"]`; ownership checks compare `stored.get("org_id") == ctx["org_id"]`.
- `GET /api/scenarios/{id}`, `GET /api/example/{id}`, `GET /api/scenario-packs`, `GET /api/stats`: reads → `require_member("viewer")`, scope by `ctx["org_id"]`.
- `GET /api/runs/{rid}` / `DELETE /api/runs/{rid}` (lines 915-923): resolve the run's project via `db.get_run`, then assert the project's `org_id == ctx["org_id"]` before returning; reads `viewer`, deletes `member`.
- `POST /api/analyze`, `/api/report/{fmt}`, `/api/render/{fmt}`, `/api/compare`: keep `require_member("member")` (they create/score). `/api/selftest` is API-key authed — leave it on `get_project_by_apikey` and set the run's `org_id` from the resolved project (`org_id=project.get("org_id", "")`).

- [ ] **Step 4: Run the full API + isolation suite**

Run: `pytest tests/test_orgs.py tests/test_platform.py tests/test_web.py -v`
Expected: PASS, including `test_isolation_between_orgs` and the viewer-403 assertion from Task 5.

- [ ] **Step 5: Run the entire suite + lint + types**

Run:
```bash
pytest -q
ruff check agentleak/ tests/
mypy agentleak/
```
Expected: all green; coverage gate (85%) holds.

- [ ] **Step 6: Commit**

```bash
git add agentleak/core/store.py agentleak/web/app.py tests/
git commit -m "feat: authorize projects, scenarios and runs by active org + role"
```

---

## Task 7: Frontend — org switcher and members page

**Files:**
- Modify: `agentleak/web/frontend/src/lib/api.ts`
- Create: `agentleak/web/frontend/src/features/OrgSwitcher.tsx`
- Create: `agentleak/web/frontend/src/pages/Members.tsx`
- Modify: `agentleak/web/frontend/src/layout/AppShell.tsx`

> Frontend is verified by build + manual/Playwright check (the repo has no FE unit tests). Keep components small and typed.

- [ ] **Step 1: Add org types and API methods**

In `agentleak/web/frontend/src/lib/api.ts`, add interfaces near `User` (line 340):

```typescript
export interface Org { id: string; name: string; created_at?: number; role: "viewer" | "member" | "admin" | "owner" }
export interface Member { user_id: string; email: string; name: string; role: Org["role"]; created_at?: number }
```

Extend the `User` interface with `org?: Org`. Add to the `api` object (after `logout`, line 405):

```typescript
  orgs: () => jsonFetch<Org[]>("/api/orgs"),
  createOrg: (name: string) =>
    jsonFetch<Org>("/api/orgs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }),
  switchOrg: (id: string) => jsonFetch<Org>(`/api/orgs/${id}/switch`, { method: "POST" }),
  members: (id: string) => jsonFetch<Member[]>(`/api/orgs/${id}/members`),
  addMember: (id: string, email: string, role: Org["role"]) =>
    jsonFetch<Member>(`/api/orgs/${id}/members`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, role }) }),
  updateMember: (id: string, uid: string, role: Org["role"]) =>
    jsonFetch<Member>(`/api/orgs/${id}/members/${uid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role }) }),
  removeMember: (id: string, uid: string) =>
    jsonFetch<{ deleted: boolean }>(`/api/orgs/${id}/members/${uid}`, { method: "DELETE" }),
```

- [ ] **Step 2: Create the org switcher**

Create `agentleak/web/frontend/src/features/OrgSwitcher.tsx`:

```tsx
import { useEffect, useState } from "react"
import { Building2, Check, ChevronsUpDown, Plus } from "lucide-react"
import { toast } from "sonner"
import { api, type Org } from "@/lib/api"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenuButton } from "@/components/ui/sidebar"

export function OrgSwitcher() {
  const [orgs, setOrgs] = useState<Org[]>([])
  const [active, setActive] = useState<Org | null>(null)

  function load() {
    api.orgs().then((list) => {
      setOrgs(list)
      api.me().then((u) => setActive(u.org ?? list[0] ?? null)).catch(() => setActive(list[0] ?? null))
    }).catch(() => {})
  }
  useEffect(load, [])

  async function pick(o: Org) {
    try {
      await api.switchOrg(o.id)
      window.location.reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function create() {
    const name = window.prompt("New organization name")?.trim()
    if (!name) return
    try {
      const o = await api.createOrg(name)
      await api.switchOrg(o.id)
      window.location.reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton size="lg">
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Building2 className="size-4" />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold">{active?.name ?? "Organization"}</span>
            <span className="truncate text-xs text-muted-foreground capitalize">{active?.role ?? ""}</span>
          </div>
          <ChevronsUpDown className="ml-auto size-4" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {orgs.map((o) => (
          <DropdownMenuItem key={o.id} onClick={() => pick(o)}>
            <span className="flex-1 truncate">{o.name}</span>
            {active?.id === o.id && <Check className="size-4" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={create}>
          <Plus className="size-4" /> New organization
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

(If `dropdown-menu` is not yet vendored under `src/components/ui/`, add it with the shadcn CLI: `npx shadcn@latest add dropdown-menu` from `agentleak/web/frontend`.)

- [ ] **Step 3: Mount the switcher in the sidebar header**

In `agentleak/web/frontend/src/layout/AppShell.tsx`, import it (`import { OrgSwitcher } from "@/features/OrgSwitcher"`) and render `<OrgSwitcher />` inside `SidebarHeader` directly **below** the existing AgentLeak logo `SidebarMenu` (after line 86, before `</SidebarHeader>`):

```tsx
        <SidebarMenu>
          <SidebarMenuItem>
            <OrgSwitcher />
          </SidebarMenuItem>
        </SidebarMenu>
```

- [ ] **Step 4: Create the members page**

Create `agentleak/web/frontend/src/pages/Members.tsx`:

```tsx
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { api, type Member, type Org } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { PageHeader } from "@/layout/AppShell"

const ROLES: Org["role"][] = ["viewer", "member", "admin", "owner"]

export function Members() {
  const [org, setOrg] = useState<Org | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<Org["role"]>("member")

  function refresh(orgId: string) {
    api.members(orgId).then(setMembers).catch((e) => toast.error(e.message))
  }
  useEffect(() => {
    api.me().then((u) => {
      if (u.org) { setOrg(u.org); refresh(u.org.id) }
    }).catch(() => {})
  }, [])

  const canManage = org && (org.role === "admin" || org.role === "owner")

  async function add() {
    if (!org || !email.trim()) return
    try {
      await api.addMember(org.id, email.trim(), role)
      setEmail("")
      refresh(org.id)
    } catch (e) { toast.error((e as Error).message) }
  }

  return (
    <div className="animate-fade-up">
      <PageHeader title="Members" description="People with access to this organization." />
      {canManage && (
        <Card className="mb-5 flex flex-wrap items-center gap-2 p-4">
          <Input className="flex-1" placeholder="teammate@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Select value={role} onValueChange={(v) => setRole(v as Org["role"])}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>)}</SelectContent>
          </Select>
          <Button onClick={add}>Add member</Button>
        </Card>
      )}
      <Card className="divide-y divide-border">
        {members.map((m) => (
          <div key={m.user_id} className="flex items-center justify-between gap-3 p-3.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{m.name}</p>
              <p className="truncate text-xs text-muted-foreground">{m.email}</p>
            </div>
            {canManage ? (
              <Select value={m.role} onValueChange={async (v) => {
                if (!org) return
                try { await api.updateMember(org.id, m.user_id, v as Org["role"]); refresh(org.id) }
                catch (e) { toast.error((e as Error).message) }
              }}>
                <SelectTrigger className="w-28 capitalize"><SelectValue /></SelectTrigger>
                <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>)}</SelectContent>
              </Select>
            ) : (
              <span className="text-xs capitalize text-muted-foreground">{m.role}</span>
            )}
          </div>
        ))}
      </Card>
    </div>
  )
}
```

- [ ] **Step 5: Add the route + nav entry**

In the router (search for where `Settings`/page routes are registered, e.g. `src/App.tsx` or wherever `Routes` live), add `<Route path="/members" element={<Members />} />` with `import { Members } from "@/pages/Members"`. In `AppShell.tsx`, add `{ to: "/members", label: "Members", icon: Users, end: false }` to the `NAV` array (import `Users` from `lucide-react`).

- [ ] **Step 6: Build the frontend**

Run:
```bash
cd agentleak/web/frontend && npm run build
```
Expected: build succeeds (this is the CI `frontend` job's check).

- [ ] **Step 7: Manual verification**

Start the app (`agentleak serve`), then: create a second org via the switcher → confirm the project list empties (isolation); add a teammate on the Members page; log in as that teammate, switch into the org, confirm a viewer sees data but gets a disabled/forbidden experience on writes.

- [ ] **Step 8: Commit**

```bash
git add agentleak/web/frontend/src
git commit -m "feat(ui): org switcher and members management page"
```

---

## Self-Review

**Spec coverage (Phase 0 exit: "two orgs can use the same instance with full data isolation"):**
- Orgs/memberships/roles → Tasks 1, 4, 5. ✓
- Tenant-scoping middleware (`require_member`) on the FastAPI app → Task 4. ✓
- Org switcher + team settings in the React shell → Task 7. ✓
- Data isolation between orgs → Task 6 + `test_isolation_between_orgs`. ✓
- Postgres / Teams → explicitly deferred (scope notes). ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. Task 6 Step 3 enumerates the route changes by exact endpoint and line; Task 7 Steps 5/6 reference router/build by concrete action. ✓

**Type consistency:** Role strings `viewer|member|admin|owner` consistent across store `ROLES`, auth `ROLES`/`role_at_least`, API payloads, and FE `Org["role"]`. Context dict shape `{user, org_id, role}` consistent across `session_context`, `require_ctx`, `require_member`, and all handlers. Store methods (`create_org`, `get_org`, `list_orgs_for_user`, `add_member`, `get_membership`, `list_members`, `update_member_role`, `remove_member`, `personal_org_for`, `backfill_orgs`, `create_session(org_id=)`, `set_session_org`, `session_context`) are referenced with matching signatures everywhere. ✓
```
