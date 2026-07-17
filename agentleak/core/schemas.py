"""Machine-readable JSON Schemas for every public AgentLeak document."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config import Config, PrivacyPolicyConfig
from .trace import Event, Trace

SCHEMA_VERSION = "2026.07"

_FINDING_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentLeak Finding",
    "type": "object",
    "required": [
        "finding_id", "run_id", "event_id", "channel", "data_type",
        "severity", "level", "confidence", "redacted_value", "detector",
    ],
    "properties": {
        "finding_id": {"type": "string"},
        "run_id": {"type": "string"},
        "event_id": {"type": "string"},
        "channel": {"type": "string"},
        "data_type": {"type": "string"},
        "severity": {"enum": ["low", "medium", "high", "critical"]},
        "level": {"type": "integer", "minimum": 1, "maximum": 4},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "redacted_value": {"type": "string"},
        "matched_value": {
            "type": "string",
            "description": "Present only when privacy.redact_values is false.",
        },
        "detector": {"type": "string"},
        "recommendation": {"type": "string"},
        "source": {"type": "string"},
        "target": {"type": "string"},
    },
    "additionalProperties": True,
}

_POLICY_EVALUATION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentLeak Privacy Policy Evaluation",
    "type": "object",
    "required": ["enabled", "passed", "assertions_checked", "violations"],
    "properties": {
        "enabled": {"type": "boolean"},
        "passed": {"type": "boolean"},
        "assertions_checked": {"type": "array", "items": {"type": "string"}},
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule", "message", "count", "finding_ids"],
                "properties": {
                    "rule": {"type": "string"},
                    "message": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                    "finding_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

_REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentLeak Analysis Report",
    "type": "object",
    "required": [
        "report", "version", "run_id", "agent_name", "privacy_score",
        "risk_index", "blocked", "summary", "findings", "privacy_policy",
    ],
    "properties": {
        "report": {"const": "agentleak"},
        "version": {"type": "integer", "minimum": 2},
        "run_id": {"type": "string"},
        "agent_name": {"type": "string"},
        "scenario_id": {"type": ["string", "null"]},
        "privacy_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "risk_index": {"type": "number", "minimum": 0, "maximum": 1},
        "wsl": {"type": "integer", "minimum": 0},
        "rho_s": {"type": "integer", "minimum": 0},
        "blocked": {"type": "boolean"},
        "summary": {"type": "object"},
        "channel_risks": {"type": "array", "items": {"type": "object"}},
        "findings": {"type": "array", "items": _FINDING_SCHEMA},
        "privacy_policy": _POLICY_EVALUATION_SCHEMA,
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "remediation_hints": {"type": "array", "items": {"type": "object"}},
        "compliance": {"type": "object"},
        "flow": {"type": "object"},
        "leak_paths": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": True,
}

_REDTEAM_REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentLeak Red Team Request",
    "type": "object",
    "properties": {
        "vertical": {
            "enum": ["healthcare", "finance", "legal", "hr", "customer_support"],
            "default": "healthcare",
        },
        "n": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        "adversary_level": {"enum": ["A0", "A1", "A2"], "default": "A1"},
        "attack_class": {"type": "string", "pattern": "^F[1-6]\\.[0-9]+$"},
        "plugins": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
        "plugin_preset": {
            "enum": ["privacy_core", "agent_core", "tool_security", "complete"],
            "default": "agent_core",
        },
        "strategies": {"type": "array", "items": {"type": "string"}},
        "strategy_profile": {
            "enum": ["baseline", "balanced", "evasion", "complete"],
            "default": "balanced",
        },
        "mode": {"enum": ["auto", "live", "scripted"], "default": "auto"},
        "base_url": {"type": "string", "format": "uri"},
        "model": {"type": "string"},
        "api_key": {"type": "string", "writeOnly": True},
    },
    "additionalProperties": False,
}

_CODE_SCAN_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentLeak Code Scan Result",
    "type": "object",
    "required": ["scan", "version", "source_type", "score", "verdict", "summary", "findings"],
    "properties": {
        "scan": {"const": "agentleak-code"},
        "version": {"type": "integer", "minimum": 2},
        "source_type": {"enum": ["files", "github", "zip"]},
        "source_ref": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "verdict": {"enum": ["Pass", "Conditional pass", "High risk", "Fail"]},
        "summary": {"type": "object"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["file", "line", "rule", "data_type", "severity", "level"],
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},
                    "rule": {"type": "string"},
                    "data_type": {"type": "string"},
                    "severity": {"enum": ["low", "medium", "high", "critical"]},
                    "level": {"type": "integer", "minimum": 1, "maximum": 4},
                    "snippet": {"type": "string"},
                    "recommendation": {"type": "string"},
                    "tier": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    },
}

_AGENT_CARD_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentLeak Agent Card",
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "capabilities": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "examples": {"type": "array", "items": {"type": "string"}},
        "input_mode": {"type": "string"},
        "output_mode": {"type": "string"},
        "agent_protocol_version": {"type": "string"},
        "endpoints": {"type": "object", "additionalProperties": {"type": "string"}},
        "source": {"type": "object"},
        "privacy": {"type": "object"},
    },
    "additionalProperties": True,
}

_SCHEMAS: dict[str, tuple[str, dict[str, Any]]] = {
    "config": ("agentleak.yaml configuration", Config.model_json_schema()),
    "trace": ("Normalized agent execution trace", Trace.model_json_schema()),
    "event": ("One normalized trace event", Event.model_json_schema()),
    "finding": ("One runtime privacy finding", _FINDING_SCHEMA),
    "analysis-report": ("Complete runtime analysis report", _REPORT_SCHEMA),
    "privacy-policy": ("Declarative privacy policy configuration", PrivacyPolicyConfig.model_json_schema()),
    "privacy-policy-evaluation": ("Result of policy assertions", _POLICY_EVALUATION_SCHEMA),
    "redteam-request": ("Red-team campaign request body", _REDTEAM_REQUEST_SCHEMA),
    "code-scan": ("Static code scan result", _CODE_SCAN_SCHEMA),
    "agent-card": ("Agent identity, source, and privacy declaration", _AGENT_CARD_SCHEMA),
}


def schema_catalog(base_path: str = "/api/schemas") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "json_schema_draft": "https://json-schema.org/draft/2020-12/schema",
        "schemas": [
            {"name": name, "description": description, "url": f"{base_path}/{name}"}
            for name, (description, _schema) in _SCHEMAS.items()
        ],
    }


def get_schema(name: str) -> dict[str, Any]:
    try:
        schema = deepcopy(_SCHEMAS[name][1])
    except KeyError as exc:
        raise KeyError(f"Unknown AgentLeak schema: {name}") from exc
    schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    schema["x-agentleak-schema-version"] = SCHEMA_VERSION
    return schema
