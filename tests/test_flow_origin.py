# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Judge a flow by where the data came from, however many agents it crossed.

Every rule before this judged one hop: sender, recipient, purpose. In a
multi-agent run the hop that reaches the sink is often innocent-looking — a
summariser posting to analytics — and what makes it a leak is that the value
started in the medical record three agents earlier.
"""

from __future__ import annotations

from agentleak.core.config import Config
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.trace import Trace

POLICY = {"privacy_policy": {
    "groups": {"external": ["analytics", "ads"]},
    "flows": [{"data_type": "group:health", "origin": "ehr_database",
               "to": "group:external", "deny": True}],
}}


def _trace(first_event: dict) -> Trace:
    events = [
        first_event,
        {"event_id": "e2", "channel": "inter_agent_message", "source": "planner",
         "target": "summarizer", "content": "Follow-up for a patient with diabetes."},
        {"event_id": "e3", "channel": "tool_call", "source": "summarizer",
         "target": "analytics", "content": {"topic": "diabetes follow-up"}},
    ]
    return Trace.model_validate({"run_id": "o", "agent_name": "planner", "events": events})


def _violations(trace: Trace):
    result = AgentLeakRunner(Config.from_dict(POLICY)).analyze(trace)
    policy = result.policy_evaluation.to_dict()
    return policy.get("flows", {}).get("violations", [])


EHR = {"event_id": "e1", "channel": "tool_response", "source": "ehr_database",
       "target": "planner", "content": {"diagnosis": "diabetes"}}
USER = {"event_id": "e1", "channel": "user_input", "source": "user",
        "target": "planner", "content": "I have diabetes, can you track my follow-ups?"}


def test_three_hops_from_the_record_is_a_violation_with_its_path():
    (violation,) = _violations(_trace(EHR))
    assert violation["recipient"] == "analytics"
    assert violation["origin"] == "ehr_database"
    assert violation["path"] == ["ehr_database", "planner", "summarizer", "analytics"]


def test_the_same_value_volunteered_by_the_user_is_not():
    assert _violations(_trace(USER)) == []


def test_findings_carry_origin_and_path():
    result = AgentLeakRunner().analyze(_trace(EHR))
    last = [f for f in result.findings if f.event_id == "e3"]
    assert last and last[0].metadata["origin"] == "ehr_database"
