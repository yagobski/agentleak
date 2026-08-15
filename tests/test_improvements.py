# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Regression tests for detection-quality improvements.

These lock in behaviour discovered during an end-to-end dogfood of a real
LangGraph agent: false positives on env-reads, low recall on realistic clinical
PHI, key-name-blind detection, and silent degradation of optional tiers.
"""

from __future__ import annotations

from agentleak.detectors.healthcare import HealthcareDetector
from agentleak.detectors.secrets import SecretsDetector


def _types(matches):
    return {m.data_type for m in matches}


# ---------------------------------------------------------------------------
# Slice 1 — env-reads are not hardcoded secrets, real literals still are
# ---------------------------------------------------------------------------

def test_env_read_is_not_a_secret_assignment():
    sd = SecretsDetector()
    line = 'API_KEY = os.environ.get("OPENROUTER_API_KEY", "")'
    assert "secret_assignment" not in _types(sd.detect(line))


def test_getenv_variants_are_not_secrets():
    sd = SecretsDetector()
    for line in [
        'token = os.getenv("SLACK_TOKEN")',
        'secret = getenv("APP_SECRET")',
        'password = config.get("db_password")',
        'api_key = settings.API_KEY',
    ]:
        assert "secret_assignment" not in _types(sd.detect(line)), line


def test_real_literal_secret_is_still_caught():
    sd = SecretsDetector()
    line = 'api_key = "sk-realKey1234567890abcdef"'
    assert "secret_assignment" in _types(sd.detect(line))


# ---------------------------------------------------------------------------
# Slice 2 — healthcare recall on realistic clinical PHI
# ---------------------------------------------------------------------------

def test_spaced_nam_health_identifier_is_caught():
    hd = HealthcareDetector()
    assert "health_identifier" in _types(hd.detect("health_id: NAM TREM 8842 0197"))


def test_oncology_diagnosis_is_caught():
    hd = HealthcareDetector()
    assert "health_condition" in _types(hd.detect("Stage II colorectal carcinoma"))


def test_chemo_regimen_is_caught():
    hd = HealthcareDetector()
    assert "medication" in _types(hd.detect("regimen FOLFOX with oxaliplatin"))


def test_existing_healthcare_terms_still_caught():
    hd = HealthcareDetector()
    types = _types(hd.detect("Patient has diabetes on insulin"))
    assert {"health_condition", "medication"} <= types


# ---------------------------------------------------------------------------
# Slice 3 — key-name-aware sensitivity (structured content)
# ---------------------------------------------------------------------------

def test_keyname_detector_flags_sensitive_keys_generically():
    from agentleak.detectors.keyname import SensitiveKeyDetector
    kd = SensitiveKeyDetector()
    text = 'diagnosis: Something Rare Syndrome | medication: ExperimentalDrug-X'
    types = _types(kd.detect(text))
    assert "health_condition" in types
    assert "medication" in types


def test_keyname_detector_handles_json_quoted_keys():
    from agentleak.detectors.keyname import SensitiveKeyDetector
    kd = SensitiveKeyDetector()
    text = '{"ssn": "123-45-6789", "account_number": "ACC-99812"}'
    types = _types(kd.detect(text))
    assert "ssn" in types
    assert "account_number" in types


def test_keyname_detector_ignores_empty_and_placeholder_values():
    from agentleak.detectors.keyname import SensitiveKeyDetector
    kd = SensitiveKeyDetector()
    assert kd.detect('address: ') == []
    assert kd.detect('salary: REDACTED') == []
    assert kd.detect('ssn: null') == []


def test_keyname_recall_via_full_runner_on_clinical_leak():
    """The end-to-end false-negative from the dogfood: a cancer diagnosis +
    chemo drug leaked through internal channels must NOT score a clean pass."""
    from agentleak import AgentLeakRunner, Trace
    t = Trace(run_id="clinical")
    t.add_event(channel="shared_memory",
                content={"diagnosis": "Stage II colorectal carcinoma",
                         "medication": "FOLFOX (oxaliplatin + 5-FU)"})
    t.add_event(channel="final_output", content="A follow-up appointment is recommended.")
    result = AgentLeakRunner().analyze(t)
    assert result.privacy_score < 100
    assert result.score.risk_index > 0


# ---------------------------------------------------------------------------
# Slice 4 — fail loud when a requested detection tier can't run
# ---------------------------------------------------------------------------

def _clinical_trace():
    from agentleak import Trace
    t = Trace(run_id="degraded")
    t.add_event(channel="shared_memory",
                content={"diagnosis": "Stage II colorectal carcinoma"})
    t.add_event(channel="final_output", content="Follow-up recommended.")
    return t


def test_hybrid_without_api_key_is_flagged_degraded(monkeypatch):
    from agentleak import AgentLeakRunner
    from agentleak.core.config import Config
    monkeypatch.delenv("AGENTLEAK_MISSING_KEY", raising=False)
    cfg = Config.model_validate({
        "detection": {
            "mode": "hybrid",
            "llm_judge": {"enabled": True, "api_key_env": "AGENTLEAK_MISSING_KEY",
                          "base_url": "https://x", "model": "m"},
        }
    })
    result = AgentLeakRunner(cfg).analyze(_clinical_trace())
    assert result.degraded is True
    assert any("llm" in w.lower() or "judge" in w.lower() for w in result.warnings)
    # warnings must survive serialization so hosted/CI consumers see them
    assert result.to_dict().get("warnings")


def test_fast_mode_is_not_degraded():
    from agentleak import AgentLeakRunner
    result = AgentLeakRunner().analyze(_clinical_trace())
    assert result.degraded is False
    assert result.warnings == []


def test_variable_reference_is_not_a_secret_assignment():
    sd = SecretsDetector()
    # Passing a constant/variable to a kwarg is a reference, not a literal.
    assert "secret_assignment" not in _types(sd.detect("api_key=API_KEY, temperature=0"))
    assert "secret_assignment" not in _types(sd.detect("token = ACCESS_TOKEN"))


def test_unquoted_lowercase_trace_secret_still_flagged():
    sd = SecretsDetector()
    # A real leaked value in a trace/log line (not code) must still be caught.
    assert "secret_assignment" in _types(sd.detect("password: hunter2swordfish"))
