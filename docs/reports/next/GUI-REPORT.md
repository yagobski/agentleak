<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# GUI report: branch `next2/gui`

Second GUI round, on `main` at v0.19.0. Everything was checked on a local
`agentleak serve --local` bound to 127.0.0.1, with synthetic data only (the
ten built-in scenarios, saved as 20 runs in two projects), in headless
Chromium (Playwright, installed in the untracked `.venv` only) at 1440 px and
390 px (360 px for the runs page), dark and light.

## 1. What shipped

| Feature | Where |
|---|---|
| Finding triage: true positive, false positive, accepted risk (optional review date), needs review; rationale required for the last three; reviewer and time; bulk action on a selection; filter by state; audit trail per finding; triage fields in the findings CSV/JSON export | `/app/runs/<id>?tab=findings` (`features/Triage.tsx`, `features/FindingsTable.tsx`, `lib/triage.ts`) |
| Carry-over: a decision applies to the same value on the same channel in later runs of the project, shown as "carried over from run X" (or "since deleted") | same; `core/triage.py:resolve` |
| Expiry: an accepted risk past its date is in force as "needs review" and says "Accepted risk expired on DATE; review it again" | same |
| Triaged view of the score, beside the measured one, labelled, with both denominators | score panel on `/app/runs/<id>` (`TriagedScore`) |
| Comparison shows each side's triage, triage counts, and the RI excluding false positives as a separate row | `/app/compare?a=&b=` |
| Server-side run listing: owner-scoped, filters in the URL (project, verdict, gate, source, date range, text), server sort and paging, export of every matching row or of the page, the menu says which | `/app/runs` (`features/RunsBrowser.tsx`) |
| Leak-path export, SVG and JSON, masked values | Trace tab toolbar (`lib/leakpath.ts`) |
| Restyled: project Settings (with the evaluation gate), Integrate, Identity & code, Administration | `pages/ProjectDetail.tsx`, `features/AgentCardView.tsx`, `pages/Admin.tsx`, `components/Section.tsx` |

## 2. Database migration

### DDL (runs on every start, `Store._init` → `Store._init_triage`)

```sql
CREATE TABLE IF NOT EXISTS finding_fingerprints (
    run_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    PRIMARY KEY (run_id, finding_id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS finding_triage (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    run_created_at REAL NOT NULL,
    finding_id TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    masked_key TEXT NOT NULL,
    state TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    expires_at REAL,
    reviewer_id TEXT NOT NULL DEFAULT '',
    reviewer_email TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_triage_project ON finding_triage(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_triage_run ON finding_triage(run_id, finding_id);
```

Nothing else. No `ALTER TABLE`, no `UPDATE`, no `DELETE` of existing data. The
DDL is the tuple `TRIAGE_DDL` in `core/store.py`.

Design points: decisions are append-only (a change is a new row), so the table
is the audit trail. The cascades are declared in the child tables, so SQLite
enforces them whichever version deletes the parent: deleting a run in 0.19.0
removes its fingerprints; deleting a project or an account (0.19.0's
`delete_user` deletes the projects) removes its triage. Deleting a run keeps
its decisions, so they still carry over to later runs.

### Tests (`tests/test_triage_migration.py`)

| Test | What it does | Result |
|---|---|---|
| `test_new_tables_are_the_only_schema_change` | Builds the 0.19.0 schema from `tests/fixtures/store_schema_v0_19_0.sql` (dumped from `sqlite_master` of a database the `v0.19.0` tag's `store.py` created; the `v0.18.0` dump is identical), fills one row in every table by raw SQL, opens it twice with this version. Asserts every pre-existing table's rows and every pre-existing schema object's SQL are identical, and that the only additions are the two tables and two indexes. | pass |
| `test_existing_endpoints_answer_on_a_019_database` | Same database through the app with a 0.19.0 session token: `auth/me`, projects list and detail, runs, history, run, stats, leaderboard, scenarios, code scans, model, both compare endpoints, admin overview and users, meta, plus the new `/api/runs` and triage on old rows. All 200; old runs fall back to the masked identity; the triaged view reports the measured RI unchanged. No pre-existing row changed by the reads. | pass |
| `test_upgrade_then_downgrade_with_tagged_store[v0.18.0]`, `[v0.19.0]` | Loads `core/store.py` from the git tag, creates two accounts, projects, runs, a scenario and a session with it; opens with this version, stores a run and a triage decision through the API; checks pre-existing rows and schema unchanged; then reopens with the tagged code: lists, reads, stats, `delete_run` (cascades fingerprints, keeps the decision), `delete_project` (cascades triage, other account untouched); then opens once more with this version. | pass (skips if the tags are absent) |

## 3. Finding identity (fingerprint)

When a run is stored, each finding gets `HMAC-SHA256(key, "fp1" | project id |
data type | raw value)`, truncated to 128 bits, in `finding_fingerprints`; the
raw value exists only in memory during analysis and is never written. A
finding's identity is its channel plus that fingerprint, so a decision
follows the same value on the same channel across runs of one project and
never across projects or accounts. Runs stored before this, and runs from the
self-test path in `selftest/http.py` (not hooked), use the masked identity
(channel, data type, level, masked value), the same rule the comparison page
uses.

Key handling: `AGENTLEAK_FINGERPRINT_KEY` (at least 32 characters) wins;
otherwise a random 256-bit key is created once in `agentleak-fingerprint.key`
next to the database, mode 0600, published with an atomic link so concurrent
workers agree. It is never stored in the database. If neither is usable,
fingerprints are off and everything falls back to the masked identity.
Residual risk, stated plainly: whoever holds both the database and the key
can test candidate values against a fingerprint (an SSN space is small). A
hosted deployment should set the environment variable from a secret store
rather than keep the key file on the database volume, and back it up: a lost
key only means old decisions match new runs by masked value.

The same fingerprint groups findings into distinct secrets for the triaged
score, which reproduces the measured WSL exactly (`exact: true`); without
fingerprints the grouping is by masked value and the view says "approximate".

## 4. Endpoints

All in `web/triage_api.py`, registered once from `create_app`.

| Route | Auth | Limits and validation |
|---|---|---|
| `GET /api/runs` | session (`require_user`); rows joined on `projects.owner_id`; `project` resolved through `_owned_project` (foreign id → 404) | `limit` 1–200, `offset` 0–1,000,000 (422 outside); `verdict` enum, `gate` blocked/passed, `source` `[A-Za-z0-9_.-]{1,64}`, `since`/`until` Unix seconds ≤ 2100 and ordered, `q` ≤ 200 chars with LIKE wildcards escaped, `sort` whitelist, `dir` asc/desc (400 otherwise). Stable order: sort column then run id. |
| `GET /api/runs/export` | same | same filters; `format` csv/json; at most 10,000 rows, `X-Total-Count` and `X-Exported-Count` headers; CSV text cells starting with `= + - @ tab CR` prefixed with `'` |
| `GET /api/runs/{rid}/triage` | session; run → project → owner check (foreign run → 404) | id format checked; decisions per project capped at 50,000 read |
| `POST /api/runs/{rid}/triage` | same | body ≤ 64 KiB (413); object; `state` in 4 states + `untriaged`; `finding_ids` 1–500 strings `[A-Za-z0-9_.:-]{1,64}`, all findings of this run; `rationale` string ≤ 1000 chars, no control characters except newline and tab, ≥ 3 chars for false positive, accepted risk, needs review; `expires_on` only for accepted risk, `YYYY-MM-DD`, after today and ≤ 3 years (UTC); 409 past 50,000 decisions per project. Rationale is stored as given and rendered as text (React escapes it; CSV export neutralises formulas). |
| `GET /api/runs/{rid}/triage/history?finding_id=` | same | `finding_id` ≤ 64 and must be in the run (404) |
| `GET /api/auth/session` | none; returns `public_user` or `{authenticated: false}` | — |

Responses never include the raw value, the identity keys or the reviewer id.
`GET /api/runs/{id}` and `POST /api/projects/{id}/runs` responses are
unchanged (tested), so the CI-facing API only gives a triaged figure when the
caller asks for `/triage`.

Two-account isolation and anonymous access: `tests/test_triage.py`
(`test_two_account_isolation`, `test_anonymous_is_401`), including that one
account's decision on a value does not apply to another account's run of the
same trace.

## 5. Backend issues from round one

| Id | Status |
|---|---|
| B1 duplicated leak-path steps | Not changed: `core/flow.py` is outside this lane. The GUI and the new leak-path export de-duplicate steps (tested). |
| B2 `/api/example` stamps the current time | Not changed: the time comes from `Event.timestamp`'s default factory in `core/trace.py`; changing it alters every trace without timestamps, a core decision for the backend lane. |
| B3 `/api/projects` lacks run statistics | Fixed in `Store.list_projects` (two grouped queries, no N+1), tested. |
| B4 | Not in the round-one list. |
| B5 401 on the sign-in page | Fixed: `GET /api/auth/session` answers 200; the GUI's auth probe uses it. |
| B6 stale `index.html` after a rebuild | Fixed: re-read when its mtime changes, tested with a temporary static dir. AGENTS.md §7 is now accurate. |
| B7 gate not stored when a run is saved | Fixed: `privacy_policy` sent with `POST /api/projects/{id}/runs` is applied unless the project defines one (a submitter cannot replace the project's gate), tested both ways. |
| Leaderboard `leaked_secrets` sums all runs | Not changed; the GUI does not show it. |

## 6. Anomalies found and fixed

| # | Anomaly | Fix |
|---|---|---|
| 1 | Saving project Settings PATCHed a config with five keys; PATCH stores it as given, so the project's test agents, its API key and any gate were deleted. | Form re-reads the project and merges. Verified in the browser: key kept after save. Suggest the backend make PATCH merge (security lane). |
| 2 | Project and account deletion used `window.confirm`; agent-card removal and API-key rotation had no confirmation. | App confirmation dialog for all four. |
| 3 | Settings and card editor controls had no associated labels (switches unnamed, rule inputs placeholder-only, vault toggle without `aria-pressed` or `type`). | Labels on every control; radio group for the vault scope. |
| 4 | Integrate snippets hard-coded `http://127.0.0.1:8000`, and the revealed self-test key was pasted into the Python and curl snippets. | Snippets use the page's origin and read `AGENTLEAK_KEY` from the environment via the `X-AgentLeak-Key` header. |
| 5 | A newly generated key was revealed automatically. | Masked by default; reveal is explicit. |
| 6 | Project tabs carried coloured icons (a red shield on "Adversarial"). | Removed. |
| 7 | The project Runs tab counted the list (capped at 200). | Uses `run_count`. |
| 8 | Administration showed "Platform operational / healthy" because the page loaded. | States when the API answered and the version. |
| 9 | Administration rates and means without denominators ("Target adoption 100%", mean privacy score without n). | "2 of 2 active in 24 h", "mean RI 0.228 over 20 runs, all accounts and scenarios", blocked "4 / 20". |
| 10 | Administration recent runs linked to other accounts' runs, which 404. | Not links; the section says runs open from their owner's workspace. |
| 11 | 14-day activity chart: colour-only bars, values only in a hover title. | Table per UTC day, exportable. |
| 12 | Administration filters hidden below 640 px; project mean score coloured by verdict band. | Filters at every width; mean plain, with run count. |
| 13 | A code scan without findings read "No static findings — clean scan." | "No finding from the enabled detectors", with the tiers that ran. |
| 14 | Code-scan findings expanded by mouse click only. | Keyboard button with `aria-expanded`. |
| 15 | Native controls (date picker, select menus, scrollbars) light in the dark theme. | `color-scheme: dark` on `.dark`. |
| 16 | "1 rows". | Pluralised. |
| 17 | Runs page and the Compare picker made one request per project. | One `/api/runs` request. |
| 18 | Runs filters stacked one per line at 390 px. | Two-column grid on phones. |
| 19 | Sign-in page logged a 401 (B5). | Session probe. |

Walk at the end: 22 routes and tabs × {1440, 390} × {dark, light} = 88 page
views. Horizontal overflow on none; console messages (error, warning, log) on
none.

Not restyled (still the older card style, outside this brief's list): the
project Test, Test agents, System map and Adversarial tabs.

## 7. Bundle size

| | Before (v0.19.0) | After | Change |
|---|---|---|---|
| JS | 695.63 kB (gzip 199.86) | 717.79 kB (gzip 208.60) | +3.2 % (gzip +4.4 %) |
| CSS | 80.78 kB (gzip 15.78) | 79.49 kB (gzip 15.58) | −1.6 % |

No new runtime dependency. Playwright was used from the untracked `.venv`
only.

## 8. Checks

- `npm run build` (tsc strict + vite): clean. A second build produces
  byte-identical assets; `git status` is clean after it.
- `npm test`: 21 passed (12 before).
- `pytest`: 1912 passed, 26 skipped, 0 failed (62 of them new: `tests/test_triage.py`, `tests/test_triage_migration.py`).
- `ruff check src/agentleak/ tests/`: all checks passed. `mypy src/agentleak/`:
  no issues.
- Wheel: `pip wheel .` → fresh venv → `pip install 'agentleak-0.19.0-py3-none-any.whl[gui]'`
  → `agentleak serve --local --port 8777`: `/app/` references
  `index-DY1rQaqe.js` and `index-Cx7p_u0q.css`, both 200 with the right MIME
  types; `/api/auth/session` and `/api/runs` answer.

## 9. Screenshots

`docs/assets/gui-next2/` (viewport size, synthetic data):
`triage-1440-dark.png`, `triage-dialog-1440-light.png`,
`compare-triage-1440-light.png`, `runs-1440-dark.png`,
`settings-1440-light.png`, `admin-1440-dark.png`, `triage-390-dark.png`.

## 10. For merging

`core/store.py`: added `TRIAGE_DDL`, `RUN_SORT_COLUMNS`, `_like_escape`
(module level); `Store._init_triage`, `fingerprint_key`,
`set_finding_fingerprints`, `finding_fingerprints`, `add_triage_decisions`,
`list_triage_decisions`, `_triage_row`, `query_runs`, `run_source_kinds`;
changed `Store.__init__` (one attribute), `Store._init` (one call),
`Store.list_projects` (B3).

`web/app.py`: one import line in `create_app`; one
`register_triage_routes(...)` call before the `# -- runs --` section; one
`record_fingerprints(db, run, result.findings)` line after each of the five
`db.create_run` calls (selftest, red team, create run, execute pipeline,
execute single); `create_run` handler gains the B7 lines; the SPA block reads
`index.html` through `index_template_now()` (B6).

New: `core/triage.py`, `web/triage_api.py`, `tests/test_triage.py`,
`tests/test_triage_migration.py`, `tests/fixtures/store_schema_v0_19_0.sql`.
