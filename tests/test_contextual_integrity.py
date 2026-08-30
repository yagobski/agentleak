# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The distinction no earlier rule could express.

Every assertion this project shipped before judged data *presence*: this type,
that channel, that many findings. A SIN reaching a KYC vendor for an identity
check and the same SIN reaching an analytics sink are identical under all of
them — same data type, same channel, same severity — and opposite under privacy
law. Contextual integrity says a flow is appropriate or not according to the
norms of the context the data came from, and the unit is the quadruple
(data type, sender, recipient, purpose).

These tests pin the four things that make such a rule usable rather than merely
correct: it distinguishes recipient, it distinguishes purpose, an undeclared
purpose fails a rule that requires one, and adopting the feature does not flood
a project with violations about data nobody wrote a rule for.
"""

from __future__ import annotations

import pytest

from agentleak.core.config import Config
from agentleak.core.contextual_integrity import (
    FlowRule,
    evaluate_flows,
    parse_flow_rules,
    purpose_of,
)
from agentleak.core.detector import Finding, Severity
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.trace import Trace


def _finding(data_type: str, *, source: str = "agent", target: str = "",
             purpose: str = "", finding_id: str = "f1") -> Finding:
    return Finding(
        finding_id=finding_id,
        run_id="run",
        event_id="evt",
        channel="tool_call",
        data_type=data_type,
        severity=Severity.CRITICAL,
        confidence=0.9,
        matched_value="123-456-789",
        redacted_value="12*******89",
        detector="test",
        source=source,
        target=target,
        level=4,
        metadata={"purpose": purpose} if purpose else {},
    )


KYC_ONLY = (
    FlowRule.from_mapping(
        {"data_type": "sin", "to": "kyc-vendor", "for": "identity_check"}
    ),
)


# ----------------------------------------------------------------------
# The four properties that matter
# ----------------------------------------------------------------------
def test_the_permitted_recipient_passes() -> None:
    result = evaluate_flows(KYC_ONLY, [
        _finding("sin", target="kyc-vendor", purpose="identity_check")
    ])
    assert not result.violations


def test_the_same_data_to_another_recipient_fails() -> None:
    """The whole point: identical type, channel and severity, opposite verdict."""
    result = evaluate_flows(KYC_ONLY, [
        _finding("sin", target="analytics", purpose="identity_check")
    ])
    assert len(result.violations) == 1
    assert result.violations[0].recipient == "analytics"


def test_the_same_data_for_another_purpose_fails() -> None:
    result = evaluate_flows(KYC_ONLY, [
        _finding("sin", target="kyc-vendor", purpose="marketing")
    ])
    assert len(result.violations) == 1
    assert result.violations[0].purpose == "marketing"


def test_an_undeclared_purpose_cannot_satisfy_a_rule_that_requires_one() -> None:
    """A flow that cannot say why it happened is exactly the case the rule
    exists to catch, so silence must not read as compliance.
    """
    result = evaluate_flows(KYC_ONLY, [_finding("sin", target="kyc-vendor")])
    assert len(result.violations) == 1
    assert "no declared purpose" in result.violations[0].describe()


def test_ungoverned_data_types_are_out_of_scope_not_violations() -> None:
    """Scoped default-deny. Writing a rule about `sin` must not turn every
    email in the trace into a violation, or nobody adopts the feature on a
    system they have not finished modelling.
    """
    result = evaluate_flows(KYC_ONLY, [
        _finding("email", target="analytics", finding_id="f2"),
        _finding("person_name", target="analytics", finding_id="f3"),
    ])
    assert not result.violations
    assert not result.decisions


# ----------------------------------------------------------------------
# Rule grammar
# ----------------------------------------------------------------------
def test_a_deny_rule_beats_an_allow_rule() -> None:
    """"Never to a third party, whatever else is permitted" has to be writable."""
    rules = parse_flow_rules([
        {"data_type": "sin", "to": "*"},
        {"data_type": "sin", "to": "third-party", "deny": True},
    ])
    permitted = evaluate_flows(rules, [_finding("sin", target="kyc-vendor")])
    forbidden = evaluate_flows(rules, [_finding("sin", target="third-party")])
    assert not permitted.violations
    assert len(forbidden.violations) == 1
    assert "forbidden by rule" in forbidden.violations[0].reason


def test_a_wildcard_recipient_accepts_anything() -> None:
    rules = parse_flow_rules([{"data_type": "health_condition", "to": "*"}])
    assert not evaluate_flows(rules, [_finding("health_condition", target="anywhere")]).violations


def test_a_rule_may_name_several_recipients() -> None:
    rules = parse_flow_rules([{"data_type": "health_condition", "to": ["clinician", "ehr"]}])
    assert not evaluate_flows(rules, [_finding("health_condition", target="ehr")]).violations
    assert evaluate_flows(rules, [_finding("health_condition", target="billing")]).violations


def test_the_sender_can_be_constrained_too() -> None:
    rules = parse_flow_rules([
        {"data_type": "sin", "from": "intake", "to": "kyc-vendor"}
    ])
    assert not evaluate_flows(rules, [
        _finding("sin", source="intake", target="kyc-vendor")]).violations
    assert evaluate_flows(rules, [
        _finding("sin", source="marketing-bot", target="kyc-vendor")]).violations


def test_a_rule_without_a_data_type_is_rejected_at_load() -> None:
    """Fail where the line number is, not silently govern nothing at run time."""
    with pytest.raises(ValueError, match="data_type"):
        parse_flow_rules([{"to": "kyc-vendor"}])


def test_the_violation_names_the_permitted_recipients() -> None:
    """An operator reading this has to know what to change."""
    result = evaluate_flows(KYC_ONLY, [_finding("sin", target="analytics",
                                                purpose="identity_check")])
    assert "kyc-vendor" in result.violations[0].reason


def test_purpose_reads_from_event_metadata() -> None:
    assert purpose_of(_finding("sin", purpose="identity_check")) == "identity_check"
    assert purpose_of(_finding("sin")) == ""


# ----------------------------------------------------------------------
# End to end, through config and the runner
# ----------------------------------------------------------------------
def _analyze(target: str, purpose: str | None):
    cfg = Config.from_dict({
        "project": {"name": "ci"},
        "privacy_policy": {"flows": [
            {"data_type": "sin", "to": "kyc-vendor", "for": "identity_check"}
        ]},
    })
    trace = Trace(run_id="flow", agent_name="triage")
    trace.add_event(
        channel="tool_call",
        content='{"sin": "123-456-789"}',
        source="agent",
        target=target,
        metadata={"purpose": purpose} if purpose else {},
    )
    return AgentLeakRunner(cfg).analyze(trace).to_dict()["privacy_policy"]


def test_a_permitted_flow_passes_the_gate() -> None:
    policy = _analyze("kyc-vendor", "identity_check")
    assert policy["passed"] is True
    assert "flows" in policy["assertions_checked"]


def test_an_inappropriate_flow_fails_the_gate() -> None:
    policy = _analyze("analytics", "identity_check")
    assert policy["passed"] is False
    assert any(v["rule"] == "flows" for v in policy["violations"])


def test_the_report_carries_the_flow_detail() -> None:
    """The count says something is wrong; the detail says what to change."""
    policy = _analyze("analytics", "identity_check")
    breaches = policy["flows"]["violations"]
    assert breaches
    assert breaches[0]["recipient"] == "analytics"
    assert breaches[0]["data_type"] == "sin"


def test_a_malformed_flow_rule_fails_at_config_load() -> None:
    with pytest.raises(Exception, match="data_type"):
        Config.from_dict({
            "project": {"name": "ci"},
            "privacy_policy": {"flows": [{"to": "kyc-vendor"}]},
        })


def test_no_flows_configured_leaves_the_policy_untouched() -> None:
    """Existing projects must not acquire a new assertion by upgrading."""
    cfg = Config.from_dict({"project": {"name": "ci"}})
    trace = Trace(run_id="none", agent_name="a")
    trace.add_event(channel="tool_call", content='{"sin": "123-456-789"}',
                    source="agent", target="anywhere")
    policy = AgentLeakRunner(cfg).analyze(trace).to_dict()["privacy_policy"]
    assert "flows" not in policy.get("assertions_checked", [])
