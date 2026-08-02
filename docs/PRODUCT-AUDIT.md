# AgentLeak product audit — 2026-08-02 (v0.9.0)

A full-project audit done hands-on: every claim below was verified against the
code, the test suite (731 passing), or a live exercise of the shipped product
(clean `pip install` of the wheel, the CLI first-run, the `watch()` SDK, and
the complete agent loop against the production instance at
`https://www.agentleak.org`). Written from the product seat: what the project
actually covers, what only pretends to, where the risks hide, and where the
unclaimed market ground is.

---

## 1. What the product actually is today

Scale: ~18,000 lines of Python, ~14,000 lines of TypeScript, 731 tests,
ruff + mypy clean, deployed at `www.agentleak.org` (public mode: free tier,
quotas, BYOK).

Four real surfaces, one engine:

| Surface | Entry point | State |
|---|---|---|
| CLI | `agentleak run / scan / report / history / compare / serve / skill` | Working, strong first-run |
| Python SDK | `agentleak.watch()` one-import; `AgentLeakClient`; 14 framework adapters + OTel | Working, one papercut |
| Platform (web) | 15 pages, ~50 API endpoints, admin console, quotas/BYOK | Working, deployed |
| Agent API | `llms.txt` → `/api/agent/onboard` → `selftest` → `improve` → `status` | Working end to end in 4 HTTP calls |

Engine coverage:

- **Detection**: 9 detector families (PII, secrets, finance, healthcare, HR,
  key-name, custom rules, Presidio NER, LLM-judge BYOK).
- **Channels**: the 6-channel trace model from the benchmark (tool_call,
  shared_memory, inter_agent_message, log, generated_file, final_output).
- **Scoring**: deterministic AgentRisk (0–1) + privacy score (0–100),
  severity levels L1–L4.
- **Compliance**: findings mapped to 14 frameworks / 22 controls (GDPR incl.
  art. 5/9/25/32, HIPAA, Quebec Law 25, PCI DSS, EU AI Act, OWASP LLM).
- **Red-team**: 32 attack classes (prompt injection, exfiltration families),
  scripted or live (BYOK).
- **Defenses**: runtime `sanitizer` + `internal_channel` guards (prevention,
  not just detection).
- **Scenarios**: 10 built-in (5 domains × leak/clean pair) + importable packs
  (AgentLeak Bench 36 scenarios, ai4privacy probes).
- **Distribution to agents**: `SKILL.md` + `agentleak skill` installer,
  `llms.txt` / `llms-full.txt` / `agents.md`, A2A agent card.

## 2. What genuinely works well (tested, not assumed)

1. **CLI first-run is excellent.** Fresh venv, wheel install, one command:
   `agentleak run --scenario healthcare_patient_summary` produces a readable
   report that demonstrates the product thesis in the terminal (final answer
   clean, internal channels leaking, CI verdict, 3 report files written).
   This is the best 60 seconds of the product.
2. **The agent loop is real.** Against production: onboard (1 call, key +
   quota back), selftest (RI + verdict + remediation hints + compliance),
   improve (delta vs. previous run). No browser, no human. Nothing else on
   the market does this today.
3. **The capture story exists.** `agentleak.watch()` wraps LangChain,
   LangGraph, CrewAI, Swarm/Agents SDK, Google ADK or plain Python in one
   context manager; 6 lines of code to a verdict. Plus OTel ingestion for
   everyone else.
4. **Deterministic scoring is a real differentiator** and it holds in
   practice: same trace, same score; regressions in CI are meaningful.
5. **Ops posture is solid**: local-first, no telemetry, BYOK so the free
   tier costs ~0, loopback-only container behind TLS, quotas and per-IP
   throttles on the public instance.

## 3. Phantom features and broken funnels (the honest list)

> **Status update (same day):** items 1-4, 6, 7 and three shadow zones were
> fixed in the P0/P1 pass that followed this audit; each fix is marked inline
> and covered by tests. Item 5 is parked by decision. Item 8 turned out not to
> be a real defect and is corrected below.

Ordered by damage.

1. **[FIXED] `pip install agentleak` did not work: the package was not on PyPI.**
   Every funnel ended here: SKILL.md, docs/install.md, llms.txt, the site,
   the CLI docs. An agent or developer that follows our own instructions
   fails at step 1. *This is the single highest-impact fix available.*
2. **[FIXED] The CI gate was sold as a "required status check" with no
   published GitHub Action.** It worked via exit code in any CI, but the
   marketing promise implied `uses: agentleak/...@v1`. Gap between story
   and artifact.
3. **[FIXED] `agentleak scan <file>` failed on a single file** ("Not a directory").
   The first instinct of every developer, scanning one suspicious file, hit a
   wall. Directory-only was an arbitrary limitation.
4. **[FIXED] `watch()` shouted a 401 at first-time users.** With no platform
   configured it still attempted submission and printed
   `platform submission failed: 401`: a local-first product with
   cloud-second behavior.
5. **A2A agent-card fetch endpoint has no UI and no consumers.**
   `/api/projects/{pid}/agent-card/fetch` exists server-side only. A2A has
   no meaningful adoption yet; this is speculative surface to park, not
   maintain.
6. **[FIXED] The 36 benchmark scenarios were one hidden import away.**
   Built-ins are 10; the bench pack had to be imported through a UI affordance
   most users would never find. The number we advertise should be one command.
7. **[FIXED] The defenses module shipped but was unreachable.**
   `agentleak.defenses` (sanitizer + internal-channel guard) existed with docs,
   but zero CLI exposure. Shipped code without a door.
8. **[NOT REPRODUCIBLE] Contributor papercut with the editable install.**
   The `agentleak` entry point failed outside the repo directory in the
   auditor's environment. Re-tested afterwards with a fresh `pip install -e .`
   in a clean venv: it works from anywhere. The original symptom was a stale
   local venv, not a repo defect. No change needed.

**How the fixed items were resolved:** release pipeline that verifies the
wheel before publishing (`docs/releasing.md`); official GitHub Action
(`action.yml` + `scripts/gh_gate.py`) with severity-graded PR annotations;
`scan_file()`/`scan_path()` for single files; opt-in platform submission in
`watch()`; `scenarios --packs` and `run --pack` for the benchmark; and
`agentleak redact` as the door into the defenses module.


## 4. Shadow zones (real risks, currently unlit)

- **[FIXED] Account recovery.** `agentleak admin reset-password` /
  `admin list-users` give the operator recovery from the machine that owns
  the database, revoking every session. No mail infrastructure invented.
- **Single-process state.** Quotas and rate limits are in-memory; SQLite is
  the store. Correct at current scale, breaks silently at multi-replica.
  Now **documented** in `deploy/README.md` section 7, with the explicit rule:
  do not add a second replica until limits are shared state.
- **Detection quality is unpublished.** We claim severities and a score, but
  no public precision/recall against a labeled set. For a *scoring* product,
  credibility is the product. The ai4privacy probes pack is already in the
  repo — measure and publish.
- **[FIXED] LLM-judge silently absent made quieter reports.** BYOK means no
  key, so the judge tier is skipped and a "Pass" without it could read as
  stronger than it was. Reports now carry `detection = {mode, tiers, degraded}` in the JSON, the CLI
  and the Action summary, so a regex-only Pass is visibly a weaker claim.
- **Version skew risk.** The live server routinely lags the repo; nothing
  alerts on it. (At audit time: server behind by 5 commits.)

## 5. Market position — where the unclaimed ground is

Adjacent categories and why they do not cover this:

| Category (examples) | What they do | What they miss |
|---|---|---|
| Runtime guardrails (Lakera, LLM Guard, NeMo, Prompt Security) | Filter inputs/outputs live | Internal channels invisible; no reproducible score; not a CI artifact |
| Red-team tooling (garak, PyRIT, promptfoo) | Attack prompts/models | Not privacy-trace forensics; output-centric; no deterministic privacy score |
| LLM observability (LangSmith, Langfuse, Phoenix) | Capture and display traces | No privacy scoring, no gate, no severity/compliance mapping — they are our *complement* (we ingest OTel) |
| DLP (Presidio, Nightfall) | Find PII in text | No agent/trace model, no channels, no score, no agent API |
| Agent-security platforms (Zenity, Lasso, Knostic) | Enterprise runtime governance | Closed, top-down, not dev-first, not local-first, no published benchmark grounding |

**Three things nobody else has, and where to capitalize:**

1. **Agents that test themselves.** The llms.txt → onboard → selftest →
   improve loop plus skill-based distribution makes AgentLeak *agent-native
   QA*. As autonomous agents proliferate, "the tool your agent uses on
   itself before shipping" is a category with no incumbent. Double down.
2. **A deterministic, benchmark-grounded privacy score as a CI artifact.**
   Guardrails give opinions at runtime; we give reproducible evidence in the
   pipeline. The paper (arXiv:2602.11510) is the moat — keep every claim
   traceable to it.
3. **Internal-channel forensics.** The 2.6× internal-leak / 45.9% missed-by-
   output-audit numbers are the wedge message. No adjacent tool audits
   shared memory, inter-agent messages, logs and generated files as a unit.

## 6. Prioritized roadmap (product recommendation)

**P0 — Repair the funnel (days, do first):**

| # | Item | Why |
|---|---|---|
| P0.1 | Publish to PyPI + release workflow (trusted publishing) | Every instruction we ship currently fails at step 1 |
| P0.2 | Official GitHub Action (`agentleak-privacy-gate`) with PR annotations | Makes the CI-gate story an artifact instead of a promise |
| P0.3 | DX papercuts: single-file `scan`, silent-local `watch()`, one-command bench-pack import, defenses in CLI help | Each is <1 day and each is a first-session wall |

**P1 — Capitalize on the unique ground (1–2 weeks):**

| # | Item | Why |
|---|---|---|
| P1.1 | Public agent trust page: `agentleak.org/a/<agent>` badge (latest verified selftest score + date) + README badge | Turns every tested agent into distribution; no competitor equivalent |
| P1.2 | MCP server mode (`agentleak mcp`): scan/selftest/improve as MCP tools | Meets agents where they already are; MCP logo is already on our wall |
| P1.3 | Publish the skill to agent-skill registries; keep SKILL.md canonical | Completes the agent-native distribution loop just built |

**P2 — Credibility and retention:**

| # | Item | Why |
|---|---|---|
| P2.1 | Published detection-quality benchmark (precision/recall vs. labeled probes, repro command) | A scoring product lives on measured trust |
| P2.2 | Tier badges on every report (which detectors actually ran) | Closes the "quiet Pass" risk honestly |
| P2.3 | Continuous watch mode (sample % of production runs → trend + threshold alert) | From one-shot audit to retention loop |
| P2.4 | Password reset + documented single-node ceilings | Hosted hygiene before growth, not after |

**Park (do not spend on):** A2A card fetch (until A2A has real adoption),
"plugins" naming in the red-team catalog (implies extensibility that does not
exist — rename or build), further marketing-site iterations (the site is now
ahead of the product funnel; the funnel is the constraint).

---

*Method note: findings marked "tested" were exercised directly during this
audit — live API calls against production, a clean wheel install in a fresh
venv, and the SDK/CLI flows above. Everything else is from code inspection at
commit `609d609`.*
