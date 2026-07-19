# Trace analysis

Trace analysis is AgentLeak's core workflow: capture the complete execution of
an agent, normalize it into one event model, detect sensitive values on every
channel, and produce a reproducible report with remediation evidence.

## What is analyzed

AgentLeak follows data across eight channels, not only the final answer:

| Channel | Typical content |
| --- | --- |
| `user_input` | user prompts and uploaded context |
| `tool_call` | arguments sent to a tool or API |
| `tool_response` | records returned by a tool |
| `inter_agent_message` | hand-offs between agents |
| `shared_memory` | state, cache, vector or working memory |
| `log` | application and framework logs |
| `generated_file` | files, exports and artifacts |
| `final_output` | content returned to the user |

A clean `final_output` does not make a run safe if a secret was copied into a
tool argument, memory entry, log, or agent hand-off.

## Install and run in five minutes

```bash
pip install "agentleak @ git+https://github.com/yagobski/agentleak-oss.git"
agentleak init
agentleak run --scenario healthcare_patient_summary
```

Reports are written to `reports/` as JSON, HTML, and Markdown. Analyze your
own trace instead:

```bash
agentleak run \
  --trace traces/latest.json \
  --output reports/latest \
  --format json,html,markdown
```

Use `--scenario all` to run every bundled example. Use `--fail-under 80` to
make the command exit non-zero when the privacy score is below 80.

## Trace schema

The smallest useful trace has a run ID and channel-tagged events:

```json
{
  "run_id": "support-001",
  "agent_name": "support-bot",
  "events": [
    {
      "channel": "tool_response",
      "source": "crm",
      "target": "agent",
      "content": {"email": "canary@example.test", "account_id": "ACC-12345"}
    },
    {
      "channel": "final_output",
      "source": "agent",
      "target": "user",
      "content": "Your ticket was updated."
    }
  ]
}
```

`content` may be a string, object, list, or nested JSON-compatible value.
Keep `source` and `target` accurate: they determine the execution boundary
used by channel risk and remediation advice.

Validate before running:

```bash
agentleak validate --trace traces/latest.json
```

## Capture from an agent

For framework-independent code, use the SDK recorder:

```python
from agentleak import AgentLeakClient, capture, monitor

client = AgentLeakClient(project="support-bot")

@monitor(channel="tool_call")
def lookup_account(account_id: str):
    return {"email": "canary@example.test", "account_id": account_id}

with capture(run_id="support-001") as run:
    lookup_account("ACC-12345")
    run.add_event(channel="final_output", content="Ticket updated.")

saved = client.submit(run.trace)
print(saved["risk_index"], saved["privacy_score"])
```

Framework adapters and OpenTelemetry ingestion are documented in
[Integrations](integrations.md). If a framework has no adapter, emit generic
events at trust boundaries rather than trying to reconstruct the run from only
the final response.

## Detection modes

The default analysis is local and deterministic:

```bash
agentleak run --trace traces/latest.json --format json
```

Optional modes add broader detectors:

| Mode | Adds | Cost/requirement |
| --- | --- | --- |
| `fast` | regex, dictionaries, entropy and canaries | local, no key |
| `standard` | Presidio and domain recognizers | `agentleak[presidio]` |
| `hybrid` | Presidio plus semantic LLM judge | configured BYOK endpoint |

Configure the mode in `agentleak.yaml` or use the project settings in the web
UI. The LLM judge can improve semantic recall, but it never defines AgentRisk;
the numeric score remains closed-form and reproducible.

## Read the result

Every report includes:

- `risk_index` from 0 to 1 and the inverse `privacy_score` from 0 to 100;
- `verdict`, blocking state, and configured policy;
- findings with severity, data type, channel, event, masked value, and fix;
- channel risk, leaked-versus-vault level profile, and compliance controls;
- the trace metadata needed to reproduce the run.

Render an existing JSON result again without re-running detection:

```bash
agentleak report --input reports/run_healthcare_001.json --format html,markdown
```

Raw values are masked by default. Do not publish raw traces or reports that
contain production personal data.

## Hosted and local UI

```bash
pip install 'agentleak[gui]'
agentleak serve --port 8000
```

The Audit tab accepts a bundled scenario or pasted trace, toggles detectors,
custom rules, vault scope, and report format. The Playground is stateless; a
project run is saved and available for history, comparison, and export.

The equivalent endpoints are `POST /api/analyze` for a stateless report,
`POST /api/projects/{project_id}/runs` for a saved run, and
`GET /api/runs/{run_id}` to read it back.

## Continuous use

Capture one trace per meaningful agent workflow and keep a clean control trace
next to it. Compare a release against its previous run:

```bash
agentleak history support-bot --limit 20
agentleak compare RUN_OLD RUN_NEW
```

See [AgentRisk scoring](agentrisk.md) for thresholds, [CI policy gate](ci-gate.md)
for release enforcement, and [Defenses](defenses.md) for preventing leaks.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| No findings despite a visible secret | Confirm the event channel and enable the relevant detector; add a canary or custom rule. |
| Final answer is clean but score is high | Inspect `tool_call`, `shared_memory`, `log`, and `inter_agent_message`. |
| Trace validation fails | Run `agentleak validate --trace ...` and ensure every event has a supported channel. |
| Semantic leaks are missed | Install Presidio or enable hybrid mode with an authorized BYOK endpoint. |
| Score changes after adding unrelated events | Define an explicit vault scope; see [scoring](scoring.md). |

## Safety boundary

Trace analysis is evidence for the captured execution and configured vault. It
does not prove that unobserved tools, prompts, model versions, integrations, or
future behavior are safe. Use synthetic or canary data and obtain authorization
before exporting traces to a hosted deployment.
