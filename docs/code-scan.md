# Static code scan

Static code scan finds privacy and secret-handling risks before an agent runs.
It accepts a local directory, ZIP archive, or GitHub repository and returns
redacted findings with file, line, rule, level, tier, and confidence.

## Install and run

```bash
pip install "agentleak @ git+https://github.com/yagobski/agentleak-oss.git"
agentleak scan ./my-agent
```

Scan other sources:

```bash
agentleak scan ./agent.zip --output reports/code.json
agentleak scan --repo acme/support-bot --branch main --fail-under 90
agentleak scan ./my-agent --format sarif --output reports/agentleak.sarif
```

`--fail-under` makes the command exit 1 when the code privacy score is below
the selected threshold. A successful scan exits 0; a scan error exits 1.

## What is detected

The scanner combines the normal detection layers with code-specific checks:

- hardcoded API keys, credentials, tokens, and high-entropy strings;
- PII in fixtures, prompts, tests, comments, and log statements;
- sensitive fields sent to third-party services;
- committed `.env` files and unsafe debug output;
- decomposed or obfuscated identifiers, card numbers, and social numbers;
- several quasi-identifiers in one file that increase re-identification risk.

Every finding includes a rule and a redacted snippet. Raw secret material is not
included in the report by default.

## Detection modes

```bash
# Fast local scan
agentleak scan ./my-agent --mode fast

# Presidio recognizers
agentleak scan ./my-agent --mode standard

# Presidio plus semantic judge
export AGENTLEAK_LLM_BASE_URL=https://openrouter.ai/api/v1
export AGENTLEAK_LLM_MODEL=openai/gpt-4o-mini
export OPENROUTER_API_KEY=sk-...
agentleak scan ./my-agent --mode hybrid
```

`standard` requires `pip install 'agentleak[presidio]'`. Hybrid mode is
optional and BYOK; it adds semantic coverage but does not replace deterministic
rules.

## Configuration

Reuse the project configuration so code and runtime scans share policy:

```bash
agentleak scan ./my-agent --config agentleak.yaml --output reports/code.json
```

Custom identifiers and regex rules belong in the configuration's custom
detection section. Keep rules narrowly scoped, assign the correct L1–L4 level,
and add a fixture test for each rule to avoid noisy CI failures.

## Read the result

The console summarizes:

```text
Code privacy score: 74/100 — Conditional pass
  mode: standard · tiers: regex, presidio
  files scanned: 42 · findings: 3 · levels: L4=1, L3=1, L2=1, L1=0
```

Use `--output` for the complete JSON result. The report contains scan source,
files scanned, detection tiers, score, verdict, finding locations, confidence,
and redacted snippets.

Use `--format sarif` for GitHub Code Scanning, VS Code SARIF viewers, or any
SARIF 2.1.0 consumer. SARIF results preserve the rule, file, line, privacy
level, detector tier, confidence, recommendation, and redacted snippet. They
never contain the raw matched secret.

Prioritize L4 credentials first, then secrets in logs or external calls, then
PII fixtures and quasi-identifier correlations. Confirm a suspected finding in
the source before changing behavior; entropy findings can be false positives.

## Hosted API

For a project-authenticated web scan:

```bash
curl -sS -X POST "$AGENTLEAK_BASE/api/projects/$PROJECT_ID/code-scan" \
  -H 'content-type: application/json' \
  -H "Cookie: $AGENTLEAK_SESSION" \
  -d '{"source":"github","repo":"acme/support-bot","branch":"main"}'
```

For an autonomous agent using its project key:

```bash
curl -sS -X POST "$AGENTLEAK_BASE/api/agent/code" \
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \
  -H 'content-type: application/json' \
  -d '{"source":"github","repo":"acme/support-bot","branch":"main"}'
```

`POST /api/agent/code` also accepts `source: "zip"` with base64 content or
`source: "files"` with explicitly submitted files. An empty body scans the
source declared on the stored agent card.

## CI workflow

```yaml
- name: Scan agent source
  run: agentleak scan . --mode standard --fail-under 90 --format sarif --output reports/agentleak.sarif

- name: Upload to GitHub code scanning
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: reports/agentleak.sarif

- name: Upload scan evidence
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: agentleak-code-scan
    path: reports/agentleak.sarif
```

Do not upload unredacted source or reports as public artifacts. Use a protected
artifact store for findings that contain sensitive context.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| Repository cannot be fetched | Verify `owner/name`, branch, network access, and GitHub authorization. |
| Too many entropy findings | Review each location, add a narrowly scoped exclusion/rule, and rotate real credentials. |
| PII in a generated file is missed | Ensure the file extension is supported and enable standard or hybrid mode. |
| Hybrid scan cannot connect | Check `AGENTLEAK_LLM_BASE_URL`, model, and BYOK key; fall back to standard mode. |
| Score does not fail CI | Confirm `--fail-under` is higher than the returned score and inspect the shell exit code. |

## Safety boundary

Scan only code you are authorized to inspect. GitHub scanning is an explicit
network operation. Treat the source, paths, and redacted snippets as sensitive;
rotate any real credential found immediately and do not use a passing scan as a
replacement for secret management or code review.
