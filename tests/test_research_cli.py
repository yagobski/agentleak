# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""`agentleak bench` end to end, the way a first-time user runs it."""

from __future__ import annotations

import json

import yaml
from typer.testing import CliRunner

from agentleak.cli import app

runner = CliRunner()


def _quick_manifest(path, name: str, detectors: object = "all") -> None:
    data = yaml.safe_load(path.read_text())
    data["name"] = name
    data["scenarios"]["sources"] = ["builtin", "agentleak_bench"]
    data["scenarios"]["max_per_source"] = 4
    data["statistics"]["bootstrap_resamples"] = 300
    data["detection"]["detectors"] = detectors
    data["output_dir"] = f"runs/{name}"
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_full_researcher_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["bench", "init", "a.yaml"])
    assert res.exit_code == 0, res.output
    assert "agentleak bench run a.yaml" in res.output
    res = runner.invoke(app, ["bench", "init", "a.yaml"])
    assert res.exit_code == 2 and "already exists" in res.output

    runner.invoke(app, ["bench", "init", "b.yaml"])
    _quick_manifest(tmp_path / "a.yaml", "all")
    _quick_manifest(tmp_path / "b.yaml", "no-pii", {"pii": False})

    res = runner.invoke(app, ["bench", "run", "a.yaml", "-q"])
    assert res.exit_code == 0, res.output
    assert "Recall (leaking fixtures)" in res.output
    assert "agentleak bench export runs/all" in res.output
    res = runner.invoke(app, ["bench", "run", "a.yaml", "-q"])
    assert "already holds a finished run" in res.output
    assert runner.invoke(app, ["bench", "run", "b.yaml", "-q"]).exit_code == 0

    res = runner.invoke(app, ["bench", "compare", "runs/all", "runs/no-pii"])
    assert res.exit_code == 0, res.output
    assert "flipped" in res.output and "p Holm" in res.output
    assert (tmp_path / "runs/no-pii/compare-vs-all/COMPARISON.md").exists()

    res = runner.invoke(app, ["bench", "export", "runs/all", "--format", "latex,methods"])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "runs/all/exports/tables.tex").exists()
    assert not (tmp_path / "runs/all/exports/metrics.csv").exists()
    res = runner.invoke(app, ["bench", "export", "runs/all", "--format", "docx"])
    assert res.exit_code == 2 and "unknown export format" in res.output

    res = runner.invoke(app, ["bench", "capsule", "runs/all", "-o", "cap.zip"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["bench", "verify", "cap.zip"])
    assert res.exit_code == 0, res.output
    assert "Reproduced." in res.output

    res = runner.invoke(app, ["bench", "ablate-scope", "runs/all"])
    assert res.exit_code == 0, res.output
    assert "flipped to leak" in res.output

    res = runner.invoke(app, ["bench", "show", "runs/all"])
    assert res.exit_code == 0 and "Detection performance" in res.output


def test_run_errors_are_messages_not_tracebacks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["bench", "run", "missing.yaml"])
    assert res.exit_code == 2 and "bench init" in res.output
    (tmp_path / "bad.yaml").write_text("name: x\nrepetitions: 4\n")
    res = runner.invoke(app, ["bench", "run", "bad.yaml"])
    assert res.exit_code == 2 and "replay mode" in res.output
    res = runner.invoke(app, ["bench", "verify", "nothing.zip"])
    assert res.exit_code == 2
    res = runner.invoke(app, ["bench", "compare", "x", "y"])
    assert res.exit_code == 2 and "not a finished benchmark run" in res.output


def test_score_corpus_and_properties_commands(tmp_path):
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("\n".join(json.dumps(r) for r in [
        {"trace_id": "paper", "vault": {"1": 5, "2": 3, "3": 2, "4": 1}},
        {"trace_id": "paper", "secret_id": "AcmeCorp", "level": 1, "channel": "final_output"},
        {"trace_id": "paper", "secret_id": "HIV+", "level": 4, "channel": "inter_agent_message"},
        {"trace_id": "other", "secret_id": "x", "level": 2, "leaked": True},
        {"trace_id": "other", "secret_id": "y", "level": 3, "leaked": False},
    ]) + "\n")
    res = runner.invoke(app, ["bench", "score-corpus", str(corpus), "--derive", "paper",
                              "--sensitivity", "--out", str(tmp_path / "o")])
    assert res.exit_code == 0, res.output
    assert "5 / 21 = 0.2381" in res.output and "Weight sensitivity" in res.output
    assert (tmp_path / "o" / "scores.csv").exists()
    res = runner.invoke(app, ["bench", "score-corpus", str(corpus), "--json"])
    assert json.loads(res.output)["traces"][0]["trace_id"] == "paper"
    res = runner.invoke(app, ["bench", "score-corpus", str(corpus), "--derive", "nope"])
    assert res.exit_code == 2
    res = runner.invoke(app, ["bench", "properties", "--trials", "40"])
    assert res.exit_code == 0 and "rank_robustness" in res.output
