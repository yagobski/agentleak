# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The researcher workflow: run an experiment, compare configurations with
paired statistics, export tables and archive a reproducible capsule.

Everything returns plain dataclasses, dicts and lists; ``pandas`` is never
required, but ``pandas.DataFrame(run.rows)`` works directly::

    from agentleak.research import Manifest, run_benchmark, compare_runs

    a = run_benchmark(Manifest(name="all-detectors"), "runs/a")
    m = Manifest(name="no-keyname")
    m.detection.detectors = {"keyname": False}
    b = run_benchmark(m, "runs/b")
    print(a.metric("recall"))
    doc = compare_runs(a, b)

AgentRisk on your own corpus::

    from agentleak.research import score_corpus
    score = score_corpus("my_corpus.jsonl")
    print(score.derivation("trace-7").text())

The statistics live in :mod:`agentleak.research.stats`.
"""

from __future__ import annotations

from . import stats
from .ablation import scope_ablation
from .agentrisk import (
    CorpusScore,
    Derivation,
    check_properties,
    derive,
    score_corpus,
    weight_sensitivity,
)
from .bench import BenchRun, RunError, load_run, run_benchmark
from .capsule import VerifyResult, build_capsule, verify_capsule
from .compare import ComparisonError, compare_runs
from .corpus import DISCLOSURE_CHANNELS, Unit, select_units
from .export import export_run
from .manifest import Manifest, ManifestError, render_template
from .rows import read_rows, scenario_table

__all__ = [
    "DISCLOSURE_CHANNELS",
    "BenchRun",
    "ComparisonError",
    "CorpusScore",
    "Derivation",
    "Manifest",
    "ManifestError",
    "RunError",
    "Unit",
    "VerifyResult",
    "build_capsule",
    "check_properties",
    "compare_runs",
    "derive",
    "export_run",
    "load_run",
    "read_rows",
    "render_template",
    "run_benchmark",
    "scenario_table",
    "scope_ablation",
    "score_corpus",
    "select_units",
    "stats",
    "verify_capsule",
    "weight_sensitivity",
]
