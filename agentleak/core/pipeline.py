# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Hybrid detection pipeline — orchestrates up to three detection tiers.

Tier 1+2 — Regex detectors (always available, stdlib only)
    The built-in pattern matchers: PII, Secrets, Healthcare, Finance, HR,
    Custom.  Fast (<1 ms/event) and deterministic.

Tier 2b — Presidio (optional, ``pip install agentleak[presidio]``)
    Presidio with 20+ domain-specific recognizers. Catches entity
    types the regex tier misses (VIN, IMEI, GPS, etc.).

Tier 3 — LLM-as-Judge (optional, requires API key + model config)
    Semantic detection of paraphrased, inferred, and context-dependent leaks.
    Only fires when a tier-3 judge is configured.

Modes::

    FAST       Tier 1+2 only (no Presidio, no LLM). Default when no extras.
    STANDARD   Tier 1+2 + Presidio (if installed).
    HYBRID     Tier 1+2 + Presidio + LLM-judge (recommended when key is set).
    LLM_ONLY   Tier 3 only (evaluation use-case, expensive).

The pipeline handles canary-token matching separately: any canary hit is
promoted to a ``tier="canary"`` finding with ``confidence=1.0`` before the
regular detector chain runs, so canary recall is always measured precisely.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from ..core.agentrisk import level_for
from ..core.canary import CanarySet, match_canaries
from ..core.detector import Finding, RawMatch, Severity, redact


class DetectionMode(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    HYBRID = "hybrid"
    LLM_ONLY = "llm_only"


class HybridPipeline:
    """Assemble and run the multi-tier detection pipeline.

    Args:
        detectors: Pre-built Tier-1/2 detector list (from
            :func:`~agentleak.detectors.build_detectors`).
        mode: Detection depth (``FAST`` / ``STANDARD`` / ``HYBRID`` /
            ``LLM_ONLY``).
        llm_judge: An optional :class:`~agentleak.detectors.llm_judge.LLMJudgeDetector`
            instance.  When *None* the HYBRID mode silently omits Tier 3.
        presidio: An optional :class:`~agentleak.detectors.presidio_detector.PresidioDetector`
            instance.  When *None* the STANDARD/HYBRID modes silently omit
            Tier 2b.
        level_overrides: Passed through to :func:`~agentleak.core.agentrisk.level_for`.
    """

    def __init__(
        self,
        detectors: list[Any],
        *,
        mode: DetectionMode | str = DetectionMode.FAST,
        llm_judge: Any | None = None,
        presidio: Any | None = None,
        level_overrides: dict[str, int] | None = None,
    ) -> None:
        self.mode = DetectionMode(mode) if isinstance(mode, str) else mode
        self._tier1 = detectors
        self._llm_judge = llm_judge
        self._presidio = presidio
        self._level_overrides = level_overrides or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_event(
        self,
        *,
        text: str,
        event_id: str,
        run_id: str,
        channel: str,
        source: str = "",
        target: str = "",
        metadata: dict[str, Any] | None = None,
        canary_set: CanarySet | None = None,
        finding_counter: int = 0,
    ) -> list[Finding]:
        """Run the pipeline on one event's text.  Returns findings."""
        if not text:
            return []

        findings: list[Finding] = []
        seen: set[tuple[str, str]] = set()
        meta = metadata or {}
        counter = finding_counter

        def _make_finding(raw: RawMatch, tier: str = "regex") -> Finding:
            nonlocal counter
            counter += 1
            level = level_for(raw.data_type, raw.severity, self._level_overrides)
            extra_meta = {**meta, "tier": tier}
            return Finding(
                finding_id=f"finding_{counter:03d}",
                run_id=run_id,
                event_id=event_id,
                channel=channel,
                data_type=raw.data_type,
                severity=raw.severity,
                confidence=raw.confidence,
                matched_value=raw.matched_value,
                redacted_value=redact(raw.matched_value),
                detector=raw.detector,
                recommendation=raw.recommendation,
                source=source,
                target=target,
                level=level,
                metadata=extra_meta,
            )

        # ---- Canary exact-match (always first, highest priority) -----------
        if canary_set and not canary_set.is_empty():
            for tier_name, token in match_canaries(text, canary_set):
                key = ("canary", token)
                if key in seen:
                    continue
                seen.add(key)
                raw = RawMatch(
                    data_type="canary",
                    severity=Severity.CRITICAL,
                    confidence=1.0,
                    matched_value=token,
                    recommendation=(
                        f"Canary token ({tier_name} tier) leaked — confirms exact disclosure."
                    ),
                    detector="canary",
                )
                findings.append(_make_finding(raw, tier=f"canary_{tier_name}"))

        # ---- Tier 1+2: regex detectors ------------------------------------
        if self.mode != DetectionMode.LLM_ONLY:
            for detector in self._tier1:
                for raw in detector.detect(text):
                    key = (raw.data_type, raw.matched_value)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(_make_finding(raw, tier="regex"))

        # ---- Tier 2b: Presidio (STANDARD / HYBRID) ------------------------
        if (
            self.mode in (DetectionMode.STANDARD, DetectionMode.HYBRID)
            and self._presidio is not None
        ):
            for raw in self._presidio.detect(text):
                key = (raw.data_type, raw.matched_value)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(_make_finding(raw, tier="presidio"))

        # ---- Tier 3: LLM-judge (HYBRID / LLM_ONLY) -----------------------
        if (
            self.mode in (DetectionMode.HYBRID, DetectionMode.LLM_ONLY)
            and self._llm_judge is not None
        ):
            for raw in self._llm_judge.detect(text):
                key = (raw.data_type, raw.matched_value)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(_make_finding(raw, tier="semantic"))

        return findings

    @property
    def finding_tiers(self) -> list[str]:
        """The active detection tiers as a list of strings (for metadata)."""
        tiers = ["regex"]
        if self.mode in (DetectionMode.STANDARD, DetectionMode.HYBRID) and self._presidio:
            tiers.append("presidio")
        if self.mode in (DetectionMode.HYBRID, DetectionMode.LLM_ONLY) and self._llm_judge:
            tiers.append("semantic")
        return tiers
