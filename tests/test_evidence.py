# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The chain has to break when somebody edits it, and say where.

A report generated on request cannot answer "did this agent stay inside its
bounds over the lifetime of the system", because it is generated on request —
nothing stops it being generated differently tomorrow. The evidence log is the
other kind of artefact: written as things happen, and chained so that changing
any earlier entry invalidates every hash after it.

That is tamper-*evident*, not tamper-*proof*: anyone who can write the file can
rewrite the whole chain. It is still the property an auditor needs and the one a
plain log does not have, and these tests pin the three ways a record gets
quietly improved after the fact — edited, deleted, reordered.
"""

from __future__ import annotations

import json

from agentleak.core.evidence import GENESIS, EvidenceLog, chain_hash, verify


def _log_with(tmp_path, actions=("allow", "block", "redact", "allow")):
    log = EvidenceLog(tmp_path / "evidence.jsonl")
    for index, action in enumerate(actions):
        log.append(
            action=action,
            tool=f"tool_{index}",
            recipient="vendor",
            data_types=["sin"],
            reason=f"decision {index}",
        )
    return log


# ----------------------------------------------------------------------
def test_an_intact_chain_verifies(tmp_path) -> None:
    log = _log_with(tmp_path)
    result = log.verify()
    assert result.ok
    assert result.entries == 4


def test_the_first_entry_starts_from_genesis(tmp_path) -> None:
    log = _log_with(tmp_path, ("allow",))
    assert log.entries()[0].previous == GENESIS


def test_each_entry_carries_the_hash_of_the_one_before(tmp_path) -> None:
    log = _log_with(tmp_path)
    entries = log.entries()
    # strict=False: the pairing is deliberately offset by one, so the shorter
    # tail is the point rather than a mismatch.
    for earlier, later in zip(entries, entries[1:], strict=False):
        assert later.previous == chain_hash(earlier.payload())


# ----------------------------------------------------------------------
# The three ways a record gets quietly improved
# ----------------------------------------------------------------------
def test_editing_an_entry_is_detected(tmp_path) -> None:
    """"It was allowed, honestly." """
    log = _log_with(tmp_path)
    lines = log.path.read_text().splitlines()
    record = json.loads(lines[1])
    record["action"] = "allow"
    lines[1] = json.dumps(record)
    edited = tmp_path / "edited.jsonl"
    edited.write_text("\n".join(lines) + "\n")

    result = verify(edited)
    assert not result.ok
    assert result.broken_at == 2
    assert "was modified" in result.detail


def test_removing_an_entry_is_detected(tmp_path) -> None:
    """"That call never happened." """
    log = _log_with(tmp_path)
    lines = log.path.read_text().splitlines()
    del lines[1]
    removed = tmp_path / "removed.jsonl"
    removed.write_text("\n".join(lines) + "\n")

    result = verify(removed)
    assert not result.ok
    assert "removed or reordered" in result.detail


def test_reordering_entries_is_detected(tmp_path) -> None:
    log = _log_with(tmp_path)
    lines = log.path.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    reordered = tmp_path / "reordered.jsonl"
    reordered.write_text("\n".join(lines) + "\n")

    assert not verify(reordered).ok


def test_the_failure_says_which_entry_broke(tmp_path) -> None:
    """An auditor needs the line, not a boolean."""
    log = _log_with(tmp_path)
    lines = log.path.read_text().splitlines()
    record = json.loads(lines[2])
    record["recipient"] = "somewhere-else"
    lines[2] = json.dumps(record)
    edited = tmp_path / "edited.jsonl"
    edited.write_text("\n".join(lines) + "\n")

    result = verify(edited)
    assert result.broken_at == 3
    assert "entry 2" in result.detail


# ----------------------------------------------------------------------
# Operational behaviour
# ----------------------------------------------------------------------
def test_a_restart_continues_the_chain(tmp_path) -> None:
    """A gateway that restarts must not fork its own history."""
    _log_with(tmp_path)
    resumed = EvidenceLog(tmp_path / "evidence.jsonl")
    resumed.append(action="allow", tool="after-restart")
    result = verify(tmp_path / "evidence.jsonl")
    assert result.ok
    assert result.entries == 5


def test_a_truncated_last_line_does_not_forge_the_rest(tmp_path) -> None:
    """A crash mid-write is not a forgery; reading stops rather than guessing."""
    log = _log_with(tmp_path)
    text = log.path.read_text()
    truncated = tmp_path / "truncated.jsonl"
    truncated.write_text(text[: -len(text.splitlines()[-1]) // 2])
    entries = EvidenceLog(truncated).entries()
    assert len(entries) == 3


def test_a_missing_log_is_reported_not_treated_as_clean(tmp_path) -> None:
    result = verify(tmp_path / "nothing-here.jsonl")
    assert not result.ok
    assert "no evidence log" in result.detail


def test_the_summary_counts_actions_and_types(tmp_path) -> None:
    log = _log_with(tmp_path)
    summary = log.summary()
    assert summary["entries"] == 4
    assert summary["by_action"] == {"allow": 2, "block": 1, "redact": 1}
    assert summary["by_data_type"] == {"sin": 4}
    assert summary["verified"] is True


def test_the_hash_ignores_key_order(tmp_path) -> None:
    """Otherwise a re-serialisation somewhere would look like tampering."""
    payload = {"b": 2, "a": 1}
    assert chain_hash(payload) == chain_hash({"a": 1, "b": 2})
