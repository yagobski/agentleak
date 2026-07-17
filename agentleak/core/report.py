"""The analysis result object — what :class:`AgentLeakRunner` returns and what
every reporter renders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import compliance as _compliance
from . import flow as _flow
from .agentrisk import BASELINE_CHANNELS, LEVEL_LABELS
from .detector import Finding, Severity
from .scoring import Score, badge_for_level

# Standard, channel-level guidance surfaced when a given channel leaks
# (spec section 13.4). Keyed by channel.
STANDARD_RECOMMENDATIONS: dict[str, str] = {
    "tool_call": "Mask or strip sensitive fields before passing arguments to external tools.",
    "tool_response": "Filter tool responses; do not propagate raw sensitive fields downstream.",
    "shared_memory": "Disable persistent memory for sensitive workflows or store references, not raw values.",
    "log": "Stop logging full payloads; redact sensitive fields at the logging boundary.",
    "inter_agent_message": "Reduce the data shared between agents; separate permissions per agent role.",
    "generated_file": "Add a redaction filter before any document is published or exported.",
    "final_output": "Apply an output guardrail that strips identifiers from the final answer.",
}

GENERAL_RECOMMENDATIONS: list[str] = [
    "Add a human approval step before publishing documents that may contain personal data.",
    "Give each agent the least privilege it needs; don't broadcast sensitive context.",
]

# Per-channel remediation templates: machine-readable advice + copy-paste code fix.
# Used by the platform UI and the /api/selftest endpoint so agents can auto-improve.
CHANNEL_REMEDIATION: dict[str, dict[str, str]] = {
    "tool_call": {
        "advice": "Strip or mask sensitive fields before passing arguments to external tools.",
        "code_fix": (
            "SENSITIVE_KEYS = {'email', 'ssn', 'phone', 'password', 'api_key', 'credit_card'}\n"
            "\n"
            "def safe_tool_args(args: dict) -> dict:\n"
            "    \"\"\"Redact sensitive keys before forwarding to any tool call.\"\"\"\n"
            "    return {k: '[REDACTED]' if k.lower() in SENSITIVE_KEYS else v\n"
            "            for k, v in args.items()}\n"
            "\n"
            "# Usage (LangChain tool wrapper example):\n"
            "# result = my_tool.run(safe_tool_args(agent_action.tool_input))\n"
        ),
    },
    "tool_response": {
        "advice": "Filter tool responses before injecting them into the LLM context or forwarding to other agents.",
        "code_fix": (
            "import re\n"
            "\n"
            "EMAIL_RE  = re.compile(r'[\\w.+-]+@[\\w-]+\\.[a-z]{2,}', re.I)\n"
            "SSN_RE    = re.compile(r'\\b\\d{3}-\\d{2}-\\d{4}\\b')\n"
            "PHONE_RE  = re.compile(r'\\b\\+?\\d[\\d\\s\\-\\.]{7,}\\d\\b')\n"
            "\n"
            "def sanitize_tool_response(text: str) -> str:\n"
            "    \"\"\"Strip PII from a tool response before it reaches the LLM context.\"\"\"\n"
            "    text = EMAIL_RE.sub('[EMAIL]', text)\n"
            "    text = SSN_RE.sub('[SSN]', text)\n"
            "    text = PHONE_RE.sub('[PHONE]', text)\n"
            "    return text\n"
        ),
    },
    "shared_memory": {
        "advice": "Never write raw sensitive data to shared memory; store opaque vault references instead.",
        "code_fix": (
            "import hashlib, secrets\n"
            "\n"
            "_vault: dict[str, str] = {}  # process-local; replace with encrypted store\n"
            "\n"
            "def vault_put(value: str) -> str:\n"
            "    \"\"\"Store a sensitive value and return an opaque reference token.\"\"\"\n"
            "    token = 'vlt_' + secrets.token_hex(8)\n"
            "    _vault[token] = value\n"
            "    return token  # safe to write to shared memory / logs\n"
            "\n"
            "def vault_get(token: str) -> str:\n"
            "    return _vault[token]\n"
            "\n"
            "# Usage: instead of memory['email'] = user_email\n"
            "#        do    memory['email_ref'] = vault_put(user_email)\n"
        ),
    },
    "log": {
        "advice": "Redact sensitive patterns at the logging boundary; never log full request/response payloads.",
        "code_fix": (
            "import re, logging\n"
            "\n"
            "_PATTERNS = [\n"
            "    (re.compile(r'[\\w.+-]+@[\\w-]+\\.[a-z]{2,}', re.I), '[EMAIL]'),\n"
            "    (re.compile(r'\\b\\d{3}-\\d{2}-\\d{4}\\b'),           '[SSN]'),\n"
            "    (re.compile(r'(?i)(api[_-]?key|secret|token)=[^&\\s]+'), r'\\1=[REDACTED]'),\n"
            "]\n"
            "\n"
            "class PrivacyFilter(logging.Filter):\n"
            "    def filter(self, record: logging.LogRecord) -> bool:\n"
            "        msg = str(record.getMessage())\n"
            "        for pattern, repl in _PATTERNS:\n"
            "            msg = pattern.sub(repl, msg)\n"
            "        record.msg, record.args = msg, ()\n"
            "        return True\n"
            "\n"
            "logging.getLogger().addFilter(PrivacyFilter())\n"
        ),
    },
    "inter_agent_message": {
        "advice": "Apply least-privilege data sharing between agents; only pass what the receiving agent strictly needs.",
        "code_fix": (
            "# Keys allowed to cross agent boundaries (allowlist beats denylist)\n"
            "AGENT_HANDOFF_ALLOWLIST = {'task_id', 'intent', 'status', 'result_summary'}\n"
            "\n"
            "def clean_handoff(payload: dict) -> dict:\n"
            "    \"\"\"Strip keys not on the allowlist before sending to the next agent.\"\"\"\n"
            "    return {k: v for k, v in payload.items() if k in AGENT_HANDOFF_ALLOWLIST}\n"
            "\n"
            "# LangGraph / CrewAI example:\n"
            "# next_agent.run(clean_handoff(current_state))\n"
        ),
    },
    "generated_file": {
        "advice": "Apply a redaction filter to every document before it is written to disk, sent to storage, or exported.",
        "code_fix": (
            "import re\n"
            "\n"
            "def redact_document(content: str) -> str:\n"
            "    \"\"\"Remove PII from a generated document before export.\"\"\"\n"
            "    content = re.sub(r'[\\w.+-]+@[\\w-]+\\.[a-z]{2,}', '[EMAIL]',   content, flags=re.I)\n"
            "    content = re.sub(r'\\b\\d{3}-\\d{2}-\\d{4}\\b',    '[SSN]',     content)\n"
            "    content = re.sub(r'\\b\\d{4}[\\s-]\\d{4}[\\s-]\\d{4}[\\s-]\\d{4}\\b', '[CARD]', content)\n"
            "    return content\n"
            "\n"
            "# Usage: open('report.pdf', 'wb').write(generate_pdf(redact_document(text)))\n"
        ),
    },
    "final_output": {
        "advice": "Apply an output guardrail that strips identifiers before the final answer reaches the user.",
        "code_fix": (
            "import re\n"
            "\n"
            "def output_guardrail(text: str) -> str:\n"
            "    \"\"\"Last-mile PII stripper — attach to every LLM output before returning.\"\"\"\n"
            "    text = re.sub(r'[\\w.+-]+@[\\w-]+\\.[a-z]{2,}', '[EMAIL]', text, flags=re.I)\n"
            "    text = re.sub(r'\\b\\d{3}-\\d{2}-\\d{4}\\b',    '[SSN]',   text)\n"
            "    text = re.sub(r'\\b(\\d{4}[\\s-]){3}\\d{4}\\b', '[CARD]',  text)\n"
            "    return text\n"
            "\n"
            "# LangChain:\n"
            "# chain = prompt | llm | StrOutputParser() | output_guardrail\n"
            "\n"
            "# AutoGen:\n"
            "# reply = output_guardrail(agent.generate_reply(messages))\n"
        ),
    },
}


@dataclass
class AnalysisResult:
    run_id: str
    agent_name: str
    scenario_id: str | None
    score: Score
    findings: list[Finding]
    project_name: str = "agentleak-project"
    redact_values: bool = True
    block_on_critical: bool = True
    fail_below: int = 40
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_count: int = 0
    # Lightweight event log ({event_id, channel, source, target, agent}) for
    # building the leak-path and topology views. Filled by the runner.
    events: list[dict[str, Any]] = field(default_factory=list)

    # -- convenience accessors (used by the SDK and reporters) -----------
    @property
    def privacy_score(self) -> int:
        return self.score.privacy_score

    @property
    def risk_index(self) -> float:
        """The AgentRisk Risk Index RI in [0, 1]."""
        return self.score.risk_index

    @property
    def risk_score(self) -> float:
        # Backwards-friendly alias for the Risk Index.
        return self.score.risk_index

    @property
    def verdict(self) -> str:
        return self.score.verdict

    @property
    def has_critical(self) -> bool:
        return self.score.has_critical

    @property
    def blocked(self) -> bool:
        """True when this run should fail a CI gate."""
        return self.privacy_score < self.fail_below or (
            self.block_on_critical and self.has_critical
        )

    # -- findings views --------------------------------------------------
    def leaked_findings(self) -> list[Finding]:
        """Findings on disclosure channels — i.e. actual leaks (not sources)."""
        return [f for f in self.findings if f.channel not in BASELINE_CHANNELS]

    # -- recommendations -------------------------------------------------
    def recommendations(self) -> list[str]:
        recs: list[str] = []
        leaking_channels = {f.channel for f in self.leaked_findings()}
        # Channel guidance, ordered by the channel's risk contribution.
        for cr in self.score.channel_risks:
            advice = STANDARD_RECOMMENDATIONS.get(cr.channel)
            if advice and advice not in recs:
                recs.append(advice)
        if leaking_channels:
            for advice in GENERAL_RECOMMENDATIONS:
                if advice not in recs:
                    recs.append(advice)
        return recs

    def remediation_hints(self) -> list[dict[str, object]]:
        """Structured per-channel remediation with copy-paste code fixes.

        Designed for programmatic consumption by agents and CI pipelines.
        Each hint carries:
        - channel      — where the leak was observed
        - data_types   — what sensitive data types leaked in that channel
        - priority     — "critical" | "high" | "medium"
        - advice       — one-sentence human-readable guidance
        - code_fix     — a Python code snippet showing exactly how to fix it
        """
        leaked = self.leaked_findings()
        seen: set[str] = set()
        hints: list[dict[str, object]] = []
        # Order by risk contribution (highest first)
        ordered_channels = [cr.channel for cr in self.score.channel_risks]
        for ch in ordered_channels:
            if ch in seen:
                continue
            ch_findings = [f for f in leaked if f.channel == ch]
            if not ch_findings:
                continue
            seen.add(ch)
            tpl = CHANNEL_REMEDIATION.get(ch)
            if not tpl:
                continue
            max_level = max(f.level for f in ch_findings)
            priority = "critical" if max_level >= 4 else "high" if max_level >= 3 else "medium"
            hints.append({
                "channel": ch,
                "data_types": sorted({f.data_type for f in ch_findings}),
                "priority": priority,
                "advice": tpl["advice"],
                "code_fix": tpl["code_fix"],
            })
        return hints

    # -- serialization ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        agentrisk = self.score.agentrisk.to_dict()
        level_profile = {LEVEL_LABELS[k]: self.score.level_profile.get(k, 0) for k in (1, 2, 3, 4)}
        leaked = self.leaked_findings()
        data: dict[str, Any] = {
            "report": "agentleak",
            "version": 2,
            "scoring": "agentrisk",
            "project": self.project_name,
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "scenario_id": self.scenario_id,
            "generated_at": self.generated_at.isoformat(),
            "event_count": self.event_count,
            "privacy_score": self.privacy_score,
            "verdict": self.verdict,
            "risk_index": self.risk_index,
            "wsl": self.score.wsl,
            "rho_s": self.score.rho_s,
            "scope_def": self.score.agentrisk.scope_def,
            "blocked": self.blocked,
            "summary": {
                "total_findings": len(leaked),
                "detected_total": len(self.findings),
                "leaked_secrets": self.score.agentrisk.leaked_count,
                "vault_secrets": self.score.agentrisk.vault_count,
                "level_profile": level_profile,
                "vault_level_profile": agentrisk["vault_level_profile"],
                "has_critical": self.has_critical,
            },
            "channel_risks": [
                {
                    "channel": cr.channel,
                    "level": cr.badge,           # color vocab: critical/high/medium/low
                    "level_label": cr.label,     # L1..L4
                    "ri": cr.ri,
                    "risk_contribution": cr.ri,  # bar magnitude
                    "finding_count": cr.finding_count,
                }
                for cr in self.score.channel_risks
            ],
            "findings": [self._finding_dict(f) for f in leaked],
            "recommendations": self.recommendations(),
            "remediation_hints": self.remediation_hints(),
            "agentrisk": agentrisk,
        }
        data["compliance"] = _compliance.evaluate(data)
        data["flow"] = _flow.build_topology(self.events, self.findings)
        data["leak_paths"] = _flow.build_leak_paths(
            self.events, self.findings, redact=self.redact_values
        )
        return data

    def _finding_dict(self, f: Finding) -> dict[str, Any]:
        data = f.to_dict(redact_values=self.redact_values)
        data["level_label"] = LEVEL_LABELS.get(f.level, "L?")
        data["badge"] = badge_for_level(f.level)
        return data

    @staticmethod
    def severity_order() -> list[str]:
        return [s.value for s in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)]
