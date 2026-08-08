# Changelog

All notable changes to AgentLeak OSS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.11.2] - 2026-08-08

### The trust page now looks like the site it is served from

- **Rebuilt in agentleak.org's own design language** — its palette, its two
  typefaces, its spacing and its mono-uppercase labels. The page is served by the
  package rather than the marketing site, so the tokens are transcribed rather
  than imported; a self-hosted install has no marketing stylesheet to borrow
  from. Dark by default because that is the site's default, with the site's own
  light palette for a light-mode reader.
- The fonts already travelled in the wheel for the product UI, so the page uses
  those rather than fetching any. A build without them falls back to the system
  grotesque instead of failing to load.
- `badge_state` now returns a `tone` alongside its colour. The badge keeps the
  shields palette so it sits naturally beside other README badges and the page
  uses the site's — one decision, two renderings, so the two can never disagree
  about whether a run passed.
- **The trend chart was understating real change.** A fixed 0–100 axis is right
  — auto-scaling turns a wobble between 97 and 99 into a cliff — but squeezed
  into a 64px sparkline a genuine thirty-point climb drew as a flat line, which
  is the same lie in the other direction. The axis is now drawn, labelled and
  given room.

## [0.11.1] - 2026-08-08

### The page the badge points at

- **`/a/<slug>` now serves a real page.** 0.11.0 shipped the badge and the JSON
  but no page, so the URL the publish endpoint handed out — the one URL the badge
  exists to make checkable — landed on a 404. It is server-rendered in the
  package rather than the marketing site, so the data and the honesty rules stay
  together, a crawler or link preview sees the actual verdict instead of an empty
  shell, and anyone self-hosting gets a working link rather than a dead one.
- The page carries its own caveats in words, not just colour: stale scores,
  degraded runs, and a standing note that this is the latest run rather than the
  best one. It shows the verdict, the date, the tiers and a trend — never a
  finding.
- The trend is drawn on a fixed 0–100 axis. An auto-scaled one turns a wobble
  between 97 and 99 into a cliff, which is the graph contradicting the numbers
  printed beside it. Fewer than two runs draws no line at all, because a line
  through one point invents a direction nobody measured.

### Fixed

- **`AGENTLEAK_DB` is now honoured.** It was set in the Docker image and read by
  nothing: `Store()` looked only at `AGENTLEAK_HOME`. Production was correct by
  way of a second variable, but a deployment that set only the documented one
  would have written its database to a container-local path and lost every
  account, run and published page on the next rebuild — silently, with the
  setting meant to prevent that sitting there looking authoritative.
- The version-consistency test imported `tomllib`, which is stdlib only from 3.11
  while the package supports 3.10 — so it failed on the oldest Python we promise
  to support, which is exactly where a mismatch is least likely to be noticed.

## [0.11.0] - 2026-08-08

### A score others can check, and one that keeps being checked

- **Public trust page and README badge** (`/a/<slug>`, `/a/<slug>/badge.svg`).
  A badge an agent awards itself is worth nothing; what makes this worth
  embedding is that AgentLeak measured the number and anyone can follow the link.
  Opt-in and reversible — a run never publishes anything as a side effect.
- **The badge is built to refuse three specific lies.** A score older than 30 days
  goes grey and shows its *age* rather than its number, because the number
  describes code that may no longer exist. A degraded run can never show the
  passing colour, since a pass from the pattern tier alone is a narrower claim.
  And the badge always shows the latest run, never the best one.
- **The public page shows the verdict, never the evidence.** Findings name real
  values from private data. A stranger sees the score, the date, the tiers that
  ran and a trend line — enough to judge the claim, not enough to reconstruct a
  run. The SVG is self-contained, because GitHub's image proxy renders anything
  needing a script or an external font as a broken image.
- **`Monitor` — continuous watch** (`agentleak.Monitor`). Sampled scoring of
  production runs with a rolling trend and threshold alerts, in-process, no
  thread and no timer. Designed around the two ways a monitor makes itself
  useless: it stays quiet on single bad samples and flat lines so nobody mutes
  it, and it reports a never-before-seen severity immediately rather than waiting
  for a trend. The baseline tracks improvement but never decays toward a
  regression — a baseline that follows a slow slide is what hides the slide.
- An exception thrown by an alert callback is swallowed. Your pager being down is
  not a reason for the agent to stop answering users.

### Agent-native: coding agents can check their own work

- **`agentleak mcp` — the engine as MCP tools** (`agentleak[mcp]`). A coding
  agent will not shell out to a CLI or chain four HTTP calls on a hunch; it calls
  tools. Four of them now: `privacy_preflight`, `privacy_scan_code`,
  `privacy_check_trace`, `privacy_redact`. Local by default — no account, no key,
  no network — because the teams who most need this are the ones whose traces
  cannot leave the building. Kept behind an extra so the core stays at four
  dependencies.
- **`preflight` reports what is *new* since the last check.** A score on its own
  changes nothing: an agent reads the number and moves on. Being told "this
  finding is new since you last looked" is what makes it iterate. The comparison
  comes from a local `.agentleak/history.jsonl` holding redacted snippets only.
- **Finding identity ignores the line number** (`core.memory`). Keying on
  `file:line` would turn every reformat into a page of false "new" findings, and
  a tool that cries wolf on every commit gets muted within a day. Identity is
  `(file, rule, fingerprint of the matched value)`. Moving a secret between files
  reads as one fixed plus one new — the rarer case, and arguably the honest one.
- **An empty trace is refused rather than scored.** `Trace.from_dict` accepts a
  payload with no events and yields a run that scores a confident 100/100. An
  agent sending a malformed trace would read that as clean: the exact false pass
  this tool exists to catch, committed by the tool itself.
- **Findings are deduplicated by identity.** Two detectors can land on the same
  value with the same rule; left alone an agent reads one problem as two, and the
  counts disagree with the deltas that are keyed by id.
- Discovery paths all say the same thing now: `SKILL.md`, `llms.txt` and
  `docs/mcp.md`. A tool an agent cannot find is a tool that does not exist.


## [0.10.0] - 2026-08-02

### Distribution and CI (closes the P0 gaps from the 2026-08 product audit)

- **Publishing to PyPI is real and self-verifying.** `.github/workflows/release.yml`
  builds once, runs `twine check --strict`, refuses a tag whose version disagrees with
  `pyproject.toml`, then installs the built wheel into a clean venv and exercises the
  actual first-run path (`version`, `scenarios --packs`, a scenario run that writes a
  report, the packaged `SKILL.md`, a single-file `scan` that finds a secret) *before*
  publishing. The publish step is no longer `continue-on-error`: a silent failure is
  exactly how `pip install agentleak` ends up broken while every doc claims otherwise.
  A manual dry-run mode runs build+verify without publishing. See `docs/releasing.md`.
- **Official GitHub Action** (`action.yml` + `scripts/gh_gate.py`). The "privacy is a
  required status check" story now has an artifact behind it: three modes (captured
  trace, scenario from a benchmark pack, static code scan), annotations graded by
  severity (L4/L3 → error, L2 → warning, L1 → notice) landing on `file:line` for scans
  and naming the leaking channel for traces, a readable job summary, typed step outputs
  (`score`, `risk-index`, `verdict`, `findings`, `report`), and an exit code that blocks
  the merge. Dogfooded by a new CI job that asserts the gate blocks a leaking run and
  passes a clean one. Starting point: `examples/workflows/privacy-gate.yml`.

### Developer experience (first-session walls)

- **`agentleak scan` accepts a single file** (and a zip), not just a directory. New
  `scan_file()` / `scan_path()`; an explicitly named file is scanned whatever its
  extension, because the user pointed at it on purpose.
- **`watch()` is local-first for real.** Naming a project no longer implies consent to
  talk to a server: submission happens only when a platform is configured (`base_url`,
  `AGENTLEAK_PLATFORM_URL`, or `submit=True`). A purely local run no longer prints a
  connection error at someone who never asked for one.
- **The published benchmark is one command away**: `agentleak scenarios --packs`,
  `--pack <id>` to list, and `run --pack agentleak_bench --scenario <id>` to execute.
  The 36 benchmark scenarios previously required a UI-only import.
- **Defenses have a door**: `agentleak redact` exposes the sanitizer that shipped with
  documentation but no entry point (file or stdin, six redaction styles).

### Scenario coverage: prompt-injection exfiltration

- **New `agentdojo_exfil` pack — 100 prompt-injection exfiltrations** derived from
  [AgentDojo](https://github.com/ethz-spylab/agentdojo) (NeurIPS 2024 Datasets &
  Benchmarks, MIT). Nothing about the agent is misconfigured: it runs the user's task,
  reads data it was right to read, and one of those tool responses carries a planted
  instruction. From there it keeps using its legitimate tools on the attacker's behalf
  — look up the 2FA code, mail it out, delete the evidence — while the answer shown to
  the user stays clean. Balanced across all four suites (banking / slack / travel /
  workspace), 10 injection goals, 41 user tasks.
- **New `agentdojo` upload format.** Trajectories are replayed against the real
  upstream environment rather than paraphrased, so the observations are what the agent
  actually saw. Events carry `prompt_injection` on the response that delivered the
  attack and `attacker_controlled` / `exfiltration` on the calls that followed, so a
  report can name where the trust boundary broke.
- **Canaries split across tiers.** These payloads are concrete values, so structured
  secrets (passport, 2FA code, card number) land in the `realistic` tier and prose (a
  private message, an email body) in `semantic` — a report shows honestly how much of
  the evidence rests on exact ground truth rather than pattern matching. Without that
  ground truth 20 of the 100 score a clean Pass and 64 would not block a CI gate; with
  it, none pass.
- **Pack extractors are in the repo** (`scripts/packs/`, with a README) rather than
  being lost build steps. Both derived packs rebuild byte-identically from their
  upstream sources, and the scripts document what was taken, what was reshaped, and
  which upstream cases were dropped — including AgentDojo's `banking/injection_task_1`,
  whose ground truth resolves "the IBAN of the pizza dinner companion" to the literal
  string `"me"`. Two rules are enforced by the extractors and re-checked by the tests
  against the shipped files: a canary must be data the agent actually read, and a
  canary that is not a secret is never invented — a false Fail is the same defect as a
  false Pass, pointing the other way.

### Scenario coverage: contextual integrity

- **New `privacylens_ci` pack — 120 contextual-integrity scenarios** derived from
  [SALT-NLP/PrivacyLens](https://huggingface.co/datasets/SALT-NLP/PrivacyLens)
  (NeurIPS 2024 Datasets & Benchmarks, CC-BY-4.0). An agent pulls private context in
  through its tools, then acts toward a recipient the norm says must not receive it.
  Curated for balance rather than volume: all three provenance sources
  (crowdsourcing / regulation / literature), four outbound channels, 99 distinct
  recipients, 115 distinct data types. This is the first pack whose leaks are *facts*
  ("Bob missed work for a court date") rather than *patterns* — the gap between
  "no PII detected" and "a privacy norm was broken".
- **New `privacylens` upload format.** `agentleak/scenarios/convert.py` replays a
  ReAct trajectory faithfully — one `tool_call`/`tool_response` pair per step,
  attributed to the toolkit that served it — then models the outbound act the
  scenario exists to describe.
- **Ground truth travels with the scenario.** Measured on this pack, the regex tier
  alone scores most scenarios a clean 100/100, so shipping the traces bare would have
  manufactured false Passes. Each scenario carries the dataset's own
  `sensitive_info_items` as **semantic canaries** (exact match, confidence 1.0), which
  makes it score deterministically with no LLM tier and no API key: `main1` goes from
  Pass 100/100 to Fail 0/100. Canaries are now persisted with imported scenarios
  (`scenarios.canaries`, additive migration) and used when the platform analyzes them,
  so a pack scenario scores the same in the GUI as in the CLI.
- **Pack licences are displayed, not just stored.** `source_url`, `license` and
  `attribution` are surfaced by `agentleak scenarios --packs`,
  `GET /api/scenario-packs` and the Scenarios page — CC-BY-4.0 requires attribution
  wherever the data appears.

### Honest reporting

- **Every result states which detection tiers produced it.** Reports carry
  `detection = {mode, tiers, degraded}`, surfaced in the JSON, in the CLI, and in the
  Action's job summary. A "Pass" from regex alone no longer reads like a "Pass" from
  the full hybrid pipeline — for a scoring product that distinction is the product.

### Operations

- **`agentleak admin reset-password` / `admin list-users`** — operator-side account
  recovery from the machine that owns the database (no mail infrastructure, no emailed
  reset link). All sessions for the account are revoked by the reset.
- `deploy/README.md` documents account recovery and the **known ceilings of the
  single-node deployment** (in-memory quotas and rate limits are correct for one
  replica only; scale vertically until they are shared state).

### Agent-native distribution

- **`agentleak skill`** (`agentleak/skill/`) — registers AgentLeak as an agent skill so
  coding agents (Claude Code, OpenClaw, Cursor, Windsurf, Codex CLI) discover the tool on
  their own instead of having to be told how to use it. Auto-detects installed agents,
  writes `<agent>/skills/agentleak/SKILL.md`, and refuses to clobber an edited skill file
  without `--force`. Supports `--target`, `--path`, `--dry-run`, `--uninstall`, `--print`.
- **`SKILL.md`** at the repository root — the canonical skill text, shipped as package data
  and installable via `npx skills add`. A test asserts the root copy and the packaged copy
  cannot drift apart.
- **`docs/install.md`** — a paste-into-your-agent installer: the agent reads it, installs
  AgentLeak, verifies with a demo scan, registers the skill and reports back.
- Covered by `tests/test_skill.py` (23 tests).

### Detection quality (0.9.0)

Findings from an end-to-end dogfood of a real LangGraph coordinator-worker
agent. All changes ship with regression tests (`tests/test_improvements.py`).

**Breaking (behavioural):** the new key-name detector is on by default and
raises recall, so traces that previously scored clean may now report findings.
Anyone with a wired CI privacy gate should re-baseline after upgrading.

### Added
- **Key-name-aware detector** (`detectors/keyname.py`, config flag `keyname`,
  on by default) — flags values carried by sensitive field names (`diagnosis`,
  `medication`, `ssn`, `account_number`, `salary`, `address`, …) even when no
  dictionary recognises the value. Closes the main recall gap on realistic,
  unseen PII/PHI leaked through internal channels.
- **Degraded-run signalling** — when a requested detection tier (Presidio,
  LLM-judge) cannot run because a dependency or API key is missing, the run is
  now flagged `degraded` with explicit `warnings` in the report JSON and a
  prominent CLI banner (shown even under `--quiet`). A run that could not fully
  check is never silently reported as a clean pass. (`core/runner.py`,
  `core/report.py`, `cli.py`)

### Improved
- **Healthcare recall** — added common oncology conditions (carcinoma,
  colorectal, melanoma, lymphoma, metastatic, …) and chemotherapy agents
  (FOLFOX, oxaliplatin, cisplatin, paclitaxel, …); the NAM/health-identifier
  shape now tolerates spaces, hyphens and an optional `NAM` label
  (`NAM TREM 8842 0197`). (`detectors/healthcare.py`)

### Fixed
- **Secret-assignment false positives** — reading a credential from the
  environment (`api_key = os.environ.get("KEY")`) and passing an ALL-CAPS
  constant reference (`api_key=API_KEY`) are no longer flagged as hardcoded
  secrets. Real quoted literals and lowercase in-trace secrets are still
  caught. Removes the dominant code-scan false positive. (`detectors/secrets.py`)

### Added

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

[0.11.2]: https://github.com/yagobski/agentleak/releases/tag/v0.11.2
[0.11.1]: https://github.com/yagobski/agentleak/releases/tag/v0.11.1
[0.11.0]: https://github.com/yagobski/agentleak/releases/tag/v0.11.0
[0.10.0]: https://github.com/yagobski/agentleak/releases/tag/v0.10.0
[0.6.0]: https://github.com/yagobski/agentleak/releases/tag/v0.6.0
[0.5.0]: https://github.com/yagobski/agentleak/releases/tag/v0.5.0
[0.4.1]: https://github.com/yagobski/agentleak/releases/tag/v0.4.1
[0.4.0]: https://github.com/yagobski/agentleak/releases/tag/v0.4.0
[0.3.0]: https://github.com/yagobski/agentleak/releases/tag/v0.3.0
[0.2.0]: https://github.com/yagobski/agentleak/releases/tag/v0.2.0
