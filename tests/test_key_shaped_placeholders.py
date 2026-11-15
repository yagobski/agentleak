# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A provider prefix followed by filler is a placeholder, not a credential.

These strings are built at run time. Written out in a fixture file they have
the exact shape of a live key, and GitHub push protection refuses the commit,
which is why `scripts/detection_hard_negatives.json` spells its Stripe example
with angle brackets instead.
"""
import pytest

from agentleak.detectors.secrets import SecretsDetector


@pytest.mark.parametrize(
    "text",
    [
        "stripe_key = sk_live_" + "X" * 24,
        "stripe_key = sk_live_" + "x" * 24,
        "stripe_key = sk_live_<your-secret-key>",
    ],
)
def test_filler_after_a_provider_prefix_is_not_a_secret(text: str) -> None:
    assert SecretsDetector().detect(text) == []
