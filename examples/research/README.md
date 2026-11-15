<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Research examples

Two runnable examples for the [research workflow](../../docs/research.md). Both
run offline, need no API key and use synthetic data only.

## Compare two detector configurations (Python)

```bash
python examples/research/compare_detectors.py research-demo
```

Runs the bundled corpus twice (every detector, then the default
`agentleak.yaml` toggles with finance and HR off), compares the runs paired by
scenario, and writes the paper exports. Takes a few seconds.

The same thing from the shell:

```bash
agentleak bench init all.yaml
agentleak bench init default-config.yaml
# edit default-config.yaml:  detectors: {finance: false, hr: false}
agentleak bench run all.yaml
agentleak bench run default-config.yaml
agentleak bench compare runs/all runs/default-config
```

## Score your own corpus with AgentRisk

`corpus.jsonl` mixes the three record kinds `score-corpus` accepts:

- the paper's worked example as **labelled secrets** with an explicit vault
  (RI = 5/21 = 0.238);
- two traces as raw **events** that AgentLeak's detectors scan;
- one trace annotated with `leaked: true/false` flags, the format of most
  hand-labelled corpora.

```bash
agentleak bench score-corpus examples/research/corpus.jsonl --derive paper-example
agentleak bench score-corpus examples/research/corpus.jsonl --sensitivity
```

From Python:

```python
from agentleak.research import score_corpus
score = score_corpus("examples/research/corpus.jsonl")
print(score.derivation("support-run-1").text())
rows = score.rows()          # list of dicts; pandas.DataFrame(rows) works
```
