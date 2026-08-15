# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AgentLeak compliance audit for the healthcare multi-agent pipeline.

Runs the pipeline twice — first in VULNERABLE mode to demonstrate what leaks,
then in HARDENED mode to prove defenses work — and prints a structured compliance
report with before/after comparison.

Usage::

    cd agentleak
    python -m examples.healthcare_compliance_demo.audit

Or run the pre-built test::

    python -m pytest examples/healthcare_compliance_demo/test_compliance.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make the demo importable when run as a script from the repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agentleak.core.compliance import evaluate
from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.trace import Trace

from .pipeline import run_pipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "─" * 68
SEP2 = "═" * 68

_COMPLIANCE_CONFIG = Config.from_dict({
    "project": {"name": "healthcare-patient-routing"},
    "policy_gate": {"fail_on": ["hipaa", "gdpr", "law25"]},
    "scoring": {"block_on_critical": True, "fail_below": 70},
})


def _analyze(trace: Trace) -> tuple[Any, Any]:
    """Run AgentLeakRunner + compliance evaluation."""
    result = AgentLeakRunner(_COMPLIANCE_CONFIG).analyze(trace)
    compliance = evaluate(result.to_dict())
    return result, compliance


def _print_run_banner(title: str, run_id: str) -> None:
    print(f"\n{SEP2}")
    print(f"  {title}")
    print(f"  run_id: {run_id}")
    print(SEP2)


def _print_findings_table(result: Any) -> None:
    if not result.findings:
        print("  ✓  No findings — all channels clean")
        return

    print(f"\n  {'Channel':<22} {'L':<3} {'Severity':<10} {'Data type':<22} {'Value'}")
    print(f"  {'─'*22} {'─'*3} {'─'*10} {'─'*22} {'─'*20}")
    for f in result.findings:
        bar = "●" if f.level == 4 else ("◑" if f.level == 3 else "○")
        print(
            f"  {f.channel:<22} {bar} L{f.level:<2} "
            f"{f.severity:<10} {f.data_type:<22} {f.redacted_value}"
        )


def _print_channel_risks(result: Any) -> None:
    if not result.score.channel_risks:
        print("\n  All channels: clean (RI = 0)")
        return
    print(f"\n  {'Channel':<22} {'Level':<8} {'RI':<8} Findings")
    print(f"  {'─'*22} {'─'*8} {'─'*8} {'─'*8}")
    for cr in sorted(result.score.channel_risks, key=lambda x: -x.ri):
        indicator = "✗" if cr.level >= 3 else "△"
        print(
            f"  {indicator} {cr.channel:<20} L{cr.level:<7} "
            f"{cr.ri:.3f}   {cr.finding_count} finding(s)"
        )


def _print_compliance_posture(compliance: Any) -> None:
    print()
    for fw in compliance["frameworks"]:
        icon = "✓" if (fw["status"] == "compliant") else "✗"
        flag = fw["id"]
        name = fw["name"]
        print(f"  {icon}  [{flag}] {name}")
        for c in [c["id"] for c in fw.get("controls", []) if c.get("status") == "at_risk"]:
            print(f"       ↳ {c}")


def _print_summary_card(label: str, result: Any, compliance: Any) -> None:
    passed = not result.blocked
    gate_failed = any(
        fw["status"] != "compliant"
        for fw in compliance["frameworks"]
        if fw["id"] in ("hipaa", "gdpr", "law25")
    )
    overall = "PASS ✓" if (passed and not gate_failed) else "FAIL ✗"
    print(f"\n  Privacy score : {result.privacy_score}/100")
    print(f"  Risk Index    : {result.risk_index:.3f}")
    print(f"  Verdict       : {result.verdict}")
    print(f"  Blocked       : {'yes' if result.blocked else 'no'}")
    print(f"  Compliance    : {'FAIL ✗' if gate_failed else 'PASS ✓'}")
    print("\n  ┌─────────────────────────────┐")
    print(f"  │  OVERALL: {overall:<20}│")
    print("  └─────────────────────────────┘")


# ---------------------------------------------------------------------------
# Main audit function
# ---------------------------------------------------------------------------

def run_audit() -> dict[str, Any]:
    """Execute full before/after audit and return structured results."""

    print(f"\n{SEP2}")
    print("  AGENTLEAK COMPLIANCE AUDIT")
    print("  Healthcare Patient Case Management Pipeline")
    print("  5 agents · 7 channels · HIPAA / GDPR / Law 25")
    print(SEP2)

    # ================================================================
    # Phase 1 — Vulnerable run
    # ================================================================
    _print_run_banner("PHASE 1 — VULNERABLE (no defenses)", "vulnerable_run_001")

    vuln_out = run_pipeline("REF-2024-001", hardened=False, run_id="vulnerable_run_001")
    vuln_result, vuln_compliance = _analyze(vuln_out["trace"])

    print(f"\n{SEP}")
    print("  FINDINGS")
    print(SEP)
    _print_findings_table(vuln_result)

    print(f"\n{SEP}")
    print("  CHANNEL RISK BREAKDOWN")
    print(SEP)
    _print_channel_risks(vuln_result)

    print(f"\n{SEP}")
    print("  COMPLIANCE POSTURE")
    print(SEP)
    _print_compliance_posture(vuln_compliance)

    print(f"\n{SEP}")
    print("  SUMMARY — VULNERABLE")
    print(SEP)
    _print_summary_card("VULNERABLE", vuln_result, vuln_compliance)

    # ================================================================
    # Phase 2 — Hardened run
    # ================================================================
    _print_run_banner("PHASE 2 — HARDENED (defenses applied)", "hardened_run_001")

    hard_out = run_pipeline("REF-2024-001", hardened=True, run_id="hardened_run_001")
    hard_result, hard_compliance = _analyze(hard_out["trace"])

    print(f"\n{SEP}")
    print("  FINDINGS")
    print(SEP)
    _print_findings_table(hard_result)

    print(f"\n{SEP}")
    print("  CHANNEL RISK BREAKDOWN")
    print(SEP)
    _print_channel_risks(hard_result)

    print(f"\n{SEP}")
    print("  COMPLIANCE POSTURE")
    print(SEP)
    _print_compliance_posture(hard_compliance)

    print(f"\n{SEP}")
    print("  SUMMARY — HARDENED")
    print(SEP)
    _print_summary_card("HARDENED", hard_result, hard_compliance)

    # ================================================================
    # Improvement delta
    # ================================================================
    delta_score = hard_result.privacy_score - vuln_result.privacy_score
    delta_ri = vuln_result.risk_index - hard_result.risk_index
    delta_findings = len(vuln_result.findings) - len(hard_result.findings)

    print(f"\n{SEP2}")
    print("  BEFORE / AFTER COMPARISON")
    print(SEP2)
    print(f"\n  {'Metric':<30} {'Vulnerable':>12} {'Hardened':>12} {'Delta':>10}")
    print(f"  {'─'*30} {'─'*12} {'─'*12} {'─'*10}")
    print(f"  {'Privacy score':<30} {vuln_result.privacy_score:>11}/100 {hard_result.privacy_score:>11}/100 {delta_score:>+10}")
    print(f"  {'Risk Index (RI)':<30} {vuln_result.risk_index:>12.3f} {hard_result.risk_index:>12.3f} {-delta_ri:>+10.3f}")
    print(f"  {'Findings':<30} {len(vuln_result.findings):>12} {len(hard_result.findings):>12} {-delta_findings:>+10}")
    print(f"  {'Blocked':<30} {'yes':>12} {'no' if not hard_result.blocked else 'yes':>12}")

    vuln_noncompliant = sum(
        1 for fw in vuln_compliance["frameworks"]
        if fw["status"] != "compliant" and fw["id"] in ("hipaa", "gdpr", "law25")
    )
    hard_noncompliant = sum(
        1 for fw in hard_compliance["frameworks"]
        if fw["status"] != "compliant" and fw["id"] in ("hipaa", "gdpr", "law25")
    )
    print(f"  {'Non-compliant frameworks':<30} {vuln_noncompliant:>12} {hard_noncompliant:>12} {hard_noncompliant - vuln_noncompliant:>+10}")

    # Defenses summary
    print(f"\n{SEP}")
    print("  DEFENSES APPLIED IN HARDENED MODE")
    print(SEP)
    print("""
  1. Sanitizer (RedactionStyle.MASKED)
     Applied to:
       • shared_memory writes (SSN → XXX-XX-9087, NAM → masked)
       • log entries (all PII patterns masked before write)
       • inter-agent messages (via InternalChannelGuard estimation)

  2. InternalChannelGuard (sender ≥ CONFIDENTIAL, recipient ≤ INTERNAL)
     Applied to:
       • risk_agent → report_agent inter-agent message
       • Clears SSN + NAM that crossed the clearance boundary

  3. Minimal-disclosure final output
     Applied to:
       • report_agent final_output: removed email + phone contact details
       • Only clinical metadata kept (risk level, diagnosis, A1C, BP)
    """)

    vuln_gate = any(
        fw["status"] != "compliant"
        for fw in vuln_compliance["frameworks"]
        if fw["id"] in ("hipaa", "gdpr", "law25")
    )
    hard_gate = any(
        fw["status"] != "compliant"
        for fw in hard_compliance["frameworks"]
        if fw["id"] in ("hipaa", "gdpr", "law25")
    )

    print(f"\n{SEP2}")
    overall_verdict = "COMPLIANT ✓" if not hard_gate and not hard_result.blocked else "NON-COMPLIANT ✗"
    print(f"  FINAL VERDICT (HARDENED): {overall_verdict}")
    print(SEP2)

    return {
        "vulnerable": {
            "privacy_score": vuln_result.privacy_score,
            "risk_index": vuln_result.risk_index,
            "findings": len(vuln_result.findings),
            "blocked": vuln_result.blocked,
            "compliance_gate_failed": vuln_gate,
        },
        "hardened": {
            "privacy_score": hard_result.privacy_score,
            "risk_index": hard_result.risk_index,
            "findings": len(hard_result.findings),
            "blocked": hard_result.blocked,
            "compliance_gate_failed": hard_gate,
        },
        "delta": {
            "privacy_score": delta_score,
            "risk_index_reduction": delta_ri,
            "findings_removed": delta_findings,
        },
    }


if __name__ == "__main__":
    results = run_audit()
    # Write machine-readable summary
    out_path = Path(__file__).parent / "audit_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\n  Results written to {out_path}")
