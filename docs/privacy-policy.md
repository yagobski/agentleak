# Declarative privacy policy

AgentLeak privacy assertions turn a release boundary into a small, reviewable
YAML block. They are deterministic and run at the analyzer seam, so the CLI,
Python SDK, reports, hosted platform, CI and autonomous-agent self-tests all
receive the same decision.

## Quickstart

Add the narrowest rules that represent your actual boundary:

```yaml
# agentleak.yaml
privacy_policy:
  max_risk_index: 0.20
  max_findings: 0
  forbid_levels: [4]
  forbid_channels: [log, shared_memory]
  forbid_data_types: [llm_api_key, credit_card]
  require_explicit_vault: true
```

Then run AgentLeak normally:

```bash
agentleak validate agentleak.yaml --trace traces/release.json
agentleak run --config agentleak.yaml --trace traces/release.json
```

A failed assertion sets `blocked` to `true`, causes the CLI or CI job to exit
non-zero, and adds a machine-readable `privacy_policy` object to the report.

## Assertion reference

| Field | Type | Meaning |
| --- | --- | --- |
| `max_risk_index` | number, 0–1 | Maximum allowed AgentRisk Risk Index. |
| `max_findings` | integer, ≥0 | Maximum findings on disclosure channels. |
| `forbid_levels` | list of 1–4 | Reject findings at selected privacy levels. |
| `forbid_channels` | channel list | Reject findings crossing selected channels. |
| `forbid_data_types` | string list | Reject exact detector data types. |
| `require_explicit_vault` | boolean | Require an audited vault denominator rather than the observed fallback. |

All configured assertions must pass. An empty block is disabled. Duplicate
levels and channels are normalized, while unknown channels and out-of-range
values fail configuration validation.

`user_input` and `tool_response` are source channels. Findings there establish
what entered the run but do not count toward `max_findings`, forbidden levels,
channels or data types unless the agent later emits the same information onto a
disclosure channel.

## Report schema

```json
{
  "blocked": true,
  "privacy_policy": {
    "enabled": true,
    "passed": false,
    "assertions_checked": ["forbid_channels", "forbid_data_types"],
    "violations": [
      {
        "rule": "forbid_channels",
        "message": "1 finding(s) crossed forbidden channel(s): log.",
        "count": 1,
        "finding_ids": ["finding_001"]
      }
    ]
  }
}
```

Use finding IDs to link policy failures back to redacted evidence. Never copy
raw matched values into policy messages, logs or CI annotations.

## Designing a useful policy

1. Start with `forbid_levels: [4]` and the channels that cross your strongest
   trust boundaries.
2. Define an explicit `vault.levels` or `vault.rho_s` before comparing Risk
   Index values between releases.
3. Add exact forbidden data types for non-negotiable secrets such as provider
   keys or payment cards.
4. Measure a synthetic baseline, then set `max_risk_index` and `max_findings`.
5. Version the policy, traces and detector mode together.

Do not use a long generic rule list as a substitute for threat modeling. A
small policy tied to real channels is easier for humans and agents to explain,
repair and keep stable.

## JSON Schema

```bash
curl -sS https://www.agentleak.org/api/schemas/privacy-policy
agentleak schema privacy-policy
```

The schema is Draft 2020-12 and includes the AgentLeak schema version.

## Safety boundary

A passing policy proves only that the submitted trace satisfied the configured
assertions. It does not cover unobserved executions, authorize production data
transfer, or constitute compliance certification.
