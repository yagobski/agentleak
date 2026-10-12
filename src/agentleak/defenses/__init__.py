# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Defenses package: sanitizers, internal-channel guards, and guardrail wrappers."""

from .gateway import Action, Gateway, GatewayDecision
from .internal_channel import AgentProfile, ClearanceLevel, InternalChannelGuard
from .sanitizer import RedactionStyle, Sanitizer, sanitize_text

__all__ = [
    "Gateway",
    "GatewayDecision",
    "Action",
    "Sanitizer",
    "RedactionStyle",
    "sanitize_text",
    "InternalChannelGuard",
    "ClearanceLevel",
    "AgentProfile",
]
