# MCP mode: let a coding agent check its own work

A coding agent will not shell out to a CLI, and it will not chain four HTTP
calls on a hunch. It calls tools. `agentleak mcp` is that surface — the same
engine the CLI runs, presented over the Model Context Protocol so an agent in
Claude Code, Cursor, or anything else that speaks MCP can reach for it.

Everything runs on your machine. No account, no key, no network.

```bash
pip install "agentleak[mcp]"
agentleak mcp          # serves over stdio; editors launch this for you
```

## Wiring it up

Most MCP clients read a JSON config. The shape below works for Claude Code and
Cursor; check your client's docs for the exact file.

```json
{
  "mcpServers": {
    "agentleak": {
      "command": "agentleak",
      "args": ["mcp"]
    }
  }
}
```

## The tools

| Tool | When an agent should reach for it |
|---|---|
| `privacy_selftest` | To test **itself**: score a run it made (`trace` inline, `trace_path`, or coding-agent `steps`; optional `code_path`, `fail_on`). Returns the same document as `agentleak selftest --json`: `passed`, per-channel status, redacted findings with fingerprints, ordered `next_steps` with `fix` objects, `delta`, `rerun`. Call again after each fix until `passed`. |
| `privacy_selftest_status` | At the start of a session: latest self-test per target, runs, best score, open findings. |
| `privacy_explain_finding` | When one finding is unclear or looks wrong: why it fired, which rule, the level, the fix. |
| `privacy_list_scenarios` / `privacy_get_scenario` | When there is no recorded run: get a scenario with freshly generated canary values, do it, then submit the trace (with `scenario_id` = the `instance_id`) to `privacy_selftest`. |
| `privacy_preflight` | Before saying the work is done. Scans the project and reports what is **new since the last check**. |
| `privacy_scan_code` | When only the current state of the code matters, not the change. |
| `privacy_check_trace` | The bare AgentRisk scoring of one native trace (no fixes, no history). |
| `privacy_redact` | Before writing anything into a log, an issue, or a commit message. |

Every tool returns structured content. Read-only tools are marked with
`readOnlyHint`; none has `openWorldHint`, because none reaches the network.

Paths an agent passes to `privacy_selftest` (`trace_path`, `code_path`) must be
inside the server root: `$AGENTLEAK_MCP_ROOT` when set, otherwise the directory
the server was started in. Symlinks are resolved before the check. Results only
carry redacted values. Self-test history lives in `<root>/.agentleak/`.

Traces are data. A trace that contains text such as "ignore your instructions" is
scored like any other content; nothing in a trace is executed or followed.

The self-test document, its fields and the full loop are described in
[selftest-agents.md](selftest-agents.md).

## Why `preflight` is the one that matters

A score on its own changes nothing. An agent reads the number, files it away,
and moves on. What makes it iterate is being told *this finding is new since you
last looked*:

```
1 new, 2 fixed since last check, 1 still open

→ New L4 — hardcoded_secret at new.py:1. Remove inline secret assignments…
```

That comparison comes from `.agentleak/history.jsonl` inside the project. It is
local, it holds only redacted snippets, and it is capped at 50 entries so it
stays readable by hand.

### Why the line number is not part of a finding's identity

To say "new" or "fixed", the tool has to recognise the same finding across two
runs. The obvious key is `file:line`, and it is wrong: reformat a file, add an
import, and every known finding shifts a line and comes back as new. A tool that
cries wolf on every commit gets muted within a day, which is worse than never
reporting a delta at all.

Identity is therefore `(file, rule, fingerprint of the matched value)`, with the
line deliberately excluded. The trade-off: moving a secret from one file to
another reads as one fixed plus one new rather than a move. That is the rarer
event, and arguably the honest reading — the secret really is somewhere new.

## What it deliberately does not do

It does not start the agent under test: MCP gives a server no way to invoke its
client. Instead `privacy_get_scenario` hands the agent a scenario with planted
canaries to do itself, and `privacy_selftest` scores the trace it brings back.
To have AgentLeak start your agent, use the CLI: `agentleak selftest --cmd`.
The 362 bundled corpus scenarios remain a corpus for the CLI and CI
(`agentleak run --pack …`).

## Reading the result honestly

Every result carries `detection`, naming the tiers that actually ran:

```json
"detection": { "mode": "fast", "tiers": ["regex", "entropy", "correlation"], "degraded": false }
```

A clean result from the pattern tier alone is a weaker claim than a clean result
from the full pipeline. [The benchmark](https://www.agentleak.org/benchmark)
measures how much weaker. An agent that cannot see the difference will overstate
it to a human, which is why the field is always present.

One more guard worth knowing about: a trace with no `events` is rejected rather
than scored. An empty run would otherwise come back as a confident 100/100 —
the exact false pass this tool exists to catch, committed by the tool itself.

## Nothing is sent anywhere

No tool makes a network call. There is no project key and no upload in MCP mode;
to keep a history across machines, run a self-hosted server and use
`POST /api/agent/selftest` (see [selftest-agents.md](selftest-agents.md)).
