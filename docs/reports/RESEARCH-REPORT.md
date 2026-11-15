<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Research workflow: report (branch `next/research`)

Work package D of `PLAN.md`: make AgentLeak and AgentRisk usable for research
from start to finish (run an experiment, compare configurations with proper
statistics, export what goes in a paper, archive it reproducibly).

## What was built

A new package, `src/agentleak/research/`, exposed as `agentleak bench` and as a
Python API. No new dependency; the statistics are standard-library Python.
The AgentRisk formula and `core/agentrisk.py` / `core/scoring.py` are
untouched; the research code calls them.

| Module | Role |
|---|---|
| `manifest.py` | Experiment manifest: parse, validate (unknown keys rejected), commented template, pins (version + SHA-256 per source), environment capture, `repin` |
| `corpus.py` | Units and labels by construction: built-in leak demos, built-in clean controls (independent negatives), pack fixtures, derived compliant counterparts; ground truth; source provenance |
| `bench.py` | Runner: analyze, write `rows.csv` / `summary.json` / `manifest.lock.json` / `REPORT.md`; resumable; live mode (BYOK) with trace capture and re-analysis |
| `rows.py`, `summary.py`, `render.py` | Row schema, metric records with a kind taxonomy, the Markdown report |
| `stats.py` | Wilson, Clopper-Pearson, BCa and percentile bootstrap, paired bootstrap, McNemar exact and chi-square, Newcombe risk difference, Cohen's h, Holm-Bonferroni, Cochran-Armitage and exact trend, sign-flip permutation, Kendall tau-b, detection metrics |
| `compare.py` | Paired comparison with comparability checks, Holm, flips |
| `export.py`, `citation.py` | LaTeX (booktabs), Markdown, CSV, Methods paragraph, BibTeX from `CITATION.cff` |
| `capsule.py` | Deterministic reproducibility zip and verifier |
| `agentrisk.py` | Corpus scoring (events, labelled secrets, explicit vaults), derivation trace, weight sensitivity, property checker |
| `ablation.py` | Scope-rule ablation (inputs as emissions) |
| `cli.py` | The `bench` Typer app |

### Commands

```
agentleak bench init [PATH] [--name] [--quick] [--force]
agentleak bench repin MANIFEST
agentleak bench run MANIFEST [--out DIR] [--fresh] [--allow-drift] [-q]
agentleak bench compare RUN_A RUN_B [--out DIR] [--force]
agentleak bench export RUN [--format all|latex,markdown,csv,methods,bibtex] [--out DIR]
agentleak bench capsule RUN [-o capsule.zip]
agentleak bench verify CAPSULE [--no-rerun]
agentleak bench score-corpus FILE [--weights 1,2,3,4] [--derive TRACE] [--sensitivity] [--no-detect] [--json] [--out DIR]
agentleak bench properties [--trials N] [--seed S]
agentleak bench ablate-scope MANIFEST_OR_RUN [--out DIR]
agentleak bench show RUN
```

### Python API (`agentleak.research`)

`Manifest`, `ManifestError`, `run_benchmark`, `load_run`, `BenchRun`
(`.rows`, `.summary`, `.lock`, `.metric(id)`, `.metrics()`), `RunError`,
`compare_runs`, `ComparisonError`, `export_run`, `build_capsule`,
`verify_capsule`, `VerifyResult`, `score_corpus`, `CorpusScore`
(`.rows()`, `.aggregate()`, `.derivation(id)`), `derive`, `Derivation`,
`weight_sensitivity`, `check_properties`, `scope_ablation`, `select_units`,
`Unit`, `read_rows`, `scenario_table`, `render_template`,
`DISCLOSURE_CHANNELS`, and the `stats` module. Everything returns dataclasses,
dicts and lists; `pandas.DataFrame(run.rows)` works without pandas being
required.

## Walkthrough (real output, bundled packs, fast tier)

Full transcript with explanations: [`docs/research.md`](docs/research.md).

```console
$ agentleak bench init all-detectors.yaml
✓ wrote all-detectors.yaml
  sources: builtin, agentdojo_exfil, agentleak_bench, privacylens_ci · detection: fast · seed 20261114 · output: runs/all-detectors

$ agentleak bench run all-detectors.yaml
all-detectors: 522 units, 3132 rows
  agentleak 0.18.0 · detection fast (tiers run: regex)
  Recall (leaking fixtures)                    0.736    192/261  95% CI 0.679-0.785
  Specificity (independent clean)              1.000        5/5  95% CI 0.566-1.000
  Specificity (derived clean)                  0.699    179/256  95% CI 0.640-0.752
  Internal-only share of detected leaks        1.000    192/192  95% CI 0.980-1.000
  Mean Risk Index                              0.369      n=261  95% CI 0.330-0.411

$ agentleak bench compare runs/all-detectors runs/default-config   # B: finance and hr detectors off
  ⚠ vault_denominator: rho_S differs for 104 of 522 paired scenarios ...
  metric                                   A       B     B-A  95% CI                  p  p Holm
  Recall                               0.736   0.617  -0.119  -0.157 to -0.080 <0.0001 <0.0001
  Specificity (derived)                0.699   0.734  +0.035  +0.016 to +0.059  0.0039  0.0273
  Mean RI (leaking)                    0.369   0.335  -0.034  -0.046 to -0.023 <0.0001  0.0004
  40 scenario(s) flipped: 0 no finding -> leak, 40 leak -> no finding

$ agentleak bench capsule runs/all-detectors
✓ runs/all-detectors-capsule.zip (81 KB)
$ agentleak bench verify runs/all-detectors-capsule.zip
✓ checksums: 18 files match SHA256SUMS
✓ software: installed software matches the capsule's pins
✓ rows.csv: byte-identical (sha256 cfa0a61476b1c938)
✓ summary.json: identical apart from generated_at
Reproduced.
```

The whole corpus runs in about 3 seconds; a full init → run → compare →
export → capsule → verify cycle takes under 15 seconds.

## Design decisions

- **Labels by construction, detectors without ground truth.** `agentleak run
  --pack` passes a pack's canaries to the detectors; `bench` does not, so
  detection is measured rather than given. Ground truth (canaries, or
  `private_vault` values for `agentleak_bench`) is used only for the
  `reference_leak` column and the fixture-integrity metrics, which have their
  own kind and their own section titled "not detector accuracy".
- **Derived counterparts drop the leaking emissions.** For each pack fixture,
  every disclosure-channel event containing a ground-truth value (exact,
  case-sensitive, as canaries match) is removed; baseline events stay, so the
  data still enters and the vault is unchanged. Dropping events rather than
  masking strings avoids residual reformatted copies counting against the
  label. Built-in leak demos have no recorded ground truth, so they get no
  derived twin; they are paired with the five hand-written clean controls.
- **Independent and derived negatives are separate metrics everywhere**
  (`specificity.independent`, `specificity.derived`, and precision/F1 "vs"
  each). There is no pooled specificity.
- **Metric records, not loose numbers.** Every number in `summary.json` has
  id, kind, definition, population, numerator, denominator (or n), estimate,
  interval bounds, method and confidence. The summary carries version, tiers
  requested and run, degraded flag and source provenance; exports repeat them
  in captions and notes.
- **Determinism.** Rows are written in selection order with fixed float
  formatting; JSON is sorted; each bootstrap seed is derived from the manifest
  seed and the metric id (adding a metric does not move another's interval);
  `generated_at` is the only timestamp. Tested in-process and checked across
  two separate installs (dev venv and a wheel in a clean venv): identical
  `rows.csv` SHA-256.
- **Replay repetitions are refused.** Replaying a fixed trace twice adds
  nothing but false confidence, so `repetitions > 1` is an error in replay
  mode. In live mode, binary metrics use "leaked in any repetition" per
  scenario, and the mean per-scenario leak fraction gets a bootstrap interval.
- **Comparisons are paired by scenario id**: exact McNemar on discordant
  pairs, paired bootstrap intervals for differences, sign-flip test for mean
  RI, Holm across all rows. Refused: different source hashes, label mismatch,
  replay vs live. Warned: different tiers, degraded runs, different versions,
  per-scenario `rho_S` differences (the observed vault moves with the
  detectors).
- **Pins.** `bench init` writes the installed version and source hashes into
  the manifest; drift stops a run. The error used to suggest `init --force`,
  which would have erased the researcher's edits; `bench repin` now rewrites
  only the `pins:` block.
- **Citations from the repository only.** BibTeX comes from `CITATION.cff`
  (embedded copy for wheel installs, kept equal to the file by a test). The
  AgentLeak Bench pack reuses the preferred-citation entry because its source
  URL is that DOI. PrivacyLens and AgentDojo have no BibTeX in the repository,
  so the file says so with their URL and licence instead of an entry.
- **Capsule.** Deterministic zip (sorted entries, fixed timestamps). Licence
  texts come from the wheel's `agentleak/licenses/` or the checkout's
  `LICENSES/`. `.zenodo.json` is a draft with `FILL-IN` fields; nothing is
  uploaded. For live runs, `verify` re-analyzes the archived traces instead of
  calling the model.
- **Scope ablation** passes an empty `baseline_channels` to the unchanged
  `compute_agentrisk`. It is a view, not a scoring option.

## Friction found and fixed during the walkthrough

- Relative `output_dir` resolved against the shell's directory; now against
  the manifest's folder.
- CLI printed long absolute paths; now relative to the working directory.
- Re-running a finished manifest silently showed old results; it now says so
  and points to `--fresh`.
- p-values below 1e-6 were serialized as `0`; they now keep significant digits
  and display as `<0.0001`.
- The Methods paragraph cited a commit even with uncommitted changes; it now
  says so.
- `pip install agentleak` installs 0.18.0, which predates `bench`; the
  tutorial says to install from a checkout until release, and the capsule
  README gives the exact source commit as well as the version.
- Ablation labels and interval names ("Wilson score", not "wilson score
  score") read cleanly.

## Findings worth knowing (from the runs above)

- Fast-tier recall on PrivacyLens is 0.483 (58/120): norm violations are facts,
  not patterns.
- Derived specificity on AgentDojo is 0.370 (37/100). Once the exfiltration
  calls are removed, ordinary tool calls still send addresses, names and IBANs
  that came from the agent's input, and AgentRisk's presence-based rule counts
  them. This is a measured cost of judging presence rather than flow.
- The toggles a fresh `agentleak.yaml` ships (finance and HR off) detect 40
  fewer leaking fixtures than running with every detector (recall 0.617 vs
  0.736, paired difference −0.119, 95% CI −0.157 to −0.080, exact McNemar
  p < 0.0001), with derived specificity +0.035 (Holm p = 0.027).
- Scope ablation: counting inputs as emissions flips all 5 independent clean
  controls and 153/256 derived counterparts to "leak" and sends their RI to 1.

## Tests and checks

- 5 new test modules (`tests/test_research_*.py`, 73 tests): statistics
  against Newcombe (1998) Table II, Newcombe's method-10 example and hand
  computations; exact trend test against brute-force enumeration; manifest
  validation and pins; corpus labels and derived counterparts; byte-identical
  re-runs; resume after interruption; refusal of mixed output directories;
  guardrails (no pooled negatives, integrity kind, no "safe"); live mode with
  a fake model and trace re-analysis; comparison, refusal and forcing;
  exports, escaping and citation sync; deterministic capsule, verification and
  tamper detection; corpus scoring in JSONL/JSON/CSV, derivations, sensitivity
  and properties; ablation; the whole CLI flow.
- Full suite: 1370 passed, 21 skipped. `ruff check src/agentleak/ tests/`
  clean. `mypy src/agentleak/` clean (118 files).
- Coverage of `agentleak.research` in the full run: 93%.

## Changes to shared files

- `src/agentleak/cli.py`: two lines (an import of `bench_app` and
  `app.add_typer(bench_app, name="bench")`).
- `README.md`: one line in the documentation list.
- `docs/cli.md`: one row in the command table (required by
  `tests/test_cli_reference.py`).
- `CHANGELOG.md`: one delimited block under Unreleased.
- `pyproject.toml`: unchanged.

## Known limitations and not done

- **Live mode is tested only with a fake model**, not a real endpoint.
- **No per-data-type recall**: rows do not carry per-type ground truth; the
  summary gives descriptive data-type prevalence instead.
- **Trend tests** are in `stats` but not computed in the summary (on the
  bundled corpus, recall by adversary level is 12/12 at every level).
- **Bench uses the observed vault per unit**; explicit vaults are supported in
  `score-corpus`, not in `bench run`.
- **Standard and hybrid tiers** were exercised only in degraded form (Presidio
  is not installed here); the degraded flag and warnings are tested.
- **Small corpus**: five independent clean controls bound specificity at
  0.566–1.000; several domains have one fixture.
- **GUI**: nothing in the web interface uses this yet (another work package).
- The capsule README's source-install line points at a local commit until the
  branch is pushed.
