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


def _build_pipeline(config: Config | None, detectors: list[Detector]) -> HybridPipeline:
    """Construct a HybridPipeline from optional config."""
    if config is None:
        return HybridPipeline(detectors, mode=DetectionMode.FAST)

    det_cfg = config.detection
    mode = DetectionMode(det_cfg.mode) if det_cfg.mode else DetectionMode.FAST

    # Tier 2b: Presidio (optional extra)
    presidio = None
    if det_cfg.presidio.enabled:
        try:
            from ..detectors.presidio_detector import PresidioDetector
            presidio = PresidioDetector(score_threshold=det_cfg.presidio.score_threshold)
        except Exception:
            pass

    # Tier 3: LLM-judge (requires API key)
    llm_judge = None
    if det_cfg.llm_judge.enabled:
        try:
            from ..detectors.llm_judge import LLMJudgeDetector
            api_key = os.environ.get(det_cfg.llm_judge.api_key_env, "")
            llm_judge = LLMJudgeDetector(
                base_url=det_cfg.llm_judge.base_url,
                model=det_cfg.llm_judge.model,
                api_key=api_key,
                threshold=det_cfg.llm_judge.threshold,
                timeout=det_cfg.llm_judge.timeout,
            )
        except Exception:
            pass

    return HybridPipeline(
        detectors,
        mode=mode,
        llm_judge=llm_judge,
        presidio=presidio,
        level_overrides=config.scoring.level_overrides if config else {},
    )


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
        self._pipeline = _build_pipeline(config, raw_detectors)

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
