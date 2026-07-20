# Configuration reference

AgentLeak accepts YAML or JSON through `Config`. The same configuration model
is used by the CLI, Python runner, hosted project settings and agent self-tests.

## Complete example

```yaml
# yaml-language-server: $schema=https://www.agentleak.org/api/schemas/config
project: {name: support-bot, description: Privacy regression suite}
agent: {name: support-bot, type: generic, endpoint: null}
scenarios:
  - {id: healthcare_patient_summary, enabled: true}
channels: [user_input, tool_call, tool_response, shared_memory, log, generated_file, inter_agent_message, final_output]
detectors: {pii: true, secrets: true, healthcare: true, finance: false, hr: false}
detection:
  mode: fast
  presidio: {enabled: false, score_threshold: 0.5}
  llm_judge: {enabled: false, threshold: 0.7}
scoring: {fail_below: 40, conditional_below: 70, block_on_critical: true, weights: [1, 2, 3, 4]}
vault:
  levels: {"1": 40, "2": 12, "3": 5, "4": 2}
  scope_def: customer records reachable by support-bot
privacy_policy: {max_risk_index: 0.20, max_findings: 0, forbid_levels: [4]}
privacy: {redact_values: true, store_raw_traces: false}
reports: {output_dir: reports, formats: [json, html, markdown]}
```

## Sections

`project` and `agent` identify the audit target. `scenarios` selects built-in
or imported traces. `channels` is an allowlist; leaving out a disclosure
channel means it is not tested. `detectors` controls the local detector family
switches. `custom_detectors` adds scoped regex rules with a severity and data
type.

`detection.mode` is `fast`, `standard`, `hybrid` or `llm_only`. Fast is the
default and requires no network. Standard enables Presidio, hybrid adds the
optional semantic judge, and `llm_only` is intended only for controlled
experiments.

`scoring` controls thresholds and weights. `vault.levels` or `vault.rho_s`
defines the audited denominator. Without a vault, the denominator is the
observed reachable set and is not suitable for comparing releases.

`privacy_policy` adds hard assertions: `max_risk_index`, `max_findings`,
`forbid_levels`, `forbid_channels`, `forbid_data_types`, and
`require_explicit_vault`. Violations set `blocked` and are returned with
finding IDs.

## Validate

```bash
agentleak validate agentleak.yaml --trace traces/release.json
agentleak schema config > config.schema.json
```

Never place provider keys or real personal data in this file. Resolve provider
credentials through environment variables or a secret manager.
