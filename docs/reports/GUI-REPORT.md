# GUI report: branch `next/gui`

Platform GUI served by `agentleak serve` (React + Vite + Tailwind source in
`src/agentleak/web/frontend`, built bundle in `src/agentleak/web/static`).
Everything below was checked on a local `agentleak serve --local` on loopback
with synthetic data only (the ten built-in scenarios and the `agentleak_bench`
pack), in headless Chromium (Playwright, installed in the untracked `.venv`
only) at 1440 px and 390 px (plus a 360 px overflow pass), dark and light.

## 1. Anomaly backlog

Status: **fixed** in this branch, **reported** (backend, outside the GUI lane),
or **open**.

| # | Anomaly (before) | Status |
|---|---|---|
| 1 | Horizontal page scroll at 390 px on 8 of 13 pages (dashboard 518 px wide, projects 684, project 823, findings 747, test lab 519, admin 455). Causes: unscrollable tab lists, fixed grids, and screen-reader-only text escaping table scroll boxes. | fixed: all 18 routes measure `scrollWidth == viewport` at 360 and 390 px |
| 2 | Every page had the same browser title. | fixed: per-page title from the breadcrumb |
| 3 | Breadcrumb read "Dashboard › Detail" on a run and "Projects › Detail" on a project. | fixed: real names (Runs › project › run id) |
| 4 | Dashboard leaderboard always "No scored agents yet" and every project card "0 runs": `/api/projects` carries no run statistics. | fixed in GUI (reads `/api/leaderboard`); backend gap reported (B3) |
| 5 | Dashboard turned the mean RI of unrelated runs into a verdict ("Conditional pass"), recomputing the verdict bands client-side. | fixed: mean shown with its n, no derived verdict; client-side band logic deleted |
| 6 | Rates without denominators: "63% releaseable", "3 blocked runs", compliance "17%". | fixed: "3 / 13", "1/6 controls clear" |
| 7 | "Risk trajectory" spline through runs of different scenarios (curve dips below 0, "+0.231" delta between unrelated runs). | fixed: removed |
| 8 | Project "Trend +44 · Improving" computed across different scenarios. | fixed: chart says when it mixes scenarios; comparison moved to like-for-like Compare |
| 9 | Clean result read "No leaks detected. 🎉". | fixed: "No finding from the enabled deterministic detectors (tiers that ran: regex)" |
| 10 | Detector tier and degraded mode never shown, although every report carries `detection`. | fixed: tier badge on every result and comparison |
| 11 | `final_output` absent from the channel list when clean; the product's thesis lived in one paragraph under a tab. | fixed: channel verdict table leads the result, final output first, with a sentence and its denominator |
| 12 | L1 drawn in green, the same family as "Pass". | fixed: L1 blue; green only means "no finding" |
| 13 | Light theme contrast below WCAG AA: L3 3.4:1, L2 2.5:1, ok 3.6:1, L1 4.0:1, muted on muted 4.3:1. | fixed: all ≥ 4.5:1 on background, card and muted surfaces |
| 14 | Deleting a run from the project list or run page was immediate, no confirmation. | fixed: confirmation dialog |
| 15 | Run/project not found: red text with no way out; loading states were bare "Loading…". | fixed: explanatory error with a link back; skeletons shaped like the page |
| 16 | Tab, finding and event selection not in the URL: refresh or Back lost them; no link to a finding. | fixed: `?tab=&finding=&event=`, copy-link buttons |
| 17 | Findings recommendation only reachable by mouse click on a row. | fixed: keyboard button per row (`aria-expanded`) |
| 18 | Toggle chips without `aria-pressed`, icon buttons without labels, no skip link. | fixed in all new and rewritten views |
| 19 | Scenarios: 46 identical cards; licenses only at the bottom; imported scenarios showed no provenance. | fixed: dense tables, provenance column, packs first |
| 20 | Scenario trace dialog showed raw synthetic values. | fixed: masked by default, explicit reveal |
| 21 | First result took a project or three choices in the test lab; the result vanished on reload. | fixed: `/analyze`, one click from an empty dashboard; masked report restored after reload |
| 22 | Gauge with glow and draw animation; logo sweep/reveal animation on every page (logo nearly invisible while it ran). | fixed: static logo, numeric score block |
| 23 | 140 kB of marketing-site CSS (`cursor-*`, `docs-*`, `integrations-*`…) shipped in the app bundle. | fixed: removed |
| 24 | Sparkle icons; marketing copy ("Live data-flow map", "Animated routes reveal…", "Safe product tour"). | fixed |
| 25 | Login theme switch used undefined CSS variables (borderless control). | fixed |
| 26 | Leak-path steps duplicated (`evt_003` listed twice for one value). | reported (B1); GUI de-duplicates |
| 27 | `/api/example/{id}` stamps the current time on every event, so the bundled trace changes on each request. | reported (B2) |
| 28 | Rebuilding the frontend under a running server breaks the page until restart: `web/app.py` caches `index.html` at start-up while the build deletes the old hashed assets. AGENTS.md §7 says a reload is enough. | reported (B6) |
| 29 | Logged-out pages log a 401 for `/api/auth/me` in the console. | reported (B5); expected, noisy |
| 30 | Evaluation gate set in Analyze is not stored when the result is saved as a run (`create_run` ignores `privacy_policy`). | reported (B7); the save dialog says so |
| 31 | Wide tables on phones scroll inside their card. | by design (dense tables) |
| 32 | Project sub-views (Identity & code, Test agents, System map, Adversarial, Settings, Admin) still use the older card style. | open |

Counts: 32 found. 25 fixed (one of them, #4, also reported as a backend gap),
5 reported to the backend lane, 1 by design, 1 open.

### Backend notes for merging (B-numbers above)

- **B1** `core/flow.py:build_leak_paths` emits the source step once per detection
  of the same value on the source event.
- **B2** `GET /api/example/{id}` (`web/app.py`) returns `timestamp` = now for every
  event.
- **B3** `GET /api/projects` (`store.list_projects`) lacks `run_count`,
  `avg_risk_index`, `last_run` that `get_project` returns and `lib/api.ts` types.
- **B5** `/api/auth/me` 401 on the sign-in page.
- **B6** `web/app.py` reads `index.html` once in `create_app`; either re-read it per
  request or fix the AGENTS.md sentence.
- **B7** `POST /api/projects/{pid}/runs` merges only detectors, vault,
  custom_detectors and redact.
- The leaderboard's `leaked_secrets` sums over all runs while its verdict and RI
  are the latest run's; the GUI does not show it.

## 2. What was built

| Feature | Where |
|---|---|
| Analyze a trace without a project: bundled scenario, file (drag and drop) or pasted JSON; options in one line; `?scenario=` permalink; Save as run | `/app/analyze` (`pages/Analyze.tsx`, `features/AnalysisOptions.tsx`) |
| Result page: verdict per channel first (final output vs internal channels, with the denominator), score, *How this number is computed* (AgentRisk derivation read from `report.agentrisk`), detector tier badge, report export | `/app/runs/<id>` and `/app/analyze` (`features/ResultsView.tsx`, `ResultSummary.tsx`, `Chips.tsx`) |
| Findings table: sort, search, channel and level filters, CSV/JSON export of the rows shown, finding → trace event, leak path, per-finding permalink | Findings tab (`features/FindingsTable.tsx`) |
| Trace explorer: timeline over all channels, source vs emission marked in text, channel filters with counts, masked payloads with per-event reveal, finding ↔ event navigation, leak path from entry to sink, 100 events per page; loads the original trace into a stored run (verified against the report, never uploaded) | Trace tab (`features/TraceExplorer.tsx`) |
| Run comparison: verdict, RI, WSL/ρ_S, leaked secrets, gate; per-channel RI delta; findings resolved/added/unchanged; dominance; warnings on different denominators, scenarios, tiers; export | `/app/compare?a=&b=` (`pages/Compare.tsx`, `lib/compare.ts`) |
| All runs across projects, select two to compare | `/app/runs` (`pages/Runs.tsx`, `features/RunsTable.tsx`) |
| Generic sortable/exportable table | `components/DataTable.tsx` |
| Dashboard rebuilt: stats with denominators, latest result per project, recent runs, one-click first result when empty | `/app/` |
| Projects and scenarios as tables; scenario provenance; masked scenario traces | `/app/projects`, `/app/scenarios` |
| Red team page (former test lab, red-team part only; old `?scenario=` links redirect) | `/app/playground` |
| Breadcrumbs, per-page titles, footer with version and API links, error boundary per page, skeletons, skip link, `/` to search | `layout/AppShell.tsx`, `layout/crumbs.tsx`, `components/ErrorBoundary.tsx` |
| `source_channels` / `emission_channels` in `/api/meta` | `web/app.py:meta` + `tests/test_gui_meta.py` |
| Frontend unit tests (vitest, dev-only) | `src/test/result.test.ts`, `npm test` |

Finding triage (true positive / false positive / accepted risk) was **not**
built: persisting it needs a new table and migration in `core/store.py` plus
endpoints; that is not a small, isolated change, and `store.py` belongs to the
backend lane.

Performance check: a synthetic 2,000-event trace (68 findings) analyzes and
renders in 0.8 s, opens the Trace tab in 0.04 s, filters in 0.2 s and jumps
from a finding to its event (page 14) in 0.07 s, with no console message.

## 3. Bundle size

| | Before | After | Change |
|---|---|---|---|
| JS | 643.00 kB (gzip 182.35) | 695.63 kB (gzip 199.86) | +8.2 % (gzip +9.6 %) |
| CSS | 220.70 kB (gzip 39.96) | 80.78 kB (gzip 15.78) | −63 % |
| JS + CSS | 863.70 kB (gzip 222.31) | 776.41 kB (gzip 215.64) | −10 % (gzip −3 %) |

No new runtime dependency. `vitest` is a dev dependency.

## 4. Checks

- `npm run build` (tsc strict + vite): clean.
- `npm test`: 12 passed.
- `pytest`: 1298 passed, 21 skipped.
- `ruff check` and `mypy` on `web/app.py` and the new test: clean.
- Browser console: no error or warning on any authenticated route, at both
  widths, in both themes.
- Wheel: `pip wheel .` → fresh venv → `pip install 'agentleak-0.18.0-py3-none-any.whl[gui]'`
  → `agentleak serve --local`: `/app/` references the new hashed assets, both
  served 200 with the right MIME types; `/api/meta` returns the channel split.

## 5. Screenshots

Committed (viewport size, synthetic data): `docs/assets/gui-next/`

- `result-1440-dark.png`, `result-1440-light.png`: result page, verdict per channel
- `derivation-1440-light.png`: score derivation
- `trace-explorer-1440-dark.png`: trace explorer with leak paths
- `compare-1440-light.png`: run comparison
- `runs-1440-dark.png`: runs table
- `result-390-dark.png`: phone width

Full before/after sets (full page, 1440 and 390 px, dark and light,
~23 MB) are left uncommitted in `gui-screenshots/before/` and
`gui-screenshots/after/`, each with `audit.json` (title, overflow, console).
