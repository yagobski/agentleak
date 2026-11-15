# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AgentRisk researcher API: corpus scoring, derivations, properties, weights."""

from __future__ import annotations

import json

import pytest

from agentleak.core.agentrisk import VaultScopeError
from agentleak.research import check_properties, derive, score_corpus, weight_sensitivity
from agentleak.research.agentrisk import load_records

PAPER = [
    {"trace_id": "paper", "vault": {"1": 5, "2": 3, "3": 2, "4": 1}},
    {"trace_id": "paper", "secret_id": "AcmeCorp", "level": 1, "channel": "final_output"},
    {"trace_id": "paper", "secret_id": "HIV+", "level": 4, "channel": "inter_agent_message"},
]


def test_paper_worked_example_through_the_corpus_api():
    score = score_corpus(PAPER, detect=False)
    t = score.get("paper")
    assert (t.wsl, t.rho_s) == (5, 21)
    assert round(t.ri, 3) == 0.238
    assert round(t.ri_by_channel["final_output"], 3) == 0.048
    assert round(t.ri_by_channel["inter_agent_message"], 3) == 0.190
    assert t.vault_mode == "explicit"
    text = score.derivation("paper").text()
    assert "WSL   = 4 + 1 = 5" in text
    assert "rho_S = 1x5 + 2x3 + 3x2 + 4x1 = 21" in text
    assert "RI    = WSL / rho_S = 5 / 21 = 0.2381" in text


def test_labelled_secrets_with_leaked_flags():
    records = [
        {"trace_id": "t", "secret_id": "dx", "level": 4, "leaked": True},
        {"trace_id": "t", "secret_id": "salary", "level": 3, "leaked": False},
        {"trace_id": "t", "secret_id": "email", "data_type": "email", "leaked": "true"},
    ]
    t = score_corpus(records, detect=False).get("t")
    assert (t.wsl, t.rho_s) == (6, 9)  # email maps to L2 through the taxonomy
    assert t.leaked_secrets == 2 and t.vault_secrets == 3


def test_detected_events_count_distinct_secrets_and_sources():
    records = [
        {"trace_id": "s", "channel": "tool_response",
         "content": {"customer": "Jane Smith", "email": "jane.smith@example.com",
                     "ssn": "123-45-6789"}},
        {"trace_id": "s", "channel": "shared_memory",
         "content": "Customer jane.smith@example.com, SSN 123-45-6789"},
        {"trace_id": "s", "channel": "log", "content": "SSN 123-45-6789 again"},
    ]
    score = score_corpus(records)
    t = score.get("s")
    assert t.wsl == 6  # ssn (4) + email (2), each once despite two channels
    d = score.derivation("s")
    assert d.wsl == t.wsl and d.rho_s == t.rho_s
    # Values are shown redacted in the derivation.
    assert "123-45-6789" not in d.text()


def test_file_formats_jsonl_json_and_csv(tmp_path):
    jsonl = tmp_path / "c.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in PAPER) + "\n")
    js = tmp_path / "c.json"
    js.write_text(json.dumps(PAPER))
    csv = tmp_path / "c.csv"
    csv.write_text(
        "trace_id,secret_id,level,channel,vault\n"
        'paper,,,,"{""1"": 5, ""2"": 3, ""3"": 2, ""4"": 1}"\n'
        "paper,AcmeCorp,1,final_output,\n"
        "paper,HIV+,4,inter_agent_message,\n"
    )
    for path in (jsonl, js, csv):
        t = score_corpus(path, detect=False).get("paper")
        assert round(t.ri, 3) == 0.238, path.suffix
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n")
    with pytest.raises(ValueError, match="bad.jsonl:1"):
        load_records(bad)
    with pytest.raises(FileNotFoundError):
        load_records(tmp_path / "missing.jsonl")


def test_undersized_explicit_vault_fails_loudly():
    records = [
        {"trace_id": "t", "vault": {"1": 1}},
        {"trace_id": "t", "secret_id": "x", "level": 4, "channel": "log"},
    ]
    with pytest.raises(VaultScopeError):
        score_corpus(records, detect=False)


def test_missing_level_is_rejected():
    with pytest.raises(ValueError, match="needs a level"):
        score_corpus([{"trace_id": "t", "secret_id": "x", "channel": "log"}], detect=False)


def test_rows_and_aggregate_are_plain_and_seeded():
    records = [
        {"trace_id": f"t{i}", "secret_id": f"s{j}", "level": 1 + (i + j) % 4,
         "leaked": j <= i % 3}
        for i in range(8) for j in range(4)
    ]
    score = score_corpus(records, detect=False)
    rows = score.rows()
    assert len(rows) == 8 and all(isinstance(r["ri"], float) for r in rows)
    agg = score.aggregate(seed=5, n_boot=500)
    assert agg == score.aggregate(seed=5, n_boot=500)
    assert agg["pooled_ri"]["denominator"] == sum(r["rho_s"] for r in rows)
    lo, hi = agg["mean_ri"]["ci_low"], agg["mean_ri"]["ci_high"]
    assert lo <= agg["mean_ri"]["estimate"] <= hi


def test_weight_sensitivity_never_reorders_dominated_pairs():
    records = []
    for i in range(6):
        records.append({"trace_id": f"t{i}", "vault": {"1": 2, "2": 2, "3": 2, "4": 2}})
        for j in range(i % 4 + 1):
            records.append({"trace_id": f"t{i}", "secret_id": f"s{j}", "level": 4 - j % 4,
                            "channel": "log"})
    score = score_corpus(records, detect=False)
    sens = weight_sensitivity(score)
    assert sens["reference"] == "linear (default)"
    for s in sens["schemes"]:
        assert s["dominance_pairs_reordered"] == 0
    ref = next(s for s in sens["schemes"] if s["scheme"] == "linear (default)")
    assert ref["kendall_tau_b_vs_reference"] == pytest.approx(1.0)
    assert ref["pairs_reordered_vs_reference"] == 0
    assert len(sens["per_trace"]) == 6


def test_derive_agrees_with_core_on_random_inputs():
    import random

    from agentleak.research.agentrisk import _findings

    rng = random.Random(0)
    for _ in range(50):
        levels = [rng.randint(1, 4) for _ in range(rng.randint(1, 15))]
        leaked = {i for i in range(len(levels)) if rng.random() < 0.5}
        d = derive(_findings(levels, leaked))
        assert d.wsl == sum(levels[i] for i in leaked)
        assert d.rho_s == sum(levels)


def test_property_checker_passes_on_the_shipped_formula():
    results = check_properties(trials=60, seed=1)
    names = {r.name for r in results}
    assert {"worked_example", "boundedness", "monotonicity", "severity_sensitivity",
            "scale_invariance", "rank_robustness", "determinism", "distinct_counting",
            "source_rule"} == names
    assert all(r.passed for r in results), [r.to_dict() for r in results if not r.passed]
