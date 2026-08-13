# Releasing AgentLeak

`pip install agentleak` is the first line of almost every instruction this
project ships: the README, `SKILL.md`, `docs/install.md`, `llms.txt`, the
website and the GitHub Action all start there. If that command fails, every
funnel fails at step 1. This page is how it keeps working.

## One-time setup (before the first release)

1. ~~Make the repository public.~~ Done: the repository is public at
   `github.com/yagobski/agentleak`.
2. **Register a PyPI Trusted Publisher** so releases need no API token
   ([docs](https://docs.pypi.org/trusted-publishers/)). On PyPI, under the
   `agentleak` project (or as a *pending* publisher before the first upload):

   | Field | Value |
   |---|---|
   | Owner | `yagobski` |
   | Repository | `agentleak` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

3. **Create the `pypi` environment** in the repository settings (Settings →
   Environments). Add required reviewers if you want a human gate on uploads.

Nothing else is needed: the workflow authenticates over OIDC.

## Cutting a release

```bash
# 1. Bump the version in exactly one place.
#    agentleak/__init__.py and pyproject.toml must agree (CI asserts it).
$EDITOR pyproject.toml agentleak/__init__.py

# 2. Write the changelog entry.
$EDITOR CHANGELOG.md

# 3. Full local gate before tagging.
pytest && ruff check agentleak/ tests/ scripts/ && mypy agentleak/
python -m build && python -m twine check --strict dist/*

# 4. Tag. The tag drives everything.
git commit -am "chore: release v0.9.1"
git tag v0.9.1
git push origin main --tags
```

The tag push runs `.github/workflows/release.yml`, which:

1. builds the sdist + wheel once,
2. runs `twine check --strict` on the metadata,
3. **fails if the tag and `pyproject.toml` version disagree**,
4. installs the built wheel into a clean venv and exercises the real first-run
   path (`version`, `scenarios --packs`, a scenario run that writes a report,
   the packaged `SKILL.md`, and a single-file `scan` that finds a secret),
5. attaches the artifacts to a GitHub Release,
6. publishes to PyPI.

The publish step is deliberately **not** `continue-on-error`. A silent publish
failure is precisely how the package ends up missing from PyPI while every
document claims otherwise.

## Dry run

To exercise the whole build-and-verify path without publishing, run the
workflow manually (Actions → Release → Run workflow) with **dry-run** checked.
The `publish` job is skipped; the `build` job still has to pass.

## After a release

```bash
# The install path everyone else follows, from a clean environment.
python -m venv /tmp/check && /tmp/check/bin/pip install agentleak
/tmp/check/bin/agentleak version
/tmp/check/bin/agentleak run --scenario healthcare_patient_summary
```

If that works, every downstream instruction works: the skill installer, the
Action (`pip install agentleak`), `docs/install.md`, and the hosted docs.

## Archiving on Zenodo (DOI)

A SoftwareX submission (or any citation that needs to survive GitHub
disappearing) needs a permanent, versioned archive with a DOI — GitHub tags
alone are not one. This is a one-time setup plus a per-release no-op:

1. **One-time, in a browser, with the repo owner's GitHub account:**
   go to [zenodo.org/account/settings/github](https://zenodo.org/account/settings/github/),
   sign in with GitHub, and flip the toggle on for `yagobski/agentleak`.
   Zenodo needs read access to the repo and to be notified on new releases —
   nothing else.
2. **`.zenodo.json`** (repo root) already carries the metadata Zenodo should
   use instead of guessing from the GitHub description: title, abstract,
   creators, license, keywords, and `related_identifiers` linking the arXiv
   paper and agentleak.org. Keep it in sync with `CITATION.cff` when authors
   or the abstract change.
3. **Cut a GitHub Release** the normal way (see "Cutting a release" above —
   the `release.yml` workflow already creates one from the tag). Zenodo
   archives it automatically within a few minutes and mints a DOI.
4. Zenodo gives two DOIs: a **version DOI** (this exact release, immutable)
   and a **concept DOI** (always resolves to the latest version) — cite the
   concept DOI in the paper and in `CITATION.cff`.
5. **After the first DOI exists**, do both:
   - Add `identifiers: [{type: doi, value: "10.5281/zenodo.XXXXXXX"}]` to
     `CITATION.cff` (concept DOI).
   - Add the badge to the top of `README.md`, next to the PyPI/License
     badges: `[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)`.

No badge or DOI is committed until step 5 actually has a real number —
a badge that 404s is worse than no badge.

## Versioning

Semantic versioning, with the practical rules this project cares about:

- **Patch** — detection-rule fixes that do not move scores, bug fixes, docs.
- **Minor** — new commands, new detectors, new integrations, and any
  *scoring change*. AgentRisk is meant to be reproducible, so a change that
  moves scores must be announced in the changelog: someone's CI threshold
  depends on it.
- **Major** — a breaking change to the trace schema, the report schema, or
  the CLI contract.
