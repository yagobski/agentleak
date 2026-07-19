# Agent API

The Agent API lets an autonomous agent discover AgentLeak, register its
identity, scan authorized source code, submit runtime traces, and iterate on
machine-readable remediation steps without a browser session.

## Discover the service

```bash
BASE=https://agentleak.org
curl -fsS "$BASE/api/meta"
curl -fsS "$BASE/llms.txt"
curl -fsS "$BASE/.well-known/agent-card.json"
curl -fsS "$BASE/openapi.json" > openapi.json
```

Use OpenAPI as the authoritative request and response schema. `/llms.txt` is a
concise navigation index; `/llms-full.txt` is a self-contained context document.

## Onboard and protect the key

```bash
curl -sS -X POST "$BASE/api/agent/onboard" \
  -H 'content-type: application/json' \
  -d '{"email":"owner@example.com","agent_name":"SupportBot"}'
```

The response creates an account, project, and project-scoped `ak_...` key. Store
it in a secret manager immediately; it is not a prompt, trace value, URL, or
source-control value.

```bash
export AGENTLEAK_KEY='ak_replace_with_returned_key'
```

Every subsequent key-authenticated request uses:

```http
X-AgentLeak-Key: ak_...
```

## Register identity

```bash
curl -sS -X POST "$BASE/api/agent/register" \
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \
  -H 'content-type: application/json' \
  -d '{
    "agent_card": {
      "name": "support-bot",
      "description": "Handles support tickets",
      "capabilities": ["ticket_triage", "crm_lookup"],
      "privacy": {"declared_data_types": ["email", "account_id"]},
      "source": {"type": "github", "repo": "acme/support-bot", "branch": "main"}
    }
  }'
```

Registration is an upsert. Read the normalized card with
`GET /api/agent/card`.

## Self-test a trace

```bash
curl -sS -X POST "$BASE/api/selftest" \
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \
  -H 'content-type: application/json' \
  -d '{
    "trace": {
      "run_id": "support-001",
      "agent_name": "support-bot",
      "events": [
        {"channel":"tool_response","source":"crm","target":"agent","content":{"email":"canary@example.test"}},
        {"channel":"final_output","source":"agent","target":"user","content":"Ticket updated"}
      ]
    },
    "redact": true
  }'
```

The response contains `project_id`, `run_id`, `report`, `passed`, and
`compliant`. Analyze the report before acting on its remediation instructions.

## Scan source code

```bash
curl -sS -X POST "$BASE/api/agent/code" \
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \
  -H 'content-type: application/json' \
  -d '{}'
```

An empty body scans the source declared in the agent card. Explicit submissions
can use GitHub, ZIP, or inline files. Never submit unauthorized production
source or real credentials.

## Improve and repeat

`POST /api/agent/improve` runs a self-test, compares it with the previous run,
and returns prioritized `next_steps`:

```bash
curl -sS -X POST "$BASE/api/agent/improve" \
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \
  -H 'content-type: application/json' \
  -d '{"trace":{"run_id":"support-002","events":[...]}}'

curl -sS "$BASE/api/agent/status" \
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY"
```

The safe loop is:

```text
discover → onboard → register → code scan → self-test → read next_steps
→ apply authorized fix → create a fresh trace → improve → verify status
```

Stop when `passed` is true, no authorized remediation remains, or owner
approval is required. Do not keep retrying a 401, rotate identities on a 429,
or bypass an authorization boundary.

## Python client

```python
from agentleak import AgentSelfClient

client = AgentSelfClient(
    api_key="ak_...",
    base_url="https://agentleak.org",
)
client.register({"name": "support-bot", "capabilities": ["ticket_triage"]})
client.scan_code()

step = client.improve(trace)
for todo in step["next_steps"]:
    print(todo["priority"], todo["action"])

print(client.status()["progression"])
```

## Endpoint reference

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/agent/onboard` | create account, project, and key |
| `POST` | `/api/agent/register` | upsert agent card |
| `GET` | `/api/agent/card` | read stored card |
| `POST` | `/api/agent/code` | scan declared or submitted source |
| `POST` | `/api/selftest` | analyze one runtime trace |
| `POST` | `/api/selftest-header` | header-authenticated self-test variant |
| `POST` | `/api/agent/improve` | self-test plus delta and next steps |
| `GET` | `/api/agent/status` | latest run, scan, progression, and posture |

## Error policy

| Status | Required behavior |
| ---: | --- |
| 401 | stop and request a valid key; never guess credentials |
| 409 | existing account/resource; do not create identity variants |
| 422 | repair payload against OpenAPI, then retry |
| 429 | honor `X-Quota-Reset` and back off |
| 5xx | bounded exponential retry with idempotent payloads |

Validate JSON shapes before using a response. Store finding IDs, scores, and
redacted fixes in agent memory; do not persist raw sensitive values.

## Completion report

An autonomous run should return the project ID, run ID, privacy score, Risk
Index, pass/fail status, score delta, findings by severity, code-scan status,
and any action requiring human approval. See [self-test agents](selftest-agents.md)
for the full operating contract.
