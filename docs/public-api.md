# AgentLeak Cloud — Public API for Autonomous Agents

AgentLeak Cloud is a **free, self-serve privacy-testing service for AI agents**.
An agent can onboard itself, test its own privacy behavior, and get
machine-actionable fixes — with no human, no dashboard, and no browser.

- **Base URL (hosted):** `https://agents.fomox.com`
- **Free detection is genuinely free.** Regex / Presidio / entropy / de-obfuscation
  run on the platform at no cost to you.
- **LLM tiers are bring-your-own-key (BYOK).** The LLM-judge detector and live
  agent runs call a paid model — supply *your* OpenRouter/OpenAI key for those.
  The platform never bills its own key against your runs.
- **Free-tier quota.** A generous monthly ceiling per account (see
  `GET /api/meta` → `free_tier.monthly_quota`). Self-host for unlimited use.

Everything below is a plain HTTP call — copy/paste into any language.

Machine-readable discovery is available at `https://agents.fomox.com/llms.txt`,
normative autonomous-agent instructions at `/agents.md`, the integrated API
reference at `/docs/api`, and the OpenAPI schema at `/openapi.json`. Swagger
still exists at `/api/docs`, but `/docs/api` is the recommended human-readable
API guide.

---

## 1. Onboard in one call

```bash
curl -sX POST https://agents.fomox.com/api/agent/onboard \
  -H 'content-type: application/json' \
  -d '{"email":"you@example.com","agent_name":"SupportBot"}'
```

Response (store the `api_key` — it is your ongoing credential):

```json
{
  "onboarded": true,
  "project_id": "proj_ab12…",
  "agent_name": "SupportBot",
  "api_key": "ak_9f8e…",
  "password": "…generated…",
  "free_tier": {"monthly_quota": 1000, "byok": true},
  "next_steps": { "…": "…" }
}
```

You may pass your own `password` to also sign in to the dashboard later; if you
omit it, a random one is generated and returned once.

All subsequent calls authenticate with the key, either header or body:

```
X-AgentLeak-Key: ak_9f8e…
```

---

## 2. Register your agent card (optional but recommended)

Declare identity, capabilities, and where your source lives so a code scan can
find it automatically.

```bash
curl -sX POST https://agents.fomox.com/api/agent/register \
  -H "X-AgentLeak-Key: $KEY" -H 'content-type: application/json' \
  -d '{"agent_card": {
        "name": "SupportBot",
        "description": "Handles support tickets",
        "capabilities": ["ticket_triage", "crm_lookup"],
        "source": {"type": "github", "repo": "acme/support-bot", "branch": "main"}
      }}'
```

---

## 3. Scan your source code (free)

Static privacy scan over your code — hardcoded secrets, PII in logs, sensitive
data sent to third parties, decomposed/obfuscated identifiers, quasi-identifier
correlation. Submit files inline, a zip, or let it re-scan the card's repo.

```bash
curl -sX POST https://agents.fomox.com/api/agent/code \
  -H "X-AgentLeak-Key: $KEY" -H 'content-type: application/json' \
  -d '{"source":"files","files":[
        {"path":"agent.py","content":"API_KEY=\"sk-live-…\"\nprint(user_ssn)"}
      ]}'
```

Returns an AgentRisk-style score, per-finding severity (L1–L4), and the rule/tier
that caught each one.

---

## 4. Test runtime behavior (free)

Submit a trace of what your agent actually did — or reference a built-in
scenario — and get a full leak analysis. Any OpenAI-style chat log
(`{"messages":[…]}`) is accepted and mapped onto channels automatically.

```bash
curl -sX POST https://agents.fomox.com/api/selftest \
  -H "X-AgentLeak-Key: $KEY" -H 'content-type: application/json' \
  -d '{"trace": {"agent_name":"SupportBot","events":[
        {"channel":"tool_call","source":"agent","target":"crm",
         "content":{"ssn":"123-45-6789"}},
        {"channel":"final_output","content":"All set!"}
      ]}}'
```

The response includes `risk_index`, `privacy_score`, per-channel findings, a
compliance posture (GDPR / Law 25 / HIPAA / OWASP LLM / …), and
`remediation_hints` — structured, machine-readable fixes (some include
ready-to-paste code).

---

## 5. Self-improvement loop

`POST /api/agent/improve` runs the same analysis **and** compares it to your
previous run, returning a `delta` and prioritized `next_steps`:

```bash
curl -sX POST https://agents.fomox.com/api/agent/improve \
  -H "X-AgentLeak-Key: $KEY" -H 'content-type: application/json' \
  -d '{"scenario_id":"finance_loan_review"}'
```

`GET /api/agent/status` returns one consolidated view: latest run, score
progression, compliance posture, latest code scan, and the current next steps.

A minimal autonomous loop:

```
onboard → register → (code scan + selftest) → improve → status → fix → repeat
```

The Python `AgentSelfClient` (in the `agentleak` package) wraps this loop.

---

## Bringing your own LLM key (for paid tiers)

The LLM-judge detector and live agent runs are BYOK. Provide your endpoint per
request (`base_url`, `model`, `api_key`) or once per account via
`POST /api/auth/model-key`. Without a key, those tiers are skipped and you still
get the full free regex/Presidio/entropy analysis.

## Discovery & limits

- `GET /api/meta` — capabilities, agent-API map, and `free_tier` limits.
- `GET /api/limits` — your account's current usage and quota reset time.
- `GET /.well-known/agent-card.json` — discovery metadata for AgentLeak's
  documented custom HTTP+JSON binding. It does not claim support for the
  standard A2A message/task transport; clients should follow `/openapi.json`.

## Fair use

The free tier is rate-limited per IP and quota-limited per account to keep the
service available to everyone. Need more? [Self-host the OSS engine](../README.md)
for unlimited local use, or run the same image in your own VPC.
