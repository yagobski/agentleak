"""Defenses package: sanitizers, internal-channel guards, and guardrail wrappers."""

from .sanitizer import Sanitizer, RedactionStyle, sanitize_text
from .internal_channel import InternalChannelGuard, ClearanceLevel, AgentProfile

__all__ = [
    "Sanitizer",
    "RedactionStyle",
    "sanitize_text",
    "InternalChannelGuard",
    "ClearanceLevel",
    "AgentProfile",
]
