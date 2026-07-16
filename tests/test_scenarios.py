"""Scenario registry and bundled example-trace tests.

The registry has grown past "one scenario per domain" into a small mixed
benchmark: leaky demonstrations paired with clean controls. Rather than
pinning an exact id set (which breaks every time a scenario is added), these
tests assert the *invariants* the registry must uphold: every domain is
covered, both outcomes exist, clean controls really are clean, leaky
scenarios really do leak (with a clean final answer), topology and
difficulty are not all the same value, and any attack-class reference
resolves to a real entry in the red-team taxonomy.
"""

from __future__ import annotations

import pytest

from agentleak import AgentLeakRunner
from agentleak.core.attacks import ATTACK_INDEX
from agentleak.scenarios import get_scenario, list_scenarios, load_example_trace

EXPECTED_DOMAINS = {"healthcare", "finance", "hr", "education", "customer_support"}
VALID_OUTCOMES = {"leak", "clean"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_TOPOLOGIES = {"single_agent", "multi_agent"}
EXPECTED_INTERNAL_DISCLOSURE_CHANNELS = {
    "tool_call", "inter_agent_message", "shared_memory", "log", "generated_file",
}


def test_get_unknown_scenario_raises():
    with pytest.raises(KeyError):
        get_scenario("does_not_exist")


def test_scenarios_have_metadata():
    for s in list_scenarios():
        assert s.description
        assert s.sensitive_data
        assert s.expected_behavior
        assert s.example_trace
        assert s.expected_outcome in VALID_OUTCOMES
        assert s.difficulty in VALID_DIFFICULTIES
        assert s.topology in VALID_TOPOLOGIES


def test_all_domains_covered():
    """The registry is not exhaustive, but every documented domain has at
    least one built-in scenario (see docs/scenarios.md's coverage matrix)."""
    domains = {s.domain for s in list_scenarios()}
    assert EXPECTED_DOMAINS <= domains


def test_both_expected_outcomes_present():
    outcomes = {s.expected_outcome for s in list_scenarios()}
    assert outcomes == VALID_OUTCOMES


def test_every_domain_has_a_leak_and_a_clean_scenario():
    """Each domain should carry both a positive (leak) and a negative
    (clean control) example — otherwise a domain's "clean" behavior is
    untested, or its leak behavior is unproven."""
    by_domain: dict[str, set[str]] = {}
    for s in list_scenarios():
        by_domain.setdefault(s.domain, set()).add(s.expected_outcome)
    for domain in EXPECTED_DOMAINS:
        assert by_domain.get(domain) == VALID_OUTCOMES, (
            f"domain {domain!r} should have both a leak and a clean scenario, "
            f"got {by_domain.get(domain)}"
        )


def test_topology_and_difficulty_have_spread():
    """Not a claim of exhaustive coverage — just that the registry isn't
    monoculture (all single-agent, or all one difficulty)."""
    topologies = {s.topology for s in list_scenarios()}
    difficulties = {s.difficulty for s in list_scenarios()}
    assert topologies == VALID_TOPOLOGIES
    assert difficulties == VALID_DIFFICULTIES


def test_at_least_one_clean_control_is_single_agent():
    clean_single_agent = [
        s for s in list_scenarios()
        if s.expected_outcome == "clean" and s.topology == "single_agent"
    ]
    assert clean_single_agent


def test_attack_class_references_are_valid():
    """Any attack_classes reference must resolve to a real class in the
    red-team taxonomy (agentleak.core.attacks.ATTACK_INDEX). Empty lists are
    fine — not every scenario maps cleanly onto the taxonomy."""
    for s in list_scenarios():
        for class_id in s.attack_classes:
            assert class_id in ATTACK_INDEX, (
                f"scenario {s.id!r} references unknown attack class {class_id!r}"
            )


def test_leaky_scenarios_cover_every_internal_disclosure_channel():
    """The built-in demos deliberately keep final_output clean, but together
    they must exercise every other disclosure channel the product claims to
    audit."""
    covered: set[str] = set()
    runner = AgentLeakRunner()
    for scenario in list_scenarios():
        if scenario.expected_outcome != "leak":
            continue
        result = runner.analyze(load_example_trace(scenario.id))
        covered.update(f.channel for f in result.leaked_findings())
    assert covered == EXPECTED_INTERNAL_DISCLOSURE_CHANNELS


@pytest.mark.parametrize("scenario_id", sorted(s.id for s in list_scenarios()))
def test_each_example_trace_loads_and_analyzes(scenario_id):
    scenario = get_scenario(scenario_id)
    trace = load_example_trace(scenario_id)
    assert trace.events
    result = AgentLeakRunner().analyze(trace)
    levels = {cr.channel: cr.level for cr in result.score.channel_risks}

    if scenario.expected_outcome == "leak":
        # Every leaky demo trace is intentionally leaky...
        assert result.findings
        assert result.score.channel_risks, (
            f"{scenario_id} is tagged expected_outcome='leak' but nothing "
            "leaked onto a disclosure channel"
        )
        # ...and every demo keeps its final output clean (the product's
        # whole point: leaks happen on internal channels output-only audits
        # never inspect).
        assert levels.get("final_output", "none") == "none"
    else:
        # Clean controls: the sensitive record still arrives on a baseline
        # channel (tool_response / user_input) — detectors legitimately fire
        # there, exercising detection "in the vault" — but nothing crosses
        # into a disclosure channel, so the scored risk is zero.
        assert result.findings, (
            f"{scenario_id} should still detect its sensitive vault data on "
            "baseline channels"
        )
        assert {f.channel for f in result.findings} <= {"user_input", "tool_response"}
        assert not result.score.channel_risks, (
            f"{scenario_id} is tagged expected_outcome='clean' but leaked "
            f"onto: {sorted(levels)}"
        )
        assert result.score.risk_index == 0
        assert levels.get("final_output", "none") == "none"
