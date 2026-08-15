# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The MCP surface, and the memory that makes it worth calling twice.

The load-bearing test here is the first one. If a finding's identity moves when
the code around it moves, every reformat reports the whole file as new, an agent
learns to ignore the delta, and the feature is worse than not having shipped it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentleak.core.memory import ProjectMemory, finding_id
from agentleak.mcp_server import (
    MCP_MISSING,
    TOOLS,
    check_trace,
    preflight,
    redact,
    scan_code,
)

LEAKY = 'API_KEY = "sk-proj-abcd1234efgh5678ijkl9012mnop3456"\n'


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "agent.py").write_text(LEAKY, encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ identity
def test_a_finding_keeps_its_identity_when_the_code_moves(project: Path) -> None:
    """The whole delta feature rests on this.

    Adding imports above a secret shifts its line. If that reads as a new
    finding, the tool cries wolf on every commit and gets muted.
    """
    first = preflight(str(project))
    assert first["since_last"]["is_first_run"] is True
    original = first["findings"][0]["id"]

    (project / "agent.py").write_text("import os\nimport sys\n\n" + LEAKY, encoding="utf-8")
    second = preflight(str(project))

    moved = second["findings"][0]
    assert moved["id"] == original, "the same secret got a new identity after moving"
    assert moved["line"] != first["findings"][0]["line"], "the fixture did not actually move it"
    assert second["since_last"]["new"] == []
    assert second["since_last"]["fixed"] == []
    assert second["since_last"]["unchanged"] == len(first["findings"])


def test_identity_separates_different_secrets_in_the_same_file() -> None:
    a = finding_id("agent.py", "hardcoded_secret", 'KEY = "aa**bb"')
    b = finding_id("agent.py", "hardcoded_secret", 'KEY = "cc**dd"')
    assert a != b


def test_identity_separates_the_same_secret_in_different_files() -> None:
    snippet = 'KEY = "aa**bb"'
    assert finding_id("a.py", "hardcoded_secret", snippet) != finding_id(
        "b.py", "hardcoded_secret", snippet
    )


# --------------------------------------------------------------------- delta
def test_fixing_a_finding_shows_up_as_fixed(project: Path) -> None:
    preflight(str(project))
    (project / "agent.py").write_text('API_KEY = os.environ["API_KEY"]\n', encoding="utf-8")

    after = preflight(str(project))
    # Removing the literal clears every rule that fired on it, not just one.
    assert len(after["since_last"]["fixed"]) >= 1
    assert after["since_last"]["new"] == []
    assert "fixed since last check" in after["summary"]


def test_a_newly_introduced_secret_is_reported_as_new(project: Path) -> None:
    preflight(str(project))
    (project / "other.py").write_text('TOKEN = "ghp_aaaabbbbccccddddeeeeffff0000111122"\n', encoding="utf-8")

    after = preflight(str(project))
    new_files = {f["file"] for f in after["since_last"]["new"]}
    assert any("other.py" in f for f in new_files)
    assert after["since_last"]["unchanged"] >= 1


def test_next_steps_lead_with_the_new_critical_finding(project: Path) -> None:
    preflight(str(project))
    (project / "worse.py").write_text('AWS = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

    steps = preflight(str(project))["next_steps"]
    assert steps and steps[0].startswith("New L")


# -------------------------------------------------------------------- memory
def test_history_is_local_to_the_project(project: Path) -> None:
    preflight(str(project))
    assert (project / ".agentleak" / "history.jsonl").is_file()


def test_history_never_stores_a_raw_secret(project: Path) -> None:
    preflight(str(project))
    written = (project / ".agentleak" / "history.jsonl").read_text(encoding="utf-8")
    assert "sk-proj-abcd1234efgh5678ijkl9012mnop3456" not in written


def test_a_corrupt_history_does_not_stop_the_check(project: Path) -> None:
    """A convenience file must never be able to block a scan."""
    preflight(str(project))
    history = project / ".agentleak" / "history.jsonl"
    history.write_text("this is not json\n", encoding="utf-8")

    result = preflight(str(project))
    assert result["verdict"] in {"Fail", "Needs attention"}
    assert result["since_last"]["is_first_run"] is True


def test_memory_keeps_the_file_bounded(tmp_path: Path) -> None:
    memory = ProjectMemory(tmp_path)
    for index in range(60):
        memory.record([{"id": f"f{index}"}])
    assert len(memory.entries()) == 50


# --------------------------------------------------------------------- tools
def test_preflight_reports_which_tiers_ran(project: Path) -> None:
    """A clean result from regex alone is a weaker claim, and must say so."""
    detection = preflight(str(project))["detection"]
    assert "regex" in detection["tiers"]
    assert "presidio" not in detection["tiers"], "the standard tier was not installed"
    assert detection["degraded"] is False


def test_preflight_on_a_missing_path_returns_an_error_not_a_crash() -> None:
    assert "error" in preflight("/nope/does/not/exist")


def test_preflight_scores_a_trace_alongside_the_code(project: Path) -> None:
    trace = {
        "run_id": "r1",
        "agent_name": "test",
        "events": [
            {"channel": "tool_response", "source": "crm", "target": "agent",
             "content": {"sin": "123-456-789"}},
            {"channel": "tool_call", "source": "agent", "target": "calendar",
             "content": {"sin": "123-456-789"}},
            {"channel": "final_output", "source": "agent", "target": "user",
             "content": "Done."},
        ],
    }
    result = preflight(str(project), trace=trace)
    assert result["privacy_score"] is not None
    assert result["risk_index"] is not None


def test_an_unreadable_trace_does_not_lose_the_code_scan(project: Path) -> None:
    result = preflight(str(project), trace={"not": "a trace"})
    assert result["code_score"] < 100, "the scan result was thrown away"
    assert any(f["rule"] == "unreadable_trace" for f in result["findings"])


def test_scan_code_finds_the_planted_key(project: Path) -> None:
    result = scan_code(str(project))
    assert result["score"] < 100
    assert result["findings"]


def test_check_trace_rejects_nonsense_politely() -> None:
    assert "error" in check_trace({"not": "a trace"})


def test_redact_removes_the_value() -> None:
    result = redact("my ssn is 123-45-6789")
    assert "123-45-6789" not in result["text"]
    assert result["changed"] is True


def test_redact_reports_an_unknown_style_rather_than_raising() -> None:
    assert "error" in redact("anything", style="not-a-style")


# ------------------------------------------------------------------ contract
def test_every_tool_is_callable_and_described() -> None:
    """The description is the only prompt the agent ever sees."""
    for tool in TOOLS:
        assert callable(tool["fn"])
        assert len(tool["description"]) > 60, f"{tool['name']}: description too thin to act on"


def test_the_tool_names_are_the_ones_the_docs_promise() -> None:
    assert {t["name"] for t in TOOLS} == {
        "privacy_preflight",
        "privacy_scan_code",
        "privacy_check_trace",
        "privacy_redact",
    }


def test_a_missing_extra_names_the_install_command() -> None:
    assert "pip install 'agentleak[mcp]'" in MCP_MISSING


def test_results_survive_json_round_trip(project: Path) -> None:
    """Everything crossing MCP is serialized; a stray dataclass would break it."""
    for payload in (preflight(str(project)), scan_code(str(project)), redact("x")):
        json.loads(json.dumps(payload))
