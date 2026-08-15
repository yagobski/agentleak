# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Scenario model.

A scenario is a named, domain-specific privacy test: a description, the kinds
of sensitive data it involves, the behavior a well-behaved agent should
exhibit, and a bundled synthetic trace that demonstrates the failure mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Scenario:
    id: str
    domain: str
    description: str
    sensitive_data: list[str] = field(default_factory=list)
    expected_behavior: list[str] = field(default_factory=list)
    # Filename (under the packaged ``examples/`` directory) of a trace that
    # demonstrates this scenario.
    example_trace: str | None = None
    # Whether the bundled trace is expected to leak sensitive data on a
    # disclosure channel ("leak") or to keep every disclosure channel clean
    # while still carrying the sensitive record on baseline channels
    # ("clean"). Clean scenarios are controls: they prove detectors *do* see
    # the sensitive vault data (on user_input / tool_response) without that
    # data crossing into an internal disclosure channel.
    expected_outcome: str = "leak"
    # Coarse difficulty of spotting the failure (or, for a clean control,
    # of getting the redaction right): "easy" | "medium" | "hard".
    difficulty: str = "medium"
    # Number of distinct agents involved: "single_agent" | "multi_agent".
    topology: str = "multi_agent"
    # Optional references into agentleak.core.attacks.ATTACK_INDEX (e.g.
    # ["F3.1", "F3.5"]) identifying which attack classes this scenario
    # illustrates or defends against. Not every scenario maps cleanly onto
    # the red-team taxonomy, so this may be empty.
    attack_classes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "description": self.description,
            "sensitive_data": list(self.sensitive_data),
            "expected_behavior": list(self.expected_behavior),
            "example_trace": self.example_trace,
            "expected_outcome": self.expected_outcome,
            "difficulty": self.difficulty,
            "topology": self.topology,
            "attack_classes": list(self.attack_classes),
        }
