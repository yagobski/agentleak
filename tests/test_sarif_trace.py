# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak run --format sarif``: trace findings as SARIF 2.1.0.

The official SARIF 2.1.0 JSON schema (OASIS) is not vendored: its licence
terms are OASIS's own, not an OSI licence. These tests instead check the
structural requirements of the SARIF 2.1.0 specification that AgentLeak's
output relies on, plus what GitHub code scanning needs (a physical location,
``security-severity`` on rules). ``SARIF_SUBSET`` is written for this test from
the specification's text; it is validated with jsonschema when available and
by plain assertions always.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentleak import AgentLeakRunner
from agentleak.cli import app
from agentleak.interop.sarif import rule_id, to_sarif
from agentleak.scenarios import load_example_trace

SARIF_SUBSET = {
    "type": "object",
    "required": ["version", "runs"],
    "properties": {
        "version": {"const": "2.1.0"},
        "$schema": {"type": "string"},
        "runs": {"type": "array", "minItems": 1, "items": {
            "type": "object",
            "required": ["tool"],
            "properties": {
                "tool": {"type": "object", "required": ["driver"], "properties": {
                    "driver": {"type": "object", "required": ["name"], "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "rules": {"type": "array", "items": {
                            "type": "object", "required": ["id"],
                            "properties": {
                                "id": {"type": "string", "minLength": 1},
                                "defaultConfiguration": {"type": "object", "properties": {
                                    "level": {"enum": ["none", "note", "warning", "error"]}}},
                                "properties": {"type": "object", "properties": {
                                    "security-severity": {"type": "string",
                                                          "pattern": r"^\d+(\.\d+)?$"}}},
                            }}},
                    }},
                }},
                "results": {"type": "array", "maxItems": 25000, "items": {
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "ruleId": {"type": "string"},
                        "ruleIndex": {"type": "integer", "minimum": 0},
                        "level": {"enum": ["none", "note", "warning", "error"]},
                        "message": {"type": "object", "required": ["text"],
                                    "properties": {"text": {"type": "string", "minLength": 1}}},
                        "partialFingerprints": {"type": "object",
                                                "additionalProperties": {"type": "string"}},
                        "locations": {"type": "array", "items": {"type": "object", "properties": {
                            "physicalLocation": {"type": "object", "required": ["artifactLocation"],
                                                 "properties": {
                                "artifactLocation": {"type": "object", "required": ["uri"],
                                                     "properties": {"uri": {"type": "string"}}},
                                "region": {"type": "object", "properties": {
                                    "startLine": {"type": "integer", "minimum": 1}}}}},
                            "logicalLocations": {"type": "array", "items": {"type": "object"}},
                        }}},
                    },
                }},
            },
        }},
    },
}


def _check(log: dict) -> None:
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - installed with the mcp extra
        pass
    else:
        jsonschema.validate(log, SARIF_SUBSET)
    assert log["version"] == "2.1.0"
    for run in log["runs"]:
        rules = run["tool"]["driver"]["rules"]
        ids = [r["id"] for r in rules]
        assert len(ids) == len(set(ids))
        for result in run["results"]:
            assert result["ruleId"] == rules[result["ruleIndex"]]["id"]
            assert result["message"]["text"]


@pytest.fixture()
def leaky_report():
    return AgentLeakRunner().analyze(load_example_trace("healthcare_patient_summary"))


def test_trace_sarif_structure_and_rules(leaky_report):
    report = leaky_report.to_dict()
    log = to_sarif(report)
    _check(log)
    run = log["runs"][0]
    assert len(run["results"]) == len(report["findings"])
    for result, finding in zip(run["results"], report["findings"], strict=True):
        assert result["ruleId"] == rule_id(finding["data_type"])
        assert result["properties"]["channel"] == finding["channel"]
        assert result["properties"]["privacyLevel"] == f"L{finding['level']}"
        assert result["level"] == {4: "error", 3: "error", 2: "warning", 1: "note"}[finding["level"]]
        logical = result["locations"][0]["logicalLocations"][0]
        assert logical["name"] == finding["event_id"]
    assert run["properties"]["verdict"] == report["verdict"]


def test_trace_sarif_never_carries_values(leaky_report):
    report = leaky_report.to_dict()
    text = json.dumps(to_sarif(report))
    for finding in leaky_report.findings:
        assert finding.matched_value not in text
    for finding in report["findings"]:
        if finding.get("redacted_value"):
            assert finding["redacted_value"] not in text


def test_rule_ids_are_stable_and_safe():
    assert rule_id("ssn") == "agentleak/trace/ssn"
    assert rule_id("Health Identifier") == "agentleak/trace/health_identifier"
    assert rule_id("../x\n::warning::y") == "agentleak/trace/.._x_warning_y"


def test_run_format_sarif_points_at_the_event_line(tmp_path):
    trace = load_example_trace("healthcare_patient_summary")
    path = tmp_path / "t.json"
    path.write_text(json.dumps(trace.to_dict(), indent=2))
    out = tmp_path / "r"
    result = CliRunner().invoke(app, ["run", "--trace", str(path), "-o", str(out),
                                      "-f", "json,sarif", "-q"])
    assert result.exit_code in (0, 1), result.output
    (sarif_file,) = out.glob("*.sarif")
    log = json.loads(sarif_file.read_text())
    _check(log)
    lines = path.read_text().splitlines()
    for res in log["runs"][0]["results"]:
        physical = res["locations"][0]["physicalLocation"]
        line = lines[physical["region"]["startLine"] - 1]
        assert f'"event_id": "{res["properties"]["eventId"]}"' in line
        assert physical["artifactLocation"]["uri"].endswith("t.json")


def test_sarif_carries_the_observation_of_an_imported_trace():
    from agentleak.interop import import_file

    fixture = Path(__file__).parent / "fixtures" / "interop" / "garak_0.17.1.report.jsonl"
    trace = next(i.trace for i in import_file(fixture).traces if "Dan" in i.trace.run_id)
    log = to_sarif(AgentLeakRunner().analyze(trace).to_dict())
    _check(log)
    assert log["runs"][0]["properties"]["observation"]["black_box"] is True


def test_report_command_rerenders_sarif(tmp_path, leaky_report):
    report = tmp_path / "run.json"
    report.write_text(json.dumps(leaky_report.to_dict()))
    result = CliRunner().invoke(app, ["report", "-i", str(report), "-f", "sarif"])
    assert result.exit_code == 0, result.output
    _check(json.loads((tmp_path / "run.sarif").read_text()))
