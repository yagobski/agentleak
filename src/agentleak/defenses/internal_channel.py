# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Internal-channel guard — protects inter_agent_message and shared_memory.

The reference paper (IEEE benchmark) found that internal channels (C2, C5)
leak ~2.6× more than the external channel (C1 final_output). Output-only audits
miss 45.9% of violations. This guard enforces *clearance levels* on internal
channel content before it leaves an agent boundary.

Model::

    AgentProfile
    ├── clearance_level: ClearanceLevel   (what level data this agent can handle)
    └── allowed_channels: set[str]        (which channels this agent may write to)

    InternalChannelGuard
    ├── sender_profile: AgentProfile
    ├── recipient_profile: AgentProfile
    └── sanitizer: Sanitizer             (applied when data exceeds recipient clearance)

Decision outcome:
    ALLOW  — data level ≤ recipient clearance; pass through unchanged.
    WARN   — data level slightly above; attach warning but allow.
    REDACT — data level > recipient clearance; sanitize before forwarding.
    BLOCK  — data level critical AND recipient has no clearance; drop message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from .sanitizer import RedactionStyle, Sanitizer


class ClearanceLevel(IntEnum):
    """Data sensitivity clearance levels, aligned with AgentRisk L1–L4."""

    PUBLIC = 1        # L1: public/organizational (person_name, org_id)
    INTERNAL = 2      # L2: behavioral/contact (email, phone, client_id)
    CONFIDENTIAL = 3  # L3: financial/legal/employment (salary, income, DOB)
    SECRET = 4        # L4: special category + credentials (health, SSN, API keys)


class GuardDecision(str):
    ALLOW = "allow"
    WARN = "warn"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class AgentProfile:
    """Represents an agent's identity and data-handling permissions."""

    name: str
    clearance: ClearanceLevel = ClearanceLevel.INTERNAL
    allowed_channels: set[str] = field(default_factory=lambda: {
        "final_output", "tool_call", "user_input",
    })

    def can_write_to(self, channel: str) -> bool:
        return channel in self.allowed_channels or not self.allowed_channels


@dataclass
class GuardResult:
    """Outcome of a guard check."""

    decision: str       # GuardDecision
    channel: str
    data_level: int     # estimated level of the content (1-4)
    original_text: str
    sanitized_text: str
    reason: str = ""

    @property
    def was_modified(self) -> bool:
        return self.sanitized_text != self.original_text


class InternalChannelGuard:
    """Enforce clearance-level access control on internal channel content.

    Args:
        sender: :class:`AgentProfile` for the sending agent.
        recipient: :class:`AgentProfile` for the receiving agent.
        sanitizer: :class:`~agentleak.defenses.sanitizer.Sanitizer` applied on
            REDACT decisions (default: placeholder style).
        block_on_secret: When *True*, SECRET-level data sent to a recipient with
            clearance < SECRET is BLOCKed rather than REDACTed.
    """

    INTERNAL_CHANNELS = frozenset(["inter_agent_message", "shared_memory"])

    def __init__(
        self,
        sender: AgentProfile | None = None,
        recipient: AgentProfile | None = None,
        *,
        sanitizer: Sanitizer | None = None,
        block_on_secret: bool = False,
    ) -> None:
        self.sender = sender or AgentProfile("default_sender")
        self.recipient = recipient or AgentProfile("default_recipient")
        self.sanitizer = sanitizer or Sanitizer(style=RedactionStyle.PLACEHOLDER)
        self.block_on_secret = block_on_secret

    def check(
        self,
        text: str,
        channel: str,
        *,
        data_level: int | None = None,
    ) -> GuardResult:
        """Evaluate whether *text* may transit *channel*.

        Args:
            text: Content to be sent over the channel.
            channel: Channel identifier (e.g. ``"inter_agent_message"``).
            data_level: Explicit AgentRisk level (1–4) of the content.
                When *None* the guard estimates level from the content via its
                internal sanitizer (count of redactable tokens as a proxy).
        """
        if data_level is None:
            data_level = self._estimate_level(text)

        # Non-internal channels: always ALLOW (not our concern here)
        if channel not in self.INTERNAL_CHANNELS:
            return GuardResult(
                decision=GuardDecision.ALLOW,
                channel=channel,
                data_level=data_level,
                original_text=text,
                sanitized_text=text,
                reason="Not an internal channel.",
            )

        recipient_clearance = int(self.recipient.clearance)

        if data_level <= recipient_clearance:
            return GuardResult(
                decision=GuardDecision.ALLOW,
                channel=channel,
                data_level=data_level,
                original_text=text,
                sanitized_text=text,
                reason=f"Data level L{data_level} ≤ recipient clearance L{recipient_clearance}.",
            )

        if data_level == 4 and self.block_on_secret:
            return GuardResult(
                decision=GuardDecision.BLOCK,
                channel=channel,
                data_level=data_level,
                original_text=text,
                sanitized_text="",
                reason=(
                    f"SECRET-level data (L4) blocked: recipient clearance is "
                    f"L{recipient_clearance}."
                ),
            )

        # REDACT: sanitize and allow
        clean = self.sanitizer.sanitize(text)
        if data_level == 4:
            decision = GuardDecision.REDACT
        else:
            decision = GuardDecision.WARN if data_level == recipient_clearance + 1 else GuardDecision.REDACT

        return GuardResult(
            decision=decision,
            channel=channel,
            data_level=data_level,
            original_text=text,
            sanitized_text=clean,
            reason=(
                f"Data level L{data_level} > recipient clearance L{recipient_clearance}. "
                f"Content sanitized with {self.sanitizer.style.value} style."
            ),
        )

    def _estimate_level(self, text: str) -> int:
        """Estimate the sensitivity level of *text* from redaction-token count."""
        count = self.sanitizer.redaction_count(text)
        if count == 0:
            return 1
        if count == 1:
            return 2
        if count <= 3:
            return 3
        return 4

    def filter_dict(
        self, data: dict[str, Any], channel: str
    ) -> tuple[dict[str, Any], GuardResult]:
        """Guard a structured dict payload; return (filtered_dict, result)."""
        import json
        text = json.dumps(data)
        result = self.check(text, channel)
        if result.decision in (GuardDecision.REDACT, GuardDecision.WARN):
            filtered = self.sanitizer.sanitize_dict(data)
            return filtered, result
        if result.decision == GuardDecision.BLOCK:
            return {}, result
        return data, result
