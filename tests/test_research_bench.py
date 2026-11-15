# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Manifest, corpus selection, benchmark runner, summary and guardrails."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from agentleak import __version__
from agentleak.core.agentrisk import BASELINE_CHANNELS
from agentleak.research import Manifest, ManifestError, RunError, load_run, run_benchmark
from agentleak.research.bench import build_config, summary_digest
from agentleak.research.corpus import (
    DISCLOSURE_CHANNELS,
    builtin_units,
    derive_counterpart,
    pack_units,
    select_units,
    source_provenance,
)
from agentleak.research.manifest import render_template
from agentleak.research.rows import ROW_FIELDS, read_rows, scenario_table
from agentleak.research.summary import find_metric

STAMP = "2026-01-01T00:00:00+00:00"


def small_manifest(name: str = "small", **detection: Any) -> Manifest:
    m = Manifest(name=name)
    m.scenarios.sources = ["builtin", "agentleak_bench", "agentdojo_exfil"]
    m.scenarios.max_per_source = 6
    m.statistics.bootstrap_resamples = 300
    for key, value in detection.items():
        setattr(m.detection, key, value)
    return m


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench") / "small"
    return run_benchmark(small_manifest(), out, generated_at=STAMP)


# -- manifest -----------------------------------------------------------------
def test_template_round_trips_and_is_pinned(tmp_path):
    path = tmp_path / "exp.yaml"
    path.write_text(render_template("exp", filename=str(path)), encoding="utf-8")
    m = Manifest.load(path)
    assert m.name == "exp"
    assert m.pins["agentleak_version"] == __version__
    assert set(m.pins["sources"]) == set(m.scenarios.sources)
    assert m.check_pins() == []
    # Relative output_dir is anchored to the manifest's folder, not the cwd.
    assert Path(m.resolved_output_dir()) == tmp_path / "runs" / "exp"
    assert f"agentleak bench run {path}" in path.read_text()


def test_manifest_rejects_typos_and_impossible_settings():
    with pytest.raises(ManifestError, match="unknown key"):
        Manifest.from_dict({"name": "x", "sead": 3})
    with pytest.raises(ManifestError, match="unknown key"):
        Manifest.from_dict({"name": "x", "detection": {"mdoe": "fast"}})
    with pytest.raises(ManifestError, match="replay mode"):
        Manifest.from_dict({"name": "x", "repetitions": 3})
    with pytest.raises(ManifestError, match="unknown scenario source"):
        Manifest.from_dict({"name": "x", "scenarios": {"sources": ["nope"]}})
    with pytest.raises(ManifestError, match="agent.model"):
        Manifest.from_dict({"name": "x", "agent": {"mode": "live"}})
    with pytest.raises(ManifestError, match="not found"):
        Manifest.load("/nonexistent/manifest.yaml")


def test_build_config_maps_detectors_and_rejects_unknown():
    m = Manifest(name="x")
    m.detection.detectors = {"keyname": False}
    cfg = build_config(m)
    toggles = cfg.detectors.as_dict()
    assert toggles["keyname"] is False and toggles["finance"] is True
    m.detection.detectors = {"nope": True}
    with pytest.raises(ManifestError, match="unknown detector"):
        build_config(m)


def test_drifted_pins_refuse_to_run_unless_allowed(tmp_path):
    m = small_manifest()
    m.scenarios.sources = ["builtin"]
    m.pins = {"agentleak_version": "0.0.1", "sources": {"builtin": "0" * 64}}
    with pytest.raises(RunError, match="pins do not match"):
        run_benchmark(m, tmp_path / "r")
    run = run_benchmark(m, tmp_path / "r", allow_drift=True)
    assert run.lock["pins"]["drift_allowed"] is True
    assert len(run.lock["pins"]["drift"]) == 2


# -- corpus -------------------------------------------------------------------
def test_builtin_units_pair_leaks_with_independent_controls():
    units = builtin_units()
    clean = [u for u in units if u.label == "clean"]
    assert len(units) == 10 and len(clean) == 5
    assert all(u.negative_kind == "independent" and u.counterpart_of for u in clean)


def test_derived_counterpart_removes_ground_truth_but_keeps_sources():
    for pack in ("agentleak_bench", "privacylens_ci", "agentdojo_exfil"):
        unit = pack_units(pack)[0]
        twin = derive_counterpart(unit)
        assert twin is not None
        assert twin.label == "clean" and twin.negative_kind == "derived"
        assert twin.counterpart_of == unit.unit_id
        assert unit.reference_channels()  # the leaking fixture carries its ground truth
        assert twin.reference_channels() == set()
        src = [e.content for e in unit.trace.events if e.channel_value in BASELINE_CHANNELS]
        twin_src = [e.content for e in twin.trace.events if e.channel_value in BASELINE_CHANNELS]
        assert src == twin_src
    assert derive_counterpart(builtin_units()[0]) is None


def test_select_units_filters_and_samples_deterministically():
    a = select_units(sources=["agentdojo_exfil"], max_per_source=5, seed=1)
    b = select_units(sources=["agentdojo_exfil"], max_per_source=5, seed=1)
    c = select_units(sources=["agentdojo_exfil"], max_per_source=5, seed=2)
    assert [u.unit_id for u in a] == [u.unit_id for u in b]
    assert [u.unit_id for u in a] != [u.unit_id for u in c]
    assert sum(u.label == "leaking" for u in a) == 5
    none = select_units(sources=["agentleak_bench"], counterparts="none")
    assert all(u.label == "leaking" for u in none) and len(none) == 36
    hijack = select_units(sources=["builtin", "agentdojo_exfil"], failure_modes=["hijack"],
                          counterparts="none")
    assert {u.source for u in hijack} == {"agentdojo_exfil"}
    with pytest.raises(ValueError):
        select_units(sources=["missing"])


def test_source_provenance_hashes_and_licences():
    for source in ("builtin", "agentleak_bench", "privacylens_ci", "agentdojo_exfil"):
        p = source_provenance(source)
        assert len(p["sha256"]) == 64 and p["license"]
    assert source_provenance("privacylens_ci")["license"] == "CC-BY-4.0"


# -- run outputs ----------------------------------------------------------------
def test_run_writes_every_output(small_run):
    out = small_run.out_dir
    for name in ("rows.csv", "summary.json", "manifest.lock.json", "REPORT.md", "manifest.yaml"):
        assert (out / name).exists(), name
    assert not (out / ".partial").exists()
    rows = read_rows(out / "rows.csv")
    assert rows == small_run.rows
    assert list(rows[0]) == list(ROW_FIELDS)
    units = scenario_table(rows)
    assert len(rows) == len(units) * len(DISCLOSURE_CHANNELS)
    assert {r["channel"] for r in rows} == set(DISCLOSURE_CHANNELS)
    lock = small_run.lock
    env = lock["environment"]
    assert env["agentleak_version"] == __version__ and env["python"]
    assert {s["source"] for s in lock["sources"]} == {"builtin", "agentleak_bench",
                                                      "agentdojo_exfil"}
    assert lock["outputs"]["rows.csv"]
    manifest_yaml = yaml.safe_load((out / "manifest.yaml").read_text())
    assert Manifest.from_dict(manifest_yaml).digest() == lock["manifest_sha256"]


def test_rows_feed_pandas_style_consumers(small_run):
    row = small_run.rows[0]
    assert all(isinstance(v, (str, int, float)) for v in row.values())
    assert row["outcome"] in ("leak_detected", "no_finding")


def test_same_manifest_and_seed_is_byte_identical(tmp_path, small_run):
    run_benchmark(small_manifest(), tmp_path / "again", generated_at="2030-05-05T00:00:00+00:00")
    assert (tmp_path / "again" / "rows.csv").read_bytes() == \
        (small_run.out_dir / "rows.csv").read_bytes()
    a = json.loads((small_run.out_dir / "summary.json").read_text())
    b = json.loads((tmp_path / "again" / "summary.json").read_text())
    assert a["generated_at"] != b["generated_at"]
    assert summary_digest(a) == summary_digest(b)
    a.pop("generated_at")
    b.pop("generated_at")
    assert a == b


def test_resume_after_interruption_gives_identical_output(tmp_path, small_run):
    calls = {"n": 0}

    def explode(done: int, total: int, unit: str) -> None:
        calls["n"] += 1
        if calls["n"] == 7:
            raise KeyboardInterrupt

    out = tmp_path / "resumed"
    with pytest.raises(KeyboardInterrupt):
        run_benchmark(small_manifest(), out, progress=explode, generated_at=STAMP)
    assert (out / ".partial" / "rows.jsonl").exists()
    run = run_benchmark(small_manifest(), out, generated_at=STAMP)
    assert run.resumed_units == 7
    assert (out / "rows.csv").read_bytes() == (small_run.out_dir / "rows.csv").read_bytes()
    # A finished directory is reused, not recomputed.
    again = run_benchmark(small_manifest(), out)
    assert again.reused is True


def test_a_directory_holding_another_manifest_is_refused(tmp_path, small_run):
    out = tmp_path / "x"
    m = small_manifest()
    m.scenarios.sources = ["builtin"]
    run_benchmark(m, out)
    with pytest.raises(RunError, match="different manifest"):
        run_benchmark(small_manifest(), out)
    run = run_benchmark(small_manifest(), out, fresh=True)
    assert run.reused is False


def test_load_run_explains_an_unfinished_directory(tmp_path):
    (tmp_path / ".partial").mkdir()
    with pytest.raises(RunError, match="resume"):
        load_run(tmp_path)


def test_empty_selection_is_a_clear_error(tmp_path):
    m = small_manifest()
    m.scenarios.domains = ["no-such-domain"]
    with pytest.raises(RunError, match="matched no scenarios"):
        run_benchmark(m, tmp_path / "empty")


# -- summary and guardrails -------------------------------------------------------
def test_every_metric_carries_numerator_denominator_and_interval(small_run):
    for rec in small_run.metrics():
        assert rec["kind"] and rec["definition"] and rec["population"]
        assert rec["ci_method"]
        assert ("numerator" in rec and "denominator" in rec) or "n" in rec
    s = small_run.summary
    assert s["software"]["agentleak_version"] == __version__
    assert s["detector"]["tiers_run"] == ["regex"]
    assert s["detector"]["canaries_used_by_detectors"] is False
    assert {p["source"] for p in s["provenance"]} == {"builtin", "agentleak_bench",
                                                      "agentdojo_exfil"}


def test_independent_and_derived_negatives_are_never_pooled(small_run):
    ids = {m["id"] for m in small_run.metrics()}
    assert {"specificity.independent", "specificity.derived"} <= ids
    assert "specificity" not in ids
    ind = small_run.metric("specificity.independent")
    der = small_run.metric("specificity.derived")
    assert ind["denominator"] == 5
    assert der["denominator"] == small_run.summary["counts"]["clean_derived"]
    assert "precision.vs_independent" in ids and "precision.vs_derived" in ids


def test_canary_integrity_is_never_labelled_as_detection(small_run):
    integrity = [m for m in small_run.metrics() if m["id"].startswith("integrity.")]
    assert integrity and all(m["kind"] == "fixture_integrity" for m in integrity)
    report = (small_run.out_dir / "REPORT.md").read_text()
    assert "Fixture integrity (corpus checks, not detector accuracy)" in report


def test_no_output_calls_a_clean_result_safe(small_run):
    assert {r["outcome"] for r in small_run.rows} <= {"leak_detected", "no_finding"}
    report = (small_run.out_dir / "REPORT.md").read_text().lower()
    assert "not that the trace is safe" in report
    assert " is safe" not in report.replace("not that the trace is safe", "")


def test_recall_matches_the_rows(small_run):
    units = scenario_table(small_run.rows)
    leaking = [u for u in units if u["label"] == "leaking"]
    rec = small_run.metric("recall")
    assert rec["denominator"] == len(leaking)
    assert rec["numerator"] == sum(u["leaked"] for u in leaking)
    assert find_metric(small_run.summary, "recall") == rec


# -- live mode ----------------------------------------------------------------
class LeakyFakeLLM:
    """Reads the records, writes one to memory, answers. No network."""

    model = "fake-model"

    def __init__(self) -> None:
        self.n = 0

    def chat(self, messages, tools):  # noqa: ANN001
        step = sum(1 for m in messages if m["role"] == "assistant") % 3
        self.n += 1
        if step == 0:
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"a{self.n}", "function": {"name": "get_records", "arguments": "{}"}}]}
        if step == 1:
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"b{self.n}", "function": {
                    "name": "save_memory",
                    "arguments": json.dumps({"note": "client SSN 123-45-6789"})}}]}
        return {"role": "assistant", "content": "Done."}


def test_live_mode_with_injected_model_and_trace_reanalysis(tmp_path):
    m = Manifest.from_dict({
        "name": "live-test", "repetitions": 2,
        "scenarios": {"sources": ["builtin"], "labels": ["leaking"], "max_per_source": 2},
        "agent": {"mode": "live", "model": "fake-model", "base_url": "http://localhost:1/v1"},
        "statistics": {"bootstrap_resamples": 300},
    })
    run = run_benchmark(m, tmp_path / "live", llm=LeakyFakeLLM(), generated_at=STAMP)
    assert {r["label"] for r in run.rows} == {"live"}
    assert {r["repetition"] for r in run.rows} == {1, 2}
    assert run.metric("leak_rate")["denominator"] == 2
    assert run.metric("leak_rate")["numerator"] == 2
    assert run.metric("leak_fraction.mean") is not None
    traces = sorted((tmp_path / "live" / "traces").glob("*.json"))
    assert len(traces) == 4
    run_benchmark(m, tmp_path / "reanalysis", traces_from=tmp_path / "live" / "traces",
                           generated_at=STAMP)
    assert (tmp_path / "reanalysis" / "rows.csv").read_bytes() == \
        (tmp_path / "live" / "rows.csv").read_bytes()


def test_repin_updates_only_the_pins_block(tmp_path):
    from agentleak.research.manifest import repin

    path = tmp_path / "exp.yaml"
    path.write_text(render_template("exp", filename=str(path)), encoding="utf-8")
    text = path.read_text().replace("seed: 20261114", "seed: 99  # my seed")
    text = text.replace(f'agentleak_version: "{__version__}"', 'agentleak_version: "0.0.1"')
    path.write_text(text)
    assert Manifest.load(path).check_pins()
    drift = repin(path)
    assert drift and "0.0.1" in drift[0]
    after = path.read_text()
    assert "seed: 99  # my seed" in after
    assert Manifest.load(path).check_pins() == []
    assert repin(path) == []
