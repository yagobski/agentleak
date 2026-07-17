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
| `run` | Analyze a trace or scenario and write reports. |
| `report` | Re-render a saved JSON report. |
| `scan` | Scan source code locally, from ZIP or GitHub. |
| `history` | Show stored project progression. |
| `compare` | Compare two stored runs. |
| `serve` | Start the local web interface. |

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
