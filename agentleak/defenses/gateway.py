# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Decide about a tool call before it is emitted, not after it is scored.

Everything else in this project reads a trace that already happened. That is the
right shape for a CI gate — you learn before you ship — and the wrong shape for
the question a deployer is now asked: *is this agent staying inside its approved
bounds right now, and can you show me?*

The gateway answers at the moment of emission. It is handed a proposed tool call
before it leaves the process, runs the same detectors the analysis uses, judges
the flow with the same contextual-integrity rules the CI gate uses, and returns
one of three answers:

* **allow** — nothing sensitive, or every flow is permitted.
* **redact** — sensitive data is present and the policy says remove it. The
  arguments go on with the values replaced; the call still happens.
* **block** — a rule forbids this flow outright. The call does not happen and
  the caller gets a structured reason it can act on.

Redact is the default for a violation, and that is a deliberate bias. A gateway
that blocks on anything it dislikes breaks the agent, gets switched off in a
week, and then protects nothing; one that redacts keeps the task working while
removing what should not have gone. Blocking is reserved for flows a `deny` rule
names, because a deny rule is someone saying "not this, ever".

Every decision is appended to a hash-chained evidence log — the artefact the
scoring report cannot be, because it is written as things happen rather than
generated on request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..core.contextual_integrity import FlowRule, evaluate_flows, parse_flow_rules
from ..core.detector import Finding, Severity
from ..core.evidence import EvidenceLog
from .sanitizer import RedactionStyle, Sanitizer

__all__ = ["Gateway", "GatewayDecision", "Action"]


class Action:
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class GatewayDecision:
    """What the gateway decided, and everything the caller needs to act on it."""

    action: str
    arguments: Any = None
    reason: str = ""
    data_types: tuple[str, ...] = ()
    violations: list[dict[str, Any]] = field(default_factory=list)
    tool: str = ""
    recipient: str = ""
    purpose: str = ""

    @property
    def blocked(self) -> bool:
        return self.action == Action.BLOCK

    @property
    def modified(self) -> bool:
        return self.action == Action.REDACT

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "data_types": list(self.data_types),
            "violations": self.violations,
            "tool": self.tool,
            "recipient": self.recipient,
            "purpose": self.purpose,
        }


def _walk_strings(value: Any) -> list[str]:
    """Every string anywhere in a nested argument structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        # Keys carry signal too: the key-name detector reads `diagnosis: ...`,
        # and a bare value string would throw that away.
        return [f"{k}: {v}" if isinstance(v, str) else str(k)
                for k, v in value.items()] + [
            s for v in value.values() if not isinstance(v, str) for s in _walk_strings(v)
        ]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in _walk_strings(item)]
    return []


class Gateway:
    """Runtime preflight for outbound tool calls.

    Args:
        flows: Contextual-integrity rules, in the same grammar the CI policy
            uses, so a policy written for the gate carries over unchanged.
        evidence: Path to the hash-chained decision log. ``None`` disables it,
            which is right for a unit test and wrong for a deployment.
        redaction_style: How removed values are rendered.
        block_on_violation: Escalate every inappropriate flow to a block rather
            than redacting it. Off by default — see the module docstring.
        detectors: Override the detector chain (tests, custom rules).
    """

    def __init__(
        self,
        *,
        flows: Any = None,
        evidence: str | None = None,
        redaction_style: str | RedactionStyle = RedactionStyle.PLACEHOLDER,
        block_on_violation: bool = False,
        detectors: list[Any] | None = None,
        agent: str = "",
        run_id: str = "",
    ) -> None:
        self.rules: tuple[FlowRule, ...] = (
            tuple(flows) if flows and isinstance(flows[0], FlowRule)  # type: ignore[index]
            else parse_flow_rules(flows)
        )
        self.sanitizer = Sanitizer(style=redaction_style, detectors=detectors)
        self.block_on_violation = block_on_violation
        self.agent = agent
        self.run_id = run_id
        self.log = EvidenceLog(evidence) if evidence else None

    # ------------------------------------------------------------------
    def _findings(self, arguments: Any, *, recipient: str, purpose: str) -> list[Finding]:
        """Detector hits over the proposed arguments, shaped as findings so the
        flow rules can judge them with no special case."""
        findings: list[Finding] = []
        for index, text in enumerate(_walk_strings(arguments)):
            for raw in self.sanitizer._spans(text):  # noqa: SLF001 - same module family
                _, _, value, data_type = raw
                findings.append(Finding(
                    finding_id=f"preflight_{index}_{len(findings)}",
                    run_id=self.run_id,
                    event_id="preflight",
                    channel="tool_call",
                    data_type=data_type.lower(),
                    severity=Severity.HIGH,
                    confidence=0.8,
                    matched_value=value,
                    redacted_value=value,
                    detector="gateway",
                    source=self.agent or "agent",
                    target=recipient,
                    metadata={"purpose": purpose} if purpose else {},
                ))
        return findings

    # ------------------------------------------------------------------
    def check(
        self,
        arguments: Any,
        *,
        tool: str = "",
        recipient: str = "",
        purpose: str = "",
    ) -> GatewayDecision:
        """Judge one proposed tool call. Emits nothing; returns the decision."""
        findings = self._findings(arguments, recipient=recipient, purpose=purpose)
        data_types = tuple(sorted({f.data_type for f in findings}))

        if not findings:
            return self._record(GatewayDecision(
                action=Action.ALLOW, arguments=arguments,
                reason="no sensitive data detected in the arguments",
                tool=tool, recipient=recipient, purpose=purpose,
            ))

        evaluation = evaluate_flows(self.rules, findings)
        breaches = evaluation.violations
        if not breaches:
            reason = (
                "every flow is permitted by policy" if self.rules
                else "sensitive data present, and no flow rules are configured"
            )
            return self._record(GatewayDecision(
                action=Action.ALLOW, arguments=arguments, reason=reason,
                data_types=data_types, tool=tool, recipient=recipient, purpose=purpose,
            ))

        violations = [d.to_dict() for d in breaches]
        # A `deny` rule is somebody saying "not this, ever" — the one case where
        # silently continuing with less data is the wrong answer.
        forbidden = [d for d in breaches if d.reason.startswith("forbidden by rule")]
        if forbidden or self.block_on_violation:
            first = (forbidden or breaches)[0]
            return self._record(GatewayDecision(
                action=Action.BLOCK, arguments=None, reason=first.describe(),
                data_types=data_types, violations=violations,
                tool=tool, recipient=recipient, purpose=purpose,
            ))

        offending = {d.data_type for d in breaches}
        return self._record(GatewayDecision(
            action=Action.REDACT,
            arguments=self._redact(arguments, offending),
            reason=(
                f"{len(breaches)} flow(s) not permitted; "
                f"{', '.join(sorted(offending))} removed before emission"
            ),
            data_types=data_types, violations=violations,
            tool=tool, recipient=recipient, purpose=purpose,
        ))

    # ------------------------------------------------------------------
    def _redact(self, value: Any, data_types: set[str]) -> Any:
        """Remove only the types whose flow was refused.

        A gateway that strips everything it can find would take the customer's
        order number out with the diagnosis, and the tool call would fail for a
        reason nobody could see. Only the offending types go.
        """
        if isinstance(value, str):
            out = value
            for start, end, matched, data_type in reversed(self.sanitizer._spans(value)):  # noqa: SLF001
                if data_type.lower() in data_types:
                    from .sanitizer import _redact_value  # noqa: PLC0415

                    out = out[:start] + _redact_value(matched, data_type, self.sanitizer.style) + out[end:]
            return out
        if isinstance(value, dict):
            return {k: self._redact(v, data_types) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(item, data_types) for item in value]
        if isinstance(value, tuple):
            return tuple(self._redact(item, data_types) for item in value)
        return value

    def _record(self, decision: GatewayDecision) -> GatewayDecision:
        if self.log is not None:
            self.log.append(
                action=decision.action,
                tool=decision.tool,
                recipient=decision.recipient,
                purpose=decision.purpose,
                data_types=decision.data_types,
                reason=decision.reason,
                run_id=self.run_id,
                agent=self.agent,
                metadata={"violations": len(decision.violations)},
            )
        return decision

    # ------------------------------------------------------------------
    def check_json(self, payload: str, **kwargs: Any) -> GatewayDecision:
        """Convenience for callers holding a JSON string of arguments."""
        try:
            arguments = json.loads(payload)
        except json.JSONDecodeError:
            arguments = payload
        return self.check(arguments, **kwargs)
