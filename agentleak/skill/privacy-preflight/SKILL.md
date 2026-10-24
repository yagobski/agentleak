---
name: agentleak-privacy-preflight
description: Run a privacy preflight on an AI agent's work before calling it done — scan tool calls, inter-agent messages, shared memory, logs, and generated files for leaked personal data or secrets. Use when the task touches PII, health records, financial data, credentials, or repository secrets; when multiple agents exchange messages; before emitting a summary, writing logs, committing code, or shipping. Wraps the AgentLeak engine (local, deterministic, no network).
---

# agentleak-privacy-preflight

The privacy equivalent of `pytest`: run it before you say "done".

A clean final answer proves nothing about the channels behind it. Measured
across 4,979 validated traces (IEEE Access 2026, DOI
10.1109/ACCESS.2026.3704541): inter-agent messages leak at **68.8%** vs
**27.2%** for final outputs, and output-only audits miss **41.7%** of
violations. If you only checked what the agent said last, you checked the
safest channel.

## When to trigger this skill

- You are about to finish a task that handled personal data, health records,
  financial data, credentials, API keys, or repository secrets.
- Two or more agents (or sub-agents) exchanged messages, tool results, or
  shared memory during the task.
- You are about to emit a summary, write a log, save a transcript, or commit
  code that could carry values the agent read earlier.
- A CI pipeline needs a privacy gate with a non-zero exit on severe findings.

## Setup (once)

```bash
agentleak version || pip install agentleak
```

For MCP access (Claude Code, Cursor, Copilot-style clients):

```bash
pip install "agentleak[mcp]"
```

Point your MCP client at the stdio server:

```bash
agentleak mcp
```

Typical client config shape (adapt to your client; full setup in the repo's
`docs/mcp.md`):

```json
{
  "mcpServers": {
    "agentleak": { "command": "agentleak", "args": ["mcp"] }
  }
}
```

Everything runs locally. No network calls, no telemetry. Values are redacted
in findings by default.

## The tools

Four MCP tools (same engine as the CLI):

| Tool | What it does |
|---|---|
| `privacy_preflight(path=".", trace=None)` | Check a project before shipping. Reports what changed **since your last check** (the delta tells you whether your last fix held). Optional trace dict is scored across all eight channels in the same call. |
| `scan_code(path=".")` | Static scan of source: secrets, PII in logs, unsafe sends. |
| `check_trace(trace)` | Score one agent run across all eight channels. |
| `redact(text, style="placeholder")` | Strip sensitive values out of text before it goes anywhere. |

`privacy_preflight` returns a `verdict`:

- `"Fail"` — any finding at level ≥ 4, or the trace verdict is `"Fail"`.
  Do not emit, commit, or ship. Fix first.
- `"Needs attention"` — findings exist, or the trace verdict is
  `"High risk"` / `"Conditional pass"`. Redact or justify each finding.
- `"Pass"` — no findings.

The response also reports which detection tiers actually ran (`detection.mode`,
`detection.tiers`). A clean result from the regex tier alone is a weaker
claim than a clean result from the full pipeline — never present them as
equivalent.

## The loop: check → redact → retry

1. **Check.** `privacy_preflight` (MCP) or `agentleak scan .` (CLI) on the
   working tree; `check_trace` (MCP) or `agentleak scan --trace run.json`
   on the execution trace.
2. **Redact.** For each finding, either remove the value at the source or
   pass the text through `redact`. Do not just delete the finding from the
   report.
3. **Retry.** Re-run the check. The `since_last` delta in the new
   `privacy_preflight` result must show the findings gone. Repeat until the
   verdict is `"Pass"` or every remaining finding is explicitly justified.

## Thresholds

Severity levels: **L4** (health data, SIN/SSN, cards, credentials) >
**L3** (income, salary, address, DOB) > **L2** (email, phone) >
**L1** (names, organizational identifiers).

- L4: block. Never emit or ship with an unresolved L4.
- L3/L2: redact, or record an explicit justification for why the value must
  travel (data minimization still applies).
- L1: note it; fix if it aggregates (many L1s can identify).

CI gate equivalent:

```bash
agentleak run --trace traces/*.json --fail-on L4   # non-zero exit on L4
```

Detection modes (`--mode`): `fast` (regex/dictionary only — sub-second,
good as the default reflex), `standard` (adds Presidio NER),
`hybrid` (adds the LLM judge, BYOK, for paraphrased or contextual leaks).

## Without an MCP client

```bash
agentleak scan .                                   # code + logs + unsafe sends
agentleak scan --trace path/to/trace.json          # one run, eight channels
agentleak scan --scenario healthcare_patient_summary  # smoke test, no user data
agentleak run --trace traces/*.json --format json,html,markdown
```

Python:

```python
from agentleak import Trace, AgentLeakRunner

trace = Trace(run_id="preflight")
trace.add_event(channel="inter_agent_message", source="researcher",
                target="writer", content={"ssn": "123-456-789"})
trace.add_event(channel="final_output", content="Summary complete.")

result = AgentLeakRunner().analyze(trace)
print(result.verdict, result.risk_index)   # verdict + Risk Index in [0,1]
for f in result.leaked_findings():
    print(f.level, f.channel, f.data_type)
```

Live capture inside your own agent code:

```python
import agentleak

with agentleak.watch("my-agent") as run:
    ...  # run your agent; framework callbacks hook in per docs
print(run.report.verdict, run.report.risk_index)
```

## Honest limits

- `fast` mode is deterministic patterns only. It will not catch paraphrased
  or heavily contextual leaks — that is `hybrid` (LLM judge) territory.
- The pre-emission proxy covers MCP `tools/call` transport. Native
  framework tool calls (plain Python functions in LangChain/CrewAI/etc.)
  are analyzed post-hoc, not gated pre-emission.
- The Python API is synchronous. There is no async in-loop audit yet —
  run the check at step boundaries, not inside a hot `asyncio` loop.
- A "Pass" is always relative to the tiers that ran. Say which they were.

## TODO (not yet in the tool — do not assume)

- Async `analyze` for in-loop auditing.
- Pre-emission hooks for native (non-MCP) framework tool calls.
- Policy auto-generated from an agent card.

## Pointers

- `references.md` — the paper, key figures, correct BibTeX.
- `examples.md` — three worked preflight runs.
- Paper: https://doi.org/10.1109/ACCESS.2026.3704541
- Tool repo: https://github.com/yagobski/agentleak
- Benchmark repo: https://github.com/Privatris/AgentLeak
