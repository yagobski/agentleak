## What this changes

<!-- One or two sentences. If it fixes an issue, "Fixes #123". -->

## Why

<!-- What was wrong, or what became possible. The reasoning is the part a
     reviewer cannot reconstruct from the diff. -->

## Checks

- [ ] `pytest` passes
- [ ] `ruff check agentleak/ tests/ scripts/` and `mypy agentleak/` are clean
- [ ] New behaviour has a test — one that fails without the change
- [ ] Docs updated if the change is user-visible

<!-- Touching detection or scoring? Say what a wrong result would look like and
     how the test would catch it. The score is the product; a silent change to
     it is the one thing we cannot ship. -->
