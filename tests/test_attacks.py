# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Tests for the attack catalog and red-team components."""

from __future__ import annotations

import pytest

from agentleak.core.attacks import (
    ATTACK_FAMILIES,
    ATTACK_INDEX,
    AdversaryLevel,
    AttackClass,
    get_classes_for_channel,
    get_classes_for_level,
)
from agentleak.core.metrics import RunResult, compute_asr, compute_elr, compute_metrics
from agentleak.generators import ScenarioGenerator, generate_vault

# ---------------------------------------------------------------------------
# Attack catalog
# ---------------------------------------------------------------------------

class TestAttackCatalog:
    def test_six_families(self):
        assert len(ATTACK_FAMILIES) == 6
        ids = [f.id for f in ATTACK_FAMILIES]
        assert ids == ["F1", "F2", "F3", "F4", "F5", "F6"]

    def test_at_least_32_classes(self):
        total = sum(len(f.classes) for f in ATTACK_FAMILIES)
        assert total >= 32

    def test_all_classes_have_templates(self):
        for fam in ATTACK_FAMILIES:
            for ac in fam.classes:
                assert ac.id.startswith(fam.id), f"{ac.id} should start with {fam.id}"
                assert ac.name
                assert ac.adversary_level in list(AdversaryLevel)

    def test_attack_index_complete(self):
        indexed_count = len(ATTACK_INDEX)
        total = sum(len(f.classes) for f in ATTACK_FAMILIES)
        assert indexed_count == total

    def test_get_classes_for_level_a0(self):
        """A0 = benign only."""
        classes = get_classes_for_level(AdversaryLevel.A0)
        assert all(c.adversary_level == AdversaryLevel.A0 for c in classes)

    def test_get_classes_for_level_a2_includes_all(self):
        """A2 should include A0 + A1 + A2 classes."""
        a2 = get_classes_for_level(AdversaryLevel.A2)
        all_classes = [c for f in ATTACK_FAMILIES for c in f.classes]
        assert len(a2) == len(all_classes)

    def test_get_classes_for_channel(self):
        final_output_classes = get_classes_for_channel("final_output")
        assert all(c.primary_channel.value == "final_output" for c in final_output_classes)
        assert len(final_output_classes) > 0

    def test_internal_channels_have_classes(self):
        inter_agent = get_classes_for_channel("inter_agent_message")
        shared_mem = get_classes_for_channel("shared_memory")
        assert len(inter_agent) > 0
        assert len(shared_mem) > 0


# ---------------------------------------------------------------------------
# Vault generator
# ---------------------------------------------------------------------------

class TestVaultGenerator:
    def test_generate_healthcare(self):
        vault = generate_vault("healthcare")
        assert vault.vertical == "healthcare"
        assert "patient_name" in vault.records or "health_identifier" in vault.records
        assert not vault.canary_set.is_empty()

    def test_generate_finance(self):
        vault = generate_vault("finance")
        assert vault.vertical == "finance"
        assert "account_number" in vault.records or "iban" in vault.records

    def test_generate_hr(self):
        vault = generate_vault("hr")
        assert "salary" in vault.records

    def test_canary_tiers_populated(self):
        vault = generate_vault("healthcare")
        assert len(vault.canary_set.obvious) >= 1
        assert len(vault.canary_set.realistic) >= 1
        assert len(vault.canary_set.semantic) >= 1

    def test_obvious_canary_in_records(self):
        vault = generate_vault("healthcare")
        # The obvious canary token is injected into records["canary_token"]
        assert "canary_token" in vault.records
        assert vault.records["canary_token"] in vault.canary_set.obvious

    def test_tool_response_content(self):
        vault = generate_vault("healthcare")
        content = vault.as_tool_response_content()
        assert isinstance(content, str)
        assert "[HEALTHCARE RECORD]" in content

    def test_to_dict(self):
        vault = generate_vault("finance")
        d = vault.to_dict()
        assert "vertical" in d
        assert "records" in d
        assert "canaries" in d
        assert "obvious" in d["canaries"]

    def test_unknown_vertical_defaults(self):
        vault = generate_vault("unknown_domain")
        assert vault.vertical == "healthcare"

    def test_all_verticals(self):
        for v in ["healthcare", "finance", "legal", "hr", "customer_support"]:
            vault = generate_vault(v)
            assert vault.vertical == v
            assert len(vault.records) > 0


# ---------------------------------------------------------------------------
# Scenario generator
# ---------------------------------------------------------------------------

class TestScenarioGenerator:
    def test_generate_single(self):
        gen = ScenarioGenerator(vertical="healthcare", adversary_level=AdversaryLevel.A1)
        scenario = gen.generate()
        assert scenario.scenario_id
        assert scenario.vertical == "healthcare"
        assert scenario.trace is not None
        assert len(scenario.trace.events) > 0
        assert len(scenario.expected_leaks) > 0

    def test_generate_specific_class(self):
        gen = ScenarioGenerator(vertical="finance")
        scenario = gen.generate("F1.1")
        assert scenario.attack_class.id == "F1.1"

    def test_generate_unknown_class_raises(self):
        gen = ScenarioGenerator()
        with pytest.raises(ValueError, match="Unknown attack class"):
            gen.generate("INVALID.99")

    def test_generate_batch(self):
        gen = ScenarioGenerator(adversary_level=AdversaryLevel.A1, seed=42)
        scenarios = gen.generate_batch(3)
        assert len(scenarios) == 3
        # Each scenario should have a unique attack class
        class_ids = [s.attack_class.id for s in scenarios]
        assert len(set(class_ids)) == len(class_ids)

    def test_trace_has_tool_response(self):
        """Every scenario should have a tool_response event with vault data."""
        gen = ScenarioGenerator()
        scenario = gen.generate("F1.1")
        channels = [e.channel_value for e in scenario.trace.events]
        assert "tool_response" in channels

    def test_trace_has_disclosure_channel(self):
        """Every scenario should have a disclosure event on the attack's primary channel."""
        gen = ScenarioGenerator()
        scenario = gen.generate("F1.1")  # F1.1 primary = final_output
        channels = [e.channel_value for e in scenario.trace.events]
        assert scenario.attack_class.primary_channel.value in channels

    def test_runner_detects_leaks_in_generated_trace(self):
        """The generated trace should trigger detections when analyzed."""
        from agentleak.core.runner import AgentLeakRunner
        gen = ScenarioGenerator(vertical="healthcare", seed=1)
        scenario = gen.generate("F1.1")
        result = AgentLeakRunner().analyze(scenario.trace, canary_set=scenario.vault.canary_set)
        # Should detect at least the obvious canary
        assert len(result.findings) > 0

    def test_canary_detected_in_generated_trace(self):
        """The obvious canary should be detected in the generated trace."""
        from agentleak.core.runner import AgentLeakRunner
        gen = ScenarioGenerator(vertical="healthcare", seed=2)
        scenario = gen.generate("F1.1")
        result = AgentLeakRunner().analyze(scenario.trace, canary_set=scenario.vault.canary_set)
        canary_findings = [f for f in result.findings if f.data_type == "canary"]
        assert len(canary_findings) >= 1


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _make_run(
    detected_leaks=None,
    detected_on_primary=None,
    expected_leaks=None,
    risk_index=0.5,
    channel="final_output",
    attack_class_id="F1.1",
    family_id="F1",
):
    return RunResult(
        scenario_id=f"s_{id(object()):x}",
        vertical="healthcare",
        attack_class_id=attack_class_id,
        attack_family_id=family_id,
        primary_channel=channel,
        adversary_level="A1",
        vault_field_count=10,
        expected_leaks=expected_leaks if expected_leaks is not None else ["ssn", "health_condition", "canary"],
        detected_leaks=detected_leaks if detected_leaks is not None else ["ssn", "canary"],
        detected_on_primary=detected_on_primary if detected_on_primary is not None else ["ssn"],
        risk_index=risk_index,
        privacy_score=round(100 * (1 - risk_index)),
    )


class TestELR:
    def test_full_leak(self):
        run = _make_run(
            expected_leaks=["ssn", "health_condition"],
            detected_leaks=["ssn", "health_condition"],
        )
        elr = compute_elr(run)
        assert elr.elr == 2 / 10  # 2 leaked of 10 vault fields

    def test_no_leak(self):
        run = _make_run(detected_leaks=[], detected_on_primary=[])
        elr = compute_elr(run)
        assert elr.elr == 0.0

    def test_partial_leak(self):
        run = _make_run(
            expected_leaks=["ssn", "health_condition", "medication"],
            detected_leaks=["ssn"],
        )
        elr = compute_elr(run)
        # 1 of 3 expected detected, vault_field_count=10 → 1/10
        assert elr.elr == 1 / 10


class TestASR:
    def test_all_successful(self):
        runs = [
            _make_run(detected_on_primary=["ssn", "canary"], expected_leaks=["ssn", "canary"])
            for _ in range(5)
        ]
        overall, _, _ = compute_asr(runs)
        assert overall == 1.0

    def test_none_successful(self):
        runs = [
            _make_run(detected_on_primary=[], expected_leaks=["ssn"])
            for _ in range(5)
        ]
        overall, _, _ = compute_asr(runs)
        assert overall == 0.0

    def test_by_family(self):
        runs = [
            _make_run(attack_class_id="F1.1", family_id="F1",
                      detected_on_primary=["ssn"], expected_leaks=["ssn"]),
            _make_run(attack_class_id="F2.1", family_id="F2",
                      detected_on_primary=[], expected_leaks=["ssn"]),
        ]
        _, family_asr, _ = compute_asr(runs)
        f1 = next(a for a in family_asr if a.id == "F1")
        f2 = next(a for a in family_asr if a.id == "F2")
        assert f1.asr == 1.0
        assert f2.asr == 0.0


class TestMetricsSummary:
    def test_empty_batch(self):
        summary = compute_metrics([])
        assert summary.total_runs == 0
        assert summary.mean_elr == 0.0

    def test_batch_aggregation(self):
        runs = [_make_run(risk_index=0.3 + 0.1 * i) for i in range(5)]
        summary = compute_metrics(runs)
        assert summary.total_runs == 5
        assert 0 <= summary.mean_elr <= 1
        assert 0 <= summary.overall_asr <= 1
        assert summary.mean_risk_index > 0

    def test_to_dict_shape(self):
        runs = [_make_run()]
        summary = compute_metrics(runs)
        d = summary.to_dict()
        assert "total_runs" in d
        assert "mean_elr" in d
        assert "overall_asr" in d
        assert "clr_per_channel" in d
        assert "asr_by_family" in d


# ---------------------------------------------------------------------------
# Scenario generator — channel & injection-surface path coverage
# ---------------------------------------------------------------------------

class TestScenarioGenChannelPaths:
    """Exercise the per-channel disclosure branches in ScenarioGenerator._build_trace."""

    def test_tool_output_injection_surface(self):
        """F2.1 (injection_surface=tool_output) adds extra tool_call + tool_response events."""
        gen = ScenarioGenerator(
            vertical="finance",
            adversary_level=AdversaryLevel.A2,
            seed=10,
        )
        scenario = gen.generate("F2.1")
        channels = [e.channel_value for e in scenario.trace.events]
        # The tool_output path adds an extra tool_call and injected tool_response
        assert channels.count("tool_response") >= 2

    def test_inter_agent_message_channel(self):
        """Attack with primary_channel=inter_agent_message emits that event."""
        gen = ScenarioGenerator(
            vertical="healthcare",
            adversary_level=AdversaryLevel.A2,
            seed=5,
        )
        # F4.1 has primary_channel=C2 (inter_agent_message)
        scenario = gen.generate("F4.1")
        channels = [e.channel_value for e in scenario.trace.events]
        assert "inter_agent_message" in channels

    def test_tool_call_channel(self):
        """Attack with primary_channel=tool_call emits that event."""
        gen = ScenarioGenerator(
            vertical="finance",
            adversary_level=AdversaryLevel.A2,
            seed=7,
        )
        # F2.2 has primary_channel=C3 (tool_call)
        scenario = gen.generate("F2.2")
        channels = [e.channel_value for e in scenario.trace.events]
        assert "tool_call" in channels

    def test_shared_memory_channel(self):
        """Attack with primary_channel=shared_memory emits that event."""
        gen = ScenarioGenerator(
            vertical="hr",
            adversary_level=AdversaryLevel.A2,
            seed=8,
        )
        # F3.1 has primary_channel=C5 (shared_memory)
        scenario = gen.generate("F3.1")
        channels = [e.channel_value for e in scenario.trace.events]
        assert "shared_memory" in channels

    def test_log_channel(self):
        """Attack with primary_channel=log emits that event."""
        gen = ScenarioGenerator(
            vertical="healthcare",
            adversary_level=AdversaryLevel.A0,
            seed=9,
        )
        # F3.5 has primary_channel=C6 (log)
        scenario = gen.generate("F3.5")
        channels = [e.channel_value for e in scenario.trace.events]
        assert "log" in channels

    def test_generated_file_channel(self):
        """Attack with primary_channel=generated_file emits that event."""
        gen = ScenarioGenerator(
            vertical="healthcare",
            adversary_level=AdversaryLevel.A0,
            seed=11,
        )
        # F3.4 has primary_channel=C7 (generated_file)
        scenario = gen.generate("F3.4")
        channels = [e.channel_value for e in scenario.trace.events]
        assert "generated_file" in channels

    def test_to_dict_unknown_family_fallback(self):
        """AdversarialScenario.to_dict falls back to 'unknown' for a fabricated attack id."""
        from agentleak.core.attacks import AdversaryLevel, AttackChannel
        from agentleak.core.trace import Trace
        from agentleak.generators.scenario_gen import AdversarialScenario
        from agentleak.generators.vault import generate_vault

        fake_class = AttackClass(
            id="ZZZFAKE",
            name="Fake",
            description="Fake attack class not in any family",
            adversary_level=AdversaryLevel.A0,
            primary_channel=AttackChannel.C1,
            injection_surface="user_message",
            payload_template="test",
        )
        vault = generate_vault("healthcare")
        trace = Trace(run_id="r")
        scenario = AdversarialScenario(
            scenario_id="fake_scenario",
            vertical="healthcare",
            attack_class=fake_class,
            vault=vault,
            trace=trace,
            expected_leaks=[],
        )
        d = scenario.to_dict()
        assert d["attack_family"] == "unknown"
