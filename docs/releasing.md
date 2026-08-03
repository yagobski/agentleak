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

## Versioning

Semantic versioning, with the practical rules this project cares about:

- **Patch** — detection-rule fixes that do not move scores, bug fixes, docs.
- **Minor** — new commands, new detectors, new integrations, and any
  *scoring change*. AgentRisk is meant to be reproducible, so a change that
  moves scores must be announced in the changelog: someone's CI threshold
  depends on it.
- **Major** — a breaking change to the trace schema, the report schema, or
  the CLI contract.
