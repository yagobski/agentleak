"""Declarative privacy policy assertions at the runner seam."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentleak import AgentLeakRunner, Trace
from agentleak.core.config import Config


def _analyze(policy: dict, channel: str = "log"):
    config = Config.from_dict({"privacy_policy": policy})
    trace = Trace(run_id="policy-run")
    trace.add_event(channel, "customer email jane@example.com")
    return AgentLeakRunner(config).analyze(trace)


def test_empty_policy_is_disabled_and_passes():
    result = _analyze({})
    assert result.policy_evaluation.enabled is False
    assert result.policy_evaluation.passed is True


def test_policy_blocks_forbidden_channel_and_serializes_ids():
    result = _analyze({"forbid_channels": ["log"]})
    evaluation = result.policy_evaluation
    assert evaluation.enabled is True
    assert evaluation.passed is False
    assert result.blocked is True
    assert evaluation.violations[0].rule == "forbid_channels"
    assert evaluation.violations[0].finding_ids
    assert result.to_dict()["privacy_policy"]["violations"][0]["finding_ids"]


def test_source_findings_do_not_count_as_agent_leaks():
    result = _analyze({"max_findings": 0}, channel="user_input")
    assert result.findings
    assert result.policy_evaluation.passed is True
    assert result.blocked is False


def test_policy_combines_risk_level_data_type_and_vault_assertions():
    result = _analyze({
        "max_risk_index": 0,
        "forbid_levels": [2],
        "forbid_data_types": ["email"],
        "require_explicit_vault": True,
    })
    rules = {violation.rule for violation in result.policy_evaluation.violations}
    assert rules == {
        "max_risk_index", "forbid_levels", "forbid_data_types", "require_explicit_vault",
    }


def test_explicit_vault_satisfies_vault_assertion():
    config = Config.from_dict({"privacy_policy": {"require_explicit_vault": True}})
    trace = Trace(run_id="vault")
    trace.add_event("final_output", "safe response")
    result = AgentLeakRunner(config).analyze(trace, vault={1: 1})
    assert result.policy_evaluation.passed is True


@pytest.mark.parametrize("policy", [
    {"max_risk_index": 1.1},
    {"max_findings": -1},
    {"forbid_levels": [5]},
    {"forbid_channels": ["unknown_channel"]},
])
def test_invalid_policy_is_rejected(policy):
    with pytest.raises(ValidationError):
        Config.from_dict({"privacy_policy": policy})
