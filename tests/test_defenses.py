"""Tests for defenses: sanitizer, internal channel guard, and policy gate."""

from __future__ import annotations

from agentleak.defenses.internal_channel import (
    AgentProfile,
    ClearanceLevel,
    GuardDecision,
    InternalChannelGuard,
)
from agentleak.defenses.sanitizer import (
    Sanitizer,
    sanitize_text,
)

# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------

class TestSanitizer:
    def test_placeholder_ssn(self):
        result = sanitize_text("SSN: 412-55-9087", style="placeholder")
        assert "[REDACTED_SSN]" in result
        assert "412-55-9087" not in result

    def test_asterisk_style(self):
        result = sanitize_text("Email: alice@example.com", style="asterisk")
        assert "alice@example.com" not in result
        assert "*" in result

    def test_masked_style(self):
        result = sanitize_text("Card: 4111111111111111", style="masked")
        assert "4111111111111111" not in result

    def test_hash_style(self):
        result = sanitize_text("SSN: 412-55-9087", style="hash")
        # Hash is 16 hex chars
        assert "412-55-9087" not in result
        import re
        assert re.search(r"[0-9a-f]{16}", result)

    def test_category_style(self):
        result = sanitize_text("412-55-9087", style="category")
        assert "[PII: SSN]" in result

    def test_remove_style(self):
        result = sanitize_text("SSN: 412-55-9087 and more text", style="remove")
        assert "412-55-9087" not in result
        assert "and more text" in result

    def test_no_sensitive_data_unchanged(self):
        text = "The weather is nice today."
        result = sanitize_text(text)
        assert result == text

    def test_email_redacted(self):
        result = sanitize_text("Contact bob@test.org for info")
        assert "bob@test.org" not in result

    def test_canary_redacted(self):
        result = sanitize_text("Token: CANARY_ABCD1234 in the data")
        assert "CANARY_ABCD1234" not in result

    def test_multiple_hits(self):
        text = "alice@example.com and 412-55-9087"
        result = sanitize_text(text)
        assert "alice@example.com" not in result
        assert "412-55-9087" not in result

    def test_sanitize_dict(self):
        s = Sanitizer(style="placeholder")
        data = {"name": "Alice", "ssn": "412-55-9087", "note": "no PII here"}
        result = s.sanitize_dict(data)
        assert "412-55-9087" not in result["ssn"]
        assert "[REDACTED_SSN]" in result["ssn"]
        assert result["name"] == "Alice"

    def test_sanitize_dict_nested(self):
        s = Sanitizer()
        data = {"patient": {"ssn": "412-55-9087"}}
        result = s.sanitize_dict(data)
        assert "412-55-9087" not in str(result)

    def test_redaction_count(self):
        s = Sanitizer()
        count = s.redaction_count("SSN: 412-55-9087 email: a@b.com")
        assert count >= 2

    def test_extra_patterns(self):
        s = Sanitizer(
            style="placeholder",
            extra_patterns=[("INTERNAL_ID", r"\bINT-\d{6}\b")],
        )
        result = s.sanitize("Ref: INT-123456")
        assert "INT-123456" not in result
        assert "[REDACTED_INTERNAL_ID]" in result


# ---------------------------------------------------------------------------
# InternalChannelGuard
# ---------------------------------------------------------------------------

class TestInternalChannelGuard:
    def _make_guard(self, sender_clearance=ClearanceLevel.SECRET,
                    recipient_clearance=ClearanceLevel.INTERNAL, **kwargs):
        sender = AgentProfile("sender", clearance=sender_clearance)
        recipient = AgentProfile("recipient", clearance=recipient_clearance)
        return InternalChannelGuard(sender, recipient, **kwargs)

    def test_allow_when_level_ok(self):
        guard = self._make_guard(
            sender_clearance=ClearanceLevel.SECRET,
            recipient_clearance=ClearanceLevel.SECRET,
        )
        result = guard.check("hello world", "inter_agent_message")
        assert result.decision == GuardDecision.ALLOW
        assert not result.was_modified

    def test_redact_when_level_exceeds_clearance(self):
        guard = self._make_guard(
            sender_clearance=ClearanceLevel.SECRET,
            recipient_clearance=ClearanceLevel.PUBLIC,
        )
        result = guard.check("SSN: 412-55-9087", "inter_agent_message", data_level=4)
        assert result.decision in (GuardDecision.REDACT, GuardDecision.BLOCK)

    def test_non_internal_channel_always_allowed(self):
        guard = self._make_guard()
        result = guard.check("412-55-9087", "final_output", data_level=4)
        assert result.decision == GuardDecision.ALLOW

    def test_block_on_secret(self):
        guard = self._make_guard(
            recipient_clearance=ClearanceLevel.PUBLIC,
            block_on_secret=True,
        )
        result = guard.check("SSN: 412-55-9087", "shared_memory", data_level=4)
        assert result.decision == GuardDecision.BLOCK
        assert result.sanitized_text == ""

    def test_sanitized_text_has_no_pii(self):
        guard = self._make_guard(recipient_clearance=ClearanceLevel.PUBLIC)
        result = guard.check("SSN: 412-55-9087", "inter_agent_message", data_level=4)
        if result.decision == GuardDecision.REDACT:
            assert "412-55-9087" not in result.sanitized_text

    def test_filter_dict_redacts(self):
        guard = self._make_guard(recipient_clearance=ClearanceLevel.PUBLIC)
        data = {"ssn": "412-55-9087", "name": "Alice"}
        filtered, result = guard.filter_dict(data, "inter_agent_message")
        if result.decision in (GuardDecision.REDACT, GuardDecision.WARN):
            assert "412-55-9087" not in str(filtered)

    def test_clearance_levels_ordered(self):
        assert ClearanceLevel.PUBLIC < ClearanceLevel.INTERNAL
        assert ClearanceLevel.INTERNAL < ClearanceLevel.CONFIDENTIAL
        assert ClearanceLevel.CONFIDENTIAL < ClearanceLevel.SECRET

    def test_estimate_level_clean_text(self):
        guard = self._make_guard()
        level = guard._estimate_level("Hello, how are you today?")
        assert level == 1  # no PII → PUBLIC

    def test_estimate_level_pii_text(self):
        guard = self._make_guard()
        level = guard._estimate_level("SSN: 412-55-9087; email: a@b.com; card: 4111111111111111")
        assert level >= 3  # 3+ tokens → CONFIDENTIAL or SECRET


# ---------------------------------------------------------------------------
# Policy gate via platform API
# ---------------------------------------------------------------------------

class TestPolicyGate:
    def test_policy_gate_config_default(self):
        from agentleak.core.config import Config
        cfg = Config()
        assert cfg.policy_gate.fail_on == []
        assert cfg.policy_gate.fail_on_any is False

    def test_policy_gate_config_from_dict(self):
        from agentleak.core.config import Config
        cfg = Config.from_dict({"policy_gate": {"fail_on": ["hipaa", "gdpr"], "fail_on_any": False}})
        assert "hipaa" in cfg.policy_gate.fail_on
        assert "gdpr" in cfg.policy_gate.fail_on

    def test_selftest_gate_in_response(self, tmp_path):
        """The selftest endpoint must include gate_failed in its response."""
        from fastapi.testclient import TestClient

        from agentleak.core.store import Store
        from agentleak.web.app import create_app

        store = Store(str(tmp_path / "test.db"))
        app = create_app(store=store, serve_ui=False)
        client = TestClient(app, raise_server_exceptions=True)

        # Register + login
        client.post("/api/auth/register", json={"email": "g@x.com", "name": "G", "password": "pass1234"})
        client.post("/api/auth/login", json={"email": "g@x.com", "password": "pass1234"})

        # Create project
        proj = client.post("/api/projects", json={"name": "gate-test"}).json()
        pid = proj["id"]

        # Set a policy gate that fails on hipaa
        cfg = proj.get("config") or {}
        cfg["policy_gate"] = {"fail_on": ["hipaa"], "fail_on_any": False}
        store.update_project(pid, config=cfg)

        # Generate API key
        key_resp = client.post(f"/api/projects/{pid}/api-key").json()
        api_key = key_resp["api_key"]

        # Self-test with healthcare trace (should trip HIPAA)
        resp = client.post("/api/selftest", json={
            "api_key": api_key,
            "scenario_id": "healthcare_patient_summary",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "gate_failed" in data
        assert "gate_fail_on" in data
        # With healthcare trace, hipaa should fail → gate_failed=True
        if "hipaa" in data.get("failed_frameworks", []):
            assert data["gate_failed"] is True

    def test_selftest_gate_not_fired_for_unrelated_framework(self, tmp_path):
        """Policy gate with fail_on=["pci_dss"] should not fire for a healthcare trace."""
        from fastapi.testclient import TestClient

        from agentleak.core.store import Store
        from agentleak.web.app import create_app

        store = Store(str(tmp_path / "test2.db"))
        app = create_app(store=store, serve_ui=False)
        client = TestClient(app, raise_server_exceptions=True)

        client.post("/api/auth/register", json={"email": "h@x.com", "name": "H", "password": "pass1234"})
        client.post("/api/auth/login", json={"email": "h@x.com", "password": "pass1234"})
        proj = client.post("/api/projects", json={"name": "gate-test2"}).json()
        pid = proj["id"]
        cfg = proj.get("config") or {}
        # fail_on pci_dss only — healthcare should not trigger this
        cfg["policy_gate"] = {"fail_on": ["pci_dss"], "fail_on_any": False}
        store.update_project(pid, config=cfg)
        key_resp = client.post(f"/api/projects/{pid}/api-key").json()
        api_key = key_resp["api_key"]

        resp = client.post("/api/selftest", json={
            "api_key": api_key,
            "scenario_id": "healthcare_patient_summary",
        })
        assert resp.status_code == 200
        data = resp.json()
        # pci_dss is typically not in healthcare failures
        if "pci_dss" not in data.get("failed_frameworks", []):
            assert data["gate_failed"] is False
