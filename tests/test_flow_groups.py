# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Groups in flow rules: fewer lines, and no rule that misses a new type.

`contextual-integrity.md` listed grouping as missing: a policy for thirty
servers was thirty rules, and a rule covering every credential named ten types
and missed the eleventh the day a detector added it.
"""

from __future__ import annotations

import pytest

from agentleak.core.config import Config
from agentleak.core.contextual_integrity import BUILTIN_TYPE_GROUPS, parse_flow_rules
from agentleak.core.transforms import CREDENTIAL_TYPES
from agentleak.defenses.gateway import Action, Gateway


def test_recipient_group_expands():
    (rule,) = parse_flow_rules(
        [{"data_type": "email", "to": "group:third-parties", "deny": True}],
        {"third-parties": ["analytics", "ads"]},
    )
    assert rule.recipients == ("analytics", "ads")


def test_credentials_group_follows_the_detectors():
    assert set(CREDENTIAL_TYPES) <= set(BUILTIN_TYPE_GROUPS["credentials"])


def test_unknown_group_fails_at_config_load():
    with pytest.raises(ValueError, match="unknown group"):
        Config.from_dict({"privacy_policy": {"flows": [{"data_type": "email", "to": "group:nope"}]}})


def test_groups_in_config_reach_the_gate_and_the_proxy():
    cfg = Config.from_dict({"privacy_policy": {
        "groups": {"third-parties": ["analytics"]},
        "flows": [{"data_type": "group:credentials", "to": "group:third-parties", "deny": True}],
    }})
    gw = Gateway(flows=cfg.privacy_policy.flows, groups=cfg.privacy_policy.groups)
    blocked = gw.check({"dsn": "postgres://app:pw@db.internal/prod"}, recipient="analytics")
    allowed = gw.check({"dsn": "postgres://app:pw@db.internal/prod"}, recipient="warehouse")
    assert blocked.action == Action.BLOCK
    assert allowed.action == Action.ALLOW
