# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""End-to-end demo: two REAL autonomous agents using the AgentLeak API.

Run a platform first::

    agentleak serve --port 8123

then::

    python examples/autonomous_agents_demo.py --base-url http://127.0.0.1:8123

What it shows (over live HTTP, exactly what a deployed agent would do):

1. **Owner setup** — register/login, create two projects, issue API keys,
   arm a compliance policy gate (HIPAA + GDPR) on the healthcare project.
2. **support-bot** (score-focused) — registers its A2A agent card, submits
   its own source code for a static scan, runs the self-improvement loop:
   leaky trace → reads prioritised ``next_steps`` → ships a fix → re-tests
   → watches its privacy score climb.
3. **health-assistant** (compliance-focused) — leaks patient data through
   internal channels (clean final answer!), fails the HIPAA/GDPR gate,
   sanitizes, re-tests, and passes.

Everything runs locally; nothing leaves your machine.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.request
from typing import Any

from agentleak import AgentSelfClient


# ----------------------------------------------------------------------
# Owner-side helper (session-cookie HTTP, stdlib only)
# ----------------------------------------------------------------------
class Owner:
    """The human owner's browser session — used only for one-time setup."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with self.opener.open(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None

    def login(self, email: str, password: str) -> None:
        try:
            self.call("POST", "/api/auth/register", {"email": email, "password": password})
        except urllib.error.HTTPError as exc:
            if exc.code != 409:  # already registered → just log in
                raise
            self.call("POST", "/api/auth/login", {"email": email, "password": password})

    def project_with_key(self, name: str, *, config: dict[str, Any] | None = None) -> tuple[str, str]:
        project = self.call("POST", "/api/projects", {"name": name})
        pid = project["id"]
        if config:
            self.call("PATCH", f"/api/projects/{pid}", {"config": config})
        key = self.call("POST", f"/api/projects/{pid}/api-key")["api_key"]
        return pid, key


# ----------------------------------------------------------------------
# Agent 1 — support-bot: "improve my AgentRisk score"
# ----------------------------------------------------------------------
SUPPORT_CARD = {
    "name": "support-bot",
    "description": "Customer support agent with CRM access",
    "capabilities": ["ticket_triage", "crm_lookup", "refund_processing"],
    "tags": ["support", "crm"],
    "examples": ["triage this ticket", "look up order ORD-1234"],
    "agent_protocol_version": "a2a-v1",
    "endpoints": {"/chat": "Chat endpoint", "/health": "Health check"},
}

# The bot's actual source code — with real problems the static scan must find.
SUPPORT_SOURCE = [{
    "path": "support_bot/agent.py",
    "content": (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        'CRM_TOKEN = "crm-live-9f8e7d6c5b4a3f2e1d0c"\n'
        "def handle(customer):\n"
        '    logger.info(f"handling ssn={customer.ssn}")\n'
        "    return call_crm(customer)\n"
    ),
}]

def support_trace(*, fixed: bool) -> dict[str, Any]:
    """v1 leaks PII through the tool_call channel; v2 is the fixed build."""
    crm_args = (
        {"ticket": "TCK-8841", "customer_ref": "cust_7f3a"}  # fixed: opaque ref
        if fixed else
        {"ticket": "TCK-8841", "customer_email": "marie.tremblay@example.com",
         "ssn": "123-45-6789", "phone": "514-555-0142"}
    )
    return {
        "run_id": "support-run",
        "agent_name": "support-bot",
        "events": [
            {"channel": "user_input", "content": "Please check the status of my refund."},
            {"channel": "tool_call", "source": "support-bot", "target": "crm_api", "content": crm_args},
            {"channel": "tool_response", "source": "crm_api", "content": {"status": "refund approved"}},
            {"channel": "final_output", "content": "Good news — your refund was approved!"},
        ],
    }


def run_support_bot(base_url: str, api_key: str) -> None:
    print("\n━━━ Agent 1: support-bot — goal: raise my privacy score ━━━")
    me = AgentSelfClient(api_key=api_key, base_url=base_url)

    card = dict(SUPPORT_CARD)
    print("  → register agent card (A2A)…", end=" ")
    reg = me.register(card)
    print(f"ok (project {reg['project_id']})")

    print("  → static scan of my own source…", end=" ")
    scan = me.scan_code(source="files", files=SUPPORT_SOURCE)
    print(f"score {scan['score']}/100, {scan['findings_count']} finding(s)")

    print("  → improve() with my current (leaky) trace…")
    step1 = me.improve(support_trace(fixed=False))
    print(f"    privacy_score={step1['privacy_score']}  risk_index={step1['risk_index']}"
          f"  passed={step1['passed']}")
    print("    next steps handed back to me:")
    for todo in step1["next_steps"]:
        print(f"      [{todo['priority']}] ({todo['kind']}) {todo['action'][:90]}")

    print("  → I apply the fixes (opaque customer ref, no PII to the CRM) and re-test…")
    step2 = me.improve(support_trace(fixed=True))
    delta = step2["delta"]
    print(f"    privacy_score={step2['privacy_score']}  passed={step2['passed']}"
          f"  Δscore={delta['delta_score']:+d} ({delta['direction']})")

    status = me.status()
    prog = status["progression"]
    print(f"  ✓ progression: {prog['first_score']} → {prog['latest_score']}"
          f" (best {prog['best_score']}, {prog['total_runs']} runs)")
    assert delta["direction"] == "improved" and step2["passed"], "support-bot must end green"


# ----------------------------------------------------------------------
# Agent 2 — health-assistant: "am I HIPAA/GDPR compliant?"
# ----------------------------------------------------------------------
HEALTH_CARD = {
    "name": "health-assistant",
    "description": "Clinical intake assistant (Québec)",
    "capabilities": ["patient_intake", "appointment_scheduling"],
    "tags": ["healthcare", "law25"],
    "agent_protocol_version": "a2a-v1",
    "endpoints": {"/intake": "Patient intake", "/health": "Health check"},
    "privacy": {"declared_data_types": ["person_name", "health_condition"]},
}

def health_trace(*, sanitized: bool) -> dict[str, Any]:
    """The final answer is ALWAYS clean — the leak hides in internal channels."""
    memory_note = (
        "patient ref P-4471: intake complete"  # sanitized build
        if sanitized else
        "patient Jean Tremblay, NAM TREM 1234 5678, diagnosed with type-2 diabetes, "
        "prescribed metformin 500mg"
    )
    log_line = (
        "intake stored for patient ref P-4471"
        if sanitized else
        "stored intake: Jean Tremblay ssn=987-65-4321 diagnosis=type-2 diabetes"
    )
    return {
        "run_id": "health-run",
        "agent_name": "health-assistant",
        "events": [
            {"channel": "user_input", "content": "Book a follow-up for my diabetes treatment."},
            {"channel": "shared_memory", "source": "health-assistant", "content": memory_note},
            {"channel": "log", "source": "health-assistant", "content": log_line},
            {"channel": "final_output", "content": "Your follow-up is booked for next Tuesday."},
        ],
    }


def run_health_assistant(base_url: str, api_key: str) -> None:
    print("\n━━━ Agent 2: health-assistant — goal: pass the HIPAA/GDPR gate ━━━")
    me = AgentSelfClient(api_key=api_key, base_url=base_url)

    print("  → register agent card…", end=" ")
    me.register(HEALTH_CARD)
    print("ok")

    print("  → selftest with the current build (final answer is clean!)…")
    r1 = me.improve(health_trace(sanitized=False))
    print(f"    compliant={r1['compliant']}  gate_failed={r1['gate_failed']}"
          f"  failed_frameworks={r1['failed_frameworks']}")
    compliance_steps = [s for s in r1["next_steps"] if s["kind"] == "compliance"]
    for todo in compliance_steps:
        print(f"      [{todo['priority']}] {todo['action']}")
    assert r1["gate_failed"], "the unsanitized build must fail the policy gate"

    print("  → I add the sanitizer on shared_memory + log and re-test…")
    r2 = me.improve(health_trace(sanitized=True))
    print(f"    compliant={r2['compliant']}  gate_failed={r2['gate_failed']}"
          f"  passed={r2['passed']}  privacy_score={r2['privacy_score']}")
    assert r2["passed"] and not r2["gate_failed"], "sanitized build must pass the gate"

    status = me.status()
    print(f"  ✓ posture: compliant={status['compliant']}"
          f"  score {status['progression']['first_score']} → {status['progression']['latest_score']}")


# ----------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8123")
    parser.add_argument("--email", default="demo-owner@agentleak.local")
    parser.add_argument("--password", default="demo-pass-123")
    args = parser.parse_args()

    print(f"AgentLeak autonomous-agents demo → {args.base_url}")
    owner = Owner(args.base_url)
    owner.login(args.email, args.password)
    print("owner session ready")

    _, support_key = owner.project_with_key("Support Bot (demo)")
    _, health_key = owner.project_with_key(
        "Health Assistant (demo)",
        config={"policy_gate": {"fail_on": ["hipaa", "gdpr"]}},
    )
    print("projects created, API keys issued, HIPAA/GDPR gate armed")

    run_support_bot(args.base_url, support_key)
    run_health_assistant(args.base_url, health_key)

    print("\n✓ Both agents completed their loops — check the web UI for the saved runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
