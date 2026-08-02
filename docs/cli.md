# CLI reference

The CLI is the local and CI interface. Run `agentleak --help` for the installed
version's complete help output.

| Command | Purpose |
| --- | --- |
| `version` | Print the package version. |
| `init [PATH]` | Scaffold configuration, folders and a sample trace. `--force` overwrites config. |
| `validate CONFIG` | Validate configuration; `--trace` also validates a trace. |
| `scenarios` | List built-in scenarios and sensitive-data domains. |
| `schema [NAME]` | Print the schema catalog or one named JSON Schema. |
| `skill` | Register AgentLeak as a skill so coding agents discover it themselves. |
| `run` | Analyze a trace or scenario and write reports. |
| `report` | Re-render a saved JSON report. |
| `scan` | Scan source code locally, from ZIP or GitHub. |
| `history` | Show stored project progression. |
| `compare` | Compare two stored runs. |
| `serve` | Start the local web interface. |

## Skill

AgentLeak ships a `SKILL.md`. Installing it into an agent's skills directory means the agent
knows to reach for `agentleak scan` on its own — no prompting, no memorized commands.

```bash
agentleak skill                       # where is it installed?
agentleak skill --install             # write it into every detected agent
agentleak skill --install -t claude-code -t cursor
agentleak skill --install --path ~/.config/myagent/skills
agentleak skill --install --dry-run   # show the plan, write nothing
agentleak skill --install --force     # overwrite a file that differs from ours
agentleak skill --uninstall
agentleak skill --print               # dump the skill text to stdout
```

Detected agents: Claude Code (`~/.claude`), OpenClaw (`~/.openclaw`), Cursor (`~/.cursor`),
Windsurf (`~/.windsurf`), Codex CLI (`~/.codex`). An agent counts as detected when its home
directory exists; the skill lands in `<agent>/skills/agentleak/SKILL.md`.

The installer never overwrites a skill file whose content differs from the packaged one — if
you edited it, you get a `conflict` and exit code 1 until you pass `--force`. Exit codes: 0
success, 1 conflict or no agent detected, 2 invalid usage.

Start a new agent session after installing; skills are read at session start.

## Run

```bash
agentleak run --trace traces/release.json \
  --config agentleak.yaml \
  --format json,html,markdown \
  --output reports \
  --fail-under 70

agentleak run --scenario healthcare_patient_summary
agentleak run --scenario all --quiet
```

`--fail-under` is a score gate. Configuration `privacy_policy` and critical
finding gates also participate in `blocked`. Exit code 0 means the run and
configured gates passed; 1 means a gate or operational run failed; 2 means
invalid usage or an unresolvable input.

## Scan

```bash
agentleak scan . --mode fast --fail-under 90
agentleak scan . --format sarif --output reports/agentleak.sarif
agentleak scan --repo owner/repository --branch main --output reports/code.json
```

SARIF contains file, line, rule, privacy level, tier, confidence and redacted
snippets. It does not contain raw matched secrets.

## Re-render and compare

```bash
agentleak report --input reports/run.json --format html,markdown
agentleak history support-bot --limit 20
agentleak compare RUN_A RUN_B
```

The report command does not re-run detection. Keep source JSON protected.
