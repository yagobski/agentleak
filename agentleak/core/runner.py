# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The orchestrator: run detectors over a trace, score the findings with
AgentRisk, and produce an :class:`AnalysisResult`.

This is the single seam everything else (CLI, SDK, integrations) goes through.
"""

from __future__ import annotations

import os
from typing import Any

from ..detectors import build_detectors
from .agentrisk import DEFAULT_WEIGHTS
from .canary import CanarySet
from .config import Config
from .detector import Detector, Finding
from .pipeline import DetectionMode, HybridPipeline
from .privacy_policy import evaluate_privacy_policy
from .report import AnalysisResult
from .scoring import score_findings
from .trace import Trace


def _build_pipeline(
    config: Config | None, detectors: list[Detector]
) -> tuple[HybridPipeline, list[str]]:
    """Construct a HybridPipeline from optional config.

    Returns the pipeline and a list of degradation warnings: when the selected
    ``mode`` asks for a tier that cannot run (missing dependency or API key), we
    surface it loudly rather than silently scoring with fewer tiers. A gate that
    turns "I couldn't check" into a green pass is worse than one that errors.
    """
    warnings: list[str] = []
    if config is None:
        return HybridPipeline(detectors, mode=DetectionMode.FAST), warnings

    det_cfg = config.detection
    mode = DetectionMode(det_cfg.mode) if det_cfg.mode else DetectionMode.FAST
    wants_presidio = mode in (DetectionMode.STANDARD, DetectionMode.HYBRID)
    wants_llm = mode in (DetectionMode.HYBRID, DetectionMode.LLM_ONLY)

    # Tier 2b: Presidio (optional extra)
    presidio = None
    if det_cfg.presidio.enabled:
        try:
            from ..detectors.presidio_detector import PresidioDetector
            presidio = PresidioDetector(score_threshold=det_cfg.presidio.score_threshold)
        except Exception as exc:
            warnings.append(
                "Presidio tier requested but could not load "
                f"({exc.__class__.__name__}); install 'agentleak[presidio]'. "
                "Entity detection (names, locations, etc.) did NOT run."
            )
    if wants_presidio and presidio is None:
        warnings.append(
            f"Detection mode '{mode.value}' includes Presidio, but it is not "
            "active; results rely on the regex tier only."
        )

    # Tier 3: LLM-judge (requires API key)
    llm_judge = None
    if det_cfg.llm_judge.enabled:
        api_key = os.environ.get(det_cfg.llm_judge.api_key_env, "")
        if not api_key:
            warnings.append(
                f"LLM-judge tier requested but ${det_cfg.llm_judge.api_key_env} "
                "is not set; semantic detection did NOT run. Paraphrased or "
                "unseen sensitive values may be missed."
            )
        else:
            try:
                from ..detectors.llm_judge import LLMJudgeDetector
                llm_judge = LLMJudgeDetector(
                    base_url=det_cfg.llm_judge.base_url,
                    model=det_cfg.llm_judge.model,
                    api_key=api_key,
                    threshold=det_cfg.llm_judge.threshold,
                    timeout=det_cfg.llm_judge.timeout,
                )
            except Exception as exc:
                warnings.append(
                    "LLM-judge tier requested but could not initialise "
                    f"({exc.__class__.__name__}); semantic detection did NOT run."
                )
    if wants_llm and llm_judge is None and det_cfg.llm_judge.enabled and os.environ.get(
        det_cfg.llm_judge.api_key_env, ""
    ):
        # Enabled + keyed but still absent — construction failed above.
        pass
    elif wants_llm and llm_judge is None and not det_cfg.llm_judge.enabled:
        warnings.append(
            f"Detection mode '{mode.value}' includes the LLM-judge, but no judge "
            "is configured (detection.llm_judge.enabled is false)."
        )

    pipeline = HybridPipeline(
        detectors,
        mode=mode,
        llm_judge=llm_judge,
        presidio=presidio,
        level_overrides=config.scoring.level_overrides if config else {},
    )
    return pipeline, warnings


class AgentLeakRunner:
    """Analyze traces for sensitive-data leakage, scored with AgentRisk.

    With no config, every built-in detector runs over every channel — handy for
    quick SDK use. Pass a :class:`Config` to honor ``agentleak.yaml`` toggles,
    channel filters, custom detectors, severity-level overrides, the audited
    vault scope, and scoring thresholds.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config
        if config is None:
            raw_detectors: list[Detector] = build_detectors(None, None)
            self._channels: set[str] | None = None
            self._redact = True
            self._block_on_critical = True
            self._fail_below = 40
            self._project = "agentleak-project"
            self._weights: tuple[int, ...] = DEFAULT_WEIGHTS
            self._level_overrides: dict[str, int] = {}
            self._vault: Any = None
            self._scope_def: str | None = None
            self._privacy_policy: Any = None
        else:
            raw_detectors = build_detectors(
                config.detectors.as_dict(), config.custom_rules_raw()
            )
            self._channels = config.enabled_channels()
            self._redact = config.privacy.redact_values
            self._block_on_critical = config.scoring.block_on_critical
            self._fail_below = config.scoring.fail_below
            self._project = config.project.name
            self._weights = tuple(config.scoring.weights) or DEFAULT_WEIGHTS
            self._level_overrides = dict(config.scoring.level_overrides)
            self._vault, self._scope_def = config.vault_spec()
            self._privacy_policy = config.privacy_policy

        self.detectors = raw_detectors
        self._pipeline, self._warnings = _build_pipeline(config, raw_detectors)

    def analyze(
        self,
        trace: Trace,
        *,
        vault: Any = None,
        scope_def: str | None = None,
        canary_set: CanarySet | None = None,
    ) -> AnalysisResult:
        """Analyze a trace. An explicit ``vault`` (per-level counts, a list of
        secrets, or a raw ρ_S) overrides the config and the observed-reachable
        default for the AgentRisk denominator.

        Pass a :class:`~agentleak.core.canary.CanarySet` to enable exact canary
        matching in addition to the regular detector chain.
        """
        findings: list[Finding] = []
        counter = 0

        for event in trace.events:
            channel = event.channel_value
            if self._channels is not None and channel not in self._channels:
                continue

            text = event.searchable_text
            if not text:
                continue

            event_findings = self._pipeline.run_event(
                text=text,
                event_id=event.event_id,
                run_id=trace.run_id,
                channel=channel,
                source=event.source,
                target=event.target,
                metadata=dict(event.metadata),
                canary_set=canary_set,
                finding_counter=counter,
            )
            counter += len(event_findings)
            findings.extend(event_findings)

        # Stable, readable ordering: highest severity level first, then confidence.
        findings.sort(key=lambda f: (-f.level, -f.confidence))

        score = score_findings(
            findings,
            weights=self._weights,
            level_overrides=self._level_overrides,
            vault=vault if vault is not None else self._vault,
            scope_def=scope_def or self._scope_def,
        )

        selected_vault = vault if vault is not None else self._vault
        policy_evaluation = evaluate_privacy_policy(
            self._privacy_policy,
            findings,
            risk_index=score.risk_index,
            explicit_vault=selected_vault is not None,
        )

        return AnalysisResult(
            run_id=trace.run_id,
            agent_name=trace.agent_name,
            scenario_id=trace.scenario_id,
            score=score,
            findings=findings,
            project_name=self._project,
            redact_values=self._redact,
            block_on_critical=self._block_on_critical,
            fail_below=self._fail_below,
            policy_evaluation=policy_evaluation,
            warnings=list(self._warnings),
            detection_mode=self._pipeline.mode.value,
            tiers=self._pipeline.finding_tiers,
            event_count=len(trace.events),
            events=[
                {
                    "event_id": e.event_id,
                    "channel": e.channel_value,
                    "source": e.source,
                    "target": e.target,
                    "agent": trace.agent_name,
                }
                for e in trace.events
            ],
        )


def analyze(trace: Trace, config: Config | None = None, **kwargs: Any) -> AnalysisResult:
    """Functional shortcut for ``AgentLeakRunner(config).analyze(trace)``."""
    return AgentLeakRunner(config).analyze(trace, **kwargs)
