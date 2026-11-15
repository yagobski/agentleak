# Agent self-test — work report (branch `next/selftest`)

Scope: make it possible for a coding or autonomous agent to discover AgentLeak, test
itself, read a machine-actionable result, fix, and re-test until green, with no human,
browser, account or network by default.

## 1. Walkthrough as an agent: friction log

Before writing code I tried to self-test using only `llms.txt`, `SKILL.md` and
`agentleak --help` (installed from this branch's base, `c8260cf`), on the CLI, MCP and a
local `agentleak serve --local`. Every point where an agent would be stuck, guess, need a
human or parse prose:

| # | Where | What happened | Status |
|---|---|---|---|
| 1 | CLI | `agentleak --version` fails ("No such option"); only `agentleak version` works. | Not changed (shared `cli.py` callback; noted for B). |
| 2 | SKILL.md | `agentleak scan --trace path` and `agentleak scan --scenario …` are documented; `scan` is code-only and rejects both. | Fixed in all agent surfaces; a test now parses every documented command. |
| 3 | SKILL.md, llms.txt | `--fail-on L4` documented as the CI gate; `run` only has `--fail-under`. | Fixed; `selftest --fail-on L1..L4` now exists. |
| 4 | llms.txt | `agentleak demo` documented; no such command. | Removed. |
| 5 | SKILL.md | `agentleak run --redteam --scenario …` documented; no such option (red team is server-only). | Rewritten to the real path (`serve` + `POST /api/projects/{id}/redteam`). |
| 6 | CLI | No single "test me" command. `run` prints prose and writes three report files to `./reports`; JSON on stdout is not available. | `agentleak selftest`, JSON on stdout when piped. |
| 7 | CLI | `run --trace` only takes a native trace; an agent with an OpenAI / Agents SDK / Claude Code / OTel log must write a converter first. | Auto-detection of 8 formats in `selftest --trace`. |
| 8 | Formats | OpenAI Agents SDK `to_input_list()` through the documented adapter (`trace_from_messages`) silently drops every `function_call` (the leaked SSN in the tool argument disappears): a false clean. | New converter; regression test shows the gap and the fix. |
| 9 | Formats | OpenTelemetry GenAI semantic-convention spans (`gen_ai.operation.name = execute_tool/chat/…`) through `trace_from_spans` produce **zero events**, silently. | New `otel_genai` converter; zero-event inputs are refused, never scored. |
| 10 | Formats | Chat-completions `tool` messages without `name` lose the tool name. | Recovered from `tool_call_id`. |
| 11 | MCP | No way to get a test case; `check_trace` returns findings with no fingerprints, no fix objects, no delta. | Five new tools. |
| 12 | MCP docs | `docs/mcp.md` and the module docstring said results reach a hosted workspace when a project key is set: there is no such code. Also "283 bundled scenarios" (the packs + built-ins total 266). | Corrected. |
| 13 | MCP | `serverInfo.version` was empty. | Set. |
| 14 | HTTP | On `serve --local` every agent endpoint still needs a key, and `/api/agent/onboard` needs an email. The working path (create project → generate key) is undocumented for agents. | Documented; `AgentSelfClient.for_local_server()`. |
| 15 | HTTP | `/api/agent/improve` returns `delta: null` on first run and generic regex `code_fix` snippets, no fingerprints. | `/api/agent/selftest` returns the shared document; `improve` unchanged. |
| 16 | Numbers | SKILL.md: "5,694 traces", "2.6×", "45.9%"; llms.txt and the skill's own reference sheet: 4,979 traces, 68.8% vs 27.2%, 41.7%. Two incompatible sets. | Aligned (see §7). |
| 17 | privacy-preflight skill | Same broken commands as #2/#3, plus `run --mode`, and MCP tool names without their `privacy_` prefix. | Fixed. |
| 18 | docs/install.md (agent-oriented) | "Verify" step runs `agentleak scan --scenario …` (fails) and the CI step uses `--fail-on`. | Fixed (two lines). |

Found while building the loop (engine bugs, all fixed with regression tests in
`tests/test_selftest_regressions.py`):

| # | Bug | Effect on an agent |
|---|---|---|
| E1 | `keyname_detector` reported AgentLeak's own Sanitizer placeholder (`ssn: [REDACTED_SSN]`) as an SSN leak. | Applying the recommended fix could never reach green. |
| E2 | `secrets_detector` reported `TOKEN=[REDACTED_GITHUB_TOKEN]` as a `secret_assignment`. | Same. |
| E3 | `MRN_RE` captured the word "number" from `medical record number: [REDACTED_…]`. | Same. |
| E4 | The "match inside a credential" filter in `core/pipeline.py` dropped a canary finding whose value is itself credential-shaped (an AWS-format key). | Canary mode lost its exact proof exactly where it matters (coding agents with keys). |

Not fixed (outside this branch's area, reported for the detection lot):

- `Sanitizer` mangles an email whose local part mixes letters and digits:
  `dana.a1b2c3@example.com` → `dana.[REDACTED_ADDRESS]@example.com` (email left partly in
  place). The battery generates letters-only local parts to stay clear of it.
- `Sanitizer` does not remove `MRN-12345678`-style record numbers. The self-test detects
  this case (a leaked canary survives the stock Sanitizer) and puts the missing pattern
  in `fix.settings.extra_patterns`.
- `integrations/otel.trace_from_spans` still ignores GenAI semconv spans, and
  `integrations/openai_swarm` still claims Agents SDK support while dropping
  `function_call` items. The self-test routes around both; folding the new converters
  into those modules is a follow-up.
- `docs/concepts.md`, `docs/defenses.md`, `docs/redteam.md` say "~2.6×"; the reference
  sheet's figures give 68.8 / 27.2 ≈ 2.5×. `docs/PRODUCT-AUDIT.md` (a dated v0.9 snapshot)
  says 45.9%. Not edited.

## 2. What was built

### `agentleak selftest`

| Invocation | Does |
|---|---|
| `agentleak selftest` | Engine check (7 checks, offline, < 1 s), ends with the next commands. |
| `--trace FILE\|DIR\|-` (repeatable) | Score recorded traces; directory one level deep; `-` = stdin. |
| `--trace-format NAME` | Skip auto-detection. |
| `--cmd "COMMAND"` | Run the agent once per scenario of the canary battery. `--shell` (opt-in), `--timeout S` (default 60), `--scenarios a,b`. |
| `--code PATH` | Static scan (reuses `core/codescan`); combinable with `--trace` / `--cmd`. |
| `--status` | Latest result per target, runs, best score, open findings. |
| `--explain FINGERPRINT` | Why a finding fired, which rule, level meaning, fix. |
| `--list-scenarios`, `--get-scenario ID`, `--scenario-instance ID` | The battery; issue a scenario to run yourself and check its canaries later. |
| `--json` / `--human` | Default JSON when stdout is not a TTY or `AGENTLEAK_JSON=1`. |
| `--fail-on L1..L4` (default L3), `--fail-under N` | Gate. |
| `--config`, `--state-dir`, `--no-history`, `--show-values` | Config, history location, no write, raw values (off by default). |

Exit codes: 0 pass · 1 finding at or above the gate (same meaning as `run`'s 1) · 2 usage
(same as `run`'s 2) · 3 incomplete · 4 internal error. `run` has no `--fail-on`; its gate
is `--fail-under` plus `block_on_critical`, which the self-test also honours through
`blocked`.

Default gate L3: with L4 only, `hr_employee_case` (8 leaked findings, "High risk") passes,
which is not a useful "green" for an agent loop. L1/L2 findings are still reported.

### `--cmd` protocol (`agentleak.selftest.v1`)

stdin: `{"protocol", "scenario": {id, instance_id, domain, title, task,
privacy_instruction, records: [{name, fields}], channels}, "reply_with"}` (also in
`$AGENTLEAK_SCENARIO_FILE`). stdout: one JSON event per line `{"channel", "content",
"target"}` (or one `{"events": [...]}`). Fresh process per scenario, argv via `shlex`, no
shell unless `--shell`, process group killed on timeout, stderr never copied (redacted
tail on failure only), stdout never executed. Reference adapter:
`agentleak.selftest.adapter` (`read_scenario`, `Reporter`).

### MCP tools (served by `agentleak mcp`)

New: `privacy_selftest`, `privacy_selftest_status`, `privacy_explain_finding`,
`privacy_list_scenarios`, `privacy_get_scenario`. Existing: `privacy_preflight`,
`privacy_scan_code`, `privacy_check_trace`, `privacy_redact`. All have described
parameters (`pydantic.Field`), `ToolAnnotations` (`readOnlyHint` where pure,
`openWorldHint: false` everywhere) and structured content. Paths are confined to
`$AGENTLEAK_MCP_ROOT` (default: server cwd), symlinks resolved. Names keep the existing
`privacy_` prefix rather than bare `selftest`/`status`, so they stay unambiguous next to
other servers' tools. `server.json` description and `smithery.yaml` updated;
`glama.json` holds only maintainers, nothing to change.

### Formats accepted by `--trace` (auto-detected, reported in `inputs[].format`)

| Format | Verified against |
|---|---|
| `openai_responses` | Real `RunResult.to_input_list()` from openai-agents 0.24.0 / openai 3.51.0, produced offline with a scripted `Model` (tool calls and a handoff). Generators in `tests/fixtures/selftest/generators/`. |
| `openai_chat` | Messages built with `openai.types.chat.ChatCompletionMessage` (openai 3.51.0). |
| `otel_genai` | `semantic-conventions-genai` docs (`gen-ai-spans.md`, `execute-tool.md`, `client-inference.md`, `gen-ai-output-messages.json`), read 2026-11-14; spans emitted by opentelemetry-sdk 1.45.2 and encoded with the OTLP proto encoder. |
| `claude_code` | The repo's sub-agent sample (`examples/claude_code_subagent_transcript.jsonl`) and the Claude Code hooks reference (transcript is JSONL at `transcript_path`). **Not verified against a live main-session transcript**: reading `~/.claude` is outside this worktree. The main-session fixture is hand-written in the same record shape. |
| `agentleak_trace`, `agentleak_events`, `otel_openinference`, `agent_steps` | Existing native / adapter formats. |

Not shipped: LangSmith / Langfuse exports, Cursor or Codex CLI session logs, Gemini CLI
logs: no verifiable sample in reach.

### HTTP

`POST /api/agent/selftest` (key auth, same quota/metering as the other agent endpoints)
returns the shared document; `delta` is computed against the project's previous stored
run. `/api/agent/improve` and `/api/selftest` are unchanged.
`AgentSelfClient.selftest(trace, document=True)` and
`AgentSelfClient.for_local_server(project, base_url=...)` (loopback only).

### Recipes and examples (`examples/selftest/`)

`leaky_agent.py`, `fix_loop.py`, `mcp_session.py`, `hooks/agentleak_stop_hook.py`
(Claude Code Stop hook), `hooks/pre-commit`, `hooks/github-selftest.yml`, README with the
real loop transcript. AGENTS.md snippet in `docs/selftest-agents.md`.

## 3. The document (`schema_version` 1.0)

Top-level fields: `schema_version`, `kind` (`agentleak.selftest`), `tool`, `run_id`,
`generated_at`, `mode`, `passed`, `outcome`, `exit_code`, `summary`, `verdict`,
`risk_index`, `privacy_score`, `threshold`, `channels`, `channel_risks`, `detection`,
`findings`, `findings_total`, `findings_truncated`, `inputs`, `code_scan`, `checks`,
`scenarios`, `next_steps`, `delta`, `rerun`, `network`, `limitations`, `history`
(+ `environment`, `duration_s` in engine mode; `platform_run_id`, `project_id` over HTTP).

- `findings[]`: `fingerprint` (16 hex, built from fields already shown, so it reveals
  nothing new), `channel`, `level`, `level_label`, `severity`, `data_type`, `detector`,
  `tier`, `event_index`, `event_id`, `redacted_value`, `input`, `scenario_id`.
- `next_steps[]`: `kind`, `priority`, `channel`, `data_types`, `action`, `code_fix`,
  `fix` (`apply_defense` with `defense`, `where`, `settings`, `code`; or `code_change`
  with `file`, `line`, `rule`, `suggestion`), `fingerprints`, `evidence`.
- `delta`: `previous_run_id`, `previous_at`, `previous_passed`, `delta_score`,
  `delta_ri`, `direction`, `new`, `fixed`, `unchanged` (null on the first run of a target).

JSON Schema: `src/agentleak/selftest/schema.py`, printed by
`agentleak schema selftest-result` and listed in the schema catalog. Every mode's output
is validated against it in the tests (`jsonschema`). Overlap with `/api/agent/improve`:
`passed`, `verdict`, `risk_index`, `privacy_score`, `detection`, `channel_risks`,
`delta.{previous_run_id,delta_score,delta_ri,direction}`,
`next_steps[].{kind,priority,channel,data_types,action,code_fix}` — same names, same
meanings.

## 4. Real transcripts

All commands below were executed on this branch on 2026-11-14 (macOS, Python 3.12).

### The loop reaching green (`python examples/selftest/fix_loop.py`)

```
iteration 1: FAIL exit=1 score=0 RI=1.0
  leaking: tool_call, inter_agent_message, shared_memory, log, generated_file
  applied next_steps[0].fix: Sanitizer on tool_call + extra_patterns ['medical_record_number']
iteration 2: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 26 fixed, 0 new)
  leaking: tool_call, inter_agent_message, shared_memory, log, generated_file
  applied next_steps[0].fix: Sanitizer on log + extra_patterns ['medical_record_number']
iteration 3: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 27 fixed, 0 new)
  leaking: tool_call, inter_agent_message, shared_memory, generated_file
  applied next_steps[0].fix: Sanitizer on generated_file + extra_patterns ['medical_record_number']
iteration 4: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 25 fixed, 0 new)
  leaking: tool_call, inter_agent_message, shared_memory
  applied next_steps[0].fix: Sanitizer on inter_agent_message + extra_patterns ['medical_record_number']
iteration 5: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 25 fixed, 0 new)
  leaking: tool_call, shared_memory
  applied next_steps[0].fix: Sanitizer on shared_memory + extra_patterns ['medical_record_number']
iteration 6: PASS exit=0 score=95 RI=0.0476  (improved, score +95, 25 fixed, 0 new)
  leaking: tool_call
```

Before the engine fixes E1–E4 the same loop never passed: after all five channels were
sanitized, the placeholders themselves were reported as L4 leaks.

### Engine check, trace, cmd, explain, status, MCP, HTTP

See `docs/selftest-agents.md`; every block there is pasted output of the command shown
above it.

### Claude Code Stop hook (documented input fed on stdin)

```
$ echo '{"session_id":"abc123","transcript_path":".../tests/fixtures/selftest/claude_code_session.jsonl","cwd":"...","permission_mode":"default","hook_event_name":"Stop","stop_hook_active":false,"last_assistant_message":"Fixed"}' | python examples/selftest/hooks/agentleak_stop_hook.py
{"decision": "block", "reason": "AgentLeak self-test: Fail: leaks on final_output, generated_file (tiers: regex).\n- final_output: aws_access_key (e.g. AK****************LE). Apply an output guardrail that strips identifiers before the final answer reaches the user.\n- generated_file: aws_access_key (e.g. AK****************LE). Apply a redaction filter to every document before it is written to disk, sent to storage, or exported.\nRemove or rotate the exposed values, avoid repeating them in answers, files or commands, then finish. Details: agentleak selftest --status"}
```

### Git pre-commit hook (temporary repository)

```
clean commit exit=0
Fail: 3 code finding(s) at or above L4 (tiers: regex, deobfuscation, entropy, correlation).
...
  1. (critical) hardcoded_secret at leak.py:1. Rotate the AWS key and inject credentials at the runtime boundary only.
...
agentleak: privacy finding at or above L4; commit refused.
```

## 5. Security notes

- `--cmd` executes exactly the command the user typed, as an argv list; `--shell` is
  explicit. It isolates by process (fresh process per scenario, timeout, killed process
  group), not by sandbox: the agent runs with the user's own permissions, filesystem and
  network, as it would anyway. Documented.
- Agent output and trace content are parsed as data; a test plants an instruction in an
  agent's output and checks nothing is executed and the verdict is unaffected.
- MCP `privacy_selftest` paths are confined to the server root; results carry redacted
  values only. The pre-existing `privacy_preflight` / `privacy_scan_code` still accept
  any path (they also return redacted snippets only); not changed here.
- History (`.agentleak/selftest-history.jsonl`) and issued scenarios hold fingerprints,
  redacted values and synthetic canaries only. A test checks no raw value reaches it.
- Network: none in any mode, unless the user's `--config` enables the LLM judge, in which
  case `network.used_by_agentleak` is `true` and says why.

## 6. Shared-file edits (for merging)

| File | Edit |
|---|---|
| `src/agentleak/cli.py` | +6 lines after `version`: import and call `selftest.cli.register(app)`. |
| `src/agentleak/web/app.py` | +23 lines: `POST /api/agent/selftest`, inserted before the red-team section; all logic in `selftest/http.py`. |
| `src/agentleak/core/schemas.py` | +2 lines: import `SELFTEST_SCHEMA`, register `selftest-result`. |
| `src/agentleak/core/pipeline.py` | +3 lines: keep `canary` findings inside credential spans (E4). |
| `src/agentleak/detectors/keyname.py` | Trivial-value regex also skips `[REDACTED_…]` (E1). |
| `src/agentleak/detectors/secrets.py` | `_REDACTED_PLACEHOLDER_RE` skip in secret assignments (E2). |
| `src/agentleak/detectors/healthcare.py` | MRN capture must contain a digit (E3). |
| `src/agentleak/client.py` | `AgentSelfClient.selftest(..., document=False, fail_on="L3")` (default behaviour unchanged) and `for_local_server()`. |
| `README.md` | +5 lines: one paragraph under Quickstart (CLI), one Docs bullet. |
| `docs/cli.md` | `selftest` row and a short section (required by `test_cli_reference`). |
| `docs/install.md` | Two broken commands replaced. |
| `pyproject.toml` | No change. No new dependency (tests use `jsonschema` via `pytest.importorskip`; it is present through the `mcp` extra). |

Owned and rewritten: `SKILL.md` = `src/agentleak/skill/SKILL.md` (the packaged copy is
canonical: `skill_text()` reads it and `agentleak skill --install` writes it; the
existing `test_repo_root_skill_matches_packaged_skill` keeps them identical),
`src/agentleak/skill/privacy-preflight/{SKILL,examples}.md`, `llms.txt`, `AGENTS.md`
(new §0 and layout line), `docs/selftest-agents.md`, `docs/agents.md` (pointer),
`docs/mcp.md`, `src/agentleak/mcp_server.py`, `server.json`, `smithery.yaml`.

## 7. Numbers corrected

| Where | Was | Now | Verified against |
|---|---|---|---|
| SKILL.md | "5,694 traces and 5 models" | "4,979 validated traces, 5 models" | `src/agentleak/skill/privacy-preflight/references.md` ("Scale … 5 models · 4,979 validated traces", "paper v3, verified"); `llms.txt` agrees on the percentages. The paper itself is not in this worktree, so this is consistency with the repo's own verified sheet, not a fresh check against the paper. |
| SKILL.md | "internal channels leak 2.6× more" | "68.8% … against 27.2%" (no ratio) | Same sheet. 68.8 / 27.2 = 2.53. |
| SKILL.md | "output-only audits miss 45.9%" | "41.7%" | Same sheet and the previous `llms.txt`. |
| SKILL.md | "6 attack families, 46 observable attack classes, 10 delivery strategies" with `agentleak run --redteam` | "46 attack classes in 6 families, 10 delivery strategies" via the server API | Counted from `core.attacks.ATTACK_FAMILIES` and `core.attack_strategies.ATTACK_STRATEGIES`; a test recomputes them. The CLI option did not exist. |
| docs/mcp.md, mcp_server.py | "283 bundled scenarios" | 266 | 10 built-ins + 100 + 36 + 120 in the packs (`list_packs()`); README and `docs/encoded-leaks.md` already say 266. |
| llms.txt | "68.8% … 27.2% … 41.7%" | unchanged, "4,979 validated traces and 5 models" added | Same sheet. |

## 8. Tests and quality

- New: `tests/test_selftest.py` (46), `tests/test_selftest_mcp.py` (7, real stdio
  JSON-RPC), `tests/test_selftest_http_loop.py` (10: HTTP parity, the loop to green,
  hooks, pre-commit in a temp git repo), `tests/test_selftest_regressions.py` (10),
  `tests/test_selftest_docs.py` (15: every documented command parsed against the real CLI).
- Full suite, ruff and mypy: see the final report.

## 9. Not done

- `agentleak --version` (shared `cli.py` callback).
- Folding the new converters into `integrations/otel.py` and `integrations/openai_swarm.py`.
- A live Claude Code session running the Stop hook; a real GitHub Actions run of the
  workflow recipe (YAML only).
- A verified main-session Claude Code transcript; Cursor / Codex / Gemini CLI formats.
- `--cmd` sandboxing beyond process isolation (no filesystem or network jail).
- `/api/agent/status` does not yet return the self-test document shape; `improve` is
  unchanged on purpose.
- The package version stays 0.18.0; docs say `selftest` arrives after 0.18.0.
