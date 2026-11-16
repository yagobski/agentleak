# CI policy gate

The CI gate turns AgentLeak into a release control. A trace or code scan is
allowed to fail the build when it crosses the project's privacy policy.

## Fastest setup

```yaml
name: Agent privacy

on: [pull_request]

jobs:
  privacy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install agentleak==0.9.1  # pin the version so the gate is reproducible
      - run: agentleak run --trace traces/latest.json --fail-under 80 --format json,markdown
```

`agentleak run` exits non-zero when the privacy score is below the threshold or
when the configured critical-finding policy blocks the run.

## Configure a policy

Commit the policy with the agent:

```yaml
scoring:
  fail_below: 80
  block_on_critical: true

vault:
  mode: explicit
  scope_def: "data reachable by the production support agent"
  levels: {"1": 40, "2": 12, "3": 5, "4": 2}
```

Use an explicit vault for comparable release scores. Keep the same detector
mode, scenario fixtures, and vault scope between baseline and candidate runs.

## Trace gate and code gate

```yaml
- name: Runtime privacy gate
  run: agentleak run --trace traces/latest.json --config agentleak.yaml --fail-under 80

- name: Static privacy gate
  run: agentleak scan . --config agentleak.yaml --mode standard --fail-under 90
```

Run a scripted red-team baseline separately when its campaign policy is defined
in Python; see [Red Team](redteam.md) for ASR/ELR/CLR thresholds and coverage.

## Artifacts and pull requests

Always preserve JSON evidence and publish HTML/Markdown to a protected CI
artifact store:

```yaml
- name: Upload AgentLeak reports
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: agentleak-reports
    path: reports/
```

The CLI prints the offending channel, level, score, and remediation insight in
the job log. The JSON report is the machine-readable source for PR comments or
security dashboards.

## SARIF and pull-request comments

The AgentLeak Action (`uses: yagobski/agentleak@<ref>`) has two optional
outputs, both off by default.

```yaml
name: Agent privacy

on: [pull_request]

permissions:
  contents: read
  security-events: write     # only for upload-sarif
  pull-requests: write       # only for pr-comment

jobs:
  privacy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: agentleak
        uses: yagobski/agentleak@main   # pin a release tag or commit
        with:
          trace: traces/latest.json
          fail-under: "80"
          sarif: agentleak.sarif              # write SARIF 2.1.0
          pr-comment: "true"                  # one sticky comment, updated on each push
          baseline: baseline/report.json      # optional: report from the base branch
      - if: always() && steps.agentleak.outputs.sarif != ''
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ${{ steps.agentleak.outputs.sarif }}
          category: agentleak-trace
```

- **`sarif`** writes trace findings as SARIF (one rule per data type, the
  channel and level on each result, values never included). Uploading it to
  the Security tab needs `security-events: write`. A finding points at the line
  of its event in the trace file, so give a `trace:` path inside the
  repository; scenario runs have no file and get a logical location only.
  With `scan:` the code scan's own SARIF is written instead.
- **`pr-comment`** posts one comment on the pull request (and edits it on later
  runs) with the verdict, the per-channel table and, when `baseline` names a
  report JSON (or a directory of them) from the base branch, the new and the
  resolved findings. It needs `pull-requests: write` and uses `github-token`
  (the job's token by default). On a pull request from a fork the token is
  read-only: the comment is skipped with a warning and the gate's verdict is
  unchanged. The `comment` output says `created`, `updated`, `failed` or
  `skipped: <why>`.

Everything the Action writes to annotations, the job summary, the comment and
`GITHUB_OUTPUT` is escaped: data types, channels, run ids and file names come
from the pull request under test. The CLI's own log output runs between
`::stop-commands::` markers, so text in a trace cannot become a workflow
command.

## Baselines and regressions

Do not compare unrelated traces. A valid regression comparison keeps constant:

1. the sensitive vault and level counts;
2. detector mode and custom rules;
3. scenario or test input;
4. framework adapter and channel mapping;
5. score policy.

For project history, use the stored platform runs and compare two run IDs. A
score improvement with a smaller vault is not evidence of a safer agent.

## Scheduled security campaign

A practical cadence is:

- every pull request: one or two deterministic traces and a fast code scan;
- protected branch: full trace suite and standard code scan;
- nightly or weekly: complete red-team and evasion profiles;
- controlled staging only: live LLM campaign with an authorized BYOK key.

Keep live credentials in CI secrets, never in `agentleak.yaml`, trace content,
or logs. Pin the AgentLeak package version in release workflows.

## Failure handling

| Result | Meaning | Action |
| --- | --- | --- |
| exit 0 | policy passed | keep artifact and merge if other checks pass |
| exit 1 | policy failed or scan failed | inspect report, remediate, rerun |
| exit 2 | invalid CLI/config/input usage | repair command or fixture |
| 502 from live API | target unavailable | retry only after checking endpoint health |

Treat an infrastructure error as a failed control in protected branches; do not
silently convert it into a pass.

## Safety boundary

A green job certifies only the tested fixtures and configured policy. It does
not prove safety against unseen prompts, tools, memory paths, model updates, or
production data. Require human review for policy changes, vault reductions, and
any exception that permits a critical finding.

### The configuration is input from the pull request

`agentleak.yaml` lives in the repository, so a pull request can change it. A
configuration cannot make AgentLeak send an arbitrary environment variable
anywhere: a key named in `api_key_env` goes only to its provider's host (or,
for another `*_API_KEY`, to a server on the runner itself), and any other pair
must be allowed by `AGENTLEAK_KEY_ENVS` in the workflow's `env:`, which the
pull request does not control on `pull_request` from a fork. See
[detection.md](detection.md#tier-3--llm-judge). Still expose to the gate step
only the secrets it needs; on `pull_request_target`, do not run the gate
against the pull request's code with secrets available.
