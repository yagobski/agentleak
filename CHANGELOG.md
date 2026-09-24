# Changelog

All notable changes to AgentLeak OSS are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.14.2] - 2026-09-23

`redact` returned text that looked sanitised and still carried the credential.
Every case below was found by piping text through the published 0.14.1 wheel;
each one produced a placeholder, and the secret sat next to it.

### Fixed

- **A private key lost its header and kept its body.** The pattern matched the
  `-----BEGIN … PRIVATE KEY-----` line only, so the redactor replaced that line
  and returned every line of key material below it. The whole block is now one
  match, through the `END` line. When a log limit has cut the `END` line off,
  the base64 lines after the header are taken instead.
- **A connection string's password was redacted as an email address, and its
  username left in place.** In `postgres://admin:secret@db.internal/prod`,
  `secret@db.internal` also looks like an email. The sanitizer's
  "inner span wins" rule then discarded the connection-string match, so `admin`
  survived and the label was wrong. That rule exists for imprecise key-name
  spans. A credential is an exact match, so it is now removed whole, along with
  anything matched inside it. URLs with credentials in any other scheme
  (`https://bot:token@github.com/…`) are now detected too.
- **`password: hunter2` came back from `redact` unchanged.**
  `secret_assignment` was listed as detect-only because "blanking the
  assignment would remove the code". The detector never matched the
  assignment, only the value after the `=`, so redacting it keeps the code.
  Assigned secrets are now redacted by value.
- **`DB_PASSWORD=…`, `OPENAI_API_KEY=…` and `aws_secret_access_key = …` were not
  seen at all.** The key-word boundary could not see past an underscore, and
  that is how most secrets are named. Prefixed names now match. Reads
  (`os.environ.get(...)`, `settings.API_KEY`, `response.next_page_token`) are
  still left alone. On this repository's own examples, the change adds one
  finding to `agentleak scan`: a hardcoded `CRM_TOKEN` that was always there.
- **GitHub fine-grained tokens** (`github_pat_…`, GitHub's default since
  2023) are detected.
- **IBANs printed in groups of four** (`FR76 3000 6000 0112 …`), as banks and
  invoices print them, are detected.
- **French birth-date keywords** (`né le`, `née le`, `date de naissance`)
  anchor a date of birth, as `born` and `DOB` already did.
- **`agentleak redact --style mask` exited with code 2.** The command's own help
  text and `docs/cli.md` both documented it. `mask` is now an alias for
  `masked`, and the help lists all six styles.
- **`Sanitizer(extra_patterns={...})` raised `ValueError`** although
  `docs/defenses.md` showed exactly that call. A dict is now accepted beside the
  list of tuples.

### Documentation

- `docs/defenses.md`: every style example was wrong (`[SSN REDACTED]`,
  `XXX-XX-6789`, `[SOCIAL_SECURITY_NUMBER]`). They are now the real output, and
  a new section explains what a redaction covers and why.
- `docs/detection.md` listed routing numbers and SWIFT codes, which no detector
  finds. The table now lists what the detectors actually emit.
- `CITATION.cff` and `.zenodo.json` had said 0.12.0 since 0.12.0.

### Unchanged

The healthcare scenario still scores 0.44 (4 of 8 secrets), and every figure
in `docs/detection-quality.md` is identical. That benchmark measures personal
data, and none of these fixes touch it.

## [0.14.1] - 2026-08-30

### Fixed

- **The scenario library said 10 when the engine has 266.** The other 256 sit in
  packs, in a section below the grid — off screen on a normal viewport — so the
  first impression of the product was a tenth of what it advertises. The header
  now reads "10 loaded, 266 available — the rest are in the packs below",
  counted from the packs the engine reports rather than written down, so it
  cannot drift from `/api/meta` the way a hand-typed figure once did. The
  sentence disappears once everything is imported.

## [0.14.0] - 2026-08-30

Catches the leak that lives between two traces, and stops the platform saying
two things badly.

### Added

- **Cross-session subject attribution.** Every other part of this project
  scores one trace against itself, which cannot see the failure that matters in
  a deployment serving more than one person: a secret written to memory while
  serving Alice, repeated while serving Bob. Both runs score independently, both
  may score well, and nothing said the second disclosed the first one's data.
  A run now names whose data it is about — `Trace.subject`, `watch(subject=...)`,
  or an event's `metadata["subject"]` — and `core/subjects.py` keeps a
  per-project ledger that reports a cross-subject disclosure. Gated in CI with
  `privacy_policy.forbid_cross_subject`; inspected and erased with
  `agentleak subjects`. See `docs/cross-session.md`.

  Attribution is reported *beside* the score, never folded into it: the secret
  leaked in this trace either way and AgentRisk already counts it, so
  discovering whose it was must not silently move the number. The ledger stores
  salted fingerprints and never a value, with a per-ledger salt at mode 600,
  because unsalted fingerprints are a dictionary attack away from the values
  they stand for. `--forget` erases a subject, because erasure is a right.

### Changed

- **A scripted red-team run now says what it measured.** It returns ASR 1.0
  across every family, which is correct — the target leaks by construction, so a
  perfect score means the detectors saw every planted leak. Read without that,
  "100% of attacks succeeded" is a devastating and false statement about an
  agent that was never executed. The response declares `fixture_integrity` or
  `policy_outcome` with a sentence naming what was attacked.

- **The red-team catalog is presented as compatibility, not a scoreboard.**
  Leading with a plugin count invites a comparison against a project with far
  more resources behind it, and winning it would not make anybody's agent
  privacy better understood. The docs say what the transpositions are for, what
  this module does that a prompt-and-response red-teamer structurally cannot,
  and that using both is the sensible answer.

## [0.13.0] - 2026-08-30

Judge the flow, not the presence — and decide before emission rather than
scoring after the fact.

### Added

- **Contextual integrity.** Every assertion this project shipped judged data
  *presence*: this type, that channel, that many findings. A SIN reaching a KYC
  vendor for an identity check and the same SIN reaching an analytics sink are
  identical under all of them, and opposite under GDPR purpose limitation.
  `privacy_policy.flows` moves the unit to the quadruple **(data type, sender,
  recipient, purpose)**. Three quarters of it was already in the trace; purpose
  comes from event metadata the SDK already passes through. Allow rules are
  *scoped* default-deny, so adopting the feature never floods an existing
  project with violations about data no rule mentions, and a flow that declares
  no purpose fails a rule that requires one. See `docs/contextual-integrity.md`.

- **`agentleak proxy` — a runtime gateway for MCP.** Sits between an agent and
  its tool servers and judges each `tools/call` on the way out: allow, redact,
  or block. Redact is the default for a refusal, deliberately — a gateway that
  blocks whatever it dislikes breaks the agent and gets switched off — and
  redaction is surgical, removing only the refused data types so the call still
  works. Everything that is not a `tools/call` crosses untouched, and a refusal
  arrives as a tool result with `isError` rather than a protocol error, so the
  agent can read the reason and adapt. See `docs/runtime-gateway.md`.

- **`agentleak evidence` — a hash-chained decision log.** Every gateway decision
  is appended with the hash of the entry before it, so editing, removing or
  reordering any entry breaks every hash after it and verification says which
  one. Tamper-evident, not tamper-proof, and the docs say so. No secret value is
  ever written to it.

- **`agentleak serve --local`.** A loopback install no longer opens by asking
  for an email address, under a footer that says "100% local". One implicit
  owner, no registration. Because this is an unauthenticated web application,
  three independent gates keep it on loopback: the CLI flag, the environment
  resolution, and `run_server` itself. Without `--local` nothing changes.

### Fixed

- **`agentleak.__version__` was left at 0.12.0 when 0.12.1 was cut.** The
  published 0.12.1 wheel therefore reports itself as 0.12.0 through
  `agentleak version`, `GET /api/health`, `GET /api/meta` and the provenance
  field on every report — on a project whose stated rule is that every public
  number must be checkable against the running software. `tests/test_version.py`
  caught it and CI went red on the release commit, but the release ran anyway:
  the tag gate only ever compared the tag with `pyproject.toml`. It now checks
  `__version__` too, so a wheel that would misreport itself cannot be published.
  The 0.12.1 already on PyPI is immutable and keeps the wrong string; this is
  the release that carries the corrected one.

  The consequence reached further than a printed string. The site deployment
  installs an exact version and then asks the running service which version it
  is; 0.12.1 answered "0.12.0", so the check concluded the Docker build had
  reused a cached layer and failed the deploy — with a diagnosis pointing at
  the wrong cause entirely. Production was in fact running 0.12.1 the whole
  time.

## [0.12.1] - 2026-08-30

Rebuilt the dashboard sign-in and registration pages as a full-screen split
rather than a centred card. The complete logo — shield and wordmark — sits in
the top bar, the ASCII mark holds the left pane at whatever size the viewport
allows, and the form keeps a fixed measure on the right; both panes run to the
bottom of the window. The mark itself was re-rasterised from the logo's own
outline at 48 by 32, so the shield closes to its point instead of stopping
short of it, and the surfaces are drawn from the shared theme tokens, so light
and dark need no separate rules.

## [0.12.0] - 2026-08-29

Detection-integrity release. Five defects, all in the deterministic tier that
runs for everyone by default, all found by exercising the shipped wheel rather
than by reading the code. **The bundled healthcare scenario now scores 0.44
instead of 0.3793** — see below for why the old number was wrong.

### Fixed

- **`agentleak redact` could not remove a SIN, a spaced credit card, a
  diagnosis or a medication.** The sanitizer kept its own table of ten patterns
  — described in its own comment as "a simplified subset of the full detector"
  — while the detector registry emitted thirty-eight data types. There was no
  SIN pattern in any format, none for special-category health data, the card
  pattern required contiguous digits so `4111 1111 1111 1111` passed through,
  and the health identifier was `[A-Z]{4}\d{8}`, which cannot match the
  `TR12345678` in this project's own demo trace. The command is the documented
  door into prevention and is exposed to coding agents as an MCP tool: it
  returned text that looked sanitised and was not.

  The `Sanitizer` now reads the detector registry — which is what its docstring
  already claimed. Spans are resolved before substitution instead of running
  patterns over a mutating string, and where spans nest the inner one wins, so
  `ssn: 412-55-9087 and more text` loses the SSN and keeps the sentence. An
  outer span with nothing inside it is still removed, because for a rare
  diagnosis it is the only signal there is. 35 types are redactable; 3 are
  declared detect-only with their reason in `DETECT_ONLY`.

- **The same secret was counted more than once, and the Risk Index moved with
  it.** AgentRisk identifies a secret by data type plus matched string, so
  `diabetes` and `Type 2 diabetes` entered the vault as two diagnoses. The
  score therefore depended on *phrasing*: the same secrets written as prose and
  as JSON scored differently, which makes a CI regression as likely to be a
  rewording as a leak. `agentleak.core.coalesce` resolves matches that contain
  one another at token boundaries into one secret, keeping the tightest span as
  its identity and the strongest classification in the cluster as its level.
  Boundaries matter: `1234` inside `12345` is a different account.

- **The key-name capture ran to the end of the line instead of the end of the
  sentence.** `final_output`, `log` and `inter_agent_message` carry prose, which
  supplies none of the delimiters the pattern stopped at, so
  `medication: insulin. Please forward to the specialist.` was stored as a
  42-character medication and a 106-character health identifier reached the
  leak-path explorer as unreadable masked evidence. A period now closes the
  value only when whitespace or the end of the text follows, so decimals and
  dotted identifiers survive; past a 120-character cap the match is dropped.

- **`agentleak scan` flagged an innocent line three times and missed the
  export.** Reading source rather than a trace, the key-name detector captured
  `patient[` out of `SIN={patient['sin']}` and reported a bracket as a leaked
  SIN, health identifier and diagnosis — all attributed to the first occurrence
  in the file, on a line containing none of them. Values that are source rather
  than data no longer become findings, and findings are emitted per occurrence
  instead of once per file. This matters past the terminal: the Action
  annotates PR lines with these.

### Added

- **`sensitive_to_memory` and `credentialed_record_export` code rules.** The
  first reads writes into memory/store/cache/session — the C4 channel this
  project exists to audit, which had no code rule at all. The second fires when
  one call carries both a credential and a whole record; either half alone is
  ordinary code, and the existing HTTP rule missed it because such calls go
  through an SDK wrapper rather than requests or fetch. That combination is the
  shape behind this year's MCP incidents.

- **Labelled-SIN detection.** A bare run of nine digits is an order number as
  often as an identifier, so the unseparated form counts only next to the word
  that names it: `SIN 123456789` is detected, `order 123456789` is not.

- **Published detection quality** — `docs/detection-quality.md`, reproducible
  with `python scripts/detection_quality.py`. 378 labelled values from the
  bundled vaults, deterministic tier only, reported in two conditions because
  the tier reads field names as well as values: **structured 0.926** (the
  internal channels the product is about) and **prose 0.275** (with the key
  gone, this tier finds emails and SSNs and little else). Zero false positives
  across independent benign controls. Every figure carries its numerator,
  denominator, version, tier and provenance; nine malformed bundled fixtures
  are excluded and the exclusion is counted rather than hidden.

- **`GET /api/meta` reports redaction coverage,** so "anything we detect, we
  can redact" is checkable against the running software rather than asserted.

### Changed

- **The bundled healthcare scenario scores 0.44, not 0.3793.** Its vault held
  `health_condition: 'diabetes'` *and* `health_condition: 'Type 2 diabetes'` —
  one diagnosis counted twice. The duplicate sat only on `tool_response`, a
  baseline channel, so it padded ρ_S without ever reaching WSL and the
  published figure read *below* the truth. Four secrets of eight leak, not four
  of nine. README, quickstart and install carry the corrected numbers.

## [0.11.10] - 2026-08-26

Redesigned the dashboard sign-in and registration pages. The wordmark is now
set as text, flush left in a tinted header band, and the AgentLeak shield is
drawn in ASCII beside the form: its three cuts are the three internal channels
the audit reads, named in the caption underneath. Both themes and the small
viewports were rebuilt with it, and the stylesheet lost the rules belonging to
the layout this replaces.

## [0.11.8] - 2026-08-16

Corrective metadata release. Every attribution of the published IEEE Access
article now names its published authors: Faouzi El Yagoubi, Godwin Badu-Marfo
and Ranwa Al Mallah. This restores Godwin Badu-Marfo in the bundled benchmark
pack and REUSE manifest, and records his ORCID in the preferred citation.
Software authorship remains El Yagoubi, Quintero and Al Mallah. The wheel now
includes canonical MIT and CC-BY-4.0 texts, the REUSE mapping, and a third-party
fixture NOTICE.
README licensing language now distinguishes AgentLeak-authored MIT components
from PrivacyLens-derived CC-BY-4.0 fixtures. Runtime behavior and the
266-scenario corpus are unchanged from v0.11.7.

## [0.11.7] - 2026-08-16

Metadata and documentation correction: the preferred citation now names the
published IEEE Access article and its published author list, while software
authorship remains El Yagoubi, Quintero and Al Mallah. Presidio references now
use the current Data Privacy Stack project branding. Runtime behavior and the
266-scenario corpus are unchanged from v0.11.6.

## [0.11.6] - 2026-08-15

Metadata-only authorship correction: José Alejandro Quintero replaces Godwin
Badu-Marfo as the second author in citation, archive and fixture-attribution
metadata. Detection, scoring, packaged scenarios, reports and public APIs are
unchanged from v0.11.5.

## [0.11.5] - 2026-08-15

Provenance and licensing release. No detection, scoring or reporting behaviour
changes; every reported number for the bundled corpus is unchanged because the
removed pack was already excluded from published results.

### Removed

- **`ai4privacy_probes` scenario pack (17 records).** The pack was described as
  modelled on `ai4privacy/pii-masking-200k`, whose upstream terms are
  non-standard, and it shipped without complete source/licence/attribution
  fields. The bundled corpus is now 266 scenarios (10 built-ins, 36
  `agentleak_bench`, 120 `privacylens_ci`, 100 `agentdojo_exfil`), all with
  resolved provenance. The `ai4privacy`-shaped record *converter* is unaffected:
  it reads a record shape supplied by the user and redistributes no dataset.

### Added

- **Complete pack provenance metadata.** `agentleak_bench` now declares
  `source_url`, `license` and `attribution`. A test asserts that every bundled
  pack declares all four provenance fields, so an undocumented pack cannot ship.
- **REUSE/SPDX compliance.** Per-file `SPDX-FileCopyrightText` and
  `SPDX-License-Identifier` headers, a `.reuse/dep5` manifest recording the
  third-party terms of the derived packs, and canonical licence texts under
  `LICENSES/`.

### Changed

- **`agentleak.core.attacks.Channel` is now `AttackChannel`.** Two enums named
  `Channel` lived in `agentleak.core`: the trace model's eight channels, and the
  attack taxonomy's seven (the paper's `C1`-`C7`, which has no `user_input`
  because a source is not a leak site). Reading either one you had to check
  which import you were looking at. The taxonomy keeps the paper's names and
  loses the collision. The exported `agentleak.Channel` is unchanged; only the
  attack-taxonomy symbol moved.

## [0.11.4] - 2026-08-09

### Every published number now comes from the software

- **`/api/meta` reports the compliance frameworks and the scenario counts**
  alongside the channels and version it already carried. The site advertised
  "all 7 compliance frameworks" while the engine evaluated 14 — a figure written
  once by hand and left behind as the code moved. Understating is the harmless
  direction, but the same mechanism overstates just as easily, and on a tool
  whose pitch is *measured, not asserted*, a claim nobody can check is the
  expensive kind of wrong. Any number on the site can now be verified against
  the running software in one request.
- `CITATION.cff`, so the software and the benchmark paper behind it can be cited
  properly.

## [0.11.3] - 2026-08-09

### Fixed

- **The CLI help deleted the word the reader needed.** Typer renders help through
  rich, and rich reads `[gui]` as a style tag — so "requires the `[gui]` extra"
  printed as "requires the  extra". It hit `serve` and `mcp`, the two commands a
  new user reaches before they have the extra installed, and the help now gives
  the whole install command. A test renders every command and fails on the gap a
  swallowed tag leaves behind.
- **The agent card is served at the names agents actually try.** A2A renamed the
  file from `agent.json` to `agent-card.json`; only the new name was served, so a
  client probing the old one — or the plugin-style convention — found nothing.
  All three names now return the same document.

### Added

- The trust page carries the AgentLeak mark, drawn in `currentColor` so one copy
  serves both themes.

## [0.11.2] - 2026-08-08

### The trust page now looks like the site it is served from

- **Rebuilt in agentleak.org's own design language** — its palette, its two
  typefaces, its spacing and its mono-uppercase labels. The page is served by the
  package rather than the marketing site, so the tokens are transcribed rather
  than imported; a self-hosted install has no marketing stylesheet to borrow
  from. Dark by default because that is the site's default, with the site's own
  light palette for a light-mode reader.
- The fonts already travelled in the wheel for the product UI, so the page uses
  those rather than fetching any. A build without them falls back to the system
  grotesque instead of failing to load.
- `badge_state` now returns a `tone` alongside its colour. The badge keeps the
  shields palette so it sits naturally beside other README badges and the page
  uses the site's — one decision, two renderings, so the two can never disagree
  about whether a run passed.
- **The trend chart was understating real change.** A fixed 0–100 axis is right
  — auto-scaling turns a wobble between 97 and 99 into a cliff — but squeezed
  into a 64px sparkline a genuine thirty-point climb drew as a flat line, which
  is the same lie in the other direction. The axis is now drawn, labelled and
  given room.

## [0.11.1] - 2026-08-08

### The page the badge points at

- **`/a/<slug>` now serves a real page.** 0.11.0 shipped the badge and the JSON
  but no page, so the URL the publish endpoint handed out — the one URL the badge
  exists to make checkable — landed on a 404. It is server-rendered in the
  package rather than the marketing site, so the data and the honesty rules stay
  together, a crawler or link preview sees the actual verdict instead of an empty
  shell, and anyone self-hosting gets a working link rather than a dead one.
- The page carries its own caveats in words, not just colour: stale scores,
  degraded runs, and a standing note that this is the latest run rather than the
  best one. It shows the verdict, the date, the tiers and a trend — never a
  finding.
- The trend is drawn on a fixed 0–100 axis. An auto-scaled one turns a wobble
  between 97 and 99 into a cliff, which is the graph contradicting the numbers
  printed beside it. Fewer than two runs draws no line at all, because a line
  through one point invents a direction nobody measured.

### Fixed

- **`AGENTLEAK_DB` is now honoured.** It was set in the Docker image and read by
  nothing: `Store()` looked only at `AGENTLEAK_HOME`. Production was correct by
  way of a second variable, but a deployment that set only the documented one
  would have written its database to a container-local path and lost every
  account, run and published page on the next rebuild — silently, with the
  setting meant to prevent that sitting there looking authoritative.
- The version-consistency test imported `tomllib`, which is stdlib only from 3.11
  while the package supports 3.10 — so it failed on the oldest Python we promise
  to support, which is exactly where a mismatch is least likely to be noticed.

## [0.11.0] - 2026-08-08

### A score others can check, and one that keeps being checked

- **Public trust page and README badge** (`/a/<slug>`, `/a/<slug>/badge.svg`).
  A badge an agent awards itself is worth nothing; what makes this worth
  embedding is that AgentLeak measured the number and anyone can follow the link.
  Opt-in and reversible — a run never publishes anything as a side effect.
- **The badge is built to refuse three specific lies.** A score older than 30 days
  goes grey and shows its *age* rather than its number, because the number
  describes code that may no longer exist. A degraded run can never show the
  passing colour, since a pass from the pattern tier alone is a narrower claim.
  And the badge always shows the latest run, never the best one.
- **The public page shows the verdict, never the evidence.** Findings name real
  values from private data. A stranger sees the score, the date, the tiers that
  ran and a trend line — enough to judge the claim, not enough to reconstruct a
  run. The SVG is self-contained, because GitHub's image proxy renders anything
  needing a script or an external font as a broken image.
- **`Monitor` — continuous watch** (`agentleak.Monitor`). Sampled scoring of
  production runs with a rolling trend and threshold alerts, in-process, no
  thread and no timer. Designed around the two ways a monitor makes itself
  useless: it stays quiet on single bad samples and flat lines so nobody mutes
  it, and it reports a never-before-seen severity immediately rather than waiting
  for a trend. The baseline tracks improvement but never decays toward a
  regression — a baseline that follows a slow slide is what hides the slide.
- An exception thrown by an alert callback is swallowed. Your pager being down is
  not a reason for the agent to stop answering users.

### Agent-native: coding agents can check their own work

- **`agentleak mcp` — the engine as MCP tools** (`agentleak[mcp]`). A coding
  agent will not shell out to a CLI or chain four HTTP calls on a hunch; it calls
  tools. Four of them now: `privacy_preflight`, `privacy_scan_code`,
  `privacy_check_trace`, `privacy_redact`. Local by default — no account, no key,
  no network — because the teams who most need this are the ones whose traces
  cannot leave the building. Kept behind an extra so the core stays at four
  dependencies.
- **`preflight` reports what is *new* since the last check.** A score on its own
  changes nothing: an agent reads the number and moves on. Being told "this
  finding is new since you last looked" is what makes it iterate. The comparison
  comes from a local `.agentleak/history.jsonl` holding redacted snippets only.
- **Finding identity ignores the line number** (`core.memory`). Keying on
  `file:line` would turn every reformat into a page of false "new" findings, and
  a tool that cries wolf on every commit gets muted within a day. Identity is
  `(file, rule, fingerprint of the matched value)`. Moving a secret between files
  reads as one fixed plus one new — the rarer case, and arguably the honest one.
- **An empty trace is refused rather than scored.** `Trace.from_dict` accepts a
  payload with no events and yields a run that scores a confident 100/100. An
  agent sending a malformed trace would read that as clean: the exact false pass
  this tool exists to catch, committed by the tool itself.
- **Findings are deduplicated by identity.** Two detectors can land on the same
  value with the same rule; left alone an agent reads one problem as two, and the
  counts disagree with the deltas that are keyed by id.
- Discovery paths all say the same thing now: `SKILL.md`, `llms.txt` and
  `docs/mcp.md`. A tool an agent cannot find is a tool that does not exist.


## [0.10.0] - 2026-08-02

### Distribution and CI (closes the P0 gaps from the 2026-08 product audit)

- **Publishing to PyPI is real and self-verifying.** `.github/workflows/release.yml`
  builds once, runs `twine check --strict`, refuses a tag whose version disagrees with
  `pyproject.toml`, then installs the built wheel into a clean venv and exercises the
  actual first-run path (`version`, `scenarios --packs`, a scenario run that writes a
  report, the packaged `SKILL.md`, a single-file `scan` that finds a secret) *before*
  publishing. The publish step is no longer `continue-on-error`: a silent failure is
  exactly how `pip install agentleak` ends up broken while every doc claims otherwise.
  A manual dry-run mode runs build+verify without publishing. See `docs/releasing.md`.
- **Official GitHub Action** (`action.yml` + `scripts/gh_gate.py`). The "privacy is a
  required status check" story now has an artifact behind it: three modes (captured
  trace, scenario from a benchmark pack, static code scan), annotations graded by
  severity (L4/L3 → error, L2 → warning, L1 → notice) landing on `file:line` for scans
  and naming the leaking channel for traces, a readable job summary, typed step outputs
  (`score`, `risk-index`, `verdict`, `findings`, `report`), and an exit code that blocks
  the merge. Dogfooded by a new CI job that asserts the gate blocks a leaking run and
  passes a clean one. Starting point: `examples/workflows/privacy-gate.yml`.

### Developer experience (first-session walls)

- **`agentleak scan` accepts a single file** (and a zip), not just a directory. New
  `scan_file()` / `scan_path()`; an explicitly named file is scanned whatever its
  extension, because the user pointed at it on purpose.
- **`watch()` is local-first for real.** Naming a project no longer implies consent to
  talk to a server: submission happens only when a platform is configured (`base_url`,
  `AGENTLEAK_PLATFORM_URL`, or `submit=True`). A purely local run no longer prints a
  connection error at someone who never asked for one.
- **The published benchmark is one command away**: `agentleak scenarios --packs`,
  `--pack <id>` to list, and `run --pack agentleak_bench --scenario <id>` to execute.
  The 36 benchmark scenarios previously required a UI-only import.
- **Defenses have a door**: `agentleak redact` exposes the sanitizer that shipped with
  documentation but no entry point (file or stdin, six redaction styles).

### Scenario coverage: prompt-injection exfiltration

- **New `agentdojo_exfil` pack — 100 prompt-injection exfiltrations** derived from
  [AgentDojo](https://github.com/ethz-spylab/agentdojo) (NeurIPS 2024 Datasets &
  Benchmarks, MIT). Nothing about the agent is misconfigured: it runs the user's task,
  reads data it was right to read, and one of those tool responses carries a planted
  instruction. From there it keeps using its legitimate tools on the attacker's behalf
  — look up the 2FA code, mail it out, delete the evidence — while the answer shown to
  the user stays clean. Balanced across all four suites (banking / slack / travel /
  workspace), 10 injection goals, 41 user tasks.
- **New `agentdojo` upload format.** Trajectories are replayed against the real
  upstream environment rather than paraphrased, so the observations are what the agent
  actually saw. Events carry `prompt_injection` on the response that delivered the
  attack and `attacker_controlled` / `exfiltration` on the calls that followed, so a
  report can name where the trust boundary broke.
- **Canaries split across tiers.** These payloads are concrete values, so structured
  secrets (passport, 2FA code, card number) land in the `realistic` tier and prose (a
  private message, an email body) in `semantic` — a report shows honestly how much of
  the evidence rests on exact ground truth rather than pattern matching. Without that
  ground truth 20 of the 100 score a clean Pass and 64 would not block a CI gate; with
  it, none pass.
- **Pack extractors are in the repo** (`scripts/packs/`, with a README) rather than
  being lost build steps. Both derived packs rebuild byte-identically from their
  upstream sources, and the scripts document what was taken, what was reshaped, and
  which upstream cases were dropped — including AgentDojo's `banking/injection_task_1`,
  whose ground truth resolves "the IBAN of the pizza dinner companion" to the literal
  string `"me"`. Two rules are enforced by the extractors and re-checked by the tests
  against the shipped files: a canary must be data the agent actually read, and a
  canary that is not a secret is never invented — a false Fail is the same defect as a
  false Pass, pointing the other way.

### Scenario coverage: contextual integrity

- **New `privacylens_ci` pack — 120 contextual-integrity scenarios** derived from
  [SALT-NLP/PrivacyLens](https://huggingface.co/datasets/SALT-NLP/PrivacyLens)
  (NeurIPS 2024 Datasets & Benchmarks, CC-BY-4.0). An agent pulls private context in
  through its tools, then acts toward a recipient the norm says must not receive it.
  Curated for balance rather than volume: all three provenance sources
  (crowdsourcing / regulation / literature), four outbound channels, 99 distinct
  recipients, 115 distinct data types. This is the first pack whose leaks are *facts*
  ("Bob missed work for a court date") rather than *patterns* — the gap between
  "no PII detected" and "a privacy norm was broken".
- **New `privacylens` upload format.** `agentleak/scenarios/convert.py` replays a
  ReAct trajectory faithfully — one `tool_call`/`tool_response` pair per step,
  attributed to the toolkit that served it — then models the outbound act the
  scenario exists to describe.
- **Ground truth travels with the scenario.** Measured on this pack, the regex tier
  alone scores most scenarios a clean 100/100, so shipping the traces bare would have
  manufactured false Passes. Each scenario carries the dataset's own
  `sensitive_info_items` as **semantic canaries** (exact match, confidence 1.0), which
  makes it score deterministically with no LLM tier and no API key: `main1` goes from
  Pass 100/100 to Fail 0/100. Canaries are now persisted with imported scenarios
  (`scenarios.canaries`, additive migration) and used when the platform analyzes them,
  so a pack scenario scores the same in the GUI as in the CLI.
- **Pack licences are displayed, not just stored.** `source_url`, `license` and
  `attribution` are surfaced by `agentleak scenarios --packs`,
  `GET /api/scenario-packs` and the Scenarios page — CC-BY-4.0 requires attribution
  wherever the data appears.

### Honest reporting

- **Every result states which detection tiers produced it.** Reports carry
  `detection = {mode, tiers, degraded}`, surfaced in the JSON, in the CLI, and in the
  Action's job summary. A "Pass" from regex alone no longer reads like a "Pass" from
  the full hybrid pipeline — for a scoring product that distinction is the product.

### Operations

- **`agentleak admin reset-password` / `admin list-users`** — operator-side account
  recovery from the machine that owns the database (no mail infrastructure, no emailed
  reset link). All sessions for the account are revoked by the reset.
- `deploy/README.md` documents account recovery and the **known ceilings of the
  single-node deployment** (in-memory quotas and rate limits are correct for one
  replica only; scale vertically until they are shared state).

### Agent-native distribution

- **`agentleak skill`** (`agentleak/skill/`) — registers AgentLeak as an agent skill so
  coding agents (Claude Code, OpenClaw, Cursor, Windsurf, Codex CLI) discover the tool on
  their own instead of having to be told how to use it. Auto-detects installed agents,
  writes `<agent>/skills/agentleak/SKILL.md`, and refuses to clobber an edited skill file
  without `--force`. Supports `--target`, `--path`, `--dry-run`, `--uninstall`, `--print`.
- **`SKILL.md`** at the repository root — the canonical skill text, shipped as package data
  and installable via `npx skills add`. A test asserts the root copy and the packaged copy
  cannot drift apart.
- **`docs/install.md`** — a paste-into-your-agent installer: the agent reads it, installs
  AgentLeak, verifies with a demo scan, registers the skill and reports back.
- Covered by `tests/test_skill.py` (23 tests).

### Detection quality (0.9.0)

Findings from an end-to-end dogfood of a real LangGraph coordinator-worker
agent. All changes ship with regression tests (`tests/test_improvements.py`).

**Breaking (behavioural):** the new key-name detector is on by default and
raises recall, so traces that previously scored clean may now report findings.
Anyone with a wired CI privacy gate should re-baseline after upgrading.

### Added
- **Key-name-aware detector** (`detectors/keyname.py`, config flag `keyname`,
  on by default) — flags values carried by sensitive field names (`diagnosis`,
  `medication`, `ssn`, `account_number`, `salary`, `address`, …) even when no
  dictionary recognises the value. Closes the main recall gap on realistic,
  unseen PII/PHI leaked through internal channels.
- **Degraded-run signalling** — when a requested detection tier (Presidio,
  LLM-judge) cannot run because a dependency or API key is missing, the run is
  now flagged `degraded` with explicit `warnings` in the report JSON and a
  prominent CLI banner (shown even under `--quiet`). A run that could not fully
  check is never silently reported as a clean pass. (`core/runner.py`,
  `core/report.py`, `cli.py`)

### Improved
- **Healthcare recall** — added common oncology conditions (carcinoma,
  colorectal, melanoma, lymphoma, metastatic, …) and chemotherapy agents
  (FOLFOX, oxaliplatin, cisplatin, paclitaxel, …); the NAM/health-identifier
  shape now tolerates spaces, hyphens and an optional `NAM` label
  (`NAM TREM 8842 0197`). (`detectors/healthcare.py`)

### Fixed
- **Secret-assignment false positives** — reading a credential from the
  environment (`api_key = os.environ.get("KEY")`) and passing an ALL-CAPS
  constant reference (`api_key=API_KEY`) are no longer flagged as hardcoded
  secrets. Real quoted literals and lowercase in-trace secrets are still
  caught. Removes the dominant code-scan false positive. (`detectors/secrets.py`)

### Added

- **Agent-first layer — autonomous self-registration, code scans, and a
  self-improvement loop.** An agent can now test and fix *itself* through the
  API, with no human in the loop:
  - **AgentCard** (`core/agentcard.py`) — an A2A / Nasiko-compatible
    `AgentCard.json` (name, capabilities, tags, examples, endpoints, declared
    code source). Parses official A2A cards too (`skills`, `protocolVersion`,
    `provider.organization`). `fetch_agent_card(url)` pulls a card from a live
    agent's well-known endpoint.
  - **Static code privacy scan** (`core/codescan.py`) — runs the exact same
    3-tier hybrid detection pipeline as trace analysis (regex, Presidio,
    LLM-judge) over an agent's *source code*, plus four code-specific layers:
    a generated EN/FR sensitive-identifier lexicon, entropy analysis for
    unknown-format secrets, de-obfuscation of decomposed PII (split literals,
    unusual separators), and quasi-identifier correlation (GDPR Rec. 26).
    Scans a local directory, an uploaded zip, or a GitHub repo
    (`agentleak scan`, `POST /api/agent/code`).
  - **Autonomous-agent API** (`X-AgentLeak-Key` auth) — `POST /api/agent/register`,
    `POST /api/agent/code`, `POST /api/agent/improve` (self-test + delta vs the
    previous run + prioritised, machine-actionable `next_steps`), and
    `GET /api/agent/status`. `AgentSelfClient` (`agentleak/client.py`) wraps
    the whole loop in a few Python calls.
  - **Public agent discovery** — `GET /.well-known/agent-card.json` serves
    AgentLeak's own A2A card unauthenticated, so orchestrators and registries
    (e.g. Nasiko) can auto-discover it as a privacy self-testing service.
    `GET /api/meta` now advertises the agent API surface. `agentleak agent-card`
    prints the same card offline.
- **SaaS admin console — multi-account, monitored, production-ready.**
  - Multi-account platform with roles: the first registered account becomes
    admin automatically. Admins can promote, disable (revokes sessions
    instantly), and delete other accounts, with lockout guards (can't disable/
    delete/demote yourself out of the last admin seat).
  - **Admin console** (`/admin`) — platform-wide stats, an accounts table, an
    **agent activity monitor** (runs executed, agent API "consumption", results,
    and a 14-day activity sparkline per project), and an immutable **audit log**
    of every admin action.
  - **Self-service account management** — change display name, change password
    (revokes all sessions), delete your own account, all gated by the current
    password.
  - `GET /api/health` (unauthenticated liveness probe) and login rate limiting
    (10 failed attempts / 5 min per e-mail → HTTP 429).

### Security
- **Fixed**: disabling a user account revoked their browser session but *not*
  their projects' `ak_...` self-test API keys — an agent could keep calling
  `/api/selftest` and `/api/agent/*` after its owner was disabled.
  `get_project_by_apikey` now checks the owner's disabled flag too.
- Per-API-key rate limiting (120 req/min) on the whole autonomous-agent surface.
- Zip-bomb guard: `scan_zip_bytes` rejects archives whose *declared*
  uncompressed size exceeds 100 MB before decompressing anything.
- `fetch_github_repo` now streams the download in 1 MB chunks capped at 50 MB
  instead of buffering an unbounded response.

- **`agentleak.watch()` — one-line connect for any agent** (`agentleak/track.py`).
  A single import and context manager replaces the five framework-specific
  patterns. It records directly (`run.tool_call(...)`), exposes a hook for every
  framework (`run.callback` for LangChain/LangGraph, `run.crew` for CrewAI,
  `run.ingest_messages(...)` for OpenAI Swarm / Agents SDK, `run.ingest_adk(...)`
  for Google ADK), auto-analyzes on exit (`run.report`), and uploads to a running
  platform when a project name is given. `agentleak.record()` / `@monitor` work
  from inside any framework node because the run is the active capture.
  Validated live against plain-Python, LangGraph, and Swarm multi-agent systems
  (see `multiagent-labs/`).
- **Computer-use / coding-agent integration** (`integrations/computer_use.py`).
  First-class support for the autonomous *action–observation* genre — OpenHands,
  Open Interpreter, Cline / "openclaw", SWE-agent, browser-use. `trace_from_steps`
  maps file **writes** to `generated_file` (the on-disk artifact a chat-only audit
  never opens), shell/code to `tool_call`, file reads to `tool_response`, agent
  reasoning to `log`, and the final message to `final_output`. Exposed as
  `run.ingest_steps(...)`, registered in the platform (`computer_use` framework),
  and validated live (a real tool-calling agent leaked a DB connection string +
  PII into the report file it wrote; see `multiagent-labs/computeruse_agent.py`).
- **OpenTelemetry / OpenInference span adapter** (`integrations/otel.py`).
  Instead of a bespoke adapter per framework, reuse the open-source tracing
  ecosystem: `trace_from_spans` ingests OpenInference / OTel GenAI spans (emitted
  by Arize Phoenix and OpenLLMetry / Traceloop for LangChain, LlamaIndex, CrewAI,
  AutoGen, DSPy, the OpenAI / Anthropic / Bedrock SDKs, …). Accepts span dicts,
  readable-span objects, or a raw OTLP `{resourceSpans}` payload; un-flattens the
  indexed `llm.*_messages` / `retrieval.documents` attributes; maps `TOOL`/
  `RETRIEVER`/`LLM`/`GUARDRAIL` span kinds to channels and promotes the last
  model output to `final_output`. Exposed as `run.ingest_spans(...)` and
  registered as the `openinference` framework.
- **Broader secret + identifier coverage for agent runtimes** (`detectors/`).
  The regex (default) tier now flags leaks that real agents routinely emit but
  that were previously invisible outside LLM-judge mode: model-provider keys
  (`llm_api_key` — OpenAI `sk-proj-…` / `sk-…`, Anthropic `sk-ant-…`), Google API
  keys (`google_api_key` — `AIza…`), opaque `Authorization: Bearer` tokens
  (`bearer_token`), IPv6 addresses, and UK National Insurance numbers
  (`national_insurance_number`, using the official valid-prefix rules). New
  regression scenarios drive each one through the runner end-to-end and assert
  channel-aware results (sources are not leaks; internal channels are).

### Changed
- The platform **Connect** snippets for all 14 frameworks now use the
  `agentleak.watch()` one-liner.
- **Findings view modernized with a filter system**: the results Findings tab now
  has full-text search (type / value / channel / source) plus severity-level
  pills and channel / detector dropdowns, a live "showing X of Y" count, and
  click-to-expand rows revealing the per-finding recommendation
  (`web/frontend/src/features/ResultsView.tsx`).

### Fixed
- **Multi-agent channel misattribution**: the LangChain/LangGraph callback tagged
  *every* LLM turn as `final_output`, so in a multi-node graph intermediate agent
  turns were misattributed to the user-facing answer (and could inflate the
  highest-severity channel). Only the final turn now stays `final_output`; earlier
  turns demote to `inter_agent_message` (`integrations/langchain.py`).
- **French / Québec civic addresses** (e.g. `1240 Rue Saint-Denis`) were missed
  by the PII detector, which only matched English `<name> Street` forms — a gap
  given the Law 25 grounding. Added a French civic-address recognizer
  (`detectors/pii.py`).
- **Version-string false positive**: a software version such as
  `version 1.2.3.4` was reported as a client `ip_address`. The IPv4 detector now
  suppresses matches preceded by a version/build/release keyword, and the new
  IPv6 matcher requires enough groups that a clock time (`12:34:56`) is never
  mistaken for an address (`detectors/pii.py`).
- Removed unused imports and a dead variable across the package.

## [0.6.0] — 2026-06-21

### Added
- **Leak flow & agent topology** (`core/flow.py`) — debugging views for
  multi-agent leaks:
  - **Leak paths**: each disclosed secret is traced from where it entered the
    system (a source channel) through every agent that handled it to each point
    of disclosure, so you can see exactly where a leak originated and how it
    propagated. Values stay redacted.
  - **Agent topology**: a behavioral graph of the agent — participants as nodes
    (inputs → agents → sinks), channels as edges, leak-carrying edges flagged by
    severity. Rendered as a diagram in the new **Leak flow** tab and embedded in
    the report (`report.flow` / `report.leak_paths`) and the Markdown export.

## [0.5.0] — 2026-06-21

Production-hardening release.

### Added
- **Release automation** — `release.yml` publishes the sdist + wheel to PyPI
  (Trusted Publishing) and attaches them to a GitHub Release on every `v*` tag.
- **Frontend CI** — a dedicated job type-checks and builds the web UI so a bad
  change can never ship a broken bundle.
- **CHANGELOG.md**.

### Changed
- Test suite expanded to **196 tests / 94% coverage**; the CI coverage gate was
  raised from 70% to **85%**. Hardened the newest code paths: the LLM client
  (59→98%), the CLI (79→90%), the SDK client (77→93%), and the LangChain adapter.

### Verified
- Clean-room wheel install (fresh venv): CLI, `run`, `serve` (GUI + API + SPA
  deep links) all functional.

## [0.4.1] — 2026-06-21

### Changed
- Adopted the official shadcn/ui **blocks** dashboard shell: collapsible sidebar
  (icon-collapse on desktop, drawer on mobile), sticky site header with route
  breadcrumb, and section-card dashboard. Light and dark themes.

## [0.4.0] — 2026-06-21

### Added
- **Live agent runner** — execute a real LLM agent (any OpenAI-compatible
  endpoint: OpenAI, OpenRouter, Ollama, vLLM) against a scenario and score the
  trace it actually produces. Deterministic scripted agent for offline/CI use.
  Per-project agent endpoint config; API keys are redacted in responses.
- Scenarios persist their original spec (objective + vault + tools) so they are
  runnable live; `POST /api/projects/{id}/execute`.
- **Tabbed run view**: Overview / Findings / Recommendations / Compliance.

## [0.3.0] — 2026-06-20

### Added
- **Scenario library** — search/filter, upload (AgentLeak traces, AgentLeak
  specs, or ai4privacy records — auto-detected & converted), and importable
  packs (AgentLeak Bench + PII Probes). One-click run in the playground.

## [0.2.0] — 2026-06-20

First public release.

### Added
- **AgentRisk** density-normalized Risk Index scoring (GDPR Art. 9 / Québec Law 25).
- Six detector families (PII, secrets, healthcare, finance, HR, custom regex)
  across eight execution channels.
- Five compliance frameworks (GDPR, Law 25, NIST AI RMF, OWASP LLM Top 10, EU AI Act).
- Pluggable agent-framework registry (LangChain / LangGraph / CrewAI / AutoGen /
  OpenAI Agents + generic).
- Local platform: SQLite persistence (projects + runs), SDK client, compare/stats.
- Web GUI (React + shadcn/ui), CLI (`init/run/report/validate/scenarios/serve`).

[0.11.4]: https://github.com/yagobski/agentleak/releases/tag/v0.11.4
[0.11.3]: https://github.com/yagobski/agentleak/releases/tag/v0.11.3
[0.11.2]: https://github.com/yagobski/agentleak/releases/tag/v0.11.2
[0.11.1]: https://github.com/yagobski/agentleak/releases/tag/v0.11.1
[0.11.0]: https://github.com/yagobski/agentleak/releases/tag/v0.11.0
[0.10.0]: https://github.com/yagobski/agentleak/releases/tag/v0.10.0
[0.6.0]: https://github.com/yagobski/agentleak/releases/tag/v0.6.0
[0.5.0]: https://github.com/yagobski/agentleak/releases/tag/v0.5.0
[0.4.1]: https://github.com/yagobski/agentleak/releases/tag/v0.4.1
[0.4.0]: https://github.com/yagobski/agentleak/releases/tag/v0.4.0
[0.3.0]: https://github.com/yagobski/agentleak/releases/tag/v0.3.0
[0.2.0]: https://github.com/yagobski/agentleak/releases/tag/v0.2.0
