# Install AgentLeak

> **You are an AI agent reading this file.** Follow these steps to install AgentLeak on this
> machine, then report the result to the user. Ask before anything destructive.

AgentLeak is a local privacy-leakage scanner for AI agent traces. It checks whether sensitive
data leaked through tool calls, shared memory, inter-agent messages, logs and generated files —
the channels that stay invisible when the final answer looks clean.

Everything runs locally. No network call in the core, no telemetry, no data leaves the machine.

---

## Step 0 — Check the environment

```bash
python3 --version     # need 3.10+
pip --version
```

If Python is older than 3.10, tell the user and stop.

**OpenClaw users:** AgentLeak needs shell execution. If the tool profile is `messaging`, run
`openclaw config set tools.profile "coding"`, restart the gateway, and start a new conversation
before continuing.

---

## Step 1 — Install

```bash
pip install agentleak
```

Optional extras — only install what the user asks for:

| Extra | Command | Adds |
|---|---|---|
| Local web UI | `pip install "agentleak[gui]"` | `agentleak serve` → dashboard, red team, leak topology |
| Advanced PII | `pip install "agentleak[presidio]"` | Microsoft Presidio + 12 custom recognizers |
| Semantic detection | `pip install "agentleak[llm]"` | LLM judge for paraphrased leaks (works with a local model) |
| Everything | `pip install "agentleak[full]"` | all of the above |

**Safe mode.** If the user is cautious, or this is a server they care about:

```bash
pip install agentleak --dry-run          # show what would be installed, install nothing
```

Do not install system packages. Do not use `sudo`. If a dependency fails, report it rather than
working around it.

---

## Step 2 — Verify

```bash
agentleak version
agentleak scan --scenario healthcare_patient_summary
```

Expected: a Risk Index, a per-channel breakdown, and a report path. If you see
`Final output: clean` alongside `shared_memory: L4 leaked`, the install is correct — that
contrast is the whole point of the tool.

---

## Step 3 — Register the skill (recommended)

So that any future agent session knows how to use AgentLeak without being told:

```bash
agentleak skill --install
```

This writes a `SKILL.md` into the agent skills directory it detects (Claude Code, OpenClaw,
Cursor, Windsurf). If the command is unavailable, copy `SKILL.md` from the repository root into
the skills directory manually.

---

## Step 4 — Wire it to the user's agent

Ask the user which framework they use, then show the matching one-liner:

```python
import agentleak

with agentleak.watch("my-agent") as run:
    # LangChain / LangGraph:  chain.invoke(x, config={"callbacks": [run.callback]})
    # CrewAI:                 Crew(..., step_callback=run.crew.step_callback).kickoff()
    # Swarm / Agents SDK:     run.ingest_messages(response.messages)
    # Coding agents:          run.ingest_steps(agent.steps)
    # Plain Python:           run.tool_call({...}, target="crm"); run.final_output("...")

print(run.report.risk_index, run.report.verdict)
```

If they don't know, default to **coding agents** — it is the fastest path to a surprising
result, because `.env` files and cloud keys routinely end up in tool calls and logs.

---

## Step 5 — Optional: CI gate

If the user wants builds to fail on regressions:

```bash
agentleak run --trace traces/*.json --fail-on L4
```

Non-zero exit code when an L4 finding appears. See `docs/ci-gate.md`.

---

## Report back to the user

Summarize in this shape:

```
✅ AgentLeak installed (version X.Y.Z)
✅ Demo scan passed — Risk Index 0.44 on the bundled scenario
📁 Reports will be written to ./reports/
⬜ Not yet wired to your agent — tell me which framework you use
⬜ Optional: `pip install "agentleak[gui]"` then `agentleak serve` for the web dashboard
```

Then ask whether they want you to wire it into their agent now.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `command not found: agentleak` | The pip scripts dir isn't on PATH. Try `python3 -m agentleak` |
| Presidio install fails | It needs a spaCy model: `python3 -m spacy download en_core_web_lg`. Or skip it — the core works without |
| `agentleak serve` won't start | The `gui` extra isn't installed: `pip install "agentleak[gui]"` |
| Everything reports clean | Your trace probably has no internal-channel events. Check `docs/integrations.md` for the right callback |

Docs: <https://github.com/yagobski/agentleak/tree/main/docs> ·
Issues: <https://github.com/yagobski/agentleak/issues>
