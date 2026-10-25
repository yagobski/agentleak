# Worked examples

Sketches of tool calls and responses. Values shown are illustrative;
the verdict semantics (`Pass` / `Needs attention` / `Fail`) are real.

## 1. Coding agent: preflight before commit

You just finished a feature that reads customer records and writes logs.
Before `git commit`, run the preflight reflex.

**Call** (MCP):

```json
{ "tool": "privacy_preflight", "arguments": { "path": "." } }
```

**Response (first run):**

```json
{
  "verdict": "Fail",
  "findings": [
    {
      "file": "src/sync.py", "line": 87, "rule": "aws_key",
      "data_type": "credentials", "level": 4,
      "snippet": "AKIA****************",
      "fix": "Remove the hardcoded key; load from environment."
    },
    {
      "file": "logs/debug.log", "line": 12, "rule": "email",
      "data_type": "contact", "level": 2,
      "snippet": "c***@***",
      "fix": "Stop logging raw customer emails or redact at write time."
    }
  ],
  "since_last": { "new": 2, "resolved": 0 },
  "next_steps": ["Remove hardcoded AWS key in src/sync.py:87", "Redact emails in logs/debug.log"]
}
```

**Loop:** move the key to an env var, strip the email logging, re-run
`privacy_preflight`. The second response must show
`"since_last": {"new": 0, "resolved": 2}` and `"verdict": "Pass"`.
Only then commit.

CLI equivalent without MCP:

```bash
agentleak scan . && git commit   # scan first; commit only on clean output
```

## 2. Multi-agent run: check the trace before emitting the summary

A researcher sub-agent read patient files; a writer agent drafts the
summary you are about to send. The final draft looks clean — check the
channels behind it.

**Call** (MCP), with the run's trace:

```json
{
  "tool": "privacy_preflight",
  "arguments": {
    "path": ".",
    "trace": {
      "run_id": "rounds-042",
      "events": [
        {"channel": "tool_call", "source": "researcher", "target": "ehr",
         "content": {"patient": "J. Tremblay", "nam": "TREM12345678",
                     "diagnosis": "diabetes"}},
        {"channel": "inter_agent_message", "source": "researcher",
         "target": "writer",
         "content": {"note": "TREM12345678 confirmed diabetic, draft summary"}},
        {"channel": "final_output", "source": "writer",
         "content": "Patient follow-up scheduled."}
      ]
    }
  }
}
```

**Response:**

```json
{
  "verdict": "Fail",
  "risk_index": 0.62,
  "findings": [
    {"channel": "inter_agent_message", "data_type": "health_identifier",
     "level": 4, "redacted_value": "TREM********"},
    {"channel": "tool_call", "data_type": "diagnosis",
     "level": 4, "redacted_value": "***"}
  ],
  "detection": {"mode": "fast", "tiers": ["regex"], "degraded": false}
}
```

The final output is clean — and irrelevant. The health identifier crossed
two internal channels at L4.

**Loop:** change the researcher to pass a case reference instead of the
raw identifier (`redact` the note first if you must forward text), re-run
`check_trace` on the corrected trace, confirm `"verdict": "Pass"`. Only
then emit the summary.

## 3. CI gate: block the merge on L4

In the pipeline, after the agent's regression traces are produced:

```bash
agentleak run --trace traces/*.json --fail-on L4 --format json
```

- Exit 0: no L4 findings — merge proceeds.
- Non-zero exit: an L4 leaked somewhere in the run — the build fails and
  the JSON report names the channel, the data type, and the event.

For a fast deterministic gate (no model calls, sub-second per trace):

```bash
agentleak run --trace traces/*.json --fail-on L4 --mode fast
```

Promote to `--mode hybrid` on the nightly run if you want the LLM judge
to catch paraphrased leaks the patterns miss.
