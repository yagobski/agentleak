<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# QA report: branch `next/qa`

Base: `main` at `c8260cf` (two PRs after v0.18.0). All test data synthetic.
Every fix has a regression test that fails on the base code and passes after;
most live in `tests/test_qa_regressions.py` and `tests/test_qa_web_regressions.py`.
No scoring formula, severity level or published number was changed.

## Results

| Check | Baseline (`c8260cf`) | Final (`next/qa`) |
| --- | --- | --- |
| `pytest -q` | 1297 passed, 21 skipped | 1368 passed, 21 skipped |
| `pytest --cov=agentleak --cov-fail-under=85` | not measured | 90.59 %, gate met |
| `ruff check .` | All checks passed | All checks passed |
| `mypy src/agentleak/` | no issues, 103 files | no issues, 104 files |
| `ruff format --check` | not used by the project (159 files would change); not run in CI | unchanged |

Toolchain: Python 3.12.15 (x86_64), editable install `.[dev,mcp]`. Note:
`pip install -e ".[dev,mcp]"` tried to build `cryptography` from source on this
machine; `--prefer-binary` picks the published wheel.

## Defects

Severity: critical / high / medium / low. "Fixed" gives the commit on `next/qa`.

### High

**QA-01 Code-scan snippets printed other findings' raw values.** Fixed `f87b6fe`.
Repro: a file with `print("Patient John Smith, SSN 123-45-6789")`, then
`agentleak scan file.py -f sarif -o out.sarif`: the SSN finding masks the SSN but
prints the name; the name and `print_sensitive` findings print the raw SSN, in
the console, the JSON and the SARIF (whose docs promise no raw values).
Cause: `_snippet` masked only the finding's own value. Fix: every value found
in the file is masked in every snippet, then the snippet is truncated (cutting
first could leave half a value).

**QA-03 Cross-account access to stored scenarios.** Fixed `fe5630b`.
Repro: user A uploads a scenario; user B sends its id as `scenario_id` to
`/api/analyze`, `/api/report/{fmt}`, `/api/projects/{B}/runs`,
`/api/projects/{B}/execute`, or with B's project key to `/api/selftest` and
`/api/agent/improve`. All returned 200 with a report on A's data (partially
masked values, data types); `execute` replays A's private records into B's run
and, in live mode, to B's model endpoint. Ids are 48 random bits, so this needs
a leaked id, but the check was simply missing. Cause: `_trace_from_payload` and
`_scenario_detail` resolved stored scenarios by id alone. Fix: owner-scoped
lookup; a foreign id answers like an unknown one. Also: `publish` accepted
projects with an empty `owner_id` (legacy), so any account could publish one;
it now uses `_owned_project` like every other project route.

**QA-04 Stored XSS in the HTML report.** Fixed `73460a2`.
Repro: a trace with `"agent_name": "<script>alert(1)</script>"` (also `run_id`,
`scenario_id`, custom rule names). The HTML report contains the script verbatim.
`/api/render/html` and `/api/report/html` serve that HTML on the platform origin,
where it runs with the viewer's session (it can read project API keys through
the API). Cause: `jinja2.Template(text)` without autoescape. Fix: autoescape on;
the one pre-built fragment (key insight) escapes its values. Diff of the
bundled reports before/after: only `&`/`'` entity changes.

**QA-07 Custom detector regex could pin a server worker (ReDoS).** Fixed `69ae118`.
Repro: `POST /api/analyze` with `custom_detectors: [{"name":"x","pattern":"(a+)+$"}]`
and a log of 30 `a` plus `!`: about a minute; 40 characters: hours. Any account
or project key can submit one, and `re` has no timeout. Fix: new
`core/regex_safety.py` refuses nested variable repetition before the platform
runs a user pattern (400). Fixed inner counts such as `(\d{3}-)+` still pass.
Limitation: overlapping alternation (`(a|aa)+`) is not detected.

**QA-15 `redact --style hash` was reversible.** Fixed `1dfe14d`.
Repro: `echo "SSN 123-45-6789" | agentleak redact --style hash` gives
`01a54629efb95228`, the first 16 hex digits of a plain SHA-256. Trying the
SSN space recovers it (0.5 s here with the area number known; the full 10^9
space is a short GPU job). Same for card numbers. Affects the CLI,
`sanitize_text`, the MCP `privacy_redact` tool and the proxies. Fix: HMAC with
the tokenizer's key (random per process, or `AGENTLEAK_TOKEN_KEY`).
`docs/defenses.md` updated.

### Medium

**QA-02 `agentleak run` / `report` / `redact` / `scan -o` crashed on bad input.**
Fixed `bddd629`, `7118185`. Repro: `agentleak run --trace` on a missing file, a
directory, an empty, malformed, non-UTF-8 or `[]` file, `--scenario nope`,
`--format pdf`: Python traceback, exit 1. `docs/cli.md` promises exit 2 for an
unresolvable input, and CI cannot tell "gate failed" from "wrong path". Worse:
any JSON object without `events` (a report, a config) loaded as an empty trace,
scored 100 and **passed the gate with exit 0**. Fix: clear `✗` messages, exit 2;
files without an `events` list are refused; an empty `events` list warns.
`report` refuses non-report JSON and unknown formats (exit 2); `redact` names
the UTF-8 problem; `scan -o <dir>` and an unwritable `run -o` are messages.

**QA-06 500s on malformed API input; a bad PATCH bricked a project.** Fixed `69ae118`.
Repro: `PATCH /api/projects/{id}` with `{"config": "bad"}` (or a non-object
vault) returned 200 and stored it; every later request on the project (runs,
code scans, API key, red team) returned 500. Also 500 for `/api/render/{fmt}`
with a non-report, `/api/compare` with non-string ids, scenario uploads whose
objective or vault has the wrong type, a trace that is a list or whose events
are not objects (`/api/analyze`, `/api/selftest`, `/api/agent/improve`), and
red team `n: "abc"`. Fix: config validated on create and PATCH (400), legacy
rows with a non-object config load as `{}`, `Trace.from_dict` and
`normalize_upload` raise `ValueError` with the reason, endpoints map it to 400.

**QA-09 Quadratic regex scans in built-in detectors.** Fixed `a3bdbdd`.
Repro: `SecretsDetector().detect("1-" * 25000)` took 23 s; `PIIDetector` about
3 s on 50 KB of any text; growth is quadratic (a 512 KB file in a code scan or
a large trace event would take tens of minutes). Fix: `SECRET_ASSIGNMENT_RE`
drops a redundant prefix group (same key words admitted; a 200,000-case
differential run against the old pattern found no difference);
`EMAIL_RE` / `URL_CREDENTIALS_RE` only run when the text contains `@` / `://`,
which cannot change their matches. Detection-quality tests unchanged.
Residual: a long run that does end in `@` is still quadratic (see open items).

**QA-10 Unbounded request bodies.** Fixed `efc56a9`. No size limit existed on
any endpoint. Requests whose `Content-Length` exceeds `AGENTLEAK_MAX_BODY_BYTES`
(default 32 MiB, `0` disables) now get 413. Chunked bodies without a length are
not capped (see open items). Documented in `docs/platform.md`.

**QA-13 GitHub Action gate (`scripts/gh_gate.py`).** Fixed `a382649`.
(a) Annotation text and properties were only newline-encoded: a data type, rule
or file name with a newline started a new workflow command (a PR controls file
names); a comma split properties; a literal `%0A` was decoded. Escaping now
follows GitHub's toolkit. (b) With `scenario: all` or `pack`, only the
alphabetically first report fed the outputs and summary, so the step could say
`verdict=Pass` while exiting 1; the lowest-scoring run is now headlined and
findings are counted across runs. (c) "Compliance at risk" read a key real
reports do not have (`compliance.failed_frameworks` instead of
`compliance.posture.failed_frameworks`) and never appeared.

### Low

| Id | Defect | Fix |
| --- | --- | --- |
| QA-05 | `/llms.txt`, `/llms-full.txt` and `docs/mcp.md` said 283 bundled scenarios; 266 ship (`/api/meta`, README, paper). | `25197b6` |
| QA-08 | `agentleak validate --trace t.json` without `agentleak.yaml` printed "config not found" and exited 1 for a valid trace. A missing *default* config is now skipped for a trace check; a named one is still required. | `cb473d3` |
| QA-11 | Event content nested about 1,000 levels deep raised `RecursionError` (500 on `/api/selftest`, traceback in the CLI). Refused past 200 levels with `ValueError`. | `3290a34` |
| QA-12 | `docs/platform.md` showed `AgentLeakClient(project=...)` against a plain `agentleak serve`; the client has no sign-in and failed with a bare `401 Not authenticated`. Docs and the error now say to use `serve --local` or `AgentSelfClient`. | `40cf022` |
| QA-14 | `action.yml` pasted `${{ inputs.version }}` into the install script (shell injection by whoever writes the workflow). Now passed through env. | `7379f5d` |
| QA-16 | `docs/install.md` gated CI with `agentleak run --trace traces/*.json --fail-on L4` (no such flag, and `--trace` takes one file). README listed a "PII Probes" pack that does not ship. | `c9b1e28` |
| QA-17 | `run.ingest({"events": [...]})`, the shape of a trace file, failed with a `TypeError`. | `68b8b87` |
| QA-18 | `redact` accepts `--style token`, but `--help` and `docs/cli.md` did not list it. | `a5303a6` |
| QA-19 | Public trust page title escaped twice (`R&D` shown as `R&amp;D`). | `fb6b15e` |

## Found, not fixed

| Severity | Item | Why not fixed / suggestion |
| --- | --- | --- |
| Medium | **SSRF through user-set LLM endpoints.** A project's `agent.base_url`, the account model key (`/api/auth/model-key`) and the red-team `base_url` override are fetched by the server with no address check. On a hosted (public-mode) deployment any account can make the server POST to `http://169.254.169.254/...` or internal hosts and read error text back. The agent-card fetch already has a guard (`core/agentcard.py`). | Design decision: self-hosted users legitimately point at `localhost` Ollama. Suggest applying the agent-card guard to LLM endpoints when `AGENTLEAK_PUBLIC_MODE=1`. |
| Low | Stale flags in the skill files: `SKILL.md` and `src/agentleak/skill/SKILL.md` (lines 60, 117, 136) use `agentleak run --trace traces/*.json --fail-on L4` and `agentleak run --redteam --scenario <name>`; `llms.txt` line 38 says "`--fail-on L4` fails the build". None of these flags exist. | Owned by the self-test branch (instructed not to edit). Equivalent today: `--fail-under N`; L4 leaks already block via `scoring.block_on_critical` (default true). README, docs/cli.md, docs/ci-gate.md, docs/quickstart.md and docs/redteam*.md were checked and are clean. |
| Low | MCP tools return `{"error": ...}` with `isError=false` (unknown path, unreadable trace, unknown redaction style). An agent may read that as success. | `mcp_server.py` is the self-test branch's area. |
| Low | `EMAIL_RE` is still quadratic when a long run of local-part characters ends in `@` (`"a" * 50000 + "@"`: 1.8 s). An exact linear rewrite changes matches in one edge case (adjacent addresses). | Detection branch's area; needs their precision/recall re-run. |
| Low | Markdown report does not escape trace-controlled strings (agent names, sources, data types). GitHub sanitises HTML, but a viewer that renders raw HTML would not. | Behavioural change to an export format; suggest escaping `<`, `>` and table pipes. |
| Low | `/llms.txt`, `/agents.md` and the agent card build absolute URLs from the `Host` header (`Host: evil.example` is reflected). Harmless unless a shared cache sits in front. | Suggest a configured public base URL. |
| Low | Input accepted without validation: `--fail-under` outside 0-100; unknown keys in `agentleak.yaml`; `execute` with an unknown `mode` runs scripted; `PATCH agent_type` and red-team `vertical` accept unknown values. | Behaviour choices; each is a one-line check if wanted. |
| Low | `agentleak.watch()` skips analysis when the `with` block raises, so a run that crashed mid-way has no report unless `run.analyze()` is called. | Deliberate (code comment); worth documenting. |
| Low | `agentleak init DIR` prints next steps relative to `DIR` without saying `cd DIR`. | Cosmetic. |
| Info | Body-size cap relies on `Content-Length`; a chunked request is not capped. | A reverse proxy limit covers it. |
| Info | The first account registered on a fresh deployment becomes admin. | Expected for self-hosting; worth stating in `docs/platform.md` for public deployments. |
| Info | Scoring: no defect found. Same trace twice, and across `PYTHONHASHSEED` values, gives byte-identical reports (minus timestamps and the integrity digest). | n/a |

## Flows exercised

- **Install**: `python -m build` (sdist + wheel); wheel contents diffed against
  `git ls-files src/` (all files present, plus licences); install in a clean
  venv outside the tree, `[gui,mcp]` extras; `python -m agentleak`;
  `import agentleak` 0.12 s with no FastAPI/MCP/Presidio/cryptography loaded;
  every `agentleak.integrations.*` module imports (except `litellm_guardrail`,
  which documents that it needs LiteLLM). Rebuilt and re-smoke-tested at the end.
- **CLI** (from the wheel): `version`, `--help`, `init` (twice), `validate`
  (good, missing, malformed YAML, unknown keys, `--trace`), `scenarios`,
  `--packs`, `--pack`, `schema` (catalog, named, unknown), `agent-card`, `skill`
  (status, `--install`, `--dry-run`, conflict, `--force`, `--uninstall`, bad
  target, `--print`, with `HOME` sandboxed), `run` (scenario, all, packs:
  agentleak_bench 36 / privacylens_ci 120 / agentdojo_exfil 100 reports,
  `--config`, every format, `--fail-under`, bad inputs listed under QA-02),
  `report` (all formats, bad inputs), `history` (with stored runs, limits),
  `compare`, `redact` (every style, stdin, file, bad style, missing, directory,
  non-UTF-8), `scan` (file, dir, default `.`, SARIF, `--fail-under`, bad
  format/mode/path/repo, output to a directory), `serve` and `serve --local`.
  Not run: `proxy`, `llm-proxy`, `evidence`, `subjects`, `admin` beyond `--help`
  (covered by existing tests, not walked by hand), `scan --repo` against GitHub
  (no network).
- **Web API** (live `agentleak serve` on loopback, plus TestClient): register,
  login, me, model key, projects CRUD, runs, history, compare, execute
  (scripted), red team, scenarios upload/list/delete, pack import, code scan
  (files, zip incl. `../` and absolute entries, which are skipped; bad base64;
  GitHub argument validation), agent card fetch SSRF guard (loopback, IPv6,
  hex/decimal IPs, link-local, `file:`, credentials in URL: all refused),
  API key, `/api/selftest`, `/api/agent/register|code|status|improve`,
  `/api/agent/onboard`, publish, trust page, badge, `/api/meta`, `/llms.txt`,
  `/llms-full.txt`, `/agents.md`, `/openapi.json`, SPA routes and path
  traversal on static files (refused). Two-account isolation on every
  project/run/scan/scenario route; anonymous access to every authenticated route.
- **MCP** over stdio with the `mcp` 2.x client: all four tools with valid,
  missing, wrong-type and unknown arguments; `.agentleak/history.jsonl` checked
  for raw values (none).
- **SDK**: `watch()` local, with a platform, with an unreachable platform, with
  an exception in the block; `record`/`tool_call`/`final_output`;
  `ingest_messages` (incl. content parts), `ingest_steps`, `ingest_spans`,
  `ingest_adk`, `ingest` with junk; `AgentLeakClient` against `--local` and an
  accounts server.
- **Core robustness**: every built-in detector timed on 24 adversarial 50 KB
  inputs; unicode, RTL override, zero-width characters, CRLF, duplicate event
  ids, timestamps, non-string content, deep nesting; determinism in-process and
  across hash seeds; HTML/markdown report injection.
- **Action**: `scripts/gh_gate.py` run against the real CLI and against stubbed
  reports (single, multiple, hostile strings); `action.yml` read for expression
  injection.

## Files most likely to conflict with other branches

`src/agentleak/web/app.py`, `src/agentleak/cli.py`, `src/agentleak/core/trace.py`,
`src/agentleak/detectors/secrets.py`, `src/agentleak/detectors/pii.py`,
`src/agentleak/scenarios/convert.py`, `src/agentleak/client.py`,
`src/agentleak/web/docs_content.py`, `docs/mcp.md`, `docs/platform.md`,
`README.md`, `CHANGELOG.md`.
