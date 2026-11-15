# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Comparison, exports, citations, capsules and the scope ablation."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import yaml

from agentleak.research import (
    ComparisonError,
    Manifest,
    build_capsule,
    compare_runs,
    export_run,
    run_benchmark,
    scope_ablation,
    verify_capsule,
)
from agentleak.research.citation import EMBEDDED, _project, references_bib
from agentleak.research.export import latex_escape

STAMP = "2026-01-01T00:00:00+00:00"
REPO = Path(__file__).resolve().parent.parent


def manifest(name: str, detectors: object = "all") -> Manifest:
    m = Manifest(name=name)
    m.scenarios.sources = ["builtin", "agentleak_bench", "agentdojo_exfil"]
    m.scenarios.max_per_source = 8
    m.statistics.bootstrap_resamples = 300
    m.detection.detectors = detectors  # type: ignore[assignment]
    return m


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("cmp")
    a = run_benchmark(manifest("all"), root / "a", generated_at=STAMP)
    b = run_benchmark(manifest("no-pii", {"pii": False}), root / "b", generated_at=STAMP)
    return a, b


# -- comparison ---------------------------------------------------------------
def test_a_run_compared_with_itself_shows_no_difference(runs):
    a, _ = runs
    doc = compare_runs(a, a)
    assert doc["flips"] == []
    for m in doc["metrics"]:
        assert m["difference"]["estimate"] == 0
        assert m["test"]["p_value"] == 1.0
    assert all(c["status"] == "ok" for c in doc["checks"])


def test_paired_comparison_reports_tests_intervals_and_flips(runs, tmp_path):
    a, b = runs
    doc = compare_runs(a, b, out_dir=tmp_path / "cmp")
    recall = next(m for m in doc["metrics"] if m["id"] == "recall")
    assert recall["test"]["test"] == "mcnemar-exact"
    assert recall["b"]["estimate"] <= recall["a"]["estimate"]
    lost = recall["discordant"]["a_only"]
    assert lost == sum(1 for f in doc["flips"]
                       if f["label"] == "leaking" and f["direction"] == "leak_detected->no_finding")
    d = recall["difference"]
    assert d["ci_low"] <= d["estimate"] <= d["ci_high"]
    assert all(m["p_holm"] >= m["test"]["p_value"] for m in doc["metrics"])
    assert any(m["id"] == "ri.mean.leaking" and m["test"]["test"].startswith("sign-flip")
               for m in doc["metrics"])
    for name in ("comparison.json", "COMPARISON.md", "comparison.tex"):
        assert (tmp_path / "cmp" / name).exists()
    md = (tmp_path / "cmp" / "COMPARISON.md").read_text()
    assert "Scenarios that flipped" in md and "p (Holm)" in md
    # Different detectors change the observed vault: the comparison says so.
    assert any(c["check"] == "vault_denominator" and c["status"] == "warn" for c in doc["checks"])


def test_incomparable_runs_are_refused_unless_forced(runs, tmp_path):
    a, _ = runs
    other = tmp_path / "tampered"
    other.mkdir()
    for name in ("rows.csv", "summary.json", "manifest.lock.json"):
        (other / name).write_bytes((a.out_dir / name).read_bytes())
    lock = json.loads((other / "manifest.lock.json").read_text())
    lock["sources"][1]["sha256"] = "0" * 64
    (other / "manifest.lock.json").write_text(json.dumps(lock))
    with pytest.raises(ComparisonError, match="sources"):
        compare_runs(a.out_dir, other)
    doc = compare_runs(a.out_dir, other, force=True)
    assert doc["forced"] is True


def test_degraded_and_tier_differences_are_warned(runs, tmp_path):
    a, _ = runs
    m = manifest("standard")
    m.scenarios.sources = ["builtin"]
    m.detection.mode = "standard"
    std = run_benchmark(m, tmp_path / "std")
    base = manifest("fast")
    base.scenarios.sources = ["builtin"]
    fast = run_benchmark(base, tmp_path / "fast")
    doc = compare_runs(fast, std)
    status = {c["check"]: c["status"] for c in doc["checks"]}
    if std.summary["detector"]["degraded"]:  # Presidio not installed in the test env
        assert status["degraded"] == "warn"
        assert "DEGRADED" in (std.out_dir / "REPORT.md").read_text()
    assert std.summary["detector"]["tiers_requested"] == ["regex", "presidio"]


# -- exports ------------------------------------------------------------------
def test_exports_are_written_with_provenance(runs):
    a, _ = runs
    written = export_run(a)
    assert set(written) == {"tables.tex", "tables.md", "metrics.csv", "scenarios.csv",
                            "methods.txt", "references.bib"}
    tex = written["tables.tex"].read_text()
    assert "\\toprule" in tex and "\\bottomrule" in tex and "\\caption{" in tex
    assert "never pooled" in tex and "Wilson score" in tex
    assert "agentleak\\_bench" in tex  # escaped
    csv_text = written["metrics.csv"].read_text().splitlines()
    header = csv_text[0].split(",")
    for col in ("numerator", "denominator", "agentleak_version", "tiers_run", "provenance"):
        assert col in header
    methods = written["methods.txt"].read_text()
    assert a.summary["software"]["agentleak_version"] in methods
    assert "received no ground truth" in methods and "never pooled" in methods


def test_latex_escape():
    assert latex_escape("a_b & 50% #1") == r"a\_b \& 50\% \#1"


def test_bibtex_uses_only_repository_citation_data():
    bib = references_bib([
        {"source": "builtin", "source_url": "", "license": "MIT"},
        {"source": "agentleak_bench", "source_url": "https://doi.org/10.1109/ACCESS.2026.3704541",
         "license": "MIT"},
        {"source": "privacylens_ci", "source_url": "https://huggingface.co/datasets/SALT-NLP/PrivacyLens",
         "license": "CC-BY-4.0"},
    ])
    assert "@software{agentleak_software" in bib
    assert "doi = {10.1109/ACCESS.2026.3704541}" in bib
    assert "% agentleak_bench: cite" in bib
    # No invented entry for a dataset whose citation the repository does not hold.
    assert "@misc" not in bib and "privacylens_ci: no BibTeX entry" in bib


def test_embedded_citation_matches_cff():
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))
    assert _project(cff) == EMBEDDED


# -- capsule ------------------------------------------------------------------
def test_capsule_is_deterministic_complete_and_verifies(runs, tmp_path):
    a, _ = runs
    one = build_capsule(a, tmp_path / "one.zip")
    two = build_capsule(a, tmp_path / "two.zip")
    assert one.read_bytes() == two.read_bytes()
    with zipfile.ZipFile(one) as zf:
        names = set(zf.namelist())
        zenodo = json.loads(zf.read(".zenodo.json"))
        readme = zf.read("README.md").decode()
    for required in ("run/rows.csv", "run/summary.json", "run/manifest.lock.json",
                     "run/REPORT.md", "run/exports/tables.tex", "environment.txt",
                     "LICENSES/MIT.txt", "SHA256SUMS", "README.md", ".zenodo.json"):
        assert required in names, required
    assert "FILL-IN" in json.dumps(zenodo)
    assert "agentleak bench verify" in readme
    result = verify_capsule(one)
    assert result.ok, result.checks
    assert {c["check"] for c in result.checks} >= {"checksums", "rows.csv", "summary.json"}


def test_tampered_capsule_fails_verification(runs, tmp_path):
    a, _ = runs
    good = build_capsule(a, tmp_path / "good.zip")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(good) as src, zipfile.ZipFile(bad, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "run/rows.csv":
                data = data.replace(b"leak_detected", b"no_finding", 1)
            dst.writestr(name, data)
    result = verify_capsule(bad, rerun=False)
    assert not result.ok
    assert "run/rows.csv" in result.checks[0]["detail"]


def test_capsule_includes_cc_by_text_for_privacylens(tmp_path):
    m = Manifest(name="pl")
    m.scenarios.sources = ["privacylens_ci"]
    m.scenarios.max_per_source = 2
    m.statistics.bootstrap_resamples = 300
    run = run_benchmark(m, tmp_path / "pl")
    with zipfile.ZipFile(build_capsule(run, tmp_path / "pl.zip")) as zf:
        assert "LICENSES/CC-BY-4.0.txt" in zf.namelist()


# -- scope ablation ---------------------------------------------------------------
def test_scope_ablation_flips_every_clean_control(runs, tmp_path):
    a, _ = runs
    doc = scope_ablation(a.out_dir, out_dir=tmp_path / "abl")
    by_id = {m["id"]: m for m in doc["metrics"]}
    ind = by_id["independent.flipped_to_leak"]
    assert ind["numerator"] == ind["denominator"] == 5
    assert by_id["independent.default"]["numerator"] == 5
    assert by_id["independent.ablated"]["numerator"] == 0
    # Default-rule leak flags agree with the run itself.
    run_leaks = {r["scenario_id"]: r["scenario_leaked"] for r in a.rows}
    assert all(run_leaks[r["scenario_id"]] == r["leaked_default"] for r in doc["rows"])
    assert all(r["ri_ablated"] >= r["ri_default"] for r in doc["rows"])
    for name in ("scope_ablation.json", "scope_ablation.csv", "SCOPE-ABLATION.md"):
        assert (tmp_path / "abl" / name).exists()


def test_comparison_outputs_carry_version_tier_and_provenance(runs, tmp_path):
    a, b = runs
    doc = compare_runs(a, b, out_dir=tmp_path / "c")
    for side in ("a", "b"):
        assert doc[side]["agentleak_version"] and doc[side]["detector"]["tiers_run"]
        assert {p["source"] for p in doc[side]["provenance"]} >= {"builtin"}
    md = (tmp_path / "c" / "COMPARISON.md").read_text()
    tex = (tmp_path / "c" / "comparison.tex").read_text()
    for text in (md, tex):
        assert "sha256" in text and "agentleak" in text
