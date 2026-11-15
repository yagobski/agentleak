# Web GUI

A local web app for running audits interactively. It's optional — the CLI and
SDK are fully functional without it.

```bash
pip install 'agentleak[gui]'
agentleak serve                 # http://127.0.0.1:8000
agentleak serve --port 9000 --no-browser
```

Everything runs in-process on your machine. Traces are never sent anywhere; the
frontend is fully self-contained (no CDN, self-hosted fonts).

## Local mode: no sign-in

`agentleak serve` presents a sign-in page on 127.0.0.1, directly under the
footer that says "100% local". The workspace belongs to whoever is at the
machine, so requiring an account to reach it is ceremony that contradicts the
product's first claim.

```bash
agentleak serve --local
```

One implicit owner, no registration, no password. The account is created on
first use with an unusable password, so nothing guessable is left behind if you
later turn local mode off.

**It may only listen on loopback**, and three independent gates enforce that: the
CLI flag refuses a routable `--host`, `Limits.from_env()` refuses to combine it
with `AGENTLEAK_PUBLIC_MODE`, and `run_server` refuses the bind even when the
`AGENTLEAK_LOCAL_MODE` environment variable is set directly. The feature is an
unauthenticated web application; the cost of one missed check is a dashboard on
a routable address, so it fails closed at every layer.

Without `--local` nothing changes: accounts, sessions and the sign-in page work
exactly as before.


## What you can do

| Route | What it is for |
| --- | --- |
| `/app/analyze` | Score one trace without a project: a bundled scenario, a JSON file (drop it on the panel) or pasted JSON. `?scenario=<id>` analyzes a bundled scenario with defaults. **Save as run** stores the report under a project. |
| `/app/runs` | Every stored run across projects, filtered, sorted and paged by the server (`/api/runs`). The filter lives in the URL. Export takes every matching run (up to 10,000) or the current page; the menu says which. Tick two rows to compare. |
| `/app/runs/<id>` | One result. Tabs: Findings, Trace, Leak paths, Remediation, Compliance. `?tab=`, `?finding=` and `?event=` make every view a permalink. |
| `/app/compare?a=<id>&b=<id>` | A (baseline) against B (candidate): verdict, RI, WSL/ρ_S, per-channel RI deltas, findings resolved / added / unchanged with their triage. Warns when the vault denominators, scenarios or detector tiers differ. |
| `/app/projects`, `/app/projects/<id>` | Projects, their runs, agents, integration snippets and settings. |
| `/app/scenarios` | Built-in, uploaded and imported scenarios with provenance (source, license, attribution); pack import. |
| `/app/playground` | Red-team campaigns against a project's harness. |

### Reading a result

1. **Verdict per channel first.** Final output, then every internal emission
   channel, each with events, findings and channel RI. The sentence above the
   table states the contrast and its denominator. A result with no finding
   reads "no finding from the enabled deterministic detectors"; the detectors
   are patterns and dictionaries, so that is not proof that nothing leaked.
2. **Detector tier.** The badge under the agent name shows the detection mode,
   the tiers that ran and whether detection was degraded.
3. **Score.** RI, leaked/vault secrets, WSL/ρ_S and privacy score.
   *How this number is computed* expands the AgentRisk derivation from the
   report's own `agentrisk` block (weights, per-level counts, sums).
4. **Trace.** Every event, sources (`user_input`, `tool_response`) marked apart
   from emissions. Selecting an event shows its findings, the leak path from
   where each value entered to where it left, and the payload, masked until you
   press *Reveal values*. Stored runs keep the report, not the trace: load the
   original file (or the bundled scenario trace) to see payloads; it is checked
   against the report and never uploaded.

### Triage

On a stored run's Findings tab, mark a finding (or a selected set) true
positive, false positive, accepted risk or needs review. Every state except
true positive needs a short rationale; an accepted risk can carry a review
date, after which it reads "needs review" again. Each decision records the
reviewer and the time, and the audit trail of a finding lists every decision
on it.

A decision follows the value: it applies to the same value on the same
channel in later runs of the project, shown as "carried over from run X". The
match uses a keyed fingerprint of the value (HMAC-SHA256, scoped to the
project); runs stored before fingerprints existed match on channel, data type, level and
masked value instead.

Triage never changes the measured result. The score panel shows a second,
labelled figure: the Risk Index excluding findings triaged as false positive,
with its numerator and denominator. The verdict and the gate are always the
measured ones. Accepted risks still count.

API: `GET /api/runs/{id}/triage` (decisions in force, counts, both scores),
`POST /api/runs/{id}/triage` (`finding_ids`, `state`, `rationale`,
`expires_on`), `GET /api/runs/{id}/triage/history?finding_id=`.

Exports from any table contain the rows currently shown, with masked values
only. The full report exports as JSON, Markdown or self-contained HTML.

Press `/` to focus the search field of the current table.

## How it's built

- Source: `agentleak/web/frontend/` (React + Vite + Tailwind + shadcn/ui).
- Built bundle: `agentleak/web/static/` (committed, shipped in the wheel).
  Rebuild with `npm run build` in the frontend directory; `npm test` runs the
  frontend unit tests.
- Server: `agentleak/web/app.py` (FastAPI) serves the SPA and the JSON API.

### API (all local)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/meta` | version, channels (with the `source_channels` / `emission_channels` split), detector names |
| GET | `/api/scenarios` | built-in scenarios |
| GET | `/api/example/{id}` | a scenario's bundled trace |
| POST | `/api/analyze` | analyze a trace/scenario → report JSON |
| POST | `/api/report/{json\|html\|markdown}` | rendered report in a format |

See [AGENTS.md](../AGENTS.md) §6–7 for the dev workflow and how to add features.
