"""Defenses package: sanitizers, internal-channel guards, and guardrail wrappers."""

from .internal_channel import AgentProfile, ClearanceLevel, InternalChannelGuard
from .sanitizer import RedactionStyle, Sanitizer, sanitize_text

__all__ = [
    "Sanitizer",
    "RedactionStyle",
    "sanitize_text",
    "InternalChannelGuard",
    "ClearanceLevel",
    "AgentProfile",
]
