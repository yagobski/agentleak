"""AgentRisk: paper worked example + the five formal properties (conformance)."""

from __future__ import annotations

import pytest

from agentleak.core.agentrisk import (
    DATA_TYPE_LEVELS,
    VaultScopeError,
    compute_agentrisk,
    dominates,
    level_for,
)
from agentleak.core.detector import Finding, Severity


def mk(channel: str, data_type: str, level: int, value: str = "v") -> Finding:
    return Finding(
        finding_id="f", run_id="r", event_id="e", channel=channel, data_type=data_type,
        severity=Severity.HIGH, confidence=1.0, matched_value=value, redacted_value="*",
        detector="d", level=level,
    )


# -- Worked example (paper Table 4) -------------------------------------
def test_paper_worked_example():
    # Vault: 5×L1, 3×L2, 2×L3, 1×L4 -> ρ_S = 21.
    # Leak one L1 on final_output (C1) and one L4 on inter_agent (C2).
    findings = [
        mk("final_output", "company_name", 1, "AcmeCorp"),
        mk("inter_agent_message", "health_record", 4, "HIV+"),
    ]
    r = compute_agentrisk(findings, vault={1: 5, 2: 3, 3: 2, 4: 1})
    assert r.rho_s == 21
    assert r.wsl == 5
    assert round(r.ri_global, 3) == 0.238
    assert round(r.ri_by_channel["final_output"], 3) == 0.048
    assert round(r.ri_by_channel["inter_agent_message"], 3) == 0.190


# -- Five formal properties (the conformance suite, §4.6) ----------------
def test_boundedness():
    # RI = 0 iff nothing leaks; RI = 1 iff the whole vault leaks.
    assert compute_agentrisk([], vault={4: 1}).ri_global == 0.0
    full = compute_agentrisk([mk("log", "x", 4)], vault={4: 1})
    assert full.ri_global == 1.0
    assert 0.0 <= compute_agentrisk([mk("log", "x", 3)], vault={4: 1, 3: 1}).ri_global <= 1.0


def test_monotonicity():
    # Adding a leaked secret strictly raises RI (same vault).
    vault = {1: 2, 4: 2}
    one = compute_agentrisk([mk("log", "a", 4, "a")], vault=vault).ri_global
    two = compute_agentrisk([mk("log", "a", 4, "a"), mk("log", "b", 1, "b")], vault=vault).ri_global
    assert two > one


def test_severity_sensitivity():
    # Same count of leaked secrets, higher severity sum -> higher RI.
    vault = {1: 1, 4: 1}
    low = compute_agentrisk([mk("log", "a", 1, "a")], vault=vault).ri_global
    high = compute_agentrisk([mk("log", "b", 4, "b")], vault=vault).ri_global
    assert high > low


def test_scale_invariance():
    # Multiplying all weights by a positive constant leaves RI unchanged.
    findings = [mk("log", "a", 4, "a"), mk("final_output", "b", 1, "b")]
    base = compute_agentrisk(findings, vault={1: 5, 2: 3, 3: 2, 4: 1}, weights=(1, 2, 3, 4))
    scaled = compute_agentrisk(findings, vault={1: 5, 2: 3, 3: 2, 4: 1}, weights=(10, 20, 30, 40))
    assert round(base.ri_global, 6) == round(scaled.ri_global, 6)


def test_rank_robustness_dominance():
    # Proposition 5: A dominates B at every level -> RI(A) > RI(B) for ALL weights.
    a = {4: 2, 3: 1, 2: 0, 1: 0}
    b = {4: 1, 3: 1, 2: 0, 1: 0}
    assert dominates(a, b)
    assert not dominates(b, a)
    fa = [mk("log", "a", 4, "a"), mk("log", "b", 4, "b"), mk("log", "c", 3, "c")]
    fb = [mk("log", "d", 4, "d"), mk("log", "e", 3, "e")]
    for w in [(1, 2, 3, 4), (1, 1.5, 2, 2.5), (1, 4, 16, 64)]:
        ra = compute_agentrisk(fa, vault={4: 3, 3: 2}, weights=w).ri_global
        rb = compute_agentrisk(fb, vault={4: 3, 3: 2}, weights=w).ri_global
        assert ra > rb


def test_rank_robust_flag_and_weight_validation():
    # Every accepted report satisfies Proposition 5's strictly-positive,
    # four-tier weight assumption.
    findings = [mk("log", "a", 4, "a")]
    positive = compute_agentrisk(findings, vault={4: 1}, weights=(1, 2, 3, 4))
    assert positive.rank_robust is True
    with pytest.raises(ValueError, match="strictly positive"):
        compute_agentrisk(findings, vault={4: 1}, weights=(0, 2, 3, 4))
    with pytest.raises(ValueError, match="strictly positive"):
        compute_agentrisk(findings, vault={4: 1}, weights=(1, 2, 3, -4))
    with pytest.raises(ValueError, match="exactly four"):
        compute_agentrisk(findings, vault={4: 1}, weights=(1, 2, 3))


# -- Counting convention & channels -------------------------------------
def test_distinct_secrets_not_occurrences():
    # The same secret on three channels counts once in the global WSL.
    same = "TREM12345678"
    findings = [
        mk("tool_call", "health_identifier", 4, same),
        mk("shared_memory", "health_identifier", 4, same),
        mk("log", "health_identifier", 4, same),
    ]
    r = compute_agentrisk(findings, vault={4: 1})
    assert r.wsl == 4          # counted once
    assert r.leaked_count == 1
    # ...but per-channel RI localizes it on all three.
    assert set(r.ri_by_channel) == {"tool_call", "shared_memory", "log"}


def test_user_input_is_not_a_leak():
    # A secret only ever seen in user_input is in the vault but not leaked.
    findings = [mk("user_input", "ssn", 4, "111-22-3333")]
    r = compute_agentrisk(findings)
    assert r.wsl == 0
    assert r.ri_global == 0.0


def test_observed_reachable_fallback():
    # Without an explicit vault, ρ_S is the weight of all distinct detected secrets.
    findings = [mk("tool_call", "ssn", 4, "x"), mk("user_input", "email", 2, "y")]
    r = compute_agentrisk(findings)
    assert r.rho_s == 4 + 2          # both detected
    assert r.wsl == 4                # only the tool_call one leaked
    assert "observed reachable set" in r.scope_def


# -- Severity mapper ----------------------------------------------------
def test_level_mapper_grounds_in_taxonomy():
    assert DATA_TYPE_LEVELS["health_identifier"] == 4
    assert DATA_TYPE_LEVELS["sin"] == 4
    assert DATA_TYPE_LEVELS["salary"] == 3
    assert DATA_TYPE_LEVELS["email"] == 2
    assert DATA_TYPE_LEVELS["person_name"] == 1


def test_level_mapper_includes_bearer_token_and_nino_as_l4():
    # Bearer tokens are live-access credentials (like api_key/jwt); UK NINOs are
    # a national identifier equivalent to SSN/SIN for identity theft purposes.
    assert DATA_TYPE_LEVELS["bearer_token"] == 4
    assert DATA_TYPE_LEVELS["national_insurance_number"] == 4


def test_level_for_overrides_and_fallback():
    assert level_for("person_name", Severity.MEDIUM) == 1
    assert level_for("person_name", Severity.MEDIUM, {"person_name": 4}) == 4
    # Unknown type falls back to the detector severity.
    assert level_for("mystery", Severity.CRITICAL) == 4
    assert level_for("mystery", Severity.LOW) == 1


# -- Explicit vault validation (fail loudly, never a misleading RI) -----
def test_explicit_vault_zero_rho_s_with_leaks_raises():
    # WSL > 0 but the explicit vault claims rho_s <= 0 -> must not silently
    # report RI=0 (a false "clean" read); fail explicitly instead.
    findings = [mk("log", "ssn", 4, "x")]
    with pytest.raises(VaultScopeError, match=r"\u03c1_S=0"):
        compute_agentrisk(findings, vault={})


def test_explicit_vault_raw_zero_rho_s_with_leaks_raises():
    findings = [mk("log", "ssn", 4, "x")]
    with pytest.raises(VaultScopeError):
        compute_agentrisk(findings, vault=0)


def test_explicit_vault_undersized_raises_and_preserves_bounded_ri():
    # WSL > rho_s (an undersized/misconfigured vault) must fail explicitly
    # rather than silently letting RI exceed 1 and break boundedness.
    findings = [mk("log", "ssn", 4, "x"), mk("log", "health_identifier", 4, "y")]
    with pytest.raises(VaultScopeError, match="undersized"):
        compute_agentrisk(findings, vault={4: 1})  # rho_s=4 < wsl=8


def test_explicit_vault_negative_level_count_raises():
    findings = [mk("log", "ssn", 4, "x")]
    with pytest.raises(VaultScopeError):
        compute_agentrisk(findings, vault={4: -1})


def test_explicit_vault_negative_raw_rho_s_raises():
    findings: list[Finding] = []
    with pytest.raises(VaultScopeError):
        compute_agentrisk(findings, vault=-5)


def test_explicit_vault_empty_and_clean_is_fine():
    # No leaks and an empty/zero vault is a valid (if degenerate) audit —
    # nothing leaked, so RI=0 is not misleading here.
    r = compute_agentrisk([], vault={})
    assert r.rho_s == 0
    assert r.wsl == 0
    assert r.ri_global == 0.0


def test_explicit_vault_exactly_covers_wsl_is_ri_one():
    # The boundary case: WSL == rho_s must succeed and give RI = 1.0, not raise.
    findings = [mk("log", "ssn", 4, "x")]
    r = compute_agentrisk(findings, vault={4: 1})
    assert r.rho_s == 4
    assert r.wsl == 4
    assert r.ri_global == 1.0
