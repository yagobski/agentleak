# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The leak that lives between two traces.

Every other part of this project scores one trace against itself, which cannot
see the failure that matters in a shared deployment: Alice's diagnosis written
to memory in one run, repeated to Bob in a later one. Both runs are scored
independently, both may score well, and nothing says the second disclosed the
first one's data. That is the gap PersistBench, CIMemories and PiSAs spent 2026
on, and it was defect #5 of this project's own audit:

    run 1 : tool_call → memory  {"user":"alice","diagnosis":"HIV positive"}  RI 1.0
    run 2 : final_output        "Previously stored: alice, HIV positive"      RI 1.0
    (no link between the two, and no notion of a subject at all)

These tests pin the behaviour that closes it — and, just as hard, the privacy of
the thing that closes it. A ledger recording who owns which secret is precisely
the file you least want readable, so it is tested for what it must *not*
contain.
"""

from __future__ import annotations

import json

import pytest

from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.subjects import SubjectLedger, secret_fingerprint
from agentleak.core.trace import Trace

DIAGNOSIS = '{"diagnosis": "Type 2 diabetes", "mrn": "TR12345678"}'


@pytest.fixture
def ledger(tmp_path):
    return SubjectLedger(path=tmp_path / "subjects.jsonl")


def _run(runner, ledger, run_id, subject, channel="final_output", content=DIAGNOSIS):
    trace = Trace(run_id=run_id, agent_name="triage", subject=subject)
    trace.add_event(channel=channel, content=content, source="agent", target="memory")
    return runner.analyze(trace, subject_ledger=ledger)


@pytest.fixture
def runner():
    return AgentLeakRunner()


# ----------------------------------------------------------------------
# The defect
# ----------------------------------------------------------------------
def test_one_subjects_data_surfacing_in_anothers_session_is_caught(runner, ledger) -> None:
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    result = _run(runner, ledger, "run_bob", "bob")

    cross = result.to_dict()["cross_session"]
    assert cross["passed"] is False
    owners = {(d["data_type"], d["owner"], d["disclosed_to"]) for d in cross["cross_subject_disclosures"]}
    assert ("health_condition", "alice", "bob") in owners


def test_a_subject_seeing_their_own_data_is_not_a_violation(runner, ledger) -> None:
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    result = _run(runner, ledger, "run_alice_again", "alice")
    assert result.to_dict()["cross_session"]["passed"] is True


def test_the_first_run_has_nothing_to_compare_against(runner, ledger) -> None:
    result = _run(runner, ledger, "run_alice", "alice")
    cross = result.to_dict()["cross_session"]
    assert cross["passed"] is True
    assert cross["secrets_attributed"] > 0


def test_data_arriving_on_a_source_channel_is_not_a_disclosure(runner, ledger) -> None:
    """Arriving is not disclosing. A record legitimately reaching the agent on
    `tool_response` attributes the secret, and must not by itself accuse the run.
    """
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    result = _run(runner, ledger, "run_bob", "bob", channel="tool_response")
    assert result.to_dict()["cross_session"]["passed"] is True


def test_each_secret_is_reported_once_per_channel(runner, ledger) -> None:
    """Coalescing unifies a secret's identity but keeps every finding, so two
    detectors agreeing about one value would otherwise be reported as two
    separate cross-subject events — the inflation this project fixed in scoring,
    reappearing one layer up.
    """
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    result = _run(runner, ledger, "run_bob", "bob")
    breaches = result.to_dict()["cross_session"]["cross_subject_disclosures"]
    keys = [(d["fingerprint"], d["channel"]) for d in breaches]
    assert len(keys) == len(set(keys))


# ----------------------------------------------------------------------
# The ledger must not become the leak
# ----------------------------------------------------------------------
def test_the_ledger_never_stores_the_secret(runner, ledger) -> None:
    """A file recording who owns which secret is the one you least want
    readable. It holds fingerprints, and this test reads the raw bytes to say so.
    """
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    raw = ledger.path.read_text()
    assert "Type 2 diabetes" not in raw
    assert "diabetes" not in raw
    assert "TR12345678" not in raw
    assert "health_condition" in raw  # the *type* is kept, and must be


def test_fingerprints_are_salted_per_ledger(tmp_path) -> None:
    """Unsalted, the fingerprints are a dictionary attack away from the values:
    the space of SINs is small enough to enumerate. A ledger stolen from one
    deployment must be useless against another.
    """
    first = SubjectLedger(path=tmp_path / "a" / "s.jsonl")
    second = SubjectLedger(path=tmp_path / "b" / "s.jsonl")
    assert first.salt != second.salt
    assert (
        secret_fingerprint("sin", "123-456-789", salt=first.salt)
        != secret_fingerprint("sin", "123-456-789", salt=second.salt)
    )


def test_the_same_value_fingerprints_the_same_within_one_ledger(ledger) -> None:
    assert (
        secret_fingerprint("sin", "123-456-789", salt=ledger.salt)
        == secret_fingerprint("sin", " 123-456-789 ", salt=ledger.salt)
    )


def test_a_subject_can_be_erased(runner, ledger) -> None:
    """Erasure is a right, not a feature request: a fingerprint of somebody's
    SIN is still about them (GDPR Art. 17, Law 25's equivalent).
    """
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    _run(runner, ledger, "run_carol", "carol", channel="shared_memory",
         content='{"diagnosis": "asthma"}')
    assert "alice" in ledger.subjects()

    removed = ledger.forget("alice")
    assert removed > 0
    assert "alice" not in ledger.subjects()
    assert "carol" in ledger.subjects()


def test_erasing_a_subject_stops_them_being_reported_as_an_owner(runner, ledger) -> None:
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    ledger.forget("alice")
    result = _run(runner, ledger, "run_bob", "bob")
    assert result.to_dict()["cross_session"]["passed"] is True


# ----------------------------------------------------------------------
# Opt-in, and silent when it cannot know
# ----------------------------------------------------------------------
def test_a_run_without_a_subject_is_not_judged(runner, ledger) -> None:
    """An undeclared subject cannot be compared against anything, and guessing
    would invent an owner for data whose owner nobody stated.
    """
    trace = Trace(run_id="anon", agent_name="a")
    trace.add_event(channel="final_output", content=DIAGNOSIS, source="agent", target="user")
    cross = runner.analyze(trace, subject_ledger=ledger).to_dict()["cross_session"]
    assert cross["enabled"] is False
    assert "no subject declared" in cross["reason"]


def test_no_ledger_means_no_opinion(runner) -> None:
    """Upgrading must not start accumulating subject data in a location nobody
    chose.
    """
    trace = Trace(run_id="r", agent_name="a", subject="alice")
    trace.add_event(channel="final_output", content=DIAGNOSIS, source="agent", target="user")
    cross = runner.analyze(trace).to_dict()["cross_session"]
    assert cross["enabled"] is False


def test_an_event_may_override_the_run_subject(runner, ledger) -> None:
    """One run can legitimately touch several people's records."""
    first = Trace(run_id="r1", agent_name="a", subject="alice")
    first.add_event(channel="shared_memory", content=DIAGNOSIS, source="agent",
                    target="memory", metadata={"subject": "dana"})
    runner.analyze(first, subject_ledger=ledger)
    assert "dana" in ledger.subjects()

    result = _run(runner, ledger, "r2", "alice")
    owners = {d["owner"] for d in result.to_dict()["cross_session"]["cross_subject_disclosures"]}
    assert owners == {"dana"}


# ----------------------------------------------------------------------
# The CI gate
# ----------------------------------------------------------------------
def test_the_gate_fails_on_a_cross_subject_disclosure(ledger) -> None:
    config = Config.from_dict({
        "project": {"name": "ci"},
        "privacy_policy": {"forbid_cross_subject": True},
    })
    runner = AgentLeakRunner(config)
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    result = _run(runner, ledger, "run_bob", "bob")

    policy = result.to_dict()["privacy_policy"]
    assert policy["passed"] is False
    assert "forbid_cross_subject" in policy["assertions_checked"]


def test_the_gate_says_nothing_when_it_cannot_check(runner) -> None:
    """Without a ledger the assertion has nothing to check, and must not pass
    vacuously — a green gate that checked nothing is worse than no gate.
    """
    config = Config.from_dict({
        "project": {"name": "ci"},
        "privacy_policy": {"forbid_cross_subject": True},
    })
    trace = Trace(run_id="r", agent_name="a", subject="alice")
    trace.add_event(channel="final_output", content=DIAGNOSIS, source="agent", target="user")
    policy = AgentLeakRunner(config).analyze(trace).to_dict()["privacy_policy"]
    assert "forbid_cross_subject" not in policy.get("assertions_checked", [])


def test_the_score_is_untouched_by_attribution(runner, ledger) -> None:
    """Attribution is a different claim from severity. The secret leaked in this
    trace either way and AgentRisk already counts it; discovering whose it was
    must not silently move the number.
    """
    trace = Trace(run_id="r", agent_name="a", subject="bob")
    trace.add_event(channel="final_output", content=DIAGNOSIS, source="agent", target="user")

    without = AgentLeakRunner().analyze(trace).risk_index
    _run(runner, ledger, "seed", "alice", channel="shared_memory")
    with_ledger = runner.analyze(trace, subject_ledger=ledger).risk_index
    assert without == with_ledger


def test_a_corrupt_ledger_line_never_fails_the_analysis(runner, ledger) -> None:
    """A history file is a convenience, never a source of truth."""
    _run(runner, ledger, "run_alice", "alice", channel="shared_memory")
    with ledger.path.open("a") as handle:
        handle.write("{not json at all\n")
    fresh = SubjectLedger(path=ledger.path)
    result = _run(runner, fresh, "run_bob", "bob")
    assert result.to_dict()["cross_session"]["enabled"] is True


def test_the_summary_counts_subjects_and_types(runner, ledger) -> None:
    _run(runner, ledger, "r1", "alice", channel="shared_memory")
    _run(runner, ledger, "r2", "carol", channel="shared_memory",
         content='{"diagnosis": "asthma"}')
    summary = ledger.summary()
    assert summary["subjects"] == 2
    assert summary["secrets_tracked"] >= 2
    assert json.dumps(summary)  # serialisable for --format json
