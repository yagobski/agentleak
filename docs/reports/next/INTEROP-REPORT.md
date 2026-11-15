# Interop report (branch `next2/interop`)

Date: 2026-11-15. Base: `main` at v0.19.0.

Goal: make "use them together" one command (`agentleak import <file> --score`
on what promptfoo, Inspect AI, garak and PyRIT already write), close the
capture gaps in AgentLeak's own SDK adapters, and give trace findings SARIF and
a pull-request comment in the Action.

## 1. Formats

Every importer was built against a file produced by the real tool, offline. No
model API was called: each run used the tool's offline mechanism and a stub
that returns canned, synthetic text. The tools were installed in throwaway
virtual environments under the git-ignored `.scratch/`; none is a dependency.
Fixtures (trimmed) and generators are in `tests/fixtures/interop/`, described
in its `README.md`.

### promptfoo

- **Verified against:** promptfoo 0.125.1 (npm, Node 24.22.1), real runs.
- **Sample:** `promptfoo eval -o results.json` with the built-in `echo`
  provider and a local JavaScript stub provider; a second run with
  `tracing: {enabled: true}` and the OTLP HTTP receiver on 127.0.0.1, where the
  stub posts OpenInference spans (AGENT, TOOL, LLM) under the `traceparent`
  promptfoo passes it. The export then has a top-level `traces` list
  (`TraceData`: `traceId`, `spans` with ms times) joined to result rows by
  `traceId`. Reading the shipped code confirmed `promptfoo export eval` writes
  the same document (`createOutputData`).
- **Mapping:** `prompt.raw` -> user_input; `response.output` -> final_output;
  application spans (no `promptfoo.span.role`) -> the OpenInference/GenAI span
  adapter (tool_call, tool_response, inter_agent_message, log); promptfoo's
  `test_case`, `target` and `grader` spans are excluded, and the trace checks
  (`trace_problem`) are now shared with the promptfoo assertion, which imports
  them from `agentleak.interop.promptfoo`. Plugin, strategy, severity,
  provider, pass/score -> `source_labels`.
- **Lost:** without tracing, everything between prompt and reply. With tracing,
  only what the application instrumented; never shared memory or files.
- **Not verified by a run:** `response.metadata.redteamHistory` (multi-turn red
  team: one user_input/final_output pair per turn) was implemented from the
  `RedteamHistoryEntry` type in promptfoo 0.125.1's shipped `index.d.ts`. A
  multi-turn strategy needs an attacker model, so no sample was produced.
  `results.version` other than 3 is accepted with a note.

### Inspect AI

- **Verified against:** Inspect AI 0.3.290 (Python 3.12), real runs.
- **Sample:** a task with `mockllm/model` and scripted `custom_outputs` (two
  tool calls, then an assistant message with a reasoning part and text), two
  tools, `includes()` scorer; written with `log_format="eval"` and `"json"`.
- **Mapping:** see `docs/interop.md`. System/user -> user_input; assistant
  `tool_calls` -> tool_call (`transfer_to_*` -> inter_agent_message); reasoning
  (not redacted) -> log; assistant text -> inter_agent_message, the last one
  final_output; `tool_use` content parts -> tool_call + tool_response; `tool`
  messages -> tool_response with the error message. `attachment://<hash>`
  references are resolved only against the sample's own `attachments` table.
- **Lost:** the sample `store`, the `events` log (sandbox commands, store
  changes), non-text parts (counted in notes).
- **Finding while verifying:** Inspect 0.3.290 compresses `.eval` members with
  zstd (zip method 93), which Python reads only from 3.14. The importer reads
  them on 3.14+ or with the optional `zstandard` package (raw member bytes are
  located through the local header, in memory), and otherwise fails with a
  message that names `inspect log convert --to json`. The fixture set includes
  the untouched zstd archive and a deflate copy of the same members.

### garak

- **Verified against:** garak 0.17.1, real run. Its full dependency set needs
  `torch>=2.13`, which has no wheel for the x86_64 Python here; garak was
  installed with `--no-deps` plus the modules its CLI imports for this run.
- **Sample:** `garak --target_type function --target_name stubagent#respond
  --probes test.Test,dan.Dan_11_0 --generations 1` with a local stub function.
- **Mapping:** attempt records (the last per `uuid`, normally `status` 2 after
  detection); `prompt.turns` user/system -> user_input; assistant turns inside
  the prompt (history the probe wrote) -> user_input with source
  `prompt_history`; each `outputs` entry -> final_output. Probe, goal, intent,
  status and `detector_results` -> `source_labels`.
- **Lost:** everything except the prompt and the reply: garak is black-box.
  Its traces have only user_input and final_output and say so.
- **Not supported:** reports from garak versions whose `prompt` was a plain
  string (before Conversation prompts); refused with a message.

### PyRIT

- **Verified against:** PyRIT 1.2.0, real run of PyRIT's own code.
- **Sample:** `PromptSendingAttack` against a stub `PromptTarget`, in-memory
  database, a prepended system message and simulated tool exchange; serialized
  with `JsonConversationMemoryPrinter` and `build_scenario_conversations_document`,
  the functions behind `output_conversation_async(format="json")`,
  `output_scenario_conversations_async` and the CLI's `scenario-results --view
  conversations|full --format json`. A stand-in object supplied only the
  scenario result id; the `pyrit_scan` CLI was not run (it reads results
  through a PyRIT server).
- **Mapping:** see `docs/interop.md`. Simulated pieces (`is_simulated: true`)
  are attacker-written history -> user_input, never a leak by the target;
  `function_call` -> tool_call with name and arguments parsed;
  `function_call_output` -> tool_response; reasoning summaries -> log.
- **Lost:** media pieces (`image_path`, `audio_path`, `video_path`,
  `binary_path`, `url`): their value is a path or URL, never opened; counted
  in notes. The `conversations` view does not record the PyRIT version.
- **Not supported:** the PyRIT 0.x memory export (a flat list of message
  pieces). PyRIT 1.2.0 no longer has it and no 0.x sample was produced.

### Channel coverage

| Source | user_input | tool_call | tool_response | inter_agent_message | log | shared_memory | generated_file | final_output |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| promptfoo, no tracing | yes | — | — | — | — | — | — | yes |
| promptfoo, with tracing | yes | spans | spans | spans | spans | — | — | yes |
| Inspect AI | yes | yes | yes | yes | yes | — | — | yes |
| garak | yes | — | — | — | — | — | — | yes |
| PyRIT | yes | if returned | if returned | — | yes | — | — | yes |

## 2. Safety of the importers

- Files are data: no URL fetch, no path dereference, no `eval`, no pickle. A
  test runs an attack payload through the garak importer with `urlopen`,
  `socket.create_connection` and `subprocess.Popen` replaced by functions that
  fail the test.
- Limits: 256 MB per file, JSON nesting 200, archive members 64 MB each and
  512 MB in total, 100,000 members, 50,000 traces. Errors name the limit.
- Archives are read in memory member by member; names with `..`, a leading
  `/`, a backslash, NUL or a drive letter are refused (zip-slip), tested.
- Run ids (they become report file names) are reduced to `[A-Za-z0-9._-]`.
- An import that yields no event is an error, not a Pass.
- Values in `trace.metadata["observation"]` are sanitized by the runner (known
  keys, known channel names, bounded strings) before they reach a report.

## 3. Adapter gaps closed

The four converters (OpenAI Agents SDK items, chat-completions messages,
Claude Code transcripts, OTel GenAI spans) moved from `selftest/formats.py` to
`agentleak/interop/convert.py`; `selftest.formats` re-exports the same names.
`integrations/openai_swarm.py` and `integrations/otel.py` now delegate to them.
Measured on the self-test fixtures (real SDK output), with the default runner:

| Input (fixture) | Adapter | Before: events | Before: leaks, score | After: events | After: leaks, score |
| --- | --- | --- | --- | --- | --- |
| `agents_sdk_items.json` (openai-agents 0.24 `to_input_list()`) | `openai_swarm.trace_from_messages` | 2 (user_input, final_output) | none, 100 (false Pass) | 6 (+2 tool_call, +2 tool_response) | `ssn@tool_call`, `email@tool_call`, 33 |
| `agents_sdk_handoff.json` | `openai_swarm.trace_from_messages` | 2 | `credit_card@final_output`, 0 | 3 (+1 inter_agent_message handoff to `billing`) | same, 0 |
| `chat_completions_messages.json` | `openai_swarm.trace_from_messages` | 6 | 4 types @ tool_call, 0 | 7 (+1 system message as user_input) | same, 0 |
| `otel_genai_otlp.json` (OTel SDK 1.45.2 spans) | `otel.trace_from_spans` | 0 | none, 100 (false Pass) | 4 (user_input, tool_call, tool_response, final_output) | `email@tool_call`, 0 |

Tests: `tests/test_adapter_capture.py` (adapter output equals the self-test
loader's on the same fixture; reasoning and handoff items; SDK item objects;
mixed OpenInference + GenAI span lists; the promptfoo assertion grading GenAI
spans).

**Intentional behaviour changes** (all in the direction of capturing more):

1. `openai_swarm.trace_from_messages` returns the Responses converter's trace
   for Agents SDK item lists (event sources/targets follow that converter:
   `source="user"/"agent"`, tool name as target). Plain chat messages keep the
   old mapping, plus `system`/`developer` -> user_input (more vault entries, so
   ρ_S can grow; no bundled scenario uses this adapter).
2. `otel.trace_from_spans` emits events for GenAI spans it used to ignore.
3. The promptfoo assertion with `require_trace: true` grades traces made of
   GenAI spans instead of returning INCOMPLETE.
4. Two regression tests that pinned the gaps
   (`tests/test_selftest_regressions.py`) now pin that they are closed.

## 4. SARIF and the Action

- `agentleak run --format sarif` / `report --format sarif` / `import --score
  --format sarif`: `interop/sarif.py`. Rule `agentleak/trace/<data_type>` with
  `security-severity` (L4 9.0, L3 7.5, L2 5.0, L1 2.0); result level L3-L4
  error, L2 warning, L1 note; properties carry channel, level, severity,
  detector, event id, source, target; `partialFingerprints` from run id,
  channel, data type, source, target and event id; logical location
  `<run_id>/<event_id>`; physical location = the trace file and the line of
  `"event_id": "<id>"` when `--trace` is known. Messages name the data type and
  channel only; a test checks that neither raw nor partially redacted values
  appear.
- Validation: the OASIS SARIF 2.1.0 schema is **not vendored** (OASIS licence
  terms, not an OSI licence). `tests/test_sarif_trace.py` validates a subset
  schema written from the specification (required `version`/`runs`/`tool.driver.name`,
  `message.text`, level enum, `ruleIndex` consistency, physical location
  shape, numeric `security-severity`, ≤25,000 results) with `jsonschema`
  (installed with the `mcp` extra) and plain assertions. The output was not
  uploaded to GitHub code scanning from this environment.
- Action (`action.yml`, `scripts/gh_gate.py`): new inputs `sarif`,
  `pr-comment` (default `false`), `baseline`, `github-token`; outputs `sarif`,
  `comment`. Multi-run SARIF (pack / `scenario: all`) is merged into one log.
  The PR comment is sticky (marker `<!-- agentleak-privacy-gate -->`, only a
  Bot-authored comment is edited), lists new/resolved findings against a
  baseline report keyed on (run id, channel, data type, detector), never fails
  the gate (a fork's read-only token gives `failed`/`skipped`), and refuses a
  non-https API URL or a malformed repository name.
- Escaping: report values in the job summary, the comment and the scan summary
  go through `_md` (HTML entities for `& < > " ' ` | [ ] \ @ * ~ # ! ( )`, control
  characters to spaces, length cap) or `_code` (identifier characters only);
  `GITHUB_OUTPUT` values lose line breaks; the echoed CLI command is escaped;
  the CLI's output runs between `::stop-commands::<random>` and `::<random>::`.
  `tests/test_gh_gate_interop.py` uses a hostile string (backticks, pipes, an
  `<img onerror>`, a Markdown link, an `@mention`, a newline followed by
  `::error::`) as data type, channel, run id, verdict and file name.
- Permissions documented in `docs/ci-gate.md`: `security-events: write` for
  the SARIF upload, `pull-requests: write` for the comment.
- Not done: a real GitHub Actions run of the new inputs.

## 5. Shared files touched

- `src/agentleak/cli.py`: 3 lines registering `import`; `run`'s `--format`
  help mentions `sarif`; `write_reports(..., trace_path=trace)`; 5 lines in
  `_print_result` printing the observation note.
- `src/agentleak/selftest/formats.py`: converter bodies replaced by
  re-exports from `agentleak.interop.convert`.
- `src/agentleak/core/trace.py`: optional `Trace.metadata` (default `{}`) and a
  nesting check on it. `core/report.py`: optional `AnalysisResult.observation`,
  emitted as `observation` only when set. `core/runner.py`: `_observation_of`.
  No existing field, formula or bundled-scenario score changed.
- `src/agentleak/reporters/__init__.py`: `sarif` format; `render`/`write_reports`
  take an optional `trace_path`. `markdown_reporter.py` and
  `templates/report.html.j2`: one note each when `observation` lists unobserved
  channels (these two are in the security reviewer's area; the edits are a
  few lines each, autoescaped in HTML).
- `integrations/promptfoo_assert.py`: trace checks moved to
  `interop/promptfoo.py`; `_trace_problem` kept as a wrapper.
- `action.yml`, `scripts/gh_gate.py`, `README.md` (two links),
  `docs/integrations.md`, `docs/cli.md`, `docs/ci-gate.md`, `CHANGELOG.md`
  (delimited block), `.gitignore` (`.scratch/`). `pyproject.toml` unchanged: no
  new dependency.

## 6. Not done / open

- promptfoo multi-turn `redteamHistory`: type definitions only (above).
- PyRIT `pyrit_scan` CLI output and PyRIT 0.x exports; PyRIT `full` view was
  not produced (needs a `ScenarioResult` from a scenario run), so reading
  `overview.scenario.pyrit_version` is untested against real output.
- Inspect `store` and sandbox events as `shared_memory` / `generated_file`:
  possible, not done (risk of double counting the message history).
- The Action's SARIF and comment were not exercised on GitHub.
- `agentleak selftest --trace` does not auto-detect the four red-team formats;
  `agentleak import` is the entry point for them.
