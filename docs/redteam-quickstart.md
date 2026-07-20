# Red-team quickstart

AgentLeak red-team testing is a controlled matrix: a plugin says what behavior
to probe, and a strategy says how to deliver the probe. This separation makes a
campaign reproducible and lets teams compare the same matrix after a fix.

## 1. Inspect the catalog

```bash
curl -sS https://www.agentleak.org/api/redteam/catalog | jq
```

The catalog exposes 46 attack classes, 24 native plugins, 38 Promptfoo privacy/security
transpositions, 10 strategies, presets and
strategy profiles. Use `privacy_core` for privacy boundaries, `agent_core` for
agent/application behavior, `tool_security` for tool and MCP boundaries, or
`complete` for the full native matrix. Add transposition IDs explicitly when
migrating an existing Promptfoo privacy or agent-security configuration.

## 2. Run a scripted campaign

```bash
curl -sS -X POST "$BASE/api/projects/$PROJECT_ID/redteam" \
  -H "Cookie: $AGENTLEAK_SESSION" \
  -H 'content-type: application/json' \
  -d '{
    "vertical": "healthcare",
    "adversary_level": "A1",
    "n": 10,
    "plugin_preset": "agent_core",
    "strategy_profile": "balanced",
    "mode": "scripted"
  }'
```

Scripted mode is offline, deterministic and appropriate for pull requests. A
campaign is capped by the API budget. Use `n` for the number of generated
cases, then inspect the returned `coverage`, `attacks`, `metrics`, `run_ids`
and `remediation`.

## 3. Understand the dimensions

Plugins include direct PII disclosure, prompt extraction, indirect injection,
data exfiltration, authorization failures, SQL/shell injection, SSRF, tool
discovery, MCP, memory poisoning, cross-session leakage and excessive agency.

Strategies include direct delivery, jailbreak framing, trusted markup, Base64,
hex, ROT13, leetspeak, Unicode homoglyphs and four-turn Crescendo.

Adversary levels progress from baseline to realistic application attacks and
advanced adversarial cases. Start at A1, then add A0 controls and A2 only when
the target and test data are authorized.

## 4. Live mode

Live mode drives an explicitly configured OpenAI-compatible target. It requires
an authorized endpoint, BYOK credentials and synthetic/canary data. Never use
the campaign API to probe a third-party service without written authorization.

## 5. Metrics and iteration

Review Attack Success Rate (ASR), exposure/leak rate (ELR), clean-leak rate
(CLR), defense rate, privacy score, strategy performance and budget-limited
coverage. Open saved run IDs to inspect the normal AgentLeak evidence: channel,
finding, leak path, compliance mapping and remediation hint.

After each change, rerun the same plugin/strategy matrix. A lower ASR is not
enough if the agent now leaks through memory, logs, tools or hand-offs; inspect
the trace-level privacy report as well.

## Safety

Use a test project, test endpoint, canary values and allowlisted tools. Redact
campaign evidence, keep API keys out of prompts and reports, and stop if a
probe would affect a real user or external system.
