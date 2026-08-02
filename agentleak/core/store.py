"""Local persistence for the AgentLeak platform — projects and runs.

Backed by SQLite (stdlib, no extra dependency), stored under a local data
directory (``$AGENTLEAK_HOME`` or ``~/.agentleak``). Everything stays on the
user's machine, consistent with the product's local-only guarantee.

A *project* represents an agent under test (its detector config, vault scope,
and agent type for SDK wiring). A *run* is one stored analysis of that agent.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from ..integrations.registry import framework_ids

# Valid agent frameworks come from the pluggable registry (extensible).
AGENT_TYPES = framework_ids()


def data_dir() -> Path:
    raw = os.environ.get("AGENTLEAK_HOME") or os.path.join(Path.home(), ".agentleak")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# -- password hashing (stdlib PBKDF2, no extra dependency) --------------
_PBKDF2_ROUNDS = 240_000


def hash_password(password: str, *, salt: str | None = None) -> str:
    """Return a ``salt$hash`` string using PBKDF2-HMAC-SHA256."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against a stored ``salt$hash``."""
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt=salt), stored)


# Session lifetime (30 days) — sessions live in the local DB only.
SESSION_TTL = 30 * 24 * 3600


class Store:
    """Thread-safe-enough SQLite store (one connection per call)."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or str(data_dir() / "agentleak.db")
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    agent_type TEXT NOT NULL DEFAULT 'generic',
                    description TEXT DEFAULT '',
                    config TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    source TEXT DEFAULT 'manual',
                    agent_name TEXT DEFAULT '',
                    risk_index REAL DEFAULT 0,
                    privacy_score INTEGER DEFAULT 0,
                    verdict TEXT DEFAULT '',
                    blocked INTEGER DEFAULT 0,
                    leaked INTEGER DEFAULT 0,
                    label TEXT DEFAULT '',
                    report TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id, created_at)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS scenarios (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL DEFAULT 'custom',
                    description TEXT DEFAULT '',
                    sensitive_data TEXT NOT NULL DEFAULT '[]',
                    tags TEXT NOT NULL DEFAULT '[]',
                    difficulty TEXT DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'custom',
                    pack_id TEXT DEFAULT '',
                    origin_id TEXT DEFAULT '',
                    trace TEXT NOT NULL,
                    created_at REAL NOT NULL
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_pack ON scenarios(pack_id, origin_id)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS code_scans (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'files',
                    source_ref TEXT DEFAULT '',
                    score INTEGER DEFAULT 0,
                    verdict TEXT DEFAULT '',
                    findings_count INTEGER DEFAULT 0,
                    result TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_code_scans_project ON code_scans(project_id, created_at)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_email TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    target_id TEXT DEFAULT '',
                    target_email TEXT DEFAULT '',
                    detail TEXT DEFAULT ''
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS api_usage (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    project_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_project ON api_usage(project_id, created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage(created_at)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS usage_meter (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    owner_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL
                )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_usage_meter_owner ON usage_meter(owner_id, created_at)")
            c.execute(
                """CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (user_id, key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
            self._migrate(c)

    @staticmethod
    def _migrate(c: sqlite3.Connection) -> None:
        """Additive schema migrations for DBs created by earlier versions."""
        cols = {r["name"] for r in c.execute("PRAGMA table_info(scenarios)")}
        if "spec" not in cols:
            c.execute("ALTER TABLE scenarios ADD COLUMN spec TEXT DEFAULT ''")
        # Per-user ownership of projects and scenarios (added in 0.7).
        proj_cols = {r["name"] for r in c.execute("PRAGMA table_info(projects)")}
        if "owner_id" not in proj_cols:
            c.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT DEFAULT ''")
        sce_cols = {r["name"] for r in c.execute("PRAGMA table_info(scenarios)")}
        if "owner_id" not in sce_cols:
            c.execute("ALTER TABLE scenarios ADD COLUMN owner_id TEXT DEFAULT ''")
        # Ground-truth canaries carried by imported packs (added in 0.10):
        # without them a semantic-leak scenario would score a false Pass.
        if "canaries" not in sce_cols:
            c.execute("ALTER TABLE scenarios ADD COLUMN canaries TEXT DEFAULT ''")
        # Run history columns (added in 0.8).
        run_cols = {r["name"] for r in c.execute("PRAGMA table_info(runs)")}
        if "privacy_score" not in run_cols:
            c.execute("ALTER TABLE runs ADD COLUMN privacy_score INTEGER DEFAULT 0")
        if "label" not in run_cols:
            c.execute("ALTER TABLE runs ADD COLUMN label TEXT DEFAULT ''")
        # Agent card (A2A-style identity + code source) — added in 0.9.
        if "agent_card" not in proj_cols:
            c.execute("ALTER TABLE projects ADD COLUMN agent_card TEXT DEFAULT ''")
        # Admin console: roles + account state (added in 0.10).
        user_cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        if "is_admin" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            # Existing single-user installs: promote the first account so the
            # admin console is reachable after upgrading.
            first = c.execute("SELECT id FROM users ORDER BY created_at LIMIT 1").fetchone()
            if first:
                c.execute("UPDATE users SET is_admin=1 WHERE id=?", (first["id"],))
        if "disabled" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN disabled INTEGER DEFAULT 0")

    # -- users & sessions ----------------------------------------------
    def create_user(self, email: str, password: str, *, name: str = "") -> dict[str, Any]:
        uid = _new_id("usr")
        with self._conn() as c:
            # The very first account owns the deployment — it gets the admin
            # role so the console is always reachable without manual SQL.
            is_admin = int(c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"] == 0)
            c.execute(
                "INSERT INTO users (id, email, name, password_hash, created_at, is_admin) VALUES (?,?,?,?,?,?)",
                (uid, email.strip().lower(), name.strip(), hash_password(password), _now(), is_admin),
            )
        return self.get_user(uid)  # type: ignore[return-value]

    def get_user(self, uid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return self._user_row(row) if row else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        return self._user_row(row) if row else None

    def verify_user(self, email: str, password: str) -> dict[str, Any] | None:
        """Return the user dict when the email/password pair is valid.

        Disabled accounts never authenticate, even with a correct password.
        """
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return None
        user = self._user_row(row)
        if user.get("disabled"):
            return None
        return user

    def count_users(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"])

    def update_user_profile(self, uid: str, *, name: str | None = None) -> dict[str, Any] | None:
        """Self-service profile update (display name only \u2014 email is the login key)."""
        if name is None:
            return self.get_user(uid)
        with self._conn() as c:
            cur = c.execute("UPDATE users SET name=? WHERE id=?", (name.strip(), uid))
            if cur.rowcount == 0:
                return None
        return self.get_user(uid)

    def change_password(self, uid: str, current_password: str, new_password: str) -> bool:
        """Change a user's own password after verifying the current one.

        Returns False (no changes made) if the current password is wrong or
        the account doesn't exist. Revokes every other session so a leaked
        old session token stops working immediately.
        """
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not row or not verify_password(current_password, row["password_hash"]):
                return False
            c.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (hash_password(new_password), uid),
            )
            c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        return True

    def reset_password(self, email: str, new_password: str) -> bool:
        """Operator-side password reset, by email, with no current password.

        AgentLeak is local-first and ships no mail infrastructure, so there is
        no emailed reset link. Recovery instead belongs to whoever owns the
        database: a self-hoster on their own machine, or the operator of a
        hosted instance over SSH (see ``agentleak admin reset-password``).
        Every session is revoked, so a stolen token dies with the reset.

        Returns False when no account has that email.
        """
        normalized = str(email or "").strip().lower()
        with self._conn() as c:
            row = c.execute("SELECT id FROM users WHERE email=?", (normalized,)).fetchone()
            if not row:
                return False
            c.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (hash_password(new_password), row["id"]),
            )
            c.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
        return True

    def delete_own_account(self, uid: str, password: str) -> bool:
        """Self-service account deletion, gated by a password re-check."""
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return False
        return self.delete_user(uid)

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                (token, user_id, now, now + SESSION_TTL),
            )
        return token

    def session_user(self, token: str) -> dict[str, Any] | None:
        """Resolve an active session token to its user (None if expired/unknown).

        Disabling an account revokes access immediately — existing sessions
        stop resolving without waiting for expiry.
        """
        if not token:
            return None
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
            if not row:
                return None
            if row["expires_at"] < _now():
                c.execute("DELETE FROM sessions WHERE token=?", (token,))
                return None
            user = c.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        if not user:
            return None
        resolved = self._user_row(user)
        return None if resolved.get("disabled") else resolved

    def delete_session(self, token: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))

    @staticmethod
    def _user_row(row: sqlite3.Row) -> dict[str, Any]:
        keys = row.keys()
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "created_at": row["created_at"],
            "is_admin": bool(row["is_admin"]) if "is_admin" in keys else False,
            "disabled": bool(row["disabled"]) if "disabled" in keys else False,
        }

    # -- admin console ---------------------------------------------------
    def list_users(self) -> list[dict[str, Any]]:
        """All accounts with per-user project/run counts (admin console)."""
        with self._conn() as c:
            rows = c.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
            users = [self._user_row(r) for r in rows]
            for user in users:
                agg = c.execute(
                    "SELECT COUNT(*) n FROM projects WHERE owner_id=?", (user["id"],)
                ).fetchone()
                runs = c.execute(
                    "SELECT COUNT(*) n FROM runs WHERE project_id IN"
                    " (SELECT id FROM projects WHERE owner_id=?)",
                    (user["id"],),
                ).fetchone()
                user["project_count"] = agg["n"] or 0
                user["run_count"] = runs["n"] or 0
        return users

    def set_user_flags(
        self, uid: str, *, is_admin: bool | None = None, disabled: bool | None = None
    ) -> dict[str, Any] | None:
        """Update the admin/disabled flags. Disabling also revokes sessions."""
        sets: list[str] = []
        vals: list[Any] = []
        if is_admin is not None:
            sets.append("is_admin=?")
            vals.append(int(is_admin))
        if disabled is not None:
            sets.append("disabled=?")
            vals.append(int(disabled))
        if not sets:
            return self.get_user(uid)
        vals.append(uid)
        with self._conn() as c:
            cur = c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)
            if cur.rowcount == 0:
                return None
            if disabled:
                c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        return self.get_user(uid)

    def delete_user(self, uid: str) -> bool:
        """Delete an account and everything it owns (projects cascade runs)."""
        with self._conn() as c:
            c.execute("DELETE FROM projects WHERE owner_id=?", (uid,))
            c.execute("DELETE FROM scenarios WHERE owner_id=?", (uid,))
            c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
            return c.execute("DELETE FROM users WHERE id=?", (uid,)).rowcount > 0

    def count_admins(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) n FROM users WHERE is_admin=1").fetchone()["n"])

    def admin_overview(self) -> dict[str, Any]:
        """Platform-wide stats for the admin console (all users)."""
        since_24h = _now() - 86400
        with self._conn() as c:
            users = c.execute(
                "SELECT COUNT(*) n, SUM(disabled) d, SUM(is_admin) a FROM users"
            ).fetchone()
            projects = int(c.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"])
            runs = c.execute(
                "SELECT COUNT(*) n, AVG(risk_index) ri, AVG(privacy_score) ps, "
                "SUM(blocked) b, MAX(created_at) last_at FROM runs"
            ).fetchone()
            runs_24h = c.execute(
                "SELECT COUNT(*) n, SUM(blocked) b FROM runs WHERE created_at >= ?",
                (since_24h,),
            ).fetchone()
            verdict_rows = c.execute(
                "SELECT verdict, COUNT(*) n FROM runs GROUP BY verdict"
            ).fetchall()
            scans = int(c.execute("SELECT COUNT(*) n FROM code_scans").fetchone()["n"])
            scans_24h = int(c.execute(
                "SELECT COUNT(*) n FROM code_scans WHERE created_at >= ?", (since_24h,)
            ).fetchone()["n"])
            api_total = int(c.execute("SELECT COUNT(*) n FROM api_usage").fetchone()["n"])
            api_24h = int(
                c.execute(
                    "SELECT COUNT(*) n FROM api_usage WHERE created_at >= ?", (since_24h,)
                ).fetchone()["n"]
            )
            active_projects_24h = int(c.execute(
                """
                SELECT COUNT(DISTINCT project_id) n FROM (
                    SELECT project_id FROM runs WHERE created_at >= ?
                    UNION
                    SELECT project_id FROM api_usage WHERE created_at >= ?
                    UNION
                    SELECT project_id FROM code_scans WHERE created_at >= ?
                )
                """,
                (since_24h, since_24h, since_24h),
            ).fetchone()["n"])
            redteam_runs = int(c.execute(
                "SELECT COUNT(*) n FROM runs WHERE source LIKE 'redteam%'"
            ).fetchone()["n"])
            recent = c.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT 15"
            ).fetchall()
        return {
            "users": int(users["n"] or 0),
            "disabled_users": int(users["d"] or 0),
            "admins": int(users["a"] or 0),
            "projects": projects,
            "runs": int(runs["n"] or 0),
            "avg_risk_index": round(runs["ri"], 4) if runs["ri"] is not None else None,
            "avg_privacy_score": round(runs["ps"], 1) if runs["ps"] is not None else None,
            "blocked_runs": int(runs["b"] or 0),
            "runs_24h": int(runs_24h["n"] or 0),
            "blocked_24h": int(runs_24h["b"] or 0),
            "active_projects_24h": active_projects_24h,
            "last_activity_at": runs["last_at"],
            "verdict_counts": {str(r["verdict"] or "unknown"): int(r["n"] or 0) for r in verdict_rows},
            "redteam_runs": redteam_runs,
            "code_scans": scans,
            "code_scans_24h": scans_24h,
            "api_calls_total": api_total,
            "api_calls_24h": api_24h,
            "recent_runs": [self._run_summary(r) for r in recent],
        }

    # -- agent API usage (monitoring / "consumption") --------------------
    def record_api_usage(self, project_id: str, endpoint: str) -> None:
        """Log one autonomous-agent API call for admin-console monitoring.

        Every hit to an agent-facing endpoint (register/code/selftest/
        improve/status) is recorded here so admins can see how much (and how)
        agents are actually using the platform, distinct from human UI runs.
        """
        with self._conn() as c:
            c.execute(
                "INSERT INTO api_usage (id, created_at, project_id, endpoint) VALUES (?,?,?,?)",
                (_new_id("usage"), _now(), project_id, endpoint),
            )

    # -- quota metering & account settings ------------------------------
    def meter_usage(self, owner_id: str, endpoint: str) -> None:
        """Record one metered action for an account (free-tier quota)."""
        owner = owner_id.strip()
        if not owner:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO usage_meter (id, created_at, owner_id, endpoint) VALUES (?,?,?,?)",
                (_new_id("meter"), _now(), owner, endpoint),
            )

    def owner_usage_since(self, owner_id: str, since_ts: float) -> int:
        """Count metered actions for ``owner_id`` since ``since_ts`` (epoch)."""
        owner = owner_id.strip()
        if not owner:
            return 0
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) n FROM usage_meter WHERE owner_id=? AND created_at>=?",
                (owner, since_ts),
            ).fetchone()
        return int((row["n"] if row else 0) or 0)

    def set_user_setting(self, user_id: str, key: str, value: str) -> None:
        """Upsert one per-user setting."""
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO user_settings (user_id, key, value, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(user_id, key)
                DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (user_id, key, value, _now()),
            )

    def get_user_setting(self, user_id: str, key: str) -> str:
        """Read one per-user setting; returns an empty string when absent."""
        with self._conn() as c:
            row = c.execute(
                "SELECT value FROM user_settings WHERE user_id=? AND key=?",
                (user_id, key),
            ).fetchone()
        return str(row["value"]) if row else ""

    def delete_user_settings(self, user_id: str, *keys: str) -> None:
        """Delete selected per-user settings (or all settings when no key is passed)."""
        with self._conn() as c:
            if keys:
                placeholders = ",".join("?" for _ in keys)
                c.execute(
                    f"DELETE FROM user_settings WHERE user_id=? AND key IN ({placeholders})",
                    [user_id, *keys],
                )
            else:
                c.execute("DELETE FROM user_settings WHERE user_id=?", (user_id,))

    def leaderboard(self, *, owner_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Rank projects by their latest run (lower risk index ranks higher)."""
        owner_filter = ""
        params: list[Any] = []
        if owner_id is not None:
            owner_filter = "WHERE p.owner_id=?"
            params.append(owner_id)
        params.append(limit)

        with self._conn() as c:
            rows = c.execute(
                f"""
                SELECT
                    p.id AS project_id,
                    p.name AS name,
                    lr.risk_index AS risk_index,
                    lr.privacy_score AS privacy_score,
                    lr.verdict AS verdict,
                    lr.created_at AS last_run_at,
                    (SELECT COUNT(*) FROM runs r2 WHERE r2.project_id = p.id) AS runs,
                    (SELECT SUM(r3.leaked) FROM runs r3 WHERE r3.project_id = p.id) AS leaked_secrets
                FROM projects p
                JOIN runs lr ON lr.id = (
                    SELECT r.id FROM runs r
                    WHERE r.project_id = p.id
                    ORDER BY r.created_at DESC
                    LIMIT 1
                )
                {owner_filter}
                ORDER BY lr.risk_index ASC, lr.privacy_score DESC, lr.created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        entries: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            entries.append(
                {
                    "project_id": row["project_id"],
                    "name": row["name"],
                    "rank": idx,
                    "risk_index": float(row["risk_index"] or 0.0),
                    "privacy_score": int(row["privacy_score"] or 0),
                    "verdict": row["verdict"] or "",
                    "leaked_secrets": int(row["leaked_secrets"] or 0),
                    "runs": int(row["runs"] or 0),
                    "last_run_at": row["last_run_at"],
                }
            )
        return entries

    def admin_projects_usage(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Per-project monitoring for the admin console: runs executed, agent
        API calls ("consumption"), code scans, results, and recency.

        Ordered by how active a project is (runs, then API calls) so the
        busiest agents surface first.
        """
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT
                    p.id, p.name, p.owner_id, u.email AS owner_email,
                    (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) AS run_count,
                    (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id AND r.blocked = 1) AS blocked_runs,
                    (SELECT AVG(r.risk_index) FROM runs r WHERE r.project_id = p.id) AS avg_ri,
                    (SELECT AVG(r.privacy_score) FROM runs r WHERE r.project_id = p.id) AS avg_score,
                    (SELECT MAX(r.created_at) FROM runs r WHERE r.project_id = p.id) AS last_run_at,
                    (SELECT COUNT(*) FROM code_scans s WHERE s.project_id = p.id) AS scan_count,
                    (SELECT COUNT(*) FROM api_usage a WHERE a.project_id = p.id) AS api_call_count,
                    (SELECT MAX(a.created_at) FROM api_usage a WHERE a.project_id = p.id) AS last_api_call_at
                FROM projects p
                LEFT JOIN users u ON u.id = p.owner_id
                ORDER BY run_count DESC, api_call_count DESC, p.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "owner_email": r["owner_email"] or "",
                "run_count": r["run_count"] or 0,
                "blocked_runs": r["blocked_runs"] or 0,
                "avg_risk_index": round(r["avg_ri"], 4) if r["avg_ri"] is not None else None,
                "avg_privacy_score": round(r["avg_score"], 1) if r["avg_score"] is not None else None,
                "last_run_at": r["last_run_at"],
                "scan_count": r["scan_count"] or 0,
                "api_call_count": r["api_call_count"] or 0,
                "last_api_call_at": r["last_api_call_at"],
            }
            for r in rows
        ]

    def admin_daily_usage(self, *, days: int = 14) -> list[dict[str, Any]]:
        """Daily run/API-call counts for the last ``days`` days (oldest first).

        Powers a simple activity sparkline in the admin console.
        """
        cutoff = _now() - days * 86400
        with self._conn() as c:
            run_rows = c.execute(
                "SELECT date(created_at, 'unixepoch') d, COUNT(*) n, SUM(blocked) blocked FROM runs"
                " WHERE created_at >= ? GROUP BY d",
                (cutoff,),
            ).fetchall()
            api_rows = c.execute(
                "SELECT date(created_at, 'unixepoch') d, COUNT(*) n FROM api_usage"
                " WHERE created_at >= ? GROUP BY d",
                (cutoff,),
            ).fetchall()
            scan_rows = c.execute(
                "SELECT date(created_at, 'unixepoch') d, COUNT(*) n FROM code_scans"
                " WHERE created_at >= ? GROUP BY d",
                (cutoff,),
            ).fetchall()
        runs_by_day = {r["d"]: r["n"] for r in run_rows}
        blocked_by_day = {r["d"]: r["blocked"] or 0 for r in run_rows}
        api_by_day = {r["d"]: r["n"] for r in api_rows}
        scans_by_day = {r["d"]: r["n"] for r in scan_rows}
        out = []
        for i in range(days - 1, -1, -1):
            d = time.strftime("%Y-%m-%d", time.gmtime(_now() - i * 86400))
            out.append({
                "date": d,
                "runs": runs_by_day.get(d, 0),
                "blocked_runs": blocked_by_day.get(d, 0),
                "api_calls": api_by_day.get(d, 0),
                "code_scans": scans_by_day.get(d, 0),
            })
        return out

    def admin_endpoint_usage(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Most-used autonomous-agent endpoints with recency for operations."""
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT endpoint, COUNT(*) n, MAX(created_at) last_at,
                       COUNT(DISTINCT project_id) projects
                FROM api_usage
                GROUP BY endpoint
                ORDER BY n DESC, last_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "endpoint": row["endpoint"],
                "count": int(row["n"] or 0),
                "projects": int(row["projects"] or 0),
                "last_called_at": row["last_at"],
            }
            for row in rows
        ]

    # -- audit log --------------------------------------------------------
    def log_admin_action(
        self,
        actor: dict[str, Any],
        action: str,
        *,
        target: dict[str, Any] | None = None,
        detail: str = "",
    ) -> None:
        """Append an immutable audit-trail entry for an admin action."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit_log"
                " (id, created_at, actor_id, actor_email, action, target_id, target_email, detail)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    _new_id("audit"), _now(),
                    actor["id"], actor.get("email", ""),
                    action,
                    (target or {}).get("id", ""), (target or {}).get("email", ""),
                    detail,
                ),
            )

    def list_audit_log(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "actor_id": r["actor_id"],
                "actor_email": r["actor_email"],
                "action": r["action"],
                "target_id": r["target_id"],
                "target_email": r["target_email"],
                "detail": r["detail"],
            }
            for r in rows
        ]

    # -- projects -------------------------------------------------------
    def create_project(
        self,
        name: str,
        *,
        agent_type: str = "generic",
        description: str = "",
        config: dict[str, Any] | None = None,
        owner_id: str = "",
    ) -> dict[str, Any]:
        pid = _new_id("proj")
        now = _now()
        if agent_type not in AGENT_TYPES:
            agent_type = "generic"
        with self._conn() as c:
            c.execute(
                "INSERT INTO projects (id, name, agent_type, description, config, owner_id, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (pid, name.strip() or "Untitled", agent_type, description, json.dumps(config or {}), owner_id, now, now),
            )
        return self.get_project(pid)  # type: ignore[return-value]

    def list_projects(self, *, owner_id: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as c:
            if owner_id is not None:
                rows = c.execute(
                    "SELECT * FROM projects WHERE owner_id=? ORDER BY updated_at DESC", (owner_id,)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [self._project_row(r) for r in rows]

    def get_project(self, pid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
            if not row:
                return None
            project = self._project_row(row)
            agg = c.execute(
                "SELECT COUNT(*) n, AVG(risk_index) avg_ri FROM runs WHERE project_id=?", (pid,)
            ).fetchone()
            last = c.execute(
                "SELECT * FROM runs WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (pid,)
            ).fetchone()
        project["run_count"] = agg["n"] or 0
        project["avg_risk_index"] = round(agg["avg_ri"], 4) if agg["avg_ri"] is not None else None
        project["last_run"] = self._run_summary(last) if last else None
        return project

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT id FROM projects WHERE name=? ORDER BY created_at LIMIT 1", (name,)).fetchone()
        return self.get_project(row["id"]) if row else None

    def get_project_by_apikey(self, api_key: str) -> dict[str, Any] | None:
        """Find a project by its self-test API key (stored in project config JSON).

        Returns ``None`` when the owning account has been disabled by an
        admin — disabling a user immediately cuts off its agents' API-key
        access too, not just its interactive browser session.
        """
        if not api_key or not api_key.startswith("ak_"):
            return None
        with self._conn() as c:
            # Scan is acceptable for typical project counts (<10 000).
            rows = c.execute("SELECT * FROM projects").fetchall()
            match: dict[str, Any] | None = None
            for row in rows:
                p = self._project_row(row)
                stored = (p.get("config") or {}).get("selftest_api_key")
                # Constant-time compare to avoid leaking the key via response timing.
                if isinstance(stored, str) and hmac.compare_digest(stored, api_key):
                    match = p
            if match and match.get("owner_id"):
                owner = c.execute(
                    "SELECT disabled FROM users WHERE id=?", (match["owner_id"],)
                ).fetchone()
                if owner and owner["disabled"]:
                    return None
        return match

    def update_project(self, pid: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"name", "agent_type", "description", "config"}
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            sets.append(f"{k}=?")
            vals.append(json.dumps(v) if k == "config" else v)
        if not sets:
            return self.get_project(pid)
        sets.append("updated_at=?")
        vals.append(_now())
        vals.append(pid)
        with self._conn() as c:
            cur = c.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", vals)
            if cur.rowcount == 0:
                return None
        return self.get_project(pid)

    def delete_project(self, pid: str) -> bool:
        with self._conn() as c:
            # ON DELETE CASCADE in the schema handles run/scenario cleanup.
            cur = c.execute("DELETE FROM projects WHERE id=?", (pid,))
            return cur.rowcount > 0

    def touch_project(self, pid: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE projects SET updated_at=? WHERE id=?", (_now(), pid))

    # -- agent cards ----------------------------------------------------
    def set_agent_card(self, pid: str, card: dict[str, Any] | None) -> dict[str, Any] | None:
        """Attach (or clear, with ``None``) the project's agent card."""
        with self._conn() as c:
            cur = c.execute(
                "UPDATE projects SET agent_card=?, updated_at=? WHERE id=?",
                (json.dumps(card) if card else "", _now(), pid),
            )
            if cur.rowcount == 0:
                return None
        return self.get_project(pid)

    # -- code scans -----------------------------------------------------
    def create_code_scan(self, project_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Persist a static code-scan result for a project."""
        sid = _new_id("scan")
        summary = result.get("summary", {})
        with self._conn() as c:
            c.execute(
                "INSERT INTO code_scans"
                " (id, project_id, created_at, source_type, source_ref, score, verdict, findings_count, result)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    sid, project_id, _now(),
                    str(result.get("source_type", "files")),
                    str(result.get("source_ref", "")),
                    int(result.get("score", 0)),
                    str(result.get("verdict", "")),
                    int(summary.get("total_findings", 0)),
                    json.dumps(result),
                ),
            )
        self.touch_project(project_id)
        return self.get_code_scan(sid)  # type: ignore[return-value]

    def get_code_scan(self, sid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM code_scans WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        scan = self._code_scan_summary(row)
        scan["result"] = json.loads(row["result"])
        return scan

    def list_code_scans(self, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM code_scans WHERE project_id=? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._code_scan_summary(r) for r in rows]

    def latest_code_scan(self, project_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM code_scans WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._code_scan_summary(row) if row else None

    def delete_code_scan(self, sid: str) -> bool:
        with self._conn() as c:
            return c.execute("DELETE FROM code_scans WHERE id=?", (sid,)).rowcount > 0

    # -- runs -----------------------------------------------------------
    def create_run(
        self,
        project_id: str,
        report: dict[str, Any],
        *,
        source: str = "manual",
        label: str = "",
    ) -> dict[str, Any]:
        rid = _new_id("run")
        now = _now()
        summary = report.get("summary", {})
        with self._conn() as c:
            c.execute(
                "INSERT INTO runs"
                " (id, project_id, created_at, source, agent_name, risk_index,"
                "  privacy_score, verdict, blocked, leaked, label, report)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid, project_id, now, source,
                    report.get("agent_name", ""),
                    float(report.get("risk_index", 0)),
                    int(report.get("privacy_score", 0)),
                    report.get("verdict", ""),
                    1 if report.get("blocked") else 0,
                    int(summary.get("leaked_secrets", 0)),
                    label.strip(),
                    json.dumps(report),
                ),
            )
        self.touch_project(project_id)
        return self.get_run(rid)  # type: ignore[return-value]

    def list_runs(self, project_id: str | None = None, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._conn() as c:
            if project_id:
                rows = c.execute(
                    "SELECT * FROM runs WHERE project_id=? ORDER BY created_at DESC LIMIT ?", (project_id, limit)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._run_summary(r) for r in rows]

    def get_run(self, rid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        if not row:
            return None
        summary = self._run_summary(row)
        summary["report"] = json.loads(row["report"])
        return summary

    def delete_run(self, rid: str) -> bool:
        with self._conn() as c:
            return c.execute("DELETE FROM runs WHERE id=?", (rid,)).rowcount > 0

    # -- run history & progression ------------------------------------
    def run_history(self, project_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Ordered run history for a project, oldest-first, with per-run deltas.

        Each entry is a run summary augmented with:
        - ``delta_score``   — privacy_score change vs the previous run (None for the first)
        - ``delta_ri``      — risk_index change vs the previous run (None for the first)
        - ``rank``          — 1-based position (1 = first run ever)
        """
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM runs WHERE project_id=? ORDER BY created_at ASC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        entries = []
        prev: dict[str, Any] | None = None
        for i, row in enumerate(rows):
            entry = self._run_summary(row)
            entry["rank"] = i + 1
            if prev is not None:
                entry["delta_score"] = entry["privacy_score"] - prev["privacy_score"]
                entry["delta_ri"] = round(entry["risk_index"] - prev["risk_index"], 4)
            else:
                entry["delta_score"] = None
                entry["delta_ri"] = None
            entries.append(entry)
            prev = entry
        return entries

    def compare_runs(self, run_id_a: str, run_id_b: str) -> dict[str, Any] | None:
        """Side-by-side comparison of two runs.

        Returns a dict with ``run_a``, ``run_b``, and ``diff`` (metric deltas,
        positive = B improved over A).  Returns ``None`` if either run is missing.
        """
        a = self.get_run(run_id_a)
        b = self.get_run(run_id_b)
        if a is None or b is None:
            return None

        def _channel_risk(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
            return {
                ch["channel"]: {"max_level": ch.get("max_level", 0), "findings": ch.get("findings", 0)}
                for ch in report.get("channel_risk", [])
            }

        def _framework_status(report: dict[str, Any]) -> dict[str, str]:
            return {
                fw["id"]: fw["status"]
                for fw in (report.get("compliance", {}).get("frameworks") or [])
            }

        rep_a = a.get("report", {})
        rep_b = b.get("report", {})

        diff = {
            "delta_score": b["privacy_score"] - a["privacy_score"],
            "delta_ri": round(b["risk_index"] - a["risk_index"], 4),
            "delta_findings": (rep_b.get("summary", {}).get("total_findings", 0)
                               - rep_a.get("summary", {}).get("total_findings", 0)),
            "delta_leaked": b["leaked_secrets"] - a["leaked_secrets"],
            "blocked_resolved": a["blocked"] and not b["blocked"],
            "score_direction": (
                "improved" if b["privacy_score"] > a["privacy_score"]
                else "regressed" if b["privacy_score"] < a["privacy_score"]
                else "unchanged"
            ),
        }

        # Per-framework compliance changes
        fw_a = _framework_status(rep_a)
        fw_b = _framework_status(rep_b)
        all_fws = sorted(set(fw_a) | set(fw_b))
        framework_diff = []
        for fw in all_fws:
            sa, sb = fw_a.get(fw, "unknown"), fw_b.get(fw, "unknown")
            change = "same"
            if sa != sb:
                change = "fixed" if sb == "compliant" else "regressed"
            framework_diff.append({"id": fw, "before": sa, "after": sb, "change": change})
        diff["frameworks"] = framework_diff

        return {"run_a": a, "run_b": b, "diff": diff}

    def best_run(self, project_id: str) -> dict[str, Any] | None:
        """Return the run with the highest privacy_score for a project."""
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM runs WHERE project_id=? ORDER BY privacy_score DESC, created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if not row:
            return None
        summary = self._run_summary(row)
        summary["report"] = json.loads(row["report"])
        return summary

    # -- scenarios ------------------------------------------------------
    def create_scenario(
        self,
        name: str,
        trace: dict[str, Any],
        *,
        domain: str = "custom",
        description: str = "",
        sensitive_data: list[str] | None = None,
        tags: list[str] | None = None,
        difficulty: str = "",
        source: str = "custom",
        pack_id: str = "",
        origin_id: str = "",
        spec: dict[str, Any] | None = None,
        canaries: dict[str, Any] | None = None,
        owner_id: str = "",
    ) -> dict[str, Any]:
        sid = _new_id("sce")
        with self._conn() as c:
            c.execute(
                "INSERT INTO scenarios (id, name, domain, description, sensitive_data, tags,"
                " difficulty, source, pack_id, origin_id, trace, spec, canaries, owner_id,"
                " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sid, name.strip() or "Untitled scenario", domain, description,
                    json.dumps(sensitive_data or []), json.dumps(tags or []),
                    difficulty, source, pack_id, origin_id, json.dumps(trace),
                    json.dumps(spec) if spec else "",
                    json.dumps(canaries) if canaries else "", owner_id, _now(),
                ),
            )
        return self.get_scenario(sid)  # type: ignore[return-value]

    def list_scenarios(self, *, owner_id: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as c:
            if owner_id is not None:
                rows = c.execute(
                    "SELECT * FROM scenarios WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM scenarios ORDER BY created_at DESC").fetchall()
        return [self._scenario_row(r, with_trace=False) for r in rows]

    def get_scenario(self, sid: str, *, with_trace: bool = True) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone()
        return self._scenario_row(row, with_trace=with_trace) if row else None

    def delete_scenario(self, sid: str) -> bool:
        with self._conn() as c:
            return c.execute("DELETE FROM scenarios WHERE id=?", (sid,)).rowcount > 0

    def scenario_exists(self, pack_id: str, origin_id: str, *, owner_id: str = "") -> bool:
        """True if a scenario from this pack/origin was already imported by the owner."""
        if not origin_id:
            return False
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM scenarios WHERE pack_id=? AND origin_id=? AND owner_id=? LIMIT 1",
                (pack_id, origin_id, owner_id),
            ).fetchone()
        return row is not None

    def count_pack_scenarios(self, pack_id: str, *, owner_id: str = "") -> int:
        """How many scenarios from a given pack are currently imported by the owner."""
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) n FROM scenarios WHERE pack_id=? AND owner_id=?", (pack_id, owner_id)
            ).fetchone()
        return int(row["n"] or 0)

    # -- stats ----------------------------------------------------------
    def stats(self, *, owner_id: str | None = None) -> dict[str, Any]:
        with self._conn() as c:
            if owner_id is not None:
                p = c.execute("SELECT COUNT(*) n FROM projects WHERE owner_id=?", (owner_id,)).fetchone()["n"]
                r = c.execute(
                    "SELECT COUNT(*) n, AVG(risk_index) avg, SUM(blocked) blocked,"
                    " AVG(privacy_score) avg_score FROM runs"
                    " WHERE project_id IN (SELECT id FROM projects WHERE owner_id=?)", (owner_id,)
                ).fetchone()
                recent = c.execute(
                    "SELECT * FROM runs WHERE project_id IN (SELECT id FROM projects WHERE owner_id=?)"
                    " ORDER BY created_at DESC LIMIT 8", (owner_id,)
                ).fetchall()
            else:
                p = c.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"]
                r = c.execute(
                    "SELECT COUNT(*) n, AVG(risk_index) avg, SUM(blocked) blocked,"
                    " AVG(privacy_score) avg_score FROM runs"
                ).fetchone()
                recent = c.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 8").fetchall()
        return {
            "projects": p,
            "runs": r["n"] or 0,
            "avg_risk_index": round(r["avg"], 4) if r["avg"] is not None else None,
            "avg_privacy_score": round(r["avg_score"], 1) if r["avg_score"] is not None else None,
            "blocked_runs": r["blocked"] or 0,
            "recent_runs": [self._run_summary(x) for x in recent],
        }

    # -- row mappers ----------------------------------------------------
    @staticmethod
    def _project_row(row: sqlite3.Row) -> dict[str, Any]:
        keys = row.keys()
        card_raw = row["agent_card"] if "agent_card" in keys else ""
        return {
            "id": row["id"],
            "name": row["name"],
            "agent_type": row["agent_type"],
            "description": row["description"],
            "owner_id": row["owner_id"] if "owner_id" in keys else "",
            "config": json.loads(row["config"]),
            "agent_card": json.loads(card_raw) if card_raw else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _code_scan_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "created_at": row["created_at"],
            "source_type": row["source_type"],
            "source_ref": row["source_ref"],
            "score": row["score"],
            "verdict": row["verdict"],
            "findings_count": row["findings_count"],
        }

    @staticmethod
    def _run_summary(row: sqlite3.Row) -> dict[str, Any]:
        keys = row.keys()
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "created_at": row["created_at"],
            "source": row["source"],
            "agent_name": row["agent_name"],
            "risk_index": row["risk_index"],
            "privacy_score": row["privacy_score"] if "privacy_score" in keys else 0,
            "verdict": row["verdict"],
            "blocked": bool(row["blocked"]),
            "leaked_secrets": row["leaked"],
            "label": row["label"] if "label" in keys else "",
        }

    @staticmethod
    def _scenario_row(row: sqlite3.Row, *, with_trace: bool) -> dict[str, Any]:
        keys = row.keys()
        spec_raw = row["spec"] if "spec" in keys else ""
        canaries_raw = row["canaries"] if "canaries" in keys else ""
        data = {
            "id": row["id"],
            "name": row["name"],
            "domain": row["domain"],
            "description": row["description"],
            "owner_id": row["owner_id"] if "owner_id" in keys else "",
            "sensitive_data": json.loads(row["sensitive_data"]),
            "tags": json.loads(row["tags"]),
            "difficulty": row["difficulty"],
            "source": row["source"],
            "pack_id": row["pack_id"],
            "origin_id": row["origin_id"],
            "created_at": row["created_at"],
            "builtin": False,
            "has_spec": bool(spec_raw),
            "has_canaries": bool(canaries_raw),
        }
        if with_trace:
            data["trace"] = json.loads(row["trace"])
            data["spec"] = json.loads(spec_raw) if spec_raw else None
            data["canaries"] = json.loads(canaries_raw) if canaries_raw else None
        return data
