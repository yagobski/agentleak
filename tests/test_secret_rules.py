# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Provider token rules: each fires on its format and stays quiet on lookalikes.

Every token here is synthetic, generated at run time by
``scripts/secret_samples.py`` with prefixes split by concatenation, so no
token-shaped string is committed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from agentleak.core.agentrisk import level_for
from agentleak.core.runner import analyze
from agentleak.core.trace import Trace
from agentleak.detectors.secret_rules import RULES
from agentleak.detectors.secrets import SecretsDetector

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "secret_samples.py"
_spec = importlib.util.spec_from_file_location("secret_samples", SCRIPT)
assert _spec and _spec.loader
secret_samples = importlib.util.module_from_spec(_spec)
sys.modules["secret_samples"] = secret_samples
_spec.loader.exec_module(secret_samples)

SAMPLES = secret_samples.samples(per_rule=2)


@pytest.mark.parametrize("rule, data_type, token", SAMPLES, ids=[s[0] + str(i) for i, s in enumerate(SAMPLES)])
def test_every_format_is_found_with_its_type(rule, data_type, token) -> None:
    found = SecretsDetector().detect(f"config value {token} end")
    assert any(m.data_type == data_type and token in m.matched_value or m.matched_value in token
               for m in found if m.data_type == data_type), [(m.data_type, m.rule) for m in found]


def test_every_provider_rule_has_a_sample() -> None:
    sampled = set(secret_samples.BUILDERS)
    missing = {r.rule for r in RULES} - sampled - {"putty_private_key"}
    assert not missing, missing


def test_rule_ids_are_unique() -> None:
    ids = [r.rule for r in RULES]
    assert len(ids) == len(set(ids))


def test_every_new_credential_is_level_4() -> None:
    from agentleak.core.detector import Severity

    for rule in RULES:
        severity = Severity.HIGH if rule.high_only else Severity.CRITICAL
        assert level_for(rule.data_type, severity) == 4, rule.rule


@pytest.mark.parametrize(
    "text",
    [
        "export OPENAI_API_KEY=sk-" + "x" * 24,
        "GITHUB_TOKEN=gh" + "p_" + "x" * 36,
        "stripe_key = sk" + "_live_" + "X" * 24,
        "api_key: <your-api-key>",
        'token = "YOUR_API_TOKEN"',
        "password: ********",
        "redis://localhost:6379/0",
        "DATABASE_URL=postgres://localhost:5432/app",
        "private_key: see the team vault",
        "client_key: production-default",
        "sha256 " + "ab" * 32,
    ],
)
def test_placeholders_and_lookalikes_are_not_secrets(text) -> None:
    assert SecretsDetector().detect(text) == [], text


def test_finding_carries_the_rule_id() -> None:
    token = secret_samples.BUILDERS["gitlab_token"][1](__import__("random").Random(1))
    events = [{"event_id": "e1", "channel": "log", "source": "a", "target": "b",
               "content": f"deploying with {token}"}]
    trace = Trace.model_validate({"run_id": "r", "agent_name": "a", "events": events})
    rules = {f.metadata.get("rule") for f in analyze(trace).findings}
    assert "gitlab_token" in rules


def test_multilingual_password_assignment() -> None:
    for text in ("mot_de_passe = Tr0ub4dor&3x", "contraseña: Tr0ub4dor&3x", "Passwort=Tr0ub4dor&3x",
                 "senha: Tr0ub4dor&3x"):
        assert {m.data_type for m in SecretsDetector().detect(text)} == {"secret_assignment"}, text


def test_key_value_connection_string() -> None:
    text = "Server=db.internal;Database=app;User Id=app;Pass" + "word=Hx81kq2Lz0;"
    assert "connection_string" in {m.data_type for m in SecretsDetector().detect(text)}
