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

- **Pick a scenario** or paste your own trace JSON (with a Format button and
  validation).
- **Toggle detectors** (PII, secrets, healthcare, finance, HR).
- **Add custom rules** — name + regex + severity level — for your own internal
  identifiers.
- **Set the vault scope** — *Observed* (auto, the denominator is what was
  detected) or *Explicit* per-level counts for a deployment-accurate ρ_S.
- **Read the AgentRisk report** — an animated Risk Index gauge, WSL/ρ_S, the
  L1–L4 leaked-vs-vault profile, the key insight, per-channel RI bars, the
  findings table (hover a row for its recommendation), and recommendations.
- **Export** the report as JSON, Markdown, or a self-contained HTML file.
- **Light / dark theme** (the toggle is in the header; preference is persisted).

## How it's built

- Source: `agentleak/web/frontend/` (React + Vite + Tailwind + shadcn/ui).
- Built bundle: `agentleak/web/static/` (committed, shipped in the wheel).
- Server: `agentleak/web/app.py` (FastAPI) serves the SPA and the JSON API.

### API (all local)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/meta` | version, channels, detector names |
| GET | `/api/scenarios` | built-in scenarios |
| GET | `/api/example/{id}` | a scenario's bundled trace |
| POST | `/api/analyze` | analyze a trace/scenario → report JSON |
| POST | `/api/report/{json\|html\|markdown}` | rendered report in a format |

See [AGENTS.md](../AGENTS.md) §6–7 for the dev workflow and how to add features.
