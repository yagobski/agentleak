# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Machine contracts remain discoverable and versioned."""

from agentleak.core.schemas import get_schema, schema_catalog


def test_schema_catalog_urls_resolve_to_named_documents():
    catalog = schema_catalog()
    assert catalog["schema_version"]
    for entry in catalog["schemas"]:
        assert entry["url"] == f"/api/schemas/{entry['name']}"
        schema = get_schema(entry["name"])
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["x-agentleak-schema-version"] == catalog["schema_version"]


def test_config_schema_exposes_privacy_policy_contract():
    schema = get_schema("config")
    assert "privacy_policy" in schema["properties"]
    policy_ref = schema["properties"]["privacy_policy"]["$ref"]
    assert policy_ref.endswith("/$defs/PrivacyPolicyConfig")
    assert "forbid_channels" in schema["$defs"]["PrivacyPolicyConfig"]["properties"]


def test_report_schema_requires_policy_evaluation():
    schema = get_schema("analysis-report")
    assert "privacy_policy" in schema["required"]
    assert "passed" in schema["properties"]["privacy_policy"]["properties"]
