# Autonomous agents — self-registration, code scans, and the improvement loop

AgentLeak is built so an **agent can test itself** — no human, no browser
session. Everything below authenticates with the project's API key
(`ak_...`, generated once in *Project → Connect* or via
`POST /api/projects/{pid}/api-key`) sent as the `X-AgentLeak-Key` header.

The loop an autonomous agent runs:

```
register (agent card) → scan code → improve (trace) → read next_steps → fix → improve again
```

## 1. Agent card (A2A / Nasiko compatible)

An agent declares its identity with an **agent card** — the same
`AgentCard.json` document used by A2A control planes such as Nasiko. The
card can also declare the agent's **code source** (GitHub repo or archive)
so AgentLeak can statically scan it.

```json
{
  "name": "support-bot",
  "description": "Handles support tickets",
  "capabilities": ["ticket_triage", "crm_lookup"],
  "tags": ["support"],
  "examples": ["triage this ticket"],
  "input_mode": "text",
  "output_mode": "text",
  "agent_protocol_version": "a2a-v1",
  "endpoints": {"/chat": "Chat endpoint", "/health": "Health check"},
  "source": {"type": "github", "repo": "acme/support-bot", "branch": "main"},
  "privacy": {"declared_data_types": ["email", "phone_number"]}
}
```

Register it (agent-side, key auth):

```bash
curl -X POST http://127.0.0.1:8000/api/agent/register \
  -H 'X-AgentLeak-Key: ak_...' -H 'content-type: application/json' \
  -d '{"agent_card": { ... }}'
```

Official A2A cards are accepted too (`skills`, `protocolVersion`,
`capabilities` as a flag object, `provider.organization` are all folded in).
The platform can also **fetch** a card from a live agent's well-known
endpoint (`/.well-known/agent-card.json`, `/.well-known/agent.json`,
`/AgentCard.json`) via *Project → Card & Code → Fetch*.

## 2. Static code scan

Before the agent even runs, its source can leak: hardcoded secrets, PII in
fixtures/prompts, sensitive variables in logs, committed `.env` files,
sensitive fields sent to external services. The scan runs the **same 3-tier
hybrid pipeline as trace analysis** — regex detectors, Presidio
(`detection.presidio.enabled`), and the LLM-judge (`detection.mode: hybrid`)
for paraphrased/semantic leaks — plus four code-specific layers:

- **generated identifier lexicon** — sensitive stems derived from the
  AgentRisk taxonomy + EN/FR synonyms, extensible via `extra_identifiers`;
- **entropy analysis** (detect-secrets style) — unknown-format secrets;
- **de-obfuscation** — decomposed PII (`"123" + "-45-" + "6789"`,
  `123 45 6789`, dotted card numbers validated by Luhn);
- **quasi-identifier correlation** — several benign-looking PII types in one
  file = re-identification risk (GDPR Rec. 26).

Each finding carries its **tier** and **confidence**, so the report stays
auditable. Scan three ways:

```bash
# agent-side: re-scan the source declared in the agent card
curl -X POST http://127.0.0.1:8000/api/agent/code \
  -H 'X-AgentLeak-Key: ak_...' -d '{}'

# or explicit: github | zip (base64) | inline files
curl -X POST http://127.0.0.1:8000/api/agent/code \
  -H 'X-AgentLeak-Key: ak_...' -H 'content-type: application/json' \
  -d '{"source": "github", "repo": "acme/support-bot", "branch": "main"}'

# CLI — no server needed; --mode standard|hybrid adds Presidio / LLM-judge
agentleak scan ./my-agent --fail-under 90
agentleak scan --repo acme/support-bot --mode hybrid
```

Server-side scans honour the project's detection settings (detector toggles,
custom rules, hybrid mode). Findings carry the AgentRisk **L1–L4 levels**;
snippets are always **redacted** — raw secrets are never persisted. GitHub
fetches are an explicit opt-in network call (stdlib urllib); everything else
is fully local.

## 3. The self-improvement loop

`POST /api/agent/improve` = one loop step: analyze a trace, auto-save the
run, and return the report **plus** `delta` (vs the previous run) and
prioritised, machine-actionable `next_steps`:

```json
{
  "privacy_score": 38, "risk_index": 0.62, "passed": false,
  "delta": {"previous_run_id": "run_...", "delta_score": -4, "direction": "regressed"},
  "next_steps": [
    {"kind": "runtime_leak", "priority": "critical", "channel": "tool_call",
     "data_types": ["ssn"], "action": "Strip or mask sensitive fields…", "code_fix": "..."},
    {"kind": "compliance", "priority": "high", "framework": "gdpr",
     "action": "Resolve 3 at-risk control(s) for GDPR (EU 2016/679)."},
    {"kind": "code_scan", "priority": "high", "action": "Fix 5 static finding(s)…"}
  ]
}
```

`GET /api/agent/status` answers "where do I stand?" in one call: latest run,
score progression, compliance posture, latest code scan, and next steps.

## 4. Python client for agents

```python
from agentleak import AgentSelfClient

me = AgentSelfClient(api_key="ak_...")          # base_url defaults to localhost:8000
me.register(card={
    "name": "support-bot",
    "capabilities": ["ticket_triage"],
    "source": {"type": "github", "repo": "acme/support-bot"},
})
me.scan_code()                                   # scans the declared repo

step = me.improve(trace)                         # one loop iteration
while not step["passed"]:
    for todo in step["next_steps"]:
        apply_fix(todo)                          # the agent acts on the hints
    step = me.improve(new_trace())

print(me.status()["progression"])                # {"total_delta": +42, ...}
```

## Endpoint reference (key auth — `X-AgentLeak-Key`)

| Method & path | Purpose |
| --- | --- |
| `POST /api/agent/register` | Upsert this agent's card |
| `GET /api/agent/card` | Read the stored card |
| `POST /api/agent/code` | Static scan (github / zip / files; empty body = card source) |
| `POST /api/selftest` · `/api/selftest-header` | One self-test (report + passed/compliant) |
| `POST /api/agent/improve` | Self-test + delta + prioritised next steps |
| `GET /api/agent/status` | Latest run, progression, posture, code scan, next steps |

Session-authenticated equivalents for the platform UI:
`GET/PUT/DELETE /api/projects/{pid}/agent-card`,
`POST /api/projects/{pid}/agent-card/fetch`,
`POST /api/projects/{pid}/code-scan`, `GET /api/projects/{pid}/code-scans`,
`GET /api/code-scans/{sid}` — all surfaced in the **Card & Code** tab.
