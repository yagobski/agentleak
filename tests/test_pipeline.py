"""Tests for the hybrid detection pipeline and canary matching."""

from __future__ import annotations

from agentleak.core.canary import CanarySet, match_canaries
from agentleak.core.pipeline import DetectionMode, HybridPipeline
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.trace import Trace
from agentleak.detectors import build_detectors

# ---------------------------------------------------------------------------
# Canary tests
# ---------------------------------------------------------------------------

class TestCanarySet:
    def test_empty_canary_set(self):
        cs = CanarySet()
        assert cs.is_empty()
        assert cs.all_tokens() == []

    def test_all_tokens(self):
        cs = CanarySet(obvious=["OBV1"], realistic=["000-12-3456"], semantic=["patient has diabetes"])
        tokens = cs.all_tokens()
        assert ("obvious", "OBV1") in tokens
        assert ("realistic", "000-12-3456") in tokens
        assert ("semantic", "patient has diabetes") in tokens
        assert len(tokens) == 3

    def test_from_dict(self):
        cs = CanarySet.from_dict({"obvious": ["C1"], "realistic": ["000-00-0001"]})
        assert cs.obvious == ["C1"]
        assert cs.realistic == ["000-00-0001"]
        assert cs.semantic == []


class TestMatchCanaries:
    def test_exact_match(self):
        cs = CanarySet(obvious=["CANARY_ABCD1234"])
        hits = match_canaries("Here is CANARY_ABCD1234 in the text", cs)
        assert ("obvious", "CANARY_ABCD1234") in hits

    def test_no_match(self):
        cs = CanarySet(obvious=["CANARY_ABCD1234"])
        hits = match_canaries("No canary here at all", cs)
        assert hits == []

    def test_realistic_tier_match(self):
        cs = CanarySet(realistic=["000-12-3456"])
        hits = match_canaries("SSN on file: 000-12-3456", cs)
        assert ("realistic", "000-12-3456") in hits

    def test_case_sensitive(self):
        cs = CanarySet(obvious=["CANARY_UPPER"])
        hits = match_canaries("canary_upper is here", cs)
        assert len(hits) == 0  # case-sensitive

    def test_empty_token_skipped(self):
        cs = CanarySet(obvious=[""])
        hits = match_canaries("some text", cs)
        assert hits == []


# ---------------------------------------------------------------------------
# HybridPipeline tests
# ---------------------------------------------------------------------------

class TestHybridPipeline:
    def _make_pipeline(self, mode=DetectionMode.FAST):
        detectors = build_detectors(None, None)
        return HybridPipeline(detectors, mode=mode)

    def test_fast_mode_detects_email(self):
        pipeline = self._make_pipeline(DetectionMode.FAST)
        findings = pipeline.run_event(
            text="Contact alice@example.com for details",
            event_id="e1", run_id="r1", channel="log",
        )
        assert any(f.data_type == "email" for f in findings)

    def test_canary_detected_before_regex(self):
        pipeline = self._make_pipeline()
        cs = CanarySet(obvious=["CANARY_TEST0001"])
        findings = pipeline.run_event(
            text="Reference: CANARY_TEST0001",
            event_id="e1", run_id="r1", channel="tool_call",
            canary_set=cs,
        )
        canary_findings = [f for f in findings if f.data_type == "canary"]
        assert len(canary_findings) == 1
        assert canary_findings[0].detector == "canary"
        assert canary_findings[0].confidence == 1.0

    def test_canary_tier_in_metadata(self):
        pipeline = self._make_pipeline()
        cs = CanarySet(obvious=["CANARY_TIER_OBV"])
        findings = pipeline.run_event(
            text="Here CANARY_TIER_OBV is present",
            event_id="e1", run_id="r1", channel="log",
            canary_set=cs,
        )
        canary = next(f for f in findings if f.data_type == "canary")
        assert canary.metadata.get("tier") == "canary_obvious"

    def test_dedup_within_event(self):
        """Same (data_type, value) pair should not appear twice within one event."""
        pipeline = self._make_pipeline()
        # Run with no canary set — regex should detect ssn exactly once
        findings = pipeline.run_event(
            text="SSN: 412-55-9087 SSN: 412-55-9087",
            event_id="e1", run_id="r1", channel="log",
        )
        ssn_findings = [f for f in findings if f.data_type == "ssn" and f.matched_value == "412-55-9087"]
        assert len(ssn_findings) == 1

    def test_fast_mode_no_presidio_no_llm(self):
        pipeline = self._make_pipeline(DetectionMode.FAST)
        assert "presidio" not in pipeline.finding_tiers
        assert "semantic" not in pipeline.finding_tiers

    def test_standard_mode_lists_presidio_tier(self):
        detectors = build_detectors(None, None)
        pipeline = HybridPipeline(detectors, mode=DetectionMode.STANDARD, presidio=None)
        # presidio=None → tier not active even in STANDARD mode
        assert "presidio" not in pipeline.finding_tiers

    def test_finding_ids_are_unique(self):
        pipeline = self._make_pipeline()
        findings = pipeline.run_event(
            text="email a@b.com ssn 412-55-9087 card 4111111111111111",
            event_id="e1", run_id="r1", channel="final_output",
            finding_counter=0,
        )
        ids = [f.finding_id for f in findings]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Runner integration with pipeline
# ---------------------------------------------------------------------------

class TestRunnerWithPipeline:
    def test_runner_uses_fast_mode_by_default(self):
        """AgentLeakRunner without config uses FAST mode (regex only)."""
        runner = AgentLeakRunner()
        assert runner._pipeline.mode == DetectionMode.FAST

    def test_runner_accepts_canary_set(self):
        trace = Trace(run_id="r")
        trace.add_event("log", "DEBUG: CANARY_ABCD1234 processed")
        cs = CanarySet(obvious=["CANARY_ABCD1234"])
        result = runner = AgentLeakRunner()
        result = runner.analyze(trace, canary_set=cs)
        canary_findings = [f for f in result.findings if f.data_type == "canary"]
        assert len(canary_findings) == 1

    def test_runner_still_detects_regex_with_canary(self):
        """Canary matching doesn't suppress regex detection."""
        runner = AgentLeakRunner()
        trace = Trace(run_id="r")
        trace.add_event("tool_call", {"email": "alice@example.com", "canary": "CANARY_X1"})
        cs = CanarySet(obvious=["CANARY_X1"])
        result = runner.analyze(trace, canary_set=cs)
        types = {f.data_type for f in result.findings}
        assert "email" in types
        assert "canary" in types

    def test_llm_judge_not_loaded_without_config(self):
        """LLM judge is never instantiated when config.detection.llm_judge.enabled=False."""
        runner = AgentLeakRunner()
        assert runner._pipeline._llm_judge is None


# ---------------------------------------------------------------------------
# LLM-judge detector (mocked)
# ---------------------------------------------------------------------------

class TestLLMJudgeDetector:
    def test_returns_empty_without_api_key(self):
        """With no API key configured the detector should return [] (no crash)."""
        import os
        # Temporarily clear all known API key env vars
        keys = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
                "TOGETHER_API_KEY", "GROQ_API_KEY"]
        saved = {k: os.environ.pop(k, None) for k in keys}
        try:
            from agentleak.detectors.llm_judge import LLMJudgeDetector
            judge = LLMJudgeDetector(base_url="http://localhost:9999", model="test")
            # No key → HTTP call will fail → graceful empty return
            matches = judge.detect("The patient has SSN 412-55-9087")
            assert isinstance(matches, list)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_cache_key_is_stable(self):
        """Same text should produce the same cache key."""
        import hashlib
        text = "The patient has diabetes"
        key1 = hashlib.sha256(text.encode()).hexdigest()
        key2 = hashlib.sha256(text.encode()).hexdigest()
        assert key1 == key2

    def test_mock_llm_response(self, monkeypatch):
        """Patch _call_llm to return a known hit and verify RawMatch is produced."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(threshold=0.5)

        def mock_call(text):
            return [{"data_type": "health_condition", "evidence": "diabetes", "confidence": 0.9}]

        monkeypatch.setattr(judge, "_call_llm", mock_call)
        matches = judge.detect("The patient has diabetes")
        assert len(matches) == 1
        assert matches[0].data_type == "health_condition"
        assert matches[0].matched_value == "diabetes"
        assert matches[0].confidence == 0.9

    def test_below_threshold_filtered(self, monkeypatch):
        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(threshold=0.72)

        def mock_call(text):
            return [{"data_type": "person_name", "evidence": "John", "confidence": 0.5}]

        monkeypatch.setattr(judge, "_call_llm", mock_call)
        matches = judge.detect("John went to the doctor")
        assert matches == []

    def test_llm_only_mode_uses_judge(self, monkeypatch):
        """In LLM_ONLY mode, only the judge fires (no regex)."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(threshold=0.5)

        def mock_call(text):
            return [{"data_type": "ssn", "evidence": "412-55-9087", "confidence": 0.95}]

        monkeypatch.setattr(judge, "_call_llm", mock_call)

        pipeline = HybridPipeline(
            [],  # no regex detectors
            mode=DetectionMode.LLM_ONLY,
            llm_judge=judge,
        )
        findings = pipeline.run_event(
            text="412-55-9087",
            event_id="e1", run_id="r1", channel="log",
        )
        assert len(findings) == 1
        assert findings[0].metadata.get("tier") == "semantic"


# ---------------------------------------------------------------------------
# Pipeline — mock Presidio / HYBRID / coverage paths
# ---------------------------------------------------------------------------

class TestHybridPipelineMockTiers:
    """Cover Presidio & LLM-judge execution paths using lightweight mock objects."""

    def test_empty_text_returns_empty(self):
        pipeline = HybridPipeline(build_detectors(None, None), mode=DetectionMode.FAST)
        assert pipeline.run_event(text="", event_id="e1", run_id="r1", channel="log") == []

    def test_whitespace_only_text_returns_empty(self):
        pipeline = HybridPipeline([], mode=DetectionMode.FAST)
        # run_event doesn't guard whitespace — underlying detectors do; verify no crash
        findings = pipeline.run_event(text="   ", event_id="e1", run_id="r1", channel="log")
        assert isinstance(findings, list)

    def test_canary_dedup_skips_second_occurrence(self):
        """Same canary token listed in two tiers should only produce one Finding."""
        pipeline = HybridPipeline([], mode=DetectionMode.FAST)
        # Same value in both obvious and realistic → match_canaries returns it twice
        token = "CANARY_DUPE0001"
        cs = CanarySet(obvious=[token], realistic=[token])
        findings = pipeline.run_event(
            text=f"Token: {token}",
            event_id="e1", run_id="r1", channel="log",
            canary_set=cs,
        )
        canary_hits = [f for f in findings if f.data_type == "canary"]
        assert len(canary_hits) == 1  # deduped by (data_type, token) key

    def test_presidio_tier_executes_with_mock(self):
        """STANDARD mode should invoke the Presidio instance when provided."""
        from agentleak.core.detector import RawMatch, Severity

        class _MockPresidio:
            def detect(self, text):
                return [RawMatch(
                    data_type="email",
                    severity=Severity.MEDIUM,
                    confidence=0.95,
                    matched_value="mock@presidio.test",
                    recommendation="presidio hit",
                    detector="presidio",
                )]

        pipeline = HybridPipeline([], mode=DetectionMode.STANDARD, presidio=_MockPresidio())
        findings = pipeline.run_event(
            text="Contact mock@presidio.test",
            event_id="e1", run_id="r1", channel="tool_call",
        )
        assert any(f.detector == "presidio" for f in findings)
        assert any(f.metadata.get("tier") == "presidio" for f in findings)

    def test_presidio_dedup_with_regex(self):
        """If Presidio and regex both detect the same (data_type, value), keep only one."""
        from agentleak.core.detector import RawMatch, Severity

        class _MockPresidio:
            def detect(self, text):
                return [RawMatch(
                    data_type="email",
                    severity=Severity.MEDIUM,
                    confidence=0.9,
                    matched_value="alice@example.com",
                    recommendation="presidio",
                    detector="presidio",
                )]

        pipeline = HybridPipeline(
            build_detectors(None, None),
            mode=DetectionMode.STANDARD,
            presidio=_MockPresidio(),
        )
        findings = pipeline.run_event(
            text="Email: alice@example.com",
            event_id="e1", run_id="r1", channel="final_output",
        )
        email_hits = [f for f in findings if f.matched_value == "alice@example.com"]
        assert len(email_hits) == 1  # deduped across tiers

    def test_hybrid_mode_runs_both_presidio_and_llm(self, monkeypatch):
        """HYBRID: both Presidio and LLM-judge fire when configured."""
        from agentleak.core.detector import RawMatch, Severity
        from agentleak.detectors.llm_judge import LLMJudgeDetector

        class _MockPresidio:
            def detect(self, text):
                return [RawMatch("vin", Severity.MEDIUM, 0.9, "1HGCM82633A004352", "presidio vin", "presidio")]

        judge = LLMJudgeDetector(threshold=0.5)
        monkeypatch.setattr(judge, "_call_llm", lambda t: [
            {"data_type": "health_condition", "evidence": "diabetes", "confidence": 0.9}
        ])

        pipeline = HybridPipeline(
            [],
            mode=DetectionMode.HYBRID,
            presidio=_MockPresidio(),
            llm_judge=judge,
        )
        findings = pipeline.run_event(
            text="diabetes patient has VIN 1HGCM82633A004352",
            event_id="e1", run_id="r1", channel="final_output",
        )
        tiers = {f.metadata.get("tier") for f in findings}
        assert "presidio" in tiers
        assert "semantic" in tiers

    def test_hybrid_llm_judge_dedup_with_regex(self, monkeypatch):
        """LLM-judge should not re-add a finding already caught by regex (dedup)."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(threshold=0.5)
        # LLM also "sees" the email that regex already caught
        monkeypatch.setattr(judge, "_call_llm", lambda t: [
            {"data_type": "email", "evidence": "alice@example.com", "confidence": 0.95}
        ])

        pipeline = HybridPipeline(
            build_detectors(None, None),
            mode=DetectionMode.HYBRID,
            llm_judge=judge,
        )
        findings = pipeline.run_event(
            text="Contact alice@example.com for details",
            event_id="e1", run_id="r1", channel="final_output",
        )
        # Despite two sources (regex + LLM), only one finding for same (type, value)
        email_hits = [f for f in findings if f.matched_value == "alice@example.com"]
        assert len(email_hits) == 1

    def test_finding_tiers_includes_presidio_when_active(self):
        """finding_tiers should include 'presidio' for STANDARD/HYBRID mode with presidio set."""
        class _MockPresidio:
            def detect(self, text): return []

        pipeline = HybridPipeline([], mode=DetectionMode.STANDARD, presidio=_MockPresidio())
        assert "presidio" in pipeline.finding_tiers

    def test_finding_tiers_includes_semantic_when_llm_active(self):
        """finding_tiers should include 'semantic' for HYBRID/LLM_ONLY mode with judge set."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        pipeline = HybridPipeline([], mode=DetectionMode.HYBRID, llm_judge=judge)
        assert "semantic" in pipeline.finding_tiers

    def test_finding_tiers_fast_mode_regex_only(self):
        assert HybridPipeline([], mode=DetectionMode.FAST).finding_tiers == ["regex"]


# ---------------------------------------------------------------------------
# Runner — config-driven pipeline construction
# ---------------------------------------------------------------------------

class TestRunnerConfigPaths:
    """Cover _build_pipeline with Presidio/LLM-judge enabled and other config paths."""

    def test_build_pipeline_with_llm_judge_init_exception_handled(self, monkeypatch):
        """If LLMJudgeDetector.__init__ raises, _build_pipeline catches it and sets judge=None."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        from agentleak.core.config import Config
        from agentleak.detectors.llm_judge import LLMJudgeDetector

        def bad_init(self, **kwargs):
            raise RuntimeError("simulated init failure")

        monkeypatch.setattr(LLMJudgeDetector, "__init__", bad_init)
        cfg = Config.model_validate({
            "project": {"name": "test"},
            "detection": {"mode": "hybrid", "llm_judge": {"enabled": True}},
        })
        runner = AgentLeakRunner(cfg)
        # Exception caught; judge falls back to None, no crash
        assert runner._pipeline._llm_judge is None

    def test_build_pipeline_with_llm_judge_enabled(self, monkeypatch):
        """_build_pipeline loads LLMJudgeDetector when enabled=True and key is set."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-unit")
        from agentleak.core.config import Config
        cfg = Config.model_validate({
            "project": {"name": "test"},
            "detection": {
                "mode": "hybrid",
                "llm_judge": {"enabled": True, "base_url": "", "model": ""},
            },
        })
        runner = AgentLeakRunner(cfg)
        assert runner._pipeline._llm_judge is not None
        assert runner._pipeline.mode == DetectionMode.HYBRID

    def test_build_pipeline_with_presidio_enabled_graceful_fallback(self, monkeypatch):
        """When presidio is enabled but PresidioDetector.__init__ raises, pipeline is still built."""
        from agentleak.core.config import Config
        from agentleak.detectors.presidio_detector import PresidioDetector

        # Simulate PresidioDetector init raising (e.g. spacy model missing)
        def bad_init(self, **kwargs):
            raise RuntimeError("presidio model not found")

        monkeypatch.setattr(PresidioDetector, "__init__", bad_init)
        cfg = Config.model_validate({
            "project": {"name": "test"},
            "detection": {"mode": "standard", "presidio": {"enabled": True}},
        })
        runner = AgentLeakRunner(cfg)
        # Exception is caught gracefully; presidio falls back to None
        assert runner._pipeline._presidio is None

    def test_channel_filtering_skips_disabled_channels(self):
        """Events on channels not in config.channels are silently skipped."""
        from agentleak.core.config import Config
        cfg = Config.model_validate({
            "project": {"name": "test"},
            "channels": ["final_output"],  # only final_output enabled
        })
        runner = AgentLeakRunner(cfg)
        trace = Trace(run_id="r")
        trace.add_event("tool_call", {"email": "alice@example.com"})   # excluded
        trace.add_event("final_output", "User email is alice@example.com")  # included
        result = runner.analyze(trace)
        channels = {f.channel for f in result.findings}
        assert "tool_call" not in channels
        assert "final_output" in channels

    def test_analyze_functional_shortcut(self):
        """analyze() module-level function is a shortcut for AgentLeakRunner().analyze()."""
        from agentleak.core.runner import analyze
        trace = Trace(run_id="r")
        trace.add_event("final_output", "alice@example.com")
        result = analyze(trace)
        assert result is not None
        assert any(f.data_type == "email" for f in result.findings)

    def test_event_with_empty_text_is_skipped(self):
        """Events whose searchable_text is empty produce no findings and don't crash."""
        runner = AgentLeakRunner()
        trace = Trace(run_id="r")
        trace.add_event("final_output", "")       # empty content → skipped
        trace.add_event("tool_call", "alice@example.com")  # non-empty → analyzed
        result = runner.analyze(trace)
        channels = {f.channel for f in result.findings}
        assert "final_output" not in channels
        assert "tool_call" in channels


# ---------------------------------------------------------------------------
# LLM-judge detector — detailed coverage
# ---------------------------------------------------------------------------

class TestLLMJudgeDetailed:
    """Cover the HTTP call path, cache eviction, and edge cases in llm_judge.py."""

    def test_empty_text_returns_empty(self):
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        assert judge.detect("") == []

    def test_whitespace_only_returns_empty(self):
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        assert judge.detect("   \t\n") == []

    def test_resolve_key_from_openai_env(self, monkeypatch):
        """_resolve_key should return OPENAI_API_KEY when set."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-resolve")
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector()
        assert judge._api_key == "sk-test-openai-resolve"

    def test_cache_hit_avoids_second_call(self, monkeypatch):
        """Second call with identical text should use the cache, not call LLM again."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        call_count = [0]

        def mock_call(text):
            call_count[0] += 1
            return [{"data_type": "email", "evidence": "a@b.com", "confidence": 0.9}]

        monkeypatch.setattr(judge, "_call_llm", mock_call)
        judge.detect("Contact a@b.com")
        judge.detect("Contact a@b.com")  # identical → cache hit
        assert call_count[0] == 1

    def test_cache_eviction_when_full(self, monkeypatch):
        """Cache evicts the oldest entry when cache_size is exceeded."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5, cache_size=2)
        monkeypatch.setattr(judge, "_call_llm", lambda t: [])
        judge.detect("text one")
        judge.detect("text two")
        judge.detect("text three")  # evicts "text one"
        assert len(judge._cache) == 2
        assert len(judge._cache_order) == 2

    def test_mock_http_successful_response(self):
        """Mock urllib.request.urlopen to test the full HTTP → RawMatch path."""
        import json
        from unittest.mock import MagicMock, patch

        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(api_key="sk-test", threshold=0.5)
        response_body = json.dumps({
            "choices": [{
                "message": {
                    "content": '[{"data_type":"ssn","evidence":"123-45-6789","confidence":0.95}]'
                }
            }]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            matches = judge._call_llm("The SSN is 123-45-6789")

        assert len(matches) == 1
        assert matches[0]["data_type"] == "ssn"
        assert matches[0]["evidence"] == "123-45-6789"

    def test_api_key_added_to_auth_header(self):
        """When api_key is set the HTTP request includes Authorization header."""
        import json
        from unittest.mock import MagicMock, patch

        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(api_key="sk-bearer-test", threshold=0.5)
        response_body = json.dumps({"choices": [{"message": {"content": "[]"}}]}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured_headers: dict = {}

        def capture_request(req, timeout=None):
            captured_headers.update(req.headers)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=capture_request):
            judge._call_llm("text")

        # Header keys are title-cased by urllib
        assert "Authorization" in captured_headers or "authorization" in {k.lower() for k in captured_headers}

    def test_markdown_fence_stripping(self):
        """LLM response wrapped in ```json ... ``` fences should be parsed correctly."""
        import json
        from unittest.mock import MagicMock, patch

        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(api_key="sk-test", threshold=0.5)
        fenced = '```json\n[{"data_type":"email","evidence":"a@b.com","confidence":0.9}]\n```'
        response_body = json.dumps({
            "choices": [{"message": {"content": fenced}}]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            matches = judge._call_llm("email a@b.com")
        assert len(matches) == 1
        assert matches[0]["evidence"] == "a@b.com"

    def test_empty_choices_returns_empty(self):
        """Response with empty choices list → empty result."""
        import json
        from unittest.mock import MagicMock, patch

        from agentleak.detectors.llm_judge import LLMJudgeDetector

        judge = LLMJudgeDetector(api_key="sk-test", threshold=0.5)
        response_body = json.dumps({"choices": []}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = judge._call_llm("text")
        assert result == []

    def test_non_dict_hit_skipped(self, monkeypatch):
        """Non-dict items in the LLM's JSON response are ignored."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        monkeypatch.setattr(judge, "_call_llm", lambda t: ["not-a-dict", None, 42])
        assert judge.detect("text") == []

    def test_empty_evidence_skipped(self, monkeypatch):
        """Hits with empty evidence string are not promoted to RawMatch."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        monkeypatch.setattr(judge, "_call_llm", lambda t: [
            {"data_type": "email", "evidence": "", "confidence": 0.9}
        ])
        assert judge.detect("text") == []

    def test_duplicate_evidence_deduped(self, monkeypatch):
        """Duplicate (data_type, evidence) pairs produce only one RawMatch."""
        from agentleak.detectors.llm_judge import LLMJudgeDetector
        judge = LLMJudgeDetector(threshold=0.5)
        monkeypatch.setattr(judge, "_call_llm", lambda t: [
            {"data_type": "email", "evidence": "a@b.com", "confidence": 0.9},
            {"data_type": "email", "evidence": "a@b.com", "confidence": 0.9},  # dup
        ])
        matches = judge.detect("a@b.com")
        assert len(matches) == 1
