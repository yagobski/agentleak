# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""JSON Schema of the self-test result document (``schema_version`` 1.x).

Printed by ``agentleak schema selftest-result``. Compatibility rule: within 1.x
fields are only added; a field is never renamed, removed or given a new
meaning. Agents should ignore fields they do not know.
"""

from __future__ import annotations

from typing import Any

_NULLABLE_STR = {"type": ["string", "null"]}
_LEVEL_LABEL = {"type": ["string", "null"], "enum": ["L1", "L2", "L3", "L4", "L?", None]}
_PRIORITY = {"enum": ["critical", "high", "medium", "low"]}

_FIX: dict[str, Any] = {
    "type": ["object", "null"],
    "description": "A concrete change. `apply_defense`: wrap the named boundary with an "
                   "AgentLeak defense; `code_change`: edit the named file and line.",
    "required": ["type"],
    "properties": {
        "type": {"enum": ["apply_defense", "code_change"]},
        "defense": {"type": "string", "description": "Importable path, e.g. agentleak.defenses.Sanitizer"},
        "channel": {"type": "string"},
        "where": {"type": "string"},
        "settings": {"type": "object"},
        "code": {"type": "string", "description": "Python snippet using the real AgentLeak API"},
        "file": _NULLABLE_STR,
        "line": {"type": ["integer", "null"]},
        "rule": _NULLABLE_STR,
        "suggestion": {"type": "string"},
        "docs": {"type": "string"},
        "also_consider": {"type": "string"},
    },
    "additionalProperties": True,
}

SELFTEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/yagobski/agentleak/schemas/selftest-result-1.json",
    "title": "AgentLeak self-test result",
    "description": (
        "Emitted by `agentleak selftest --json`, the privacy_selftest MCP tool and "
        "POST /api/agent/selftest. passed=true means no finding at or above the threshold "
        "from the detection tiers listed in detection.tiers; it is not a certification."
    ),
    "type": "object",
    "required": [
        "schema_version", "kind", "tool", "run_id", "generated_at", "mode", "passed",
        "outcome", "exit_code", "summary", "verdict", "risk_index", "privacy_score",
        "threshold", "channels", "detection", "findings", "next_steps", "delta", "rerun",
        "network", "limitations",
    ],
    "properties": {
        "schema_version": {"type": "string", "pattern": "^1\\.[0-9]+$"},
        "kind": {"const": "agentleak.selftest"},
        "tool": {
            "type": "object", "required": ["name", "version"],
            "properties": {"name": {"const": "agentleak"}, "version": {"type": "string"}},
        },
        "run_id": {"type": "string", "pattern": "^st_[0-9a-f]+$"},
        "generated_at": {"type": "string"},
        "mode": {
            "type": "string",
            "description": "engine | trace | cmd | code | trace+code | cmd+code | http",
        },
        "passed": {"type": "boolean"},
        "outcome": {"enum": ["pass", "fail", "incomplete", "error"]},
        "exit_code": {"enum": [0, 1, 2, 3, 4],
                      "description": "0 pass, 1 fail, 2 usage, 3 incomplete, 4 error"},
        "summary": {"type": "string"},
        "verdict": {"enum": ["Pass", "Conditional pass", "High risk", "Fail", None],
                    "description": "Worst AgentRisk verdict across scored traces; null when no trace was scored."},
        "risk_index": {"type": ["number", "null"], "minimum": 0, "maximum": 1,
                       "description": "Highest AgentRisk RI across scored traces."},
        "privacy_score": {"type": ["integer", "null"], "minimum": 0, "maximum": 100,
                          "description": "Lowest privacy score across scored traces (100 x (1 - RI))."},
        "threshold": {
            "type": "object", "required": ["fail_on"],
            "properties": {"fail_on": {"enum": ["L1", "L2", "L3", "L4"]}},
        },
        "channels": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["channel", "role", "status", "events_observed", "finding_count"],
                "properties": {
                    "channel": {"type": "string"},
                    "role": {"enum": ["disclosure", "source"]},
                    "status": {"enum": ["leak", "clean", "not_observed", "source"]},
                    "events_observed": {"type": "integer", "minimum": 0},
                    "finding_count": {"type": "integer", "minimum": 0},
                    "worst_level": _LEVEL_LABEL,
                    "ri": {"type": "number"},
                },
            },
        },
        "channel_risks": {"type": "array", "description": "Same shape as the analysis report."},
        "detection": {
            "type": "object",
            "required": ["mode", "tiers", "canary", "deterministic_only", "degraded"],
            "properties": {
                "mode": {"type": "string"},
                "tiers": {"type": "array", "items": {"type": "string"}},
                "code_tiers": {"type": "array", "items": {"type": "string"}},
                "canary": {"type": "boolean"},
                "llm_judge": {"type": "boolean"},
                "deterministic_only": {"type": "boolean"},
                "degraded": {"type": "boolean"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["fingerprint", "channel", "level", "level_label", "severity",
                             "data_type", "detector", "tier", "event_index", "redacted_value"],
                "properties": {
                    "fingerprint": {"type": "string", "pattern": "^[0-9a-f]{16}$"},
                    "input": {"type": "string"},
                    "scenario_id": _NULLABLE_STR,
                    "channel": {"type": "string"},
                    "level": {"type": "integer", "minimum": 1, "maximum": 4},
                    "level_label": _LEVEL_LABEL,
                    "severity": {"enum": ["low", "medium", "high", "critical"]},
                    "data_type": {"type": "string"},
                    "detector": {"type": "string"},
                    "tier": {"enum": ["regex", "canary", "presidio", "llm_judge"]},
                    "event_index": {"type": ["integer", "null"], "minimum": 0,
                                    "description": "0-based index into the scored trace's events."},
                    "event_id": _NULLABLE_STR,
                    "redacted_value": {"type": "string"},
                    "matched_value": {"type": "string",
                                      "description": "Only with --show-values."},
                },
            },
        },
        "findings_total": {"type": "integer"},
        "findings_truncated": {"type": "integer"},
        "inputs": {"type": "array"},
        "code_scan": {"type": ["object", "null"]},
        "checks": {
            "type": ["array", "null"],
            "items": {
                "type": "object", "required": ["name", "passed", "detail"],
                "properties": {"name": {"type": "string"}, "passed": {"type": "boolean"},
                               "detail": {"type": "string"}},
            },
        },
        "scenarios": {"type": ["array", "null"]},
        "next_steps": {
            "type": "array",
            "description": "Ordered: act on next_steps[0] first.",
            "items": {
                "type": "object",
                "required": ["kind", "priority", "action"],
                "properties": {
                    "kind": {"enum": ["runtime_leak", "canary_leak", "code_scan", "coverage",
                                      "detection", "incomplete", "strengthen", "next_command",
                                      "rerun", "compliance"]},
                    "priority": _PRIORITY,
                    "channel": _NULLABLE_STR,
                    "data_types": {"type": "array", "items": {"type": ["string", "null"]}},
                    "action": {"type": "string"},
                    "code_fix": {"type": "string",
                                 "description": "Dependency-free snippet, as in /api/agent/improve."},
                    "fix": _FIX,
                    "fingerprints": {"type": "array", "items": {"type": "string"}},
                    "command": {"type": "string"},
                },
            },
        },
        "delta": {
            "type": ["object", "null"],
            "description": "null on the first self-test of this target.",
            "properties": {
                "previous_run_id": _NULLABLE_STR,
                "previous_at": _NULLABLE_STR,
                "previous_passed": {"type": "boolean"},
                "delta_score": {"type": ["integer", "null"]},
                "delta_ri": {"type": ["number", "null"]},
                "direction": {"enum": ["improved", "regressed", "stable"]},
                "new": {"type": "array", "items": {"type": "string"}},
                "fixed": {"type": "array", "items": {"type": "string"}},
                "unchanged": {"type": "integer"},
            },
        },
        "rerun": {
            "type": ["object", "null"],
            "properties": {
                "cli": {"type": "string"},
                "argv": {"type": "array", "items": {"type": "string"}},
                "mcp": {"type": "object"},
                "http": {"type": "object"},
            },
        },
        "network": {
            "type": "object", "required": ["used_by_agentleak"],
            "properties": {"used_by_agentleak": {"type": "boolean"}, "note": {"type": "string"}},
        },
        "limitations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "history": {"type": "object"},
        "environment": {"type": "object"},
    },
    "additionalProperties": True,
}

__all__ = ["SELFTEST_SCHEMA"]
