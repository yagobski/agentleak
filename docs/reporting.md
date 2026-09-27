# Reports and evidence

AgentLeak produces one canonical analysis result and renders it as JSON,
Markdown or HTML. The same result is also returned by the hosted API and agent
self-test endpoints.

## Report shape

```json
{
  "report": "agentleak",
  "run_id": "run_001",
  "risk_index": 0.44,
  "privacy_score": 56,
  "verdict": "High risk",
  "blocked": true,
  "findings": [],
  "channel_risks": [],
  "leak_paths": [],
  "privacy_policy": {"enabled": true, "passed": false, "violations": []},
  "remediation_hints": [],
  "compliance": {}
}
```

`findings` contain the redacted value, data type, channel, severity level,
confidence, detector and recommendation. `channel_risks` shows which trust
boundary contributed to the score. `leak_paths` explains propagation across
agents, tools, memory, files and output. `remediation_hints` are ordered next
actions and may include a channel-specific code fix.

## Formats

```bash
agentleak run --trace traces/release.json --format json,html,markdown
agentleak report --input reports/run.json --format html,markdown
```

JSON is for automation and schema validation. Markdown is suitable for pull
requests. HTML is suitable for local review. Static code scans additionally
support SARIF 2.1.0 for GitHub Code Scanning.

## Redaction and retention

Redaction is enabled by default. Raw matched values are omitted from normal
reports, while masked values and finding IDs remain. Keep `store_raw_traces`
disabled unless the environment is controlled and retention is understood.
Use synthetic or canary values for hosted analysis. A redacted report can still
reveal file names, channels, tools and workflow structure, so protect it.

## Machine contracts

```bash
curl -sS https://www.agentleak.org/api/schemas/analysis-report
agentleak schema analysis-report
```

Pin the schema version when reports are consumed by long-lived automation.

## Utility beside privacy

An agent that refuses everything leaks nothing and scores 100/100. When the
caller knows whether the task was accomplished, it can say so on the trace
(`"task_success": true`, or `Trace(task_success=...)`), and the report gains a
`utility` block beside the score — never inside it:

```json
"utility": {"task_success": false, "leaked": false, "quadrant": "safe_by_failing"}
```

The four quadrants are `useful_and_safe`, `useful_but_leaky`,
`safe_by_failing` and `failed_and_leaky`. AgentLeak does not judge task
success itself; only the harness that set the task can.
