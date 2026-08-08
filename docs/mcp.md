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

## The four tools

| Tool | When an agent should reach for it |
|---|---|
| `privacy_preflight` | Before saying the work is done. Scans the project and reports what is **new since the last check**. |
| `privacy_scan_code` | When only the current state matters, not the change. |
| `privacy_check_trace` | When a run has been captured and you want it scored across all eight channels. |
| `privacy_redact` | Before writing anything into a log, an issue, or a commit message. |

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

It does not run the 283 bundled scenarios against your agent. Those are traces,
and replaying them would mean invoking the agent under test, which MCP gives no
way to do. They remain what they are: a corpus for the CLI and CI
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

## Sending results to a project

If a project key is configured, results also reach the hosted workspace, so runs
accumulate into a history you can compare across sessions. A network failure is
reported and ignored; it never swallows the local verdict.

Without a key, nothing leaves the machine. That is the default.
