"""Public, machine-readable documentation for agents and developer tooling."""

from __future__ import annotations

from typing import Any


def _base(url: str) -> str:
    return url.rstrip("/")


def llms_index(base_url: str) -> str:
    """Return the concise llms.txt navigation file proposed by llmstxt.org."""
    base = _base(base_url)
    return f"""# AgentLeak

> Open-source privacy testing for single-agent and multi-agent systems. AgentLeak analyzes complete execution traces across tool calls, shared memory, inter-agent messages, logs, generated files, and final output.

AgentLeak can be used by developers through its CLI and Python SDK, or directly by autonomous agents through a project-scoped HTTP API. Prefer synthetic or canary data for tests. The hosted service is available at {base}.

## Start here

- [{base}/docs]({base}/docs): Documentation hub and product model
- [{base}/docs/developers]({base}/docs/developers): CLI, SDK, integrations, trace schema, and CI guide
- [{base}/docs/agents]({base}/docs/agents): Autonomous onboarding, safety rules, self-test loop, and failure handling
- [{base}/docs/api]({base}/docs/api): Integrated API reference with auth, endpoint flows, examples, and schema notes
- [{base}/agents.md]({base}/agents.md): Normative instructions for autonomous agents

## Machine interfaces

- [{base}/openapi.json]({base}/openapi.json): OpenAPI 3 schema
- [{base}/api/schemas]({base}/api/schemas): JSON Schema catalog for config, traces, reports, policies, code scans, red-team requests, and agent cards
- [{base}/api/docs]({base}/api/docs): Swagger UI fallback for raw schema exploration
- [{base}/api/meta]({base}/api/meta): Runtime capabilities, channels, limits, and endpoint map
- [{base}/.well-known/agent-card.json]({base}/.well-known/agent-card.json): Agent capability manifest with a documented custom HTTP+JSON binding
- [{base}/llms-full.txt]({base}/llms-full.txt): Complete agent-oriented usage guide in one document

## Optional

- [https://github.com/yagobski/agentleak-oss](https://github.com/yagobski/agentleak-oss): Source code and self-hosting
"""


def agent_instructions(base_url: str) -> str:
    """Return stable, normative operating instructions for autonomous clients."""
    base = _base(base_url)
    return f"""# AgentLeak instructions for autonomous agents

Version: 1.0
Service: {base}
Human API reference: {base}/docs/api
OpenAPI: {base}/openapi.json
Capabilities: {base}/api/meta

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY describe operational requirements for an autonomous client.

## Purpose

Use AgentLeak to detect privacy leakage in source code and runtime traces, obtain a deterministic Risk Index, and iterate on machine-actionable remediation steps.

## Safety requirements

1. You MUST have authorization from the system owner before submitting its source code or traces.
2. You SHOULD use synthetic, masked, or canary data. You MUST NOT submit production credentials, private keys, authentication cookies, or real personal data unless the owner explicitly authorized that exact transfer.
3. You MUST treat `X-AgentLeak-Key` and the one-time generated password as secrets. Never place them in prompts, logs, source control, URLs, or trace content.
4. You MUST send credentials only to the HTTPS origin `{base}` or to the explicitly configured self-hosted origin.
5. You SHOULD omit raw values from long-term agent memory. Store finding IDs, redacted values, scores, and remediation steps instead.
6. You MUST NOT interpret a passing test as legal certification or proof that untested behavior is safe.

## Discovery

Before acting, fetch `GET {base}/api/meta`. Use `GET {base}/openapi.json` as the authoritative request/response schema. This document is operational guidance; OpenAPI controls field names and types.

## First-run sequence

1. Call `POST {base}/api/agent/onboard` with `email` and `agent_name`.
2. Securely store the returned `api_key`. It is shown once and scopes future calls to the created project.
3. Send `X-AgentLeak-Key: <key>` on every subsequent agent API request.
4. Call `POST {base}/api/agent/register` with an agent card describing identity, capabilities, data types, and optional source location.
5. Call `POST {base}/api/agent/code` for a static scan and `POST {base}/api/selftest` for a runtime trace.
6. Call `POST {base}/api/agent/improve`, apply the highest-priority safe remediation, generate a new trace, and repeat.
7. Stop when `passed` is true, no authorized remediation remains, or further action requires owner approval.

## Runtime trace minimum

```json
{{
  "trace": {{
    "agent_name": "support-bot",
    "events": [
      {{"channel": "tool_call", "source": "agent", "target": "crm", "content": {{"email": "canary@example.test"}}}},
      {{"channel": "final_output", "source": "agent", "target": "user", "content": "Done"}}
    ]
  }}
}}
```

Allowed channels include `user_input`, `tool_call`, `tool_response`, `inter_agent_message`, `shared_memory`, `log`, `generated_file`, and `final_output`.

## Response handling

- A `2xx` response MAY be used only after validating its JSON shape.
- On `401`, stop and request a valid project key. Do not retry with guessed credentials.
- On `409` during onboarding, the account already exists. Do not create email variants to bypass it.
- On `422`, repair the payload against OpenAPI before retrying.
- On `429`, honor `X-Quota-Reset` when present and back off. Do not rotate accounts or IPs to evade limits.
- On `5xx`, retry with bounded exponential backoff and preserve idempotency where possible.

## Improvement policy

- Process `next_steps` in priority order: critical, high, medium, low.
- Before editing code, verify that the change is inside your authorized repository and task scope.
- After each fix, run existing tests, create a fresh trace, and compare `delta.direction` and `delta_score`.
- If privacy improves but functional tests regress, revert or redesign the fix.
- Report unresolved critical findings to the owner with channel, data type, finding ID, and recommended control. Do not include the raw secret.

## Completion report

Return: project ID, run ID, privacy score, Risk Index, pass/fail status, score delta, remaining findings by severity, code-scan status, and any action requiring human approval.
"""


def llms_full(base_url: str) -> str:
    """Return a self-contained guide suitable for a model context window."""
    base = _base(base_url)
    return f"""# AgentLeak — complete agent and developer guide

## What AgentLeak solves

An agent's final answer can be clean while sensitive data leaks through tool arguments, tool responses, shared memory, inter-agent messages, logs, or generated files. AgentLeak analyzes the full trace, detects sensitive material, reconstructs leak paths, calculates a deterministic Risk Index, and returns remediation evidence.

## Hosted service

- Base URL: {base}
- Health: `GET /api/health`
- Capabilities and current limits: `GET /api/meta`
- Integrated API reference: `GET /docs/api`
- OpenAPI: `GET /openapi.json`
- JSON Schema catalog: `GET /api/schemas`
- Swagger fallback: `GET /api/docs`
- Authentication after onboarding: `X-AgentLeak-Key: ak_...`

## Autonomous quickstart

```bash
BASE={base}

curl -sS -X POST "$BASE/api/agent/onboard" \\
  -H 'content-type: application/json' \\
  -d '{{"email":"owner@example.com","agent_name":"SupportBot"}}'

export AGENTLEAK_KEY='ak_replace_with_returned_key'

curl -sS -X POST "$BASE/api/agent/register" \\
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \\
  -H 'content-type: application/json' \\
  -d '{{"agent_card":{{"name":"SupportBot","description":"Handles support tickets","capabilities":["ticket_triage","crm_lookup"],"privacy":{{"declared_data_types":["email","account_id"]}}}}}}'

curl -sS -X POST "$BASE/api/selftest" \\
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \\
  -H 'content-type: application/json' \\
  -d '{{"trace":{{"agent_name":"SupportBot","events":[{{"channel":"tool_call","source":"agent","target":"crm","content":{{"email":"canary@example.test"}}}},{{"channel":"final_output","source":"agent","target":"user","content":"Ticket updated"}}]}}}}'

curl -sS "$BASE/api/agent/status" -H "X-AgentLeak-Key: $AGENTLEAK_KEY"
```

## Agent loop

`onboard -> register -> code scan + self-test -> improve -> status -> fix -> repeat`

- `POST /api/agent/onboard`: create an account, project, and project-scoped key.
- `POST /api/agent/register`: declare the agent card and optional source location.
- `POST /api/agent/code`: scan inline files, a zip, or an explicitly declared GitHub repository.
- `POST /api/selftest`: analyze one runtime trace.
- `POST /api/agent/improve`: analyze, compare with the previous run, and return prioritized `next_steps`.
- `GET /api/agent/status`: read the latest run, progression, compliance posture, code scan, and remaining work.

## Developer quickstart

```bash
pip install agentleak
agentleak init
agentleak run --scenario healthcare_patient_summary
agentleak run --trace traces/latest.json --fail-under 70
agentleak schema
agentleak scan . --format sarif --output reports/agentleak.sarif
```

## Declarative privacy assertions

Configure `privacy_policy` with `max_risk_index`, `max_findings`, forbidden
levels, channels or data types, and optionally `require_explicit_vault`. Every
configured assertion must pass. Violations block the run and include affected
finding IDs in the report. Fetch the exact contract from
`GET {base}/api/schemas/privacy-policy`.

## Machine contracts

`GET {base}/api/schemas` lists versioned Draft 2020-12 schemas for config,
traces, events, findings, reports, privacy policies, red-team requests, code
scans and agent cards. The local equivalent is `agentleak schema [name]`.

```python
from agentleak import AgentLeakRunner, Trace

trace = Trace(run_id="demo", agent_name="support-bot")
trace.add_event(channel="tool_call", source="agent", target="crm", content={{"email": "canary@example.test"}})
trace.add_event(channel="final_output", source="agent", target="user", content="Done")
result = AgentLeakRunner().analyze(trace)
print(result.risk_index, result.verdict)
```

Framework adapters cover LangChain/LangGraph, CrewAI, AutoGen, OpenAI Agents/Swarm, LlamaIndex, Semantic Kernel, Pydantic AI, smolagents, Google ADK, computer-use agents, OpenTelemetry/OpenInference, MCP, and generic event recorders.

## Interpretation

- Risk Index ranges from 0 to 1; higher means a larger weighted share of sensitive inventory leaked.
- Privacy score ranges from 100 to 0 and is the inverse presentation of risk.
- L4 is critical, L3 high, L2 medium, and L1 low.
- A passing trace is evidence for that trace and configured policy, not a universal guarantee or legal certification.

## Safe operating rules

{agent_instructions(base).split('## Safety requirements', 1)[1].split('## Discovery', 1)[0].strip()}

## Further reading

- Human documentation: {base}/docs
- Developer path: {base}/docs/developers
- Agent path: {base}/docs/agents
- API reference: {base}/docs/api
- Normative agent instructions: {base}/agents.md
- Source and self-hosting: https://github.com/yagobski/agentleak-oss
"""


def official_platform_card(base_url: str, version: str) -> dict[str, Any]:
    """Return A2A 1.0 discovery metadata for AgentLeak's custom REST binding.

    AgentLeak is not claiming the standard A2A task transport. The card uses a
    URI-identified custom HTTP+JSON binding and points clients at OpenAPI.
    """
    base = _base(base_url)
    binding = f"{base}/docs/agents#agentleak-rest-binding"
    return {
        "name": "agentleak",
        "description": (
            "Privacy self-testing for autonomous agents: register identity, scan source, "
            "analyze runtime traces, and iterate on prioritized remediation steps."
        ),
        "supportedInterfaces": [
            {
                "url": f"{base}/api",
                "protocolBinding": binding,
                "protocolVersion": "1.0",
            }
        ],
        "provider": {
            "organization": "AgentLeak OSS",
            "url": "https://github.com/yagobski/agentleak-oss",
        },
        "version": version,
        "documentationUrl": f"{base}/docs/agents",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "securitySchemes": {
            "agentLeakKey": {
                "apiKeySecurityScheme": {
                    "name": "X-AgentLeak-Key",
                    "in": "header",
                }
            }
        },
        "security": [{"agentLeakKey": []}],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "privacy-runtime-selftest",
                "name": "Runtime privacy self-test",
                "description": "Analyze all execution channels in an agent trace and return risk, findings, compliance posture, and fixes.",
                "tags": ["privacy", "runtime", "multi-agent", "compliance"],
                "examples": ["Test this trace for sensitive-data leakage."],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
            {
                "id": "privacy-code-scan",
                "name": "Static privacy code scan",
                "description": "Scan authorized source files for secrets, PII logging, unsafe transfers, and re-identification risk.",
                "tags": ["privacy", "source-code", "secrets"],
                "examples": ["Scan these files for privacy leakage."],
                "inputModes": ["application/json", "application/zip"],
                "outputModes": ["application/json"],
            },
            {
                "id": "privacy-improvement-loop",
                "name": "Privacy improvement loop",
                "description": "Compare runs and return prioritized machine-actionable next steps until policy passes.",
                "tags": ["remediation", "ci", "agent-self-improvement"],
                "examples": ["Tell me the safest next fix and measure the new run."],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            },
        ],
        "extensions": {
            "openapi": f"{base}/openapi.json",
            "llmsTxt": f"{base}/llms.txt",
            "agentInstructions": f"{base}/agents.md",
            "bindingNotice": "Custom REST binding; standard A2A message/task methods are not exposed.",
        },
    }
