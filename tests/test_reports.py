# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Reporter tests: JSON, Markdown, HTML rendering and redaction."""

from __future__ import annotations

import json

from agentleak import AgentLeakRunner
from agentleak.reporters import normalize_formats, render, write_reports
from agentleak.scenarios import load_example_trace


def _result():
    return AgentLeakRunner().analyze(load_example_trace("healthcare_patient_summary"))


def test_normalize_formats_aliases():
    assert normalize_formats(["md", "JSON", "html"]) == ["markdown", "json", "html"]


def test_normalize_formats_rejects_unknown():
    import pytest
    with pytest.raises(ValueError):
        normalize_formats(["pdf"])


def test_json_report_is_valid_and_redacted():
    data = _result().to_dict()
    text = render(data, "json")
    parsed = json.loads(text)
    assert parsed["scoring"] == "agentrisk"
    assert parsed["verdict"] in {"High risk", "Fail"}
    assert 0.0 <= parsed["risk_index"] <= 1.0
    assert "agentrisk" in parsed and "ri_global" in parsed["agentrisk"]
    # No raw NAM anywhere in the serialized report.
    assert "TREM12345678" not in text
    assert any(f["redacted_value"] == "TR********78" for f in parsed["findings"])


def test_remediation_hints_structure():
    result = _result()
    hints = result.remediation_hints()
    assert hints, "a leaky scenario must yield remediation hints"
    for h in hints:
        assert set(h) >= {"channel", "data_types", "priority", "advice", "code_fix"}
        assert h["priority"] in {"critical", "high", "medium"}
        assert isinstance(h["data_types"], list) and h["data_types"]
        assert str(h["code_fix"]).strip()
    # each channel appears at most once
    channels = [h["channel"] for h in hints]
    assert len(channels) == len(set(channels))


def test_remediation_hints_in_serialized_report():
    parsed = json.loads(render(_result().to_dict(), "json"))
    assert "remediation_hints" in parsed
    assert parsed["remediation_hints"] == _result().remediation_hints()


def test_markdown_has_sections():
    md = render(_result().to_dict(), "markdown")
    assert "# AgentLeak Privacy Report" in md
    assert "## Risk by channel" in md
    assert "## Findings" in md
    assert "TREM12345678" not in md


def test_html_is_self_contained():
    html = render(_result().to_dict(), "html")
    assert "<!DOCTYPE html>" in html
    assert "AgentLeak" in html
    assert "Risk Index" in html
    assert _result().verdict in html
    # No external/CDN resources.
    assert "http://" not in html
    assert "https://" not in html
    assert "TREM12345678" not in html


def test_html_shows_key_insight():
    html = render(_result().to_dict(), "html")
    assert "Key insight" in html


def test_write_reports_creates_files(tmp_path):
    written = write_reports(_result(), str(tmp_path), ["json", "html", "markdown"], basename="r")
    assert set(written) == {"json", "html", "markdown"}
    assert (tmp_path / "r.json").exists()
    assert (tmp_path / "r.html").exists()
    assert (tmp_path / "r.md").exists()


def test_clean_report_has_no_insight_and_pass(tmp_path):
    from agentleak import Trace
    trace = Trace(run_id="clean")
    trace.add_event("final_output", "All good, nothing sensitive here.")
    data = AgentLeakRunner().analyze(trace).to_dict()
    html = render(data, "html")
    assert "Key insight" not in html
    md = render(data, "markdown")
    assert "No leaks detected" in md
