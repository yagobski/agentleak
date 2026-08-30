# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Judge the flow, not the presence.

Every rule this project shipped before now answers "was this kind of data on
this kind of channel". That is a useful question and it is not the one privacy
law asks. A SIN reaching a KYC vendor for an identity check is the system
working; the same SIN reaching an analytics sink is a violation. Same data type,
same channel, same severity — different *flow*.

This is contextual integrity (Nissenbaum): privacy is a property of information
*flows*, not of data in isolation, and a flow is appropriate or not according to
the norms of the context it started in. The unit is the quadruple

    (data type, sender, recipient, purpose)

and AgentLeak already carried three quarters of it. Every event records its
``source`` and ``target``, and every finding inherits them. Purpose is the piece
that was missing; it comes from the event metadata, which the SDK already passes
through untouched.

Two rule forms, because the strict reading of contextual integrity — enumerate
every legitimate flow, deny the rest — is correct in theory and unusable as a
default on a system nobody has finished modelling:

* **allow** rules are *scoped* default-deny. Writing one allow rule for
  ``sin`` means SIN may reach the recipients you named and nowhere else, while
  data types you have said nothing about stay unjudged. You buy strictness one
  data type at a time, and adopting the feature never floods an existing project
  with violations about data it was never asked about.
* **deny** rules forbid a flow outright, and win over any allow rule. They are
  how you write "never to a third party, whatever else is permitted".

Matching is by exact value or ``*``. Recipients name the ``target`` node in the
trace, which is whatever the adapter recorded — an agent name, ``memory``, a
tool name, an MCP server. Purpose is compared against ``metadata["purpose"]`` on
the event; a rule that names a purpose cannot be satisfied by a flow that
declares none, because an undeclared purpose is exactly the case the rule exists
to catch.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["FlowRule", "FlowDecision", "evaluate_flows", "purpose_of"]

WILDCARD = "*"


def purpose_of(finding: Any) -> str:
    """The declared purpose of the flow that produced ``finding``.

    Empty when the event declared none. That is a meaningful answer, not a
    missing one: a flow that cannot say why it happened cannot be checked
    against a rule about why it is allowed to happen.
    """
    metadata = getattr(finding, "metadata", None) or {}
    return str(metadata.get("purpose") or "").strip()


def _as_tuple(value: Any) -> tuple[str, ...]:
    """Accept a scalar, a list, or nothing, and normalise to a tuple."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Iterable):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),)


def _matches(candidates: tuple[str, ...], value: str) -> bool:
    """Does ``value`` satisfy this facet of a rule?

    An empty facet means the rule does not constrain it. ``*`` matches anything
    *including* an empty value; a named facet does not, so a flow with no
    declared purpose never satisfies a rule that requires one.
    """
    if not candidates:
        return True
    if WILDCARD in candidates:
        return True
    return value in candidates


@dataclass(frozen=True)
class FlowRule:
    """One permitted or forbidden information flow."""

    data_types: tuple[str, ...] = ()
    senders: tuple[str, ...] = ()
    recipients: tuple[str, ...] = ()
    purposes: tuple[str, ...] = ()
    allow: bool = True
    description: str = ""

    @classmethod
    def from_mapping(cls, raw: Any) -> FlowRule:
        """Build a rule from configuration.

        ``to``/``from``/``for`` read the way the sentence does — "sin to
        kyc-vendor for identity_check" — and the longer names are accepted so a
        generated config is not forced into prose.
        """
        if not isinstance(raw, dict):
            raise ValueError(f"a flow rule must be a mapping, got {type(raw).__name__}")
        data_types = _as_tuple(raw.get("data_type") or raw.get("data_types"))
        if not data_types:
            raise ValueError("a flow rule must name at least one data_type")
        allow = raw.get("allow")
        if allow is None:
            allow = not bool(raw.get("deny"))
        return cls(
            data_types=data_types,
            senders=_as_tuple(raw.get("from") or raw.get("senders")),
            recipients=_as_tuple(raw.get("to") or raw.get("recipients")),
            purposes=_as_tuple(raw.get("for") or raw.get("purposes")),
            allow=bool(allow),
            description=str(raw.get("description") or "").strip(),
        )

    def governs(self, data_type: str) -> bool:
        """Does this rule have anything to say about this data type?"""
        return _matches(self.data_types, data_type)

    def matches(self, *, data_type: str, sender: str, recipient: str, purpose: str) -> bool:
        return (
            _matches(self.data_types, data_type)
            and _matches(self.senders, sender)
            and _matches(self.recipients, recipient)
            and _matches(self.purposes, purpose)
        )

    def describe(self) -> str:
        if self.description:
            return self.description
        parts = [f"{'allow' if self.allow else 'deny'} {'/'.join(self.data_types)}"]
        if self.senders:
            parts.append(f"from {'/'.join(self.senders)}")
        if self.recipients:
            parts.append(f"to {'/'.join(self.recipients)}")
        if self.purposes:
            parts.append(f"for {'/'.join(self.purposes)}")
        return " ".join(parts)


@dataclass
class FlowDecision:
    """Why one finding's flow was judged the way it was."""

    finding_id: str
    data_type: str
    sender: str
    recipient: str
    purpose: str
    permitted: bool
    reason: str
    rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "data_type": self.data_type,
            "sender": self.sender,
            "recipient": self.recipient,
            "purpose": self.purpose,
            "permitted": self.permitted,
            "reason": self.reason,
            "rule": self.rule,
        }

    def describe(self) -> str:
        flow = f"{self.data_type} from {self.sender or '?'} to {self.recipient or '?'}"
        if self.purpose:
            flow += f" for {self.purpose}"
        else:
            flow += " with no declared purpose"
        return f"{flow} — {self.reason}"


@dataclass
class FlowEvaluation:
    rules_applied: int = 0
    decisions: list[FlowDecision] = field(default_factory=list)

    @property
    def violations(self) -> list[FlowDecision]:
        return [d for d in self.decisions if not d.permitted]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_applied": self.rules_applied,
            "checked": len(self.decisions),
            "violations": [d.to_dict() for d in self.violations],
        }


def evaluate_flows(rules: Sequence[FlowRule], findings: Iterable[Any]) -> FlowEvaluation:
    """Judge each finding's flow against the configured rules.

    Only data types some rule speaks about are judged. A finding whose data type
    appears in no rule is not a pass and not a failure — it is out of scope, and
    saying so is more honest than implying the policy has an opinion it does not
    have.
    """
    rules = tuple(rules)
    if not rules:
        return FlowEvaluation()

    denies = [rule for rule in rules if not rule.allow]
    allows = [rule for rule in rules if rule.allow]
    evaluation = FlowEvaluation(rules_applied=len(rules))

    for finding in findings:
        data_type = getattr(finding, "data_type", "")
        if not any(rule.governs(data_type) for rule in rules):
            continue

        sender = str(getattr(finding, "source", "") or "")
        recipient = str(getattr(finding, "target", "") or "")
        purpose = purpose_of(finding)
        context = {
            "data_type": data_type,
            "sender": sender,
            "recipient": recipient,
            "purpose": purpose,
        }

        # A deny is a statement about a flow that must not happen, so it is
        # checked first and beats any permission granted elsewhere.
        denied = next((rule for rule in denies if rule.matches(**context)), None)
        if denied is not None:
            evaluation.decisions.append(FlowDecision(
                finding_id=getattr(finding, "finding_id", ""),
                permitted=False,
                reason=f"forbidden by rule: {denied.describe()}",
                rule=denied.describe(),
                **context,
            ))
            continue

        governing_allows = [rule for rule in allows if rule.governs(data_type)]
        if not governing_allows:
            # Only deny rules mention this type, and none of them matched.
            continue

        permitted = next((rule for rule in governing_allows if rule.matches(**context)), None)
        if permitted is not None:
            evaluation.decisions.append(FlowDecision(
                finding_id=getattr(finding, "finding_id", ""),
                permitted=True,
                reason=f"permitted by rule: {permitted.describe()}",
                rule=permitted.describe(),
                **context,
            ))
            continue

        expected = sorted({r for rule in governing_allows for r in rule.recipients} - {WILDCARD})
        detail = f" Permitted recipients: {', '.join(expected)}." if expected else ""
        evaluation.decisions.append(FlowDecision(
            finding_id=getattr(finding, "finding_id", ""),
            permitted=False,
            reason=(
                f"no rule permits this flow, and {data_type} is governed by "
                f"{len(governing_allows)} allow rule(s).{detail}"
            ),
            **context,
        ))

    return evaluation


def parse_flow_rules(raw: Any) -> tuple[FlowRule, ...]:
    """Build rules from the ``flows:`` block of a configuration."""
    if not raw:
        return ()
    if isinstance(raw, dict):
        raw = [raw]
    return tuple(FlowRule.from_mapping(item) for item in raw)
