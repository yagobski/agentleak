# Pack extractors

The scenario packs bundled in `agentleak/scenarios/packs/` are derived from
public research datasets. These scripts are how they were built — kept in the
repo so anyone can check what we took, what we changed, and what we dropped.

They are **not** part of the installed package and are not needed at runtime.

| Script | Builds | Upstream | Licence |
| --- | --- | --- | --- |
| `build_privacylens_pack.py` | `privacylens_ci.json` (120) | [SALT-NLP/PrivacyLens](https://huggingface.co/datasets/SALT-NLP/PrivacyLens) | CC-BY-4.0 |
| `build_agentdojo_pack.py` | `agentdojo_exfil.json` (100) | [ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo) | MIT |

Both packs carry `source`, `source_url`, `license` and `attribution`, and those
fields are displayed everywhere the pack appears.

## Running them

```bash
python scripts/packs/build_privacylens_pack.py
```

Expects `privacylens.json` (the dataset's records) in the working directory.

```bash
python scripts/packs/build_agentdojo_pack.py
```

Needs `agentdojo` importable — install it from the upstream repo into a
throwaway virtualenv (it requires Python ≥ 3.10):

```bash
pip install git+https://github.com/ethz-spylab/agentdojo.git
```

Both builds are deterministic: the same inputs produce a byte-identical pack.
The AgentDojo script re-execs itself with `PYTHONHASHSEED=0` and pins
`datetime.now()` stamps to get there, because the upstream environment
serializes sets and wall-clock times into tool observations.

## What the extractors guarantee

Both packs ship **ground-truth canaries**, because both datasets leak things a
regex tier cannot see. Two rules protect that ground truth, and the pack tests
in `tests/` re-check them against the shipped files:

- **A canary must be data the agent actually read.** The AgentDojo extractor
  validates every candidate against the observations it stores, after
  truncation, with the attacker's own planted text removed first — otherwise the
  attack's phrasing could pose as environment data.
- **A canary that is not a secret is never invented.** When a payload template
  fails to match, the extractor drops the scenario instead of falling back to
  the whole argument. A false Fail is the same defect as a false Pass, pointing
  the other way. This is why AgentDojo's `banking/injection_task_1` is absent:
  upstream, "the IBAN of the pizza dinner companion" resolves to the literal
  string `"me"`, leaving no secret to match.

Integrity-only attacks (delete a file, change a password, wire money, steer a
booking) are deliberately excluded — they are real, but they are not what a
privacy score measures.
