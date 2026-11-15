# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Map findings and attack classes to AI-security framework identifiers.

This is separate from :mod:`agentleak.core.compliance`. Compliance asks
whether a run meets a privacy regulation's control; this module only says
which entries of three AI-security catalogues a finding or an attack class
relates to, so a reviewer can file it next to their own threat model:

* **OWASP Top 10 for Agentic Applications (2026)**, identifiers ASI01-ASI10.
  The OWASP text is CC BY-SA 4.0, so only the identifiers are used here; the
  one-line summaries are AgentLeak's own words.
* **MITRE ATLAS** technique identifiers and names (data Apache-2.0,
  ``mitre-atlas/atlas-data``, collection version 2026.10).
* **NIST AI 100-2 E2025** attack identifiers and terms (``NISTAML.*``, a U.S.
  government publication).

It is a mapping to support review, not a certification and not a finding of
compliance. Every identifier was checked against the primary source listed in
:data:`SOURCES`; an identifier that could not be checked is not listed. The
mapping is a closed table, no inference: it never changes a score, a verdict
or the compliance posture.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

NOTE = (
    "A mapping to support review, not a certification: it names the framework "
    "entries a finding or attack class relates to. It does not change the score, "
    "the verdict or the compliance posture."
)

SOURCES: dict[str, dict[str, str]] = {
    "owasp_asi_2026": {
        "name": "OWASP Top 10 for Agentic Applications (2026)",
        "url": "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/",
        "version": "2026 (published 2025-12-09)",
        "verified": "2026-11-15, against the published PDF (SHA-256 a2db94cd00b0...)",
        "licence": "CC BY-SA 4.0; identifiers only, summaries are AgentLeak's own",
    },
    "mitre_atlas": {
        "name": "MITRE ATLAS",
        "url": "https://github.com/mitre-atlas/atlas-data",
        "version": "2026.10 (dist/v6/ATLAS-latest.yaml, commit f56c1468731d6428e5bf875263b4643b46d67437)",
        "verified": "2026-11-15",
        "licence": "Apache-2.0, Copyright 2021-2026 MITRE",
    },
    "nist_ai_100_2_e2025": {
        "name": "NIST AI 100-2 E2025, Adversarial Machine Learning: A Taxonomy and Terminology",
        "url": "https://doi.org/10.6028/NIST.AI.100-2e2025",
        "version": "March 2025",
        "verified": "2026-11-15, against the taxonomy index (pp. x-xi) and section 3.4.3",
        "licence": "U.S. government work",
    },
}

#: Every identifier this module can emit. ATLAS and NIST entries carry the
#: source's own name; OWASP entries carry an AgentLeak-written summary.
IDENTIFIERS: dict[str, dict[str, str]] = {
    # OWASP Agentic Top 10 (2026)
    "ASI01": {"framework": "owasp_asi_2026",
              "summary": "Content the agent reads changes what it is trying to achieve."},
    "ASI02": {"framework": "owasp_asi_2026",
              "summary": "A tool the agent is allowed to use is used harmfully, for example to send data out."},
    "ASI03": {"framework": "owasp_asi_2026",
              "summary": "Delegated rights, trust between agents or inherited credentials reach further than intended."},
    "ASI04": {"framework": "owasp_asi_2026",
              "summary": "A third-party tool, MCP server, model or agent the system loads is malicious or tampered with."},
    "ASI05": {"framework": "owasp_asi_2026",
              "summary": "Code the agent writes or triggers runs in a way nobody intended."},
    "ASI06": {"framework": "owasp_asi_2026",
              "summary": "Stored memory or retrieved context is seeded with content that steers the agent later."},
    "ASI07": {"framework": "owasp_asi_2026",
              "summary": "Messages or shared state between agents can be read, forged or altered, or carry what they should not."},
    "ASI08": {"framework": "owasp_asi_2026",
              "summary": "A fault in one agent spreads through the agents and systems connected to it."},
    "ASI09": {"framework": "owasp_asi_2026",
              "summary": "The trust a person places in the agent is used to obtain a harmful decision."},
    "ASI10": {"framework": "owasp_asi_2026",
              "summary": "An agent acts outside its intended scope or against the people it serves."},
    # MITRE ATLAS (names as published)
    "AML.T0051.000": {"framework": "mitre_atlas", "name": "LLM Prompt Injection: Direct"},
    "AML.T0051.001": {"framework": "mitre_atlas", "name": "LLM Prompt Injection: Indirect"},
    "AML.T0080.000": {"framework": "mitre_atlas", "name": "AI Agent Context Poisoning: Memory"},
    "AML.T0085.002": {"framework": "mitre_atlas",
                      "name": "Data from AI Services: Conversation Context and Memory"},
    "AML.T0085.003": {"framework": "mitre_atlas", "name": "Data from AI Services: System Instructions"},
    "AML.T0086": {"framework": "mitre_atlas", "name": "Exfiltration via AI Agent Tool Invocation"},
    "AML.T0110.000": {"framework": "mitre_atlas",
                      "name": "AI Agent Tool Poisoning: Definition and Instructions"},
    # NIST AI 100-2 E2025 (terms as published)
    "NISTAML.015": {"framework": "nist_ai_100_2_e2025", "name": "Indirect Prompt Injection"},
    "NISTAML.018": {"framework": "nist_ai_100_2_e2025", "name": "Prompt Injection"},
    "NISTAML.03": {"framework": "nist_ai_100_2_e2025", "name": "Privacy Compromises"},
    "NISTAML.035": {"framework": "nist_ai_100_2_e2025", "name": "Prompt Extraction"},
    "NISTAML.039": {"framework": "nist_ai_100_2_e2025", "name": "Compromising connected resources"},
}

#: Disclosure channel of a finding -> identifiers. Any leak is a privacy
#: compromise in NIST's terms; the agentic entries depend on where it went.
CHANNEL_MAP: dict[str, tuple[str, ...]] = {
    "tool_call": ("ASI02", "AML.T0086", "NISTAML.03"),
    "inter_agent_message": ("ASI07", "NISTAML.03"),
    "shared_memory": ("ASI07", "AML.T0085.002", "NISTAML.03"),
    "log": ("NISTAML.03",),
    "generated_file": ("NISTAML.03",),
    "final_output": ("NISTAML.03",),
}

#: AgentLeak attack class (``agentleak.core.attacks``) -> identifiers. Only
#: classes with a clear counterpart are listed; the rest map to nothing.
ATTACK_CLASS_MAP: dict[str, tuple[str, ...]] = {
    "F1.1": ("ASI01", "AML.T0051.000", "NISTAML.018"),
    "F1.7": ("AML.T0085.003", "NISTAML.035"),
    "F1.8": ("ASI01",),
    "F2.1": ("ASI01", "AML.T0051.001", "NISTAML.015", "NISTAML.039"),
    "F2.5": ("ASI02", "AML.T0086", "NISTAML.039"),
    "F2.14": ("ASI04", "AML.T0110.000"),
    "F3.1": ("ASI06", "AML.T0080.000"),
    "F3.3": ("AML.T0085.002",),
    "F4.1": ("ASI07",),
    "F4.4": ("ASI03", "ASI07"),
}


def for_channel(channel: str) -> list[str]:
    return list(CHANNEL_MAP.get(channel, ()))


def for_attack_class(class_id: str) -> list[str]:
    return list(ATTACK_CLASS_MAP.get(class_id, ()))


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    """The framework identifiers for a report's leaked findings.

    Reads only ``report["findings"]`` (leaks), so it adds a key and changes
    nothing else in the report.
    """
    per_finding = []
    counts: Counter[str] = Counter()
    for finding in report.get("findings") or []:
        ids = for_channel(str(finding.get("channel") or ""))
        per_finding.append({
            "finding_id": finding.get("finding_id", ""),
            "channel": finding.get("channel", ""),
            "identifiers": ids,
        })
        counts.update(ids)
    return {
        "note": NOTE,
        "identifiers": {
            ident: {**IDENTIFIERS[ident], "findings": counts[ident]}
            for ident in sorted(counts)
        },
        "findings": per_finding,
    }


def catalog() -> dict[str, Any]:
    """Everything this module can emit, for ``/api/meta``."""
    return {
        "note": NOTE,
        "sources": SOURCES,
        "identifiers": IDENTIFIERS,
        "channels": {k: list(v) for k, v in CHANNEL_MAP.items()},
        "attack_classes": {k: list(v) for k, v in ATTACK_CLASS_MAP.items()},
    }


__all__ = [
    "ATTACK_CLASS_MAP",
    "CHANNEL_MAP",
    "IDENTIFIERS",
    "NOTE",
    "SOURCES",
    "catalog",
    "evaluate",
    "for_attack_class",
    "for_channel",
]
