# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Deciding before emission, not scoring after the fact.

Everything else in this project reads a trace that already happened, which is
the right shape for a CI gate and the wrong shape for the question a deployer
has been asked since 2 August 2026: is this agent inside its bounds right now,
and can you show me.

The gateway answers at the moment of emission with allow, redact or block. The
tests below pin the parts that decide whether such a thing is usable rather
than merely correct: redaction is selective, blocking is reserved for rules that
say never, and a refusal reaches the agent as something it can read and adapt
to rather than a broken transport.
"""

from __future__ import annotations

import json

import pytest

from agentleak.defenses.gateway import Action, Gateway

KYC_POLICY = [
    {"data_type": "sin", "to": "kyc-vendor", "for": "identity_check"},
    {"data_type": "health_condition", "to": "*", "deny": True},
]


@pytest.fixture
def gateway(tmp_path):
    return Gateway(
        flows=KYC_POLICY,
        evidence=str(tmp_path / "evidence.jsonl"),
        agent="triage",
    )


# ----------------------------------------------------------------------
# The three answers
# ----------------------------------------------------------------------
def test_a_permitted_flow_passes_untouched(gateway) -> None:
    args = {"sin": "123-456-789"}
    decision = gateway.check(args, recipient="kyc-vendor", purpose="identity_check")
    assert decision.action == Action.ALLOW
    assert decision.arguments == args


def test_a_refused_flow_is_redacted_not_blocked(gateway) -> None:
    """The bias that keeps the thing switched on. A gateway that blocks whatever
    it dislikes breaks the agent and gets removed within the week, and then it
    protects nothing.
    """
    decision = gateway.check(
        {"sin": "123-456-789"}, recipient="analytics", purpose="usage_metrics"
    )
    assert decision.action == Action.REDACT
    assert "123-456-789" not in json.dumps(decision.arguments)


def test_a_denied_flow_is_blocked(gateway) -> None:
    """A `deny` rule is somebody saying "not this, ever" — the one case where
    quietly continuing with less data is the wrong answer.
    """
    decision = gateway.check(
        {"diagnosis": "Type 2 diabetes"}, recipient="analytics", purpose="metrics"
    )
    assert decision.action == Action.BLOCK
    assert decision.arguments is None


def test_ordinary_arguments_pass(gateway) -> None:
    args = {"order_id": "ORD-7781", "page": "/pricing"}
    decision = gateway.check(args, recipient="analytics", purpose="metrics")
    assert decision.action == Action.ALLOW
    assert decision.arguments == args


# ----------------------------------------------------------------------
# Redaction has to be surgical
# ----------------------------------------------------------------------
def test_redaction_removes_only_the_offending_type(gateway) -> None:
    """Stripping everything findable would take the order number out with the
    SIN, and the tool call would fail for a reason nobody could see.
    """
    decision = gateway.check(
        {"sin": "123-456-789", "order": "ORD-7781", "page": "/pricing"},
        recipient="analytics",
        purpose="usage_metrics",
    )
    assert decision.action == Action.REDACT
    assert decision.arguments["order"] == "ORD-7781"
    assert decision.arguments["page"] == "/pricing"
    assert "123-456-789" not in decision.arguments["sin"]


def test_redaction_reaches_into_nested_arguments(gateway) -> None:
    decision = gateway.check(
        {"batch": [{"sin": "123-456-789"}, {"sin": "987-654-321"}]},
        recipient="analytics",
        purpose="usage_metrics",
    )
    assert decision.action == Action.REDACT
    assert "123-456-789" not in json.dumps(decision.arguments)
    assert "987-654-321" not in json.dumps(decision.arguments)


def test_purpose_changes_the_answer_for_identical_arguments(gateway) -> None:
    """The contextual-integrity claim, at runtime: same data, same recipient,
    different purpose, different decision.
    """
    args = {"sin": "123-456-789"}
    allowed = gateway.check(args, recipient="kyc-vendor", purpose="identity_check")
    refused = gateway.check(args, recipient="kyc-vendor", purpose="marketing")
    assert allowed.action == Action.ALLOW
    assert refused.action == Action.REDACT


def test_block_on_violation_escalates_every_refusal(tmp_path) -> None:
    strict = Gateway(
        flows=KYC_POLICY,
        evidence=str(tmp_path / "e.jsonl"),
        block_on_violation=True,
    )
    decision = strict.check({"sin": "123-456-789"}, recipient="analytics")
    assert decision.action == Action.BLOCK


def test_no_rules_means_nothing_is_refused(tmp_path) -> None:
    """Adopting the proxy without writing a policy must not start dropping data
    — it records, and says so.
    """
    open_gateway = Gateway(evidence=str(tmp_path / "e.jsonl"))
    decision = open_gateway.check({"sin": "123-456-789"}, recipient="anywhere")
    assert decision.action == Action.ALLOW
    assert "no flow rules" in decision.reason


# ----------------------------------------------------------------------
# Evidence
# ----------------------------------------------------------------------
def test_every_decision_is_recorded(gateway, tmp_path) -> None:
    gateway.check({"sin": "123-456-789"}, recipient="kyc-vendor", purpose="identity_check")
    gateway.check({"sin": "123-456-789"}, recipient="analytics", purpose="metrics")
    gateway.check({"diagnosis": "Type 2 diabetes"}, recipient="analytics")
    summary = gateway.log.summary()
    assert summary["entries"] == 3
    assert summary["by_action"] == {"allow": 1, "block": 1, "redact": 1}
    assert summary["verified"] is True


def test_the_evidence_log_never_contains_the_value(gateway) -> None:
    """This file is the one most likely to be pasted into a ticket. Writing the
    secret into it would make the log the leak it exists to prevent.
    """
    gateway.check(
        {"sin": "123-456-789", "diagnosis": "Type 2 diabetes"},
        recipient="analytics",
        purpose="metrics",
    )
    raw = gateway.log.path.read_text()
    assert "123-456-789" not in raw
    assert "Type 2 diabetes" not in raw
    assert "sin" in raw  # the *type* is recorded, and must be


def test_a_gateway_without_evidence_still_decides(tmp_path) -> None:
    decision = Gateway(flows=KYC_POLICY).check({"sin": "1"}, recipient="analytics")
    assert decision.action in {Action.ALLOW, Action.REDACT}


def test_check_json_accepts_a_string_payload(gateway) -> None:
    decision = gateway.check_json(
        '{"sin": "123-456-789"}', recipient="analytics", purpose="metrics"
    )
    assert decision.action == Action.REDACT
