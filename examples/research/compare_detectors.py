# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Compare two detector configurations on the bundled corpus, from Python.

    python examples/research/compare_detectors.py [OUTPUT_DIR]

Runs offline in a few seconds (no model, no API key). Writes two runs, their
paired comparison and the paper exports under OUTPUT_DIR (default
``research-demo/``), then prints the headline numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

from agentleak.research import Manifest, compare_runs, export_run, run_benchmark


def main(root: Path) -> None:
    # A: every built-in detector (what `agentleak run` uses without a config).
    a = Manifest(name="all-detectors", seed=7)

    # B: the toggles of a fresh agentleak.yaml, where finance and HR are off.
    b = Manifest(name="default-config", seed=7)
    b.detection.detectors = {"finance": False, "hr": False}

    run_a = run_benchmark(a, root / "all-detectors")
    run_b = run_benchmark(b, root / "default-config")

    for run in (run_a, run_b):
        recall = run.metric("recall")
        spec = run.metric("specificity.derived")
        assert recall and spec
        print(f"{run.manifest.name:<16} recall {recall['estimate']:.3f} "
              f"({recall['numerator']}/{recall['denominator']}, "
              f"95% CI {recall['ci_low']:.3f}-{recall['ci_high']:.3f})  "
              f"derived specificity {spec['estimate']:.3f} "
              f"({spec['numerator']}/{spec['denominator']})")

    doc = compare_runs(run_a, run_b, out_dir=root / "comparison")
    print()
    for m in doc["metrics"][:3]:
        d = m["difference"]
        print(f"{m['label']:<24} B-A {d['estimate']:+.3f} "
              f"(95% CI {d['ci_low']:+.3f} to {d['ci_high']:+.3f}), "
              f"{m['test']['test']} p={m['test']['p_value']:.3g}, Holm p={m['p_holm']:.3g}")
    print(f"{len(doc['flips'])} scenarios changed outcome; see {root / 'comparison'}/COMPARISON.md")

    written = export_run(run_a)
    print(f"\nExports for A: {', '.join(sorted(written))} in {run_a.out_dir / 'exports'}")

    # Rows are plain dicts: pandas is optional.
    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ImportError:
        print("(pandas not installed; run.rows is a list of dicts either way)")
    else:
        df = pd.DataFrame(run_a.rows)
        print(df.groupby("channel")["channel_leaked"].mean().round(3))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("research-demo"))
