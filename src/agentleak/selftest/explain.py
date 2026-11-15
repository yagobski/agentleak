# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Explain one finding by fingerprint: why it fired, which rule, how to fix it."""

from __future__ import annotations

from typing import Any

from .fixes import fix_for_channel
from .history import SelftestHistory, trusted_rerun

LEVEL_MEANING: dict[int, str] = {
    4: "L4, special category or credential: health data, national ID (SSN/SIN), card number, IBAN, account number, secret key or token.",
    3: "L3, financial, legal or employment data: income, salary, credit score, home address, date of birth.",
    2: "L2, behavioral or contact data: email address, phone number, IP address, client identifier.",
    1: "L1, public or organizational identifier: person name.",
}

CHANNEL_MEANING: dict[str, str] = {
    "final_output": "the answer shown to the user",
    "tool_call": "arguments the agent sent to a tool, API or command: data leaving the agent",
    "inter_agent_message": "a message or handoff to another agent: an internal channel output-only audits miss",
    "shared_memory": "a write to memory or a scratchpad: the value persists beyond this run",
    "log": "a log line or debug print: logs are kept, shipped and read by more people than the agent's user",
    "generated_file": "a file the agent wrote: it outlives the run and can be shared or committed",
    "source_code": "the agent's own source code (static scan)",
}

DETECTOR_MEANING: dict[str, str] = {
    "canary": "Exact match of a synthetic canary value planted in the scenario's record. Zero false positives: the value cannot appear unless the agent copied it.",
    "pii_detector": "Pattern rule for personal data formats (email, phone, SSN/SIN, dates of birth, addresses), with checksums where a format has one.",
    "secrets_detector": "Pattern rule for credential formats (cloud keys, tokens, private keys, connection strings).",
    "finance_detector": "Pattern rule for financial identifiers (card numbers with Luhn check, IBAN with mod-97 check, account numbers).",
    "healthcare_detector": "Dictionary and pattern rule for health identifiers, diagnoses and medications.",
    "hr_detector": "Pattern rule for employment data (salary, performance, disciplinary records).",
    "keyname_detector": "A value attached to a sensitive key name (ssn:, diagnosis:, salary:) even when its format is unknown.",
    "custom_detector": "A custom rule from your agentleak.yaml.",
    "presidio": "Microsoft Presidio named-entity recognition (standard detection mode).",
    "llm_judge": "The optional LLM judge (hybrid mode).",
}


def explain(fingerprint: str, *, state_dir: str | None = None) -> dict[str, Any]:
    """Look the fingerprint up in the local history and explain it."""
    found = SelftestHistory(state_dir).find_finding(fingerprint)
    if found is None:
        return {
            "fingerprint": fingerprint,
            "found": False,
            "explanation": (
                "No self-test in the local history has a finding with this fingerprint. "
                "Fingerprints come from the `findings[].fingerprint` field of a self-test "
                "document; run the self-test in the same directory (or with the same "
                "--state-dir) first."
            ),
        }
    entry, finding = found
    channel = str(finding.get("channel") or "")
    detector = str(finding.get("detector") or "")
    level = int(finding.get("level") or 0)
    if channel == "source_code":
        why = (f"The static scan rule `{detector}` matched in {finding.get('file')}:"
               f"{finding.get('line')}. {finding.get('fix') or ''}").strip()
        fix: dict[str, Any] | None = {
            "type": "code_change", "file": finding.get("file"), "line": finding.get("line"),
            "rule": detector, "suggestion": finding.get("fix") or "", "docs": "docs/code-scan.md",
        }
    else:
        why = (
            f"A {finding.get('data_type')} value ({finding.get('redacted_value')}) appeared on "
            f"`{channel}` — {CHANNEL_MEANING.get(channel, channel)}. Data arriving on "
            "user_input or tool_response is a source and is never counted; it counts here "
            "because the agent passed it on."
        )
        fix = fix_for_channel(channel)
    return {
        "fingerprint": fingerprint,
        "found": True,
        "seen_in_run": entry.get("run_id"),
        "seen_at": entry.get("at"),
        "still_open_in_latest_run": _still_open(fingerprint, entry.get("target"), state_dir),
        "finding": finding,
        "why": why,
        "rule": {
            "detector": detector,
            "tier": finding.get("tier"),
            "what_it_matches": DETECTOR_MEANING.get(detector, "See docs/detection.md."),
        },
        "severity": {"level": finding.get("level_label"), "meaning": LEVEL_MEANING.get(level, "")},
        "channel": {"name": channel, "meaning": CHANNEL_MEANING.get(channel, "")},
        "fix": fix,
        "false_positive": (
            "Pattern rules can misfire. If this value is not personal data or a secret, "
            "add a custom allowlist rule in agentleak.yaml or report it; do not silence the "
            "whole channel."
        ),
        "rerun": trusted_rerun(entry.get("rerun")),
    }


def _still_open(fingerprint: str, target: Any, state_dir: str | None) -> bool | None:
    hist = SelftestHistory(state_dir)
    latest = hist.previous(str(target)) if target else None
    if latest is None:
        return None
    return any(f.get("fingerprint") == fingerprint for f in latest.get("findings", []))


__all__ = ["CHANNEL_MEANING", "DETECTOR_MEANING", "LEVEL_MEANING", "explain"]
