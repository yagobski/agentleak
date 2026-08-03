# Contributing to AgentLeak

Thanks for helping make agents safer. AgentLeak is intentionally small and
dependency-light — keep contributions in that spirit.

## Where to start

Pick whichever of these sounds like your afternoon.

| If you want to… | Start here | Effort |
|---|---|---|
| **Support a framework we do not cover** | `agentleak/integrations/` — an adapter is one function that turns a framework's own events into a trace. A dozen worked examples sit next to yours. | An afternoon |
| **Add a detector** | `agentleak/core/detector.py` — a pattern, a name, a severity, a test that proves it fires and one that proves it does not over-fire. | An afternoon |
| **Report a wrong score** | [Open an issue](https://github.com/yagobski/agentleak/issues/new/choose) with the trace. This is the single most valuable thing you can send us: the score *is* the product. | Ten minutes |
| **Improve the corpus** | `scripts/packs/` — the extractors that build the scenario packs, and the rules that keep their ground truth honest. | A day |
| **Improve the docs** | `docs/` in this repository is the source; the site renders it. Anything that confused you is a bug in the docs. | Any size |

Two things are worth knowing before you touch scoring or detection:

- **Determinism is a feature, not an implementation detail.** The same trace must
  always produce the same score, or a regression in someone's CI stops meaning
  anything. No model may sit in the default path.
- **A false pass and a false finding are equally serious.** One tells someone
  they are safe when they are not; the other teaches them to ignore us. Tests
  for new detection should cover both directions.

## Ground rules

Everything runs locally by default and sends nothing anywhere. Any change that
adds a network call has to be opt-in and say so in the docs.

> **Working on this with an AI agent?** Read [AGENTS.md](AGENTS.md) first — it's
> the architecture map, the invariants, and the "how to extend" guide.

## Setup (Python)

```bash
pip install -e ".[dev]"
pytest                       # run the tests
ruff check agentleak/        # lint
mypy agentleak/              # type-check
```

## Setup (web GUI)

The GUI is a React + Vite + Tailwind + shadcn/ui app in
`agentleak/web/frontend/`. The **built** bundle is committed to
`agentleak/web/static/` and shipped in the wheel, so end users never need Node.

```bash
cd agentleak/web/frontend
npm install
npm run dev          # Vite dev server; proxies /api → http://127.0.0.1:8000
                     # In another terminal: `agentleak serve`
npm run build        # type-check + build into ../static
```

After changing the frontend, run `npm run build` and commit the updated
`agentleak/web/static/` so the change ships. Then `pip install .` to refresh the
installed bundle and restart `agentleak serve`.

## Guidelines

- **No network, no LLM in the core.** Detection must stay local, deterministic,
  and explainable (regex + dictionaries). LLM-based detection, if ever added,
  belongs behind an optional extra — never a required dependency.
- **Privacy first.** Never log or persist raw sensitive values. Reports show
  redacted values by default.
- **Type everything.** New code should pass `mypy` and `ruff`.
- **Test what you add.** Keep coverage at or above 70%. Detectors need both
  positive cases and false-positive guards.

## Adding a detector

1. Subclass `agentleak.core.detector.Detector`, set `name`, implement `detect`.
2. Return `RawMatch` objects with a `data_type`, `severity`, `confidence`, and a
   `recommendation`.
3. Register it in `agentleak/detectors/__init__.py` if it's a built-in toggle.
4. Add tests in `tests/test_detectors.py` (detection **and** a clean-text guard).

## Adding a scenario

1. Define a `Scenario` under `agentleak/scenarios/`.
2. Bundle a **synthetic** trace under `agentleak/examples/`.
3. Add it to the registry and to `tests/test_scenarios.py`.

## Test coverage guarantees

The suite under `tests/` asserts real behavior, not just line coverage. The
following guarantees are enforced by tests and should stay true for any
follow-up change:

- **Agent-card URL fetch is SSRF-safe** (`agentleak/core/agentcard.py`,
  exercised end-to-end via the API in `tests/test_agent_api.py` and directly
  in `tests/test_agentcard.py`). Only `http`/`https` are allowed; URLs with
  embedded credentials are rejected; the resolved IP (literal or via DNS) is
  checked against loopback/link-local/private/CGNAT/reserved/multicast/
  unspecified ranges, including every hop of an HTTP redirect. Disallowed
  targets return a clear `400` (`UnsafeURLError`); a name that fails to
  resolve, or a reachable-but-erroring host, returns `502` — that distinction
  (SSRF finding vs. network failure) is itself covered by tests.
- **Orchestrator/runner failures don't lose the trace.** `AgentRunError`
  (raised when the LLM backend fails mid-run, in both the single-agent
  `agent/runner.py` and multi-agent `agent/orchestrator.py` live paths) carries
  the partially captured `Trace` on a `.trace` attribute so callers can still
  inspect what happened before the failure. Also covered: malformed tool-call
  JSON from the model (falls back to a text answer instead of crashing),
  max-step exhaustion, non-dict/empty-name tool entries in `_normalize_tools`,
  and MCP server/tool detection in `_toolbox_for` (`tests/test_orchestrator.py`,
  `tests/test_runner.py`).
- **Client (`agentleak/client.py`) never leaks a raw exception for a bad
  server response.** Both a non-JSON error body and a non-JSON `200` body are
  turned into a clear `AgentLeakError` instead of an uncaught
  `json.JSONDecodeError` (`tests/test_client.py`).
- **OTEL/OpenInference and computer-use ingestion tolerate messy input.**
  Nested/typed OTLP attribute values, missing attributes, duck-typed span
  objects, and unknown/failed/browse computer-use actions all convert to a
  usable `Trace` instead of raising (`tests/test_integrations.py`).
- **Track/watch submission failures never take down a user's run.**
  `agentleak.track.Run` records network/API submission failures on a public
  `submit_error` attribute and surfaces a `⚠ platform submission failed`
  warning in `summary()` — the local analysis report is always still
  available, and the failure is never swallowed silently. A submission that
  fails for an unexpected (non-`AgentLeakError`) reason still propagates, since
  that indicates a real bug rather than a transient/API issue
  (`tests/test_track.py`).
- **`agentleak scan` gives clear, non-crashing errors.** Missing zip files,
  invalid zip content, a malformed `owner/repo` argument, GitHub `403`s,
  unreachable GitHub, a non-directory path, and `--fail-under` threshold
  breaches all exit with code `1` and a `✗ ...` message instead of a traceback
  (`tests/test_cli.py`).

### Known optional / uncovered areas

These are intentionally out of scope for the guarantees above — don't assume a
regression here will be caught by CI:

- **Presidio detector** (`agentleak/detectors/presidio_detector.py`, ~17%
  coverage) — only exercised when the optional `presidio` extra is installed
  and its NER model downloaded; the default test run stubs/skips it.
- **Frontend/browser rendering** (`agentleak/web/frontend/`) — no headless
  browser tests; only the built static bundle and backend API are covered.
- **Live external LLM calls** — all LLM-backed tests (orchestrator, runner,
  `llm.py`) mock `urllib.request.urlopen`; nothing in the suite makes a real
  network call to OpenRouter/OpenAI-compatible endpoints. Run with
  `OPENROUTER_API_KEY`/`AGENTLEAK_LLM_*` unset (and no local `.env` loaded) to
  confirm no test accidentally depends on real credentials.

## Pull requests

Run the full check suite before opening a PR. Describe the leak class or channel
your change covers, and include a before/after of the score where relevant.
