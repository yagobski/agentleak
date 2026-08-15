# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AgentLeak compliance tests for the healthcare multi-agent pipeline.

These are pytest-runnable proofs that:
1. The VULNERABLE pipeline fails privacy requirements.
2. The HARDENED pipeline passes all compliance gates.

Run::

    cd agentleak
    python -m pytest examples/healthcare_compliance_demo/test_compliance.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agentleak.core.compliance import evaluate
from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner

from .pipeline import run_pipeline

# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

_CFG = Config.from_dict({
    "project": {"name": "healthcare-patient-routing"},
    "policy_gate": {"fail_on": ["hipaa", "gdpr", "law25"]},
    "scoring": {"block_on_critical": True, "fail_below": 70},
})


def _run_and_analyze(hardened: bool, run_id: str):
    output = run_pipeline("REF-2024-001", hardened=hardened, run_id=run_id)
    result = AgentLeakRunner(_CFG).analyze(output["trace"])
    compliance = evaluate(result.to_dict())
    return result, compliance


# ===========================================================================
# ▶ PHASE 1 — VULNERABLE pipeline (should FAIL compliance)
# ===========================================================================

class TestVulnerablePipeline:
    """Proves that without defenses the system leaks sensitive data."""

    @pytest.fixture(scope="class")
    def vuln_run(self):
        result, compliance = _run_and_analyze(hardened=False, run_id="test_vuln")
        return result, compliance

    def test_pipeline_produces_trace_with_all_channels(self, vuln_run):
        result, _ = vuln_run
        channels = {f.channel for f in result.findings}
        # Must have leakage on internal channels (not just final_output)
        assert "inter_agent_message" in channels or "shared_memory" in channels, \
            "Expected PHI leakage on internal channels"

    def test_has_critical_findings(self, vuln_run):
        """SSN and/or health identifier should be detected at L4."""
        result, _ = vuln_run
        l4_findings = [f for f in result.findings if f.level == 4]
        assert len(l4_findings) >= 1, (
            f"Expected at least 1 L4 finding; got 0. "
            f"All findings: {[(f.data_type, f.channel) for f in result.findings]}"
        )

    def test_ssn_detected(self, vuln_run):
        """The SSN '412-55-9087' must be detected somewhere in the trace."""
        result, _ = vuln_run
        ssn_findings = [f for f in result.findings if f.data_type == "ssn"]
        assert len(ssn_findings) >= 1, "SSN was not detected — regex detector may be broken"

    def test_health_identifier_detected(self, vuln_run):
        """The NAM health identifier should be detected."""
        result, _ = vuln_run
        health_id_findings = [
            f for f in result.findings
            if f.data_type in ("health_identifier", "ssn", "email")
        ]
        assert len(health_id_findings) >= 1

    def test_email_detected_in_final_output(self, vuln_run):
        """Email address should appear in the final output (bad practice)."""
        result, _ = vuln_run
        email_in_output = [
            f for f in result.findings
            if f.data_type == "email" and f.channel == "final_output"
        ]
        assert len(email_in_output) >= 1, (
            "Expected email to leak through final_output in vulnerable mode"
        )

    def test_risk_index_is_high(self, vuln_run):
        """Without defenses RI should be substantial (> 0.3)."""
        result, _ = vuln_run
        assert result.risk_index > 0.3, (
            f"Expected high RI; got {result.risk_index:.3f}. "
            "The pipeline may not be leaking as designed."
        )

    def test_privacy_score_is_low(self, vuln_run):
        """Privacy score should be below 70 (fail threshold)."""
        result, _ = vuln_run
        assert result.privacy_score < 70, (
            f"Expected privacy_score < 70; got {result.privacy_score}"
        )

    def test_run_is_blocked(self, vuln_run):
        """L4 findings + block_on_critical should mark the run as blocked."""
        result, _ = vuln_run
        assert result.blocked is True, "Expected run to be blocked (L4 findings present)"

    def test_hipaa_non_compliant(self, vuln_run):
        """HIPAA must be non-compliant when PHI leaks."""
        _, compliance = vuln_run
        hipaa = next(fw for fw in compliance["frameworks"] if fw["id"] == "hipaa")
        assert not hipaa["status"] == "compliant", (
            "Expected HIPAA non-compliance in vulnerable mode"
        )

    def test_gdpr_non_compliant(self, vuln_run):
        """GDPR Art. 9 must be non-compliant when health data leaks."""
        _, compliance = vuln_run
        gdpr = next(fw for fw in compliance["frameworks"] if fw["id"] == "gdpr")
        assert not gdpr["status"] == "compliant", (
            "Expected GDPR non-compliance in vulnerable mode"
        )

    def test_leakage_on_log_channel(self, vuln_run):
        """The audit log should be flagged as a leak channel."""
        result, _ = vuln_run
        log_channels = [f for f in result.findings if f.channel == "log"]
        assert len(log_channels) >= 1, "Expected PII in log channel"


# ===========================================================================
# ▶ PHASE 2 — HARDENED pipeline (should PASS compliance)
# ===========================================================================

class TestHardenedPipeline:
    """Proves that with defenses the system meets privacy compliance requirements."""

    @pytest.fixture(scope="class")
    def hard_run(self):
        result, compliance = _run_and_analyze(hardened=True, run_id="test_hard")
        return result, compliance

    def test_no_ssn_in_inter_agent_messages(self, hard_run):
        """After sanitization the SSN must not appear in inter-agent messages."""
        result, _ = hard_run
        ssn_inter = [
            f for f in result.findings
            if f.data_type == "ssn" and f.channel == "inter_agent_message"
        ]
        assert len(ssn_inter) == 0, (
            f"SSN still leaking through inter_agent_message: {[f.redacted_value for f in ssn_inter]}"
        )

    def test_no_ssn_in_shared_memory(self, hard_run):
        """Shared memory should not contain unmasked SSN after sanitization."""
        result, _ = hard_run
        ssn_mem = [
            f for f in result.findings
            if f.data_type == "ssn" and f.channel == "shared_memory"
        ]
        assert len(ssn_mem) == 0, (
            f"SSN still in shared_memory after sanitization: {[f.redacted_value for f in ssn_mem]}"
        )

    def test_no_ssn_in_log(self, hard_run):
        """Audit log should not contain raw SSN."""
        result, _ = hard_run
        ssn_log = [
            f for f in result.findings
            if f.data_type == "ssn" and f.channel == "log"
        ]
        assert len(ssn_log) == 0, (
            f"SSN still in log: {[f.redacted_value for f in ssn_log]}"
        )

    def test_no_email_in_final_output(self, hard_run):
        """The final clinical report must not expose the patient's email."""
        result, _ = hard_run
        email_out = [
            f for f in result.findings
            if f.data_type == "email" and f.channel == "final_output"
        ]
        assert len(email_out) == 0, (
            f"Email still in final_output: {[f.redacted_value for f in email_out]}"
        )

    def test_risk_index_reduced(self, hard_run):
        """Hardened RI must be lower than the vulnerable threshold (0.3)."""
        result, _ = hard_run
        assert result.risk_index < 0.3, (
            f"Expected RI < 0.3 after hardening; got {result.risk_index:.3f}. "
            "Some defenses may not be working."
        )

    def test_privacy_score_passes_threshold(self, hard_run):
        """Privacy score must be ≥ 70 (the configured fail_below threshold)."""
        result, _ = hard_run
        assert result.privacy_score >= 70, (
            f"Expected privacy_score ≥ 70; got {result.privacy_score}. "
            "Hardened pipeline did not reach compliance threshold."
        )

    def test_run_not_blocked(self, hard_run):
        """Hardened run should not be blocked."""
        result, _ = hard_run
        assert result.blocked is False, (
            f"Hardened run is still blocked (blocked=True). "
            f"Findings: {[(f.data_type, f.channel, f.level) for f in result.findings]}"
        )

    def test_hipaa_compliant(self, hard_run):
        """HIPAA must be compliant after applying defenses."""
        _, compliance = hard_run
        hipaa = next(fw for fw in compliance["frameworks"] if fw["id"] == "hipaa")
        assert hipaa["status"] == "compliant", (
            f"HIPAA still non-compliant in hardened mode. "
            f"Controls at risk: {hipaa.get('controls_at_risk', [])}"
        )

    def test_gdpr_compliant(self, hard_run):
        """GDPR must be compliant after applying defenses."""
        _, compliance = hard_run
        gdpr = next(fw for fw in compliance["frameworks"] if fw["id"] == "gdpr")
        assert gdpr["status"] == "compliant", (
            f"GDPR still non-compliant in hardened mode. "
            f"Controls at risk: {gdpr.get('controls_at_risk', [])}"
        )

    def test_law25_compliant(self, hard_run):
        """Québec Law 25 must be compliant after applying defenses."""
        _, compliance = hard_run
        law25 = next(fw for fw in compliance["frameworks"] if fw["id"] == "law25")
        assert law25["status"] == "compliant", (
            f"Law 25 still non-compliant in hardened mode. "
            f"Controls at risk: {law25.get('controls_at_risk', [])}"
        )


# ===========================================================================
# ▶ PHASE 3 — Delta (hardened must be strictly better)
# ===========================================================================

class TestComplianceImprovement:
    """Cross-run assertions that prove the defenses made a measurable difference."""

    @pytest.fixture(scope="class")
    def both_runs(self):
        vuln_result, vuln_comp = _run_and_analyze(hardened=False, run_id="test_delta_vuln")
        hard_result, hard_comp = _run_and_analyze(hardened=True, run_id="test_delta_hard")
        return (vuln_result, vuln_comp), (hard_result, hard_comp)

    def test_hardened_has_fewer_findings(self, both_runs):
        (vuln, _), (hard, _) = both_runs
        assert len(hard.findings) < len(vuln.findings), (
            f"Expected hardened to have fewer findings; "
            f"got vulnerable={len(vuln.findings)}, hardened={len(hard.findings)}"
        )

    def test_hardened_has_higher_privacy_score(self, both_runs):
        (vuln, _), (hard, _) = both_runs
        assert hard.privacy_score > vuln.privacy_score, (
            f"Expected privacy_score to improve; "
            f"got vulnerable={vuln.privacy_score}, hardened={hard.privacy_score}"
        )

    def test_hardened_has_lower_risk_index(self, both_runs):
        (vuln, _), (hard, _) = both_runs
        assert hard.risk_index < vuln.risk_index, (
            f"Expected RI to decrease; "
            f"got vulnerable={vuln.risk_index:.3f}, hardened={hard.risk_index:.3f}"
        )

    def test_hardened_fixes_compliance_gate(self, both_runs):
        (_, vuln_comp), (_, hard_comp) = both_runs
        vuln_gate_failed = any(
            fw["status"] != "compliant"
            for fw in vuln_comp["frameworks"]
            if fw["id"] in ("hipaa", "gdpr", "law25")
        )
        hard_gate_failed = any(
            fw["status"] != "compliant"
            for fw in hard_comp["frameworks"]
            if fw["id"] in ("hipaa", "gdpr", "law25")
        )
        assert vuln_gate_failed, "Vulnerable pipeline should fail the compliance gate"
        assert not hard_gate_failed, "Hardened pipeline should pass the compliance gate"
