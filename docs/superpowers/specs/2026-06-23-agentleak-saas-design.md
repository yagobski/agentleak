# AgentLeak Cloud — SaaS Design

> **Status:** Design / brainstorm — not yet approved for implementation.
> **Date:** 2026-06-23
> **Owner:** faouzi
> **Built on:** the AgentLeak OSS engine (`agentleak-oss`, v0.6.0)

---

## 1. One-line positioning

**The compliance & debugging layer for AI agents.** Companies connect their
agents and get two things continuously: (1) **proof** their agents don't leak
regulated data (GDPR, Québec Law 25, EU AI Act, HIPAA-style PHI), and (2) the
**exact leak path** when they do — which agent, which channel, which hop — so
engineers can fix it.

The OSS tool already produces a privacy report from a trace, scored with
AgentRisk, with leak-flow/topology debugging and a GDPR/Law 25 compliance map.
The SaaS turns that one-off local scan into a **continuous, multi-tenant,
auditable, certifiable** service.

---

## 2. The two buyers (dual value prop)

| | Compliance buyer | Engineering buyer |
|---|---|---|
| **Persona** | DPO / Legal / Security / CISO | AI/ML engineer, agent team lead |
| **Job** | Prove + document + certify agents handle regulated data correctly; produce audit evidence | Find a leak, trace it to the exact agent/channel/hop, fix it, prevent regression |
| **What they pay for** | Tamper-evident reports, compliance badge, audit trail, regulation-mapped scenario packs kept current | Leak-flow debugger, CI/CD gate, run history & trends, scenario authoring |
| **Existing OSS foundation** | Compliance frameworks (GDPR Art. 5/9, Law 25), reports | Leak paths + topology diagram, detectors, AgentRisk |

Selling to both is the wedge: engineers adopt bottom-up (free/OSS → team plan),
compliance pays top-down (certification, audit, SSO, residency).

---

## 3. Why SaaS, not just the OSS local tool

The OSS tool is one machine, one run, self-certified. The SaaS adds what an
organization actually needs:

1. **Continuous** — scheduled scans + CI/CD gate + regression detection, not a manual one-off.
2. **Collaborative** — orgs/teams/RBAC, shared run history, trends over time.
3. **Auditable & certifiable** — tamper-evident signed reports + immutable audit trail. *You cannot self-certify with a local tool* — this is the core reason compliance buyers pay.
4. **Always-current scenarios** — a managed library that tracks regulatory change (new Law 25 obligations, EU AI Act milestones), pushed to every tenant.
5. **Scale** — run thousands of scenarios in parallel via a worker fleet.
6. **Integrated** — Slack/email alerts, webhooks, ticketing, status badges.

---

## 4. The meta-privacy problem (and its resolution)

A privacy-compliance tool that uploads your agent's sensitive data to *our* cloud
is a hard sell to the exact buyer we want. We resolve this with a **hybrid
deployment model**, which is also the strongest differentiator:

- **AgentLeak Engine** (the OSS package) = the **data plane / runner**. It executes
  scenarios against the customer's agent and produces reports. It runs **either in
  our cloud or inside the customer's own VPC**.
- **AgentLeak Cloud** = the **control plane**: tenancy, auth, billing, scheduling,
  dashboards, certification, scenario distribution, alerting.
- **By default, only redacted artifacts leave the runner**: scores, findings with
  *redacted* values, channel risks, topology, leak paths (values already redacted
  in OSS via `redact_values`). **Raw matched values never sync** unless the tenant
  explicitly opts in.

Three deployment tiers:

| Tier | Where the agent + data live | What reaches AgentLeak Cloud |
|---|---|---|
| **Hosted** | Our cloud (EU/Québec region) | Everything (tenant-isolated, encrypted) |
| **Hybrid runner** | Customer VPC (self-hosted engine) | Redacted reports + scores only |
| **Air-gapped / BYO-key** | Customer VPC, customer LLM keys | Redacted reports only; optional export, no live sync |

The OSS "redact by default" behavior is the foundation that makes Hybrid credible.

---

## 5. Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           AgentLeak Cloud                 │
                    │            (control plane)                │
                    │                                           │
  Browser ───────▶  │  Web app (React/Vite SPA, shadcn shell)   │
                    │  API gateway (FastAPI, multi-tenant)      │
                    │  Auth/RBAC · Orgs/Teams · SSO             │
                    │  Scheduler · Billing · Alerts · Certs     │
                    │                                           │
                    │  Postgres (tenants, runs meta, audit)     │
                    │  Object store (reports, signed artifacts) │
                    │  Redis + job queue (run orchestration)    │
                    └───────────────┬───────────────────────────┘
                                    │  authenticated pull/push
                                    │  (assignments ↓ , redacted reports ↑)
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                        ▼
   ┌─────────────────┐   ┌─────────────────┐    ┌─────────────────────┐
   │ Cloud runner    │   │ Cloud runner    │    │ Customer VPC runner  │
   │ (AgentLeak      │   │ (AgentLeak      │    │ (self-hosted OSS     │
   │  engine worker) │   │  engine worker) │    │  engine, hybrid)     │
   └────────┬────────┘   └────────┬────────┘    └──────────┬──────────┘
            ▼                     ▼                         ▼
      customer agent        customer agent           customer agent
   (OpenAI-compat / SDK) (OpenAI-compat / SDK)    (inside their network)
```

**Reuse vs build:**

- **Reuse from OSS (the engine):** detectors, AgentRisk scoring (`core/`), live
  agent runner (`agent/`), leak flow & topology (`core/flow.py`), compliance
  mapping, reporters (JSON/MD/HTML). Package the engine as a **worker** that takes
  a job (project config + scenario) and returns a report. This is mostly already
  there — `POST /api/projects/{id}/execute` is the seam.
- **Build new for Cloud:** multi-tenancy, Postgres data layer (replacing local
  SQLite), auth/RBAC/SSO, org/team model, scheduler, job queue + worker pool,
  billing, certification/signing, audit log, alerting, scenario distribution,
  per-tenant dashboards & trends.

**Tech choices (recommended, overridable):**

- Keep the engine in **Python** (it already is) — wrap as a queue consumer.
- **Control-plane API:** extend the existing **FastAPI** rather than rewrite. Add
  tenant scoping middleware, move storage from SQLite → **Postgres** (the
  `core/store.py` layer is the abstraction point).
- **Frontend:** keep the existing React/Vite + shadcn shell; add org switcher,
  billing, team settings, trends.
- **Queue:** Redis + RQ/Celery, or a managed queue. Workers run the engine.
- **Object storage:** S3-compatible, region-pinned (EU + `ca-central` for Québec).
- **Auth:** email/password (already in OSS) + OAuth/SSO (Google, Microsoft, SAML)
  for the enterprise tier.

---

## 6. Core capabilities (what a tenant can do)

1. **Connect an agent** — OpenAI-compatible endpoint, or via the SDK
   (`@monitor`/`capture` already exist), or a hybrid runner in their VPC.
2. **Run** — on demand, on a schedule, or in CI. Pick scenario packs (industry +
   regulation specific) or upload custom scenarios.
3. **Debug** — leak-flow view: trace each secret from entry → agents → disclosure;
   topology diagram of the multi-agent system with leak-carrying edges by severity.
4. **Gate** — CI/CD check (`agentleak ci`) that fails a build if Risk Index or any
   L4 leak exceeds a tenant-set threshold.
5. **Certify** — generate a signed, timestamped compliance report mapped to
   GDPR / Law 25 / EU AI Act controls; export evidence bundle for auditors/DPO.
6. **Monitor** — dashboards (RI over time, per-agent, per-team), regression alerts
   to Slack/email/webhook when a previously-clean channel starts leaking.
7. **Govern** — audit log of who ran what, when; RBAC; data-residency control.

---

## 7. Data model (multi-tenant, sketch)

```
Organization 1───* Team 1───* Membership *───1 User
Organization 1───* Project (an agent under test)
Project       1───* Agent (multi-agent topology member)
Project       1───* Run ───1 Report (redacted artifact) ──* Finding
Organization  1───* ScenarioLibrary (built-in packs + custom + imported)
Organization  1───* ApiKey / RunnerToken (for CI + hybrid runners)
Organization  1───* Certificate (signed, immutable)
Organization  1───* AuditEvent (append-only)
Organization  1───1 Subscription (plan, usage, limits)
```

Every row carries `org_id`; all queries are tenant-scoped at the API boundary.
Runs/reports are **redacted by default**; raw values stored only with explicit
per-org opt-in and stricter encryption.

---

## 8. Security & compliance (the product must practice what it sells)

- **Tenant isolation** — `org_id` scoping enforced in a single data-access layer; row-level checks.
- **Encryption** — at rest (DB + object store) and in transit; per-tenant key option for enterprise.
- **Data residency** — EU and `ca-central` (Québec) regions; tenant chooses.
- **Redaction-first** — raw matched values never persisted by default (inherits OSS behavior).
- **BYO LLM keys** — customer keys used for live runs are encrypted, redacted in all responses (OSS already redacts `api_key` via `_safe_project()`), never logged.
- **Secret hygiene** — runner tokens scoped & rotatable; no secrets in URLs.
- **Audit trail** — append-only, exportable; underpins the certification claim.
- **Our own compliance posture** — SOC 2 path, DPA, sub-processor list, GDPR/Law 25 self-attestation using AgentLeak on our own agents (dogfooding = marketing).

---

## 9. Packaging & pricing (hypothesis)

| Plan | Audience | Includes | Price model |
|---|---|---|---|
| **OSS / Free** | Individual engineers | Local engine, all detectors, manual runs | $0 (drives adoption) |
| **Team** | Agent teams | Hosted runs, history/trends, CI gate, Slack/webhook alerts, 3 seats | Per-seat + usage (runs/scenarios) |
| **Business** | Companies w/ compliance needs | + SSO, scheduled scans, compliance reports, scenario packs by regulation, more seats | Per-seat + usage, higher limits |
| **Enterprise** | Regulated orgs | + Hybrid/VPC runner, data residency, signed certification + audit export, SAML, DPA, support SLA | Annual contract |

Usage meter = **runs × scenarios** (or scored events). Mirrors how the OSS engine
already counts events.

---

## 10. Phased roadmap

**Phase 0 — Foundations (multi-tenancy spine)**
- Postgres-backed store behind the existing `core/store.py` interface.
- Org/Team/User/Membership + RBAC; tenant-scoping middleware on the FastAPI app.
- Org switcher + team settings in the existing React shell.
- *Exit:* two orgs can use the same instance with full data isolation.

**Phase 1 — Hosted runs at scale (MVP for engineering buyer)**
- Job queue + worker pool running the existing engine; `execute` becomes async.
- CI/CD gate CLI (`agentleak ci`) authenticating with a runner token; threshold config.
- Run history, trends, leak-flow debugger already exist → expose per-tenant.
- *Exit:* a team connects an agent, runs scenarios in CI, sees trends + leak paths.

**Phase 2 — Compliance product (MVP for compliance buyer)**
- Signed, timestamped certification report + evidence bundle export.
- Append-only audit log; regulation-mapped scenario packs (GDPR/Law 25/EU AI Act).
- Scheduled scans + regression alerts (Slack/email/webhook).
- *Exit:* a DPO can pull an auditor-ready compliance certificate for an agent.

**Phase 3 — Hybrid / VPC runner (enterprise unlock)**
- Self-hosted engine that pulls assignments, pushes only redacted reports.
- Data-residency regions; SSO/SAML; per-tenant encryption keys.
- *Exit:* a regulated customer runs entirely in their VPC, syncing redacted results.

**Phase 4 — Scale & ecosystem**
- Scenario marketplace (industry/regulation packs, community contributions).
- Billing + usage metering + plan limits; self-serve upgrade.
- More agent-framework adapters (LangChain exists; add CrewAI, AutoGen, etc.).

---

## 11. Key differentiators

1. **Internal-channel auditing** — scores tool calls, shared memory, inter-agent
   messages, logs — not just the final answer (OSS core thesis).
2. **Leak-path debugging** — not just "you leaked," but *where it entered and how it
   propagated* across a multi-agent system.
3. **Hybrid privacy model** — redacted-only sync lets the most privacy-sensitive
   buyers use a cloud privacy tool without sending raw data.
4. **Regulation-mapped & current** — GDPR/Law 25/EU AI Act controls, updated centrally.
5. **OSS-led adoption** — engineers already trust the open engine; SaaS is the upgrade.

---

## 12. Open questions / decisions to confirm

1. **Primary launch buyer** — lead with the engineering (debug/CI) wedge or the
   compliance (certification) wedge for the MVP? *(Recommendation: engineering wedge
   first — faster adoption, OSS already does most of it; compliance in Phase 2.)*
2. **Hosting** — which cloud / managed Postgres / queue? Residency requirements?
3. **Auth/SSO scope for MVP** — email/password only at first, SSO in Phase 2/3?
4. **Certification legal weight** — is the "compliance certificate" a self-attestation
   aid (most realistic) or do we pursue a recognized standard/partner?
5. **Pricing meter** — runs×scenarios vs scored-events vs seats-only?
6. **Relationship to OSS** — open-core (engine OSS, cloud proprietary) — confirm.

---

## 13. Risks

- **Trust paradox** — a cloud privacy tool. *Mitigation:* hybrid runner + redaction-first.
- **Certification credibility** — claims must be defensible. *Mitigation:* tamper-evident audit trail; clear scope ("evidence aid," not legal guarantee unless partnered).
- **Regulatory drift** — frameworks change. *Mitigation:* centrally-managed scenario/control packs as a recurring value.
- **Build scope** — multi-tenancy + billing + workers is large. *Mitigation:* strict phasing; reuse the OSS engine wholesale as the worker.
```
