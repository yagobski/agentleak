# Pack extractors

The scenario packs bundled in `src/agentleak/scenarios/packs/` are derived from
public research datasets. These scripts are how they were built — kept in the
repo so anyone can check what we took, what we changed, and what we dropped.

They are **not** part of the installed package and are not needed at runtime.

| Script | Builds | Upstream | Licence |
| --- | --- | --- | --- |
| `build_privacylens_pack.py` | `privacylens_ci.json` (120) | [SALT-NLP/PrivacyLens](https://huggingface.co/datasets/SALT-NLP/PrivacyLens) | CC-BY-4.0 |
| `build_agentdojo_pack.py` | `agentdojo_exfil.json` (100) | [ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo) | MIT |
| `build_injecagent_pack.py` | `injecagent_ds.json` (96) | [uiuc-kang-lab/InjecAgent](https://github.com/uiuc-kang-lab/InjecAgent) | MIT |
| `build_agentsocialbench_pack.py` | `agentsocialbench_ma.json` (105) | [kingofspace0wzz/agentsocialbench](https://github.com/kingofspace0wzz/agentsocialbench) | MIT |
| `build_mcptox_pack.py` | `mcptox_recipient_hijack.json` (24) | [zhiqiangwang4/MCPTox-Benchmark](https://github.com/zhiqiangwang4/MCPTox-Benchmark) | CC-BY-4.0 (data) |

All packs carry `source`, `source_url`, `license` and `attribution`, and those
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

```bash
python -I scripts/packs/build_injecagent_pack.py PATH/TO/InjecAgent/data
```

Reads the data-stealing cases and `attacker_simulated_responses.json` from a
checkout of InjecAgent (commit `f19c9f2`). Plain JSON, no upstream code is run.
A canary is a value from the private data the attacker's tool returned that
does not already appear in the user's request, the user's tool call or the
injected response, so the clean counterpart (same run, attacker steps removed)
scores no canary; `tests/test_injecagent.py` checks both directions.

```bash
git clone https://github.com/kingofspace0wzz/agentsocialbench /tmp/asb
git -C /tmp/asb checkout 6d8497c05dbab812714b2545a563e6fe7d4160ec
python -I scripts/packs/build_agentsocialbench_pack.py /tmp/asb
```

Reads `prism/data/scenarios/` (plain JSON). Five categories, a fixed quota
each, scenarios ordered by the SHA-256 of their id. Each record holds the
sender's private context, two must-not-cross statements (the canaries) and
the source's abstractions for them; `"variant": "clean"` on a record gives the
clean counterpart. `tests/test_multiagent_packs.py` checks that every canary
was in the sender's context, lands on the claimed channel, and is absent from
the counterpart.

```bash
git clone https://github.com/zhiqiangwang4/MCPTox-Benchmark /tmp/mcptox
git -C /tmp/mcptox checkout 630121b3275f74cc72d000a7a056e4d3c68648ef
python -I scripts/packs/build_mcptox_pack.py /tmp/mcptox
```

Reads `response_all.json`. Keeps the cases where a model's recorded call sends
the user's data to a recipient the poisoned description named, and a model
that ignored the description gives the clean counterpart. The script prints
how many of the 1,348 instances each rule removed; the same counts are stored
in the pack under `selection`.

All builds are deterministic: the same inputs produce a byte-identical pack.
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
