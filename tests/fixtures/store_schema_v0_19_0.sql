-- SPDX-FileCopyrightText: 2026 AgentLeak contributors
-- SPDX-License-Identifier: MIT
-- Schema of a database created by agentleak 0.19.0 (identical for 0.18.0), dumped
-- from sqlite_master. Used by tests/test_triage_migration.py.
CREATE TABLE api_usage (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    project_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
CREATE TABLE audit_log (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_email TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    target_id TEXT DEFAULT '',
                    target_email TEXT DEFAULT '',
                    detail TEXT DEFAULT ''
                );
CREATE TABLE code_scans (
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
                );
CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    agent_type TEXT NOT NULL DEFAULT 'generic',
                    description TEXT DEFAULT '',
                    config TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                , owner_id TEXT DEFAULT '', agent_card TEXT DEFAULT '', public_slug TEXT DEFAULT '');
CREATE TABLE runs (
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
                );
CREATE TABLE scenarios (
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
                , spec TEXT DEFAULT '', owner_id TEXT DEFAULT '', canaries TEXT DEFAULT '');
CREATE TABLE sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
CREATE TABLE usage_meter (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    owner_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL
                );
CREATE TABLE user_settings (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (user_id, key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                , is_admin INTEGER DEFAULT 0, disabled INTEGER DEFAULT 0);
CREATE INDEX idx_api_usage_created ON api_usage(created_at);
CREATE INDEX idx_api_usage_project ON api_usage(project_id, created_at);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);
CREATE INDEX idx_code_scans_project ON code_scans(project_id, created_at);
CREATE UNIQUE INDEX idx_projects_slug ON projects(public_slug) WHERE public_slug != '';
CREATE INDEX idx_runs_project ON runs(project_id, created_at);
CREATE INDEX idx_scenarios_pack ON scenarios(pack_id, origin_id);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_usage_meter_owner ON usage_meter(owner_id, created_at);
