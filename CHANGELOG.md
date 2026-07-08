# Changelog

All notable changes to AgentLeak OSS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.7.0] — 2026-07-08

### Added
- **Universal chat-log import** — the scenario uploader (and `detect_format`)
  now accepts any OpenAI-style chat log (`{"messages": [...]}`): roles are
  mapped faithfully onto channels (system/user → `user_input`, `tool_calls` →
  `tool_call`, tool results → `tool_response`, intermediate assistant turns →
  `inter_agent_message`, the last assistant text → `final_output`), so sessions
  exported from the OpenAI SDK, LiteLLM, LangSmith or benchmark dumps are scored
  by the same uniform engine (`scenarios/convert.py`).
- **Account-level default model key** — paste one OpenRouter / OpenAI / Groq /
  Ollama endpoint in *Settings → Default model key* and it powers the whole
  test core (live runs, multi-agent pipelines, red-team, LLM-judge) for every
  project that has no endpoint of its own. Stored per-user (`user_settings`),
  redacted everywhere (`GET/POST/DELETE /api/auth/model-key` never return the
  key; a blank key preserves the stored one).
- **Agent leaderboard** — `GET /api/leaderboard` ranks your agents by their
  latest AgentRisk result (Risk Index ascending, privacy score as tiebreak);
  the Dashboard shows the ranked list so agents can be differentiated at a
  glance.
- **Code upload in the scan panel** — the static code scan UI now takes a
  `.zip` archive or a handful of source files directly (in addition to a
  GitHub repo link), matching the API's `zip` / `files` sources.
- **Agent-first layer — autonomous self-registration, code scans, and a
  self-improvement loop.** An agent can now test and fix *itself* through the
  API, with no human in the loop:
  - **AgentCard** (`core/agentcard.py`) — an A2A / Nasiko-compatible
    `AgentCard.json` (name, capabilities, tags, examples, endpoints, declared
    code source). Parses official A2A cards too (`skills`, `protocolVersion`,
    `provider.organization`). `fetch_agent_card(url)` pulls a card from a live
    agent's well-known endpoint.
  - **Static code privacy scan** (`core/codescan.py`) — runs the exact same
    3-tier hybrid detection pipeline as trace analysis (regex, Presidio,
    LLM-judge) over an agent's *source code*, plus four code-specific layers:
    a generated EN/FR sensitive-identifier lexicon, entropy analysis for
    unknown-format secrets, de-obfuscation of decomposed PII (split literals,
    unusual separators), and quasi-identifier correlation (GDPR Rec. 26).
    Scans a local directory, an uploaded zip, or a GitHub repo
    (`agentleak scan`, `POST /api/agent/code`).
  - **Autonomous-agent API** (`X-AgentLeak-Key` auth) — `POST /api/agent/register`,
    `POST /api/agent/code`, `POST /api/agent/improve` (self-test + delta vs the
    previous run + prioritised, machine-actionable `next_steps`), and
    `GET /api/agent/status`. `AgentSelfClient` (`agentleak/client.py`) wraps
    the whole loop in a few Python calls.
  - **Public agent discovery** — `GET /.well-known/agent-card.json` serves
    AgentLeak's own A2A card unauthenticated, so orchestrators and registries
    (e.g. Nasiko) can auto-discover it as a privacy self-testing service.
    `GET /api/meta` now advertises the agent API surface. `agentleak agent-card`
    prints the same card offline.
- **SaaS admin console — multi-account, monitored, production-ready.**
  - Multi-account platform with roles: the first registered account becomes
    admin automatically. Admins can promote, disable (revokes sessions
    instantly), and delete other accounts, with lockout guards (can't disable/
    delete/demote yourself out of the last admin seat).
  - **Admin console** (`/admin`) — platform-wide stats, an accounts table, an
    **agent activity monitor** (runs executed, agent API "consumption", results,
    and a 14-day activity sparkline per project), and an immutable **audit log**
    of every admin action.
  - **Self-service account management** — change display name, change password
    (revokes all sessions), delete your own account, all gated by the current
    password.
  - `GET /api/health` (unauthenticated liveness probe) and login rate limiting
    (10 failed attempts / 5 min per e-mail → HTTP 429).

### Security
- **Fixed**: disabling a user account revoked their browser session but *not*
  their projects' `ak_...` self-test API keys — an agent could keep calling
  `/api/selftest` and `/api/agent/*` after its owner was disabled.
  `get_project_by_apikey` now checks the owner's disabled flag too.
- Per-API-key rate limiting (120 req/min) on the whole autonomous-agent surface.
- Zip-bomb guard: `scan_zip_bytes` rejects archives whose *declared*
  uncompressed size exceeds 100 MB before decompressing anything.
- `fetch_github_repo` now streams the download in 1 MB chunks capped at 50 MB
  instead of buffering an unbounded response.

- **`agentleak.watch()` — one-line connect for any agent** (`agentleak/track.py`).
  A single import and context manager replaces the five framework-specific
  patterns. It records directly (`run.tool_call(...)`), exposes a hook for every
  framework (`run.callback` for LangChain/LangGraph, `run.crew` for CrewAI,
  `run.ingest_messages(...)` for OpenAI Swarm / Agents SDK, `run.ingest_adk(...)`
  for Google ADK), auto-analyzes on exit (`run.report`), and uploads to a running
  platform when a project name is given. `agentleak.record()` / `@monitor` work
  from inside any framework node because the run is the active capture.
  Validated live against plain-Python, LangGraph, and Swarm multi-agent systems
  (see `multiagent-labs/`).
- **Computer-use / coding-agent integration** (`integrations/computer_use.py`).
  First-class support for the autonomous *action–observation* genre — OpenHands,
  Open Interpreter, Cline / "openclaw", SWE-agent, browser-use. `trace_from_steps`
  maps file **writes** to `generated_file` (the on-disk artifact a chat-only audit
  never opens), shell/code to `tool_call`, file reads to `tool_response`, agent
  reasoning to `log`, and the final message to `final_output`. Exposed as
  `run.ingest_steps(...)`, registered in the platform (`computer_use` framework),
  and validated live (a real tool-calling agent leaked a DB connection string +
  PII into the report file it wrote; see `multiagent-labs/computeruse_agent.py`).
- **OpenTelemetry / OpenInference span adapter** (`integrations/otel.py`).
  Instead of a bespoke adapter per framework, reuse the open-source tracing
  ecosystem: `trace_from_spans` ingests OpenInference / OTel GenAI spans (emitted
  by Arize Phoenix and OpenLLMetry / Traceloop for LangChain, LlamaIndex, CrewAI,
  AutoGen, DSPy, the OpenAI / Anthropic / Bedrock SDKs, …). Accepts span dicts,
  readable-span objects, or a raw OTLP `{resourceSpans}` payload; un-flattens the
  indexed `llm.*_messages` / `retrieval.documents` attributes; maps `TOOL`/
  `RETRIEVER`/`LLM`/`GUARDRAIL` span kinds to channels and promotes the last
  model output to `final_output`. Exposed as `run.ingest_spans(...)` and
  registered as the `openinference` framework.
- **Broader secret + identifier coverage for agent runtimes** (`detectors/`).
  The regex (default) tier now flags leaks that real agents routinely emit but
  that were previously invisible outside LLM-judge mode: model-provider keys
  (`llm_api_key` — OpenAI `sk-proj-…` / `sk-…`, Anthropic `sk-ant-…`), Google API
  keys (`google_api_key` — `AIza…`), opaque `Authorization: Bearer` tokens
  (`bearer_token`), IPv6 addresses, and UK National Insurance numbers
  (`national_insurance_number`, using the official valid-prefix rules). New
  regression scenarios drive each one through the runner end-to-end and assert
  channel-aware results (sources are not leaks; internal channels are).

### Changed
- The platform **Connect** snippets for all 14 frameworks now use the
  `agentleak.watch()` one-liner.
- **Findings view modernized with a filter system**: the results Findings tab now
  has full-text search (type / value / channel / source) plus severity-level
  pills and channel / detector dropdowns, a live "showing X of Y" count, and
  click-to-expand rows revealing the per-finding recommendation
  (`web/frontend/src/features/ResultsView.tsx`).

### Fixed
- **Multi-agent channel misattribution**: the LangChain/LangGraph callback tagged
  *every* LLM turn as `final_output`, so in a multi-node graph intermediate agent
  turns were misattributed to the user-facing answer (and could inflate the
  highest-severity channel). Only the final turn now stays `final_output`; earlier
  turns demote to `inter_agent_message` (`integrations/langchain.py`).
- **French / Québec civic addresses** (e.g. `1240 Rue Saint-Denis`) were missed
  by the PII detector, which only matched English `<name> Street` forms — a gap
  given the Law 25 grounding. Added a French civic-address recognizer
  (`detectors/pii.py`).
- **Version-string false positive**: a software version such as
  `version 1.2.3.4` was reported as a client `ip_address`. The IPv4 detector now
  suppresses matches preceded by a version/build/release keyword, and the new
  IPv6 matcher requires enough groups that a clock time (`12:34:56`) is never
  mistaken for an address (`detectors/pii.py`).
- Removed unused imports and a dead variable across the package.

## [0.6.0] — 2026-06-21

### Added
- **Leak flow & agent topology** (`core/flow.py`) — debugging views for
  multi-agent leaks:
  - **Leak paths**: each disclosed secret is traced from where it entered the
    system (a source channel) through every agent that handled it to each point
    of disclosure, so you can see exactly where a leak originated and how it
    propagated. Values stay redacted.
  - **Agent topology**: a behavioral graph of the agent — participants as nodes
    (inputs → agents → sinks), channels as edges, leak-carrying edges flagged by
    severity. Rendered as a diagram in the new **Leak flow** tab and embedded in
    the report (`report.flow` / `report.leak_paths`) and the Markdown export.

## [0.5.0] — 2026-06-21

Production-hardening release.

### Added
- **Release automation** — `release.yml` publishes the sdist + wheel to PyPI
  (Trusted Publishing) and attaches them to a GitHub Release on every `v*` tag.
- **Frontend CI** — a dedicated job type-checks and builds the web UI so a bad
  change can never ship a broken bundle.
- **CHANGELOG.md**.

### Changed
- Test suite expanded to **196 tests / 94% coverage**; the CI coverage gate was
  raised from 70% to **85%**. Hardened the newest code paths: the LLM client
  (59→98%), the CLI (79→90%), the SDK client (77→93%), and the LangChain adapter.

### Verified
- Clean-room wheel install (fresh venv): CLI, `run`, `serve` (GUI + API + SPA
  deep links) all functional.

## [0.4.1] — 2026-06-21

### Changed
- Adopted the official shadcn/ui **blocks** dashboard shell: collapsible sidebar
  (icon-collapse on desktop, drawer on mobile), sticky site header with route
  breadcrumb, and section-card dashboard. Light and dark themes.

## [0.4.0] — 2026-06-21

### Added
- **Live agent runner** — execute a real LLM agent (any OpenAI-compatible
  endpoint: OpenAI, OpenRouter, Ollama, vLLM) against a scenario and score the
  trace it actually produces. Deterministic scripted agent for offline/CI use.
  Per-project agent endpoint config; API keys are redacted in responses.
- Scenarios persist their original spec (objective + vault + tools) so they are
  runnable live; `POST /api/projects/{id}/execute`.
- **Tabbed run view**: Overview / Findings / Recommendations / Compliance.

## [0.3.0] — 2026-06-20

### Added
- **Scenario library** — search/filter, upload (AgentLeak traces, AgentLeak
  specs, or ai4privacy records — auto-detected & converted), and importable
  packs (AgentLeak Bench + PII Probes). One-click run in the playground.

## [0.2.0] — 2026-06-20

First public release.

### Added
- **AgentRisk** density-normalized Risk Index scoring (GDPR Art. 9 / Québec Law 25).
- Six detector families (PII, secrets, healthcare, finance, HR, custom regex)
  across eight execution channels.
- Five compliance frameworks (GDPR, Law 25, NIST AI RMF, OWASP LLM Top 10, EU AI Act).
- Pluggable agent-framework registry (LangChain / LangGraph / CrewAI / AutoGen /
  OpenAI Agents + generic).
- Local platform: SQLite persistence (projects + runs), SDK client, compare/stats.
- Web GUI (React + shadcn/ui), CLI (`init/run/report/validate/scenarios/serve`).

[0.6.0]: https://github.com/yagobski/agentleak-oss/releases/tag/v0.6.0
[0.5.0]: https://github.com/yagobski/agentleak-oss/releases/tag/v0.5.0
[0.4.1]: https://github.com/yagobski/agentleak-oss/releases/tag/v0.4.1
[0.4.0]: https://github.com/yagobski/agentleak-oss/releases/tag/v0.4.0
[0.3.0]: https://github.com/yagobski/agentleak-oss/releases/tag/v0.3.0
[0.2.0]: https://github.com/yagobski/agentleak-oss/releases/tag/v0.2.0
