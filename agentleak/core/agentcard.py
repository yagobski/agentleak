"""AgentCard — A2A-style identity card for an agent under test.

An *agent card* is a small JSON document describing an agent: its name,
capabilities, tags, example queries, protocol version, and endpoints. The
format is compatible with the Nasiko / A2A ``AgentCard.json`` convention so a
card written for an agent control plane can be registered with AgentLeak
as-is, and vice versa.

The card also carries AgentLeak-specific (optional) privacy metadata: the
data types the agent *declares* it handles and the source of its code
(a GitHub repo or an uploaded archive) so the platform can cross-check
declarations against detected leaks and run static code scans.

Local-only guarantee: parsing and validation never touch the network.
:func:`fetch_agent_card` is an explicit opt-in helper (stdlib urllib) used to
pull a card from a running agent's well-known endpoint.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Protocols commonly seen in the wild — informative only, any value is
# accepted (new protocols appear faster than any list can track).
KNOWN_PROTOCOLS = ("a2a-v1", "a2a", "mcp", "acp", "openai-assistants", "custom")

# Modes commonly seen in the wild — informative only, free-form accepted.
KNOWN_MODES = ("text", "json", "audio", "image", "video", "file", "multimodal")

# Well-known paths tried (in order) when fetching a card from an agent URL.
WELL_KNOWN_PATHS = (
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
    "/AgentCard.json",
)


@dataclass
class AgentCard:
    """Structured description of an agent (Nasiko/A2A ``AgentCard.json``)."""

    name: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    input_mode: str = "text"
    output_mode: str = "text"
    agent_protocol_version: str = "a2a-v1"
    endpoints: dict[str, str] = field(default_factory=dict)
    # AgentLeak extensions (all optional, ignored by other platforms).
    framework: str = ""
    version: str = ""
    provider: str = ""
    url: str = ""
    privacy: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)

    # -- serialisation ---------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCard:
        """Build a card from a dict, tolerating A2A/Nasiko field variants.

        - ``skills`` (official A2A card): list of skill objects — folded into
          ``capabilities`` using each skill's ``id``/``name``.
        - ``capabilities`` may be a list of strings (Nasiko) or a dict of
          feature flags (official A2A) — dict keys with truthy values are kept.
        """
        if not isinstance(data, dict):
            raise ValueError("Agent card must be a JSON object.")

        caps_raw = data.get("capabilities") or []
        capabilities: list[str] = []
        if isinstance(caps_raw, dict):
            capabilities = [str(k) for k, v in caps_raw.items() if v]
        elif isinstance(caps_raw, list):
            capabilities = [str(c) for c in caps_raw if isinstance(c, (str, int))]

        for skill in data.get("skills") or []:
            if isinstance(skill, dict):
                label = str(skill.get("id") or skill.get("name") or "").strip()
                if label and label not in capabilities:
                    capabilities.append(label)
            elif isinstance(skill, str) and skill not in capabilities:
                capabilities.append(skill)

        endpoints_raw = data.get("endpoints") or {}
        endpoints = (
            {str(k): str(v) for k, v in endpoints_raw.items()}
            if isinstance(endpoints_raw, dict)
            else {}
        )

        def _str_list(key: str) -> list[str]:
            raw = data.get(key) or []
            return [str(x) for x in raw if isinstance(x, (str, int))] if isinstance(raw, list) else []

        provider = data.get("provider")
        if isinstance(provider, dict):  # official A2A: {"organization": ...}
            provider = provider.get("organization") or provider.get("name") or ""

        return cls(
            name=str(data.get("name") or "").strip(),
            description=str(data.get("description") or ""),
            capabilities=capabilities,
            tags=_str_list("tags"),
            examples=_str_list("examples"),
            input_mode=str(data.get("input_mode") or (data.get("defaultInputModes") or ["text"])[0]),
            output_mode=str(data.get("output_mode") or (data.get("defaultOutputModes") or ["text"])[0]),
            agent_protocol_version=str(
                data.get("agent_protocol_version") or data.get("protocolVersion") or "a2a-v1"
            ),
            endpoints=endpoints,
            framework=str(data.get("framework") or ""),
            version=str(data.get("version") or ""),
            provider=str(provider or ""),
            url=str(data.get("url") or ""),
            privacy=dict(data.get("privacy") or {}),
            source=dict(data.get("source") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "tags": list(self.tags),
            "examples": list(self.examples),
            "input_mode": self.input_mode,
            "output_mode": self.output_mode,
            "agent_protocol_version": self.agent_protocol_version,
            "endpoints": dict(self.endpoints),
        }
        for key in ("framework", "version", "provider", "url"):
            value = getattr(self, key)
            if value:
                data[key] = value
        if self.privacy:
            data["privacy"] = dict(self.privacy)
        if self.source:
            data["source"] = dict(self.source)
        return data

    # -- validation --------------------------------------------------------
    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty = valid).

        Deliberately liberal: protocol versions and input/output modes are
        free-form (the A2A ecosystem moves faster than any whitelist), only
        structural coherence is enforced.
        """
        errors: list[str] = []
        if not self.name:
            errors.append("'name' is required.")
        elif len(self.name) > 120:
            errors.append("'name' must be at most 120 characters.")
        if not self.capabilities:
            errors.append("'capabilities' should list at least one capability.")
        if not isinstance(self.input_mode, str) or not self.input_mode.strip():
            errors.append("'input_mode' must be a non-empty string.")
        if not isinstance(self.output_mode, str) or not self.output_mode.strip():
            errors.append("'output_mode' must be a non-empty string.")
        src_type = str(self.source.get("type") or "")
        if src_type and src_type not in ("github", "zip", "files"):
            errors.append("'source.type' must be one of: github, zip, files.")
        if src_type == "github" and not self.source.get("repo"):
            errors.append("'source.repo' is required when source.type is 'github'.")
        declared = self.privacy.get("declared_data_types")
        if declared is not None and not isinstance(declared, list):
            errors.append("'privacy.declared_data_types' must be a list of data types.")
        return errors

    @property
    def is_valid(self) -> bool:
        return not self.validate()


def parse_agent_card(data: dict[str, Any] | str) -> AgentCard:
    """Parse a card from a dict or a JSON string, raising ``ValueError``."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid agent card JSON: {exc}") from exc
    return AgentCard.from_dict(data)  # type: ignore[arg-type]


def fetch_agent_card(url: str, *, timeout: float = 10.0) -> AgentCard:
    """Fetch an agent card from a live agent (explicit opt-in network call).

    Tries the URL as-is when it points at a JSON document, then the A2A
    well-known paths. Only http/https URLs are accepted.
    """
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("Agent card URL must start with http:// or https://")
    candidates = [url] if url.endswith(".json") else [f"{url}{p}" for p in WELL_KNOWN_PATHS]
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            req = urllib.request.Request(candidate, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")
            return parse_agent_card(raw)
        except (urllib.error.URLError, ValueError, OSError) as exc:
            last_error = exc
    raise ValueError(f"Could not fetch an agent card from {url}: {last_error}")


def platform_card(version: str = "") -> AgentCard:
    """AgentLeak's own A2A/Nasiko-compatible agent card.

    Describes the *platform itself* (not a specific project under test) so
    external agents, orchestrators, and registries (e.g. Nasiko) can
    auto-discover it as a privacy self-testing service — no authentication,
    no guessing at the API shape. Served unauthenticated at
    ``/.well-known/agent-card.json`` and printable offline via
    ``agentleak agent-card``.
    """
    return AgentCard(
        name="agentleak",
        description=(
            "Local privacy-leakage testing platform for AI agents. An agent can "
            "register itself, statically scan its own source code, run an "
            "AgentRisk + regulatory-compliance self-test, and iterate on a "
            "remediation loop (next_steps) until it passes — autonomously, "
            "through this API."
        ),
        capabilities=[
            "privacy_selftest",
            "code_privacy_scan",
            "compliance_check",
            "remediation_hints",
            "agentrisk_scoring",
            "redteam_testing",
        ],
        tags=["privacy", "compliance", "gdpr", "hipaa", "law25", "security", "audit", "agentrisk"],
        examples=[
            "test my agent for GDPR and HIPAA compliance",
            "scan my repository for hardcoded secrets and PII in code",
            "score my agent's AgentRisk and tell me how to fix the leaks",
        ],
        input_mode="json",
        output_mode="json",
        agent_protocol_version="a2a-v1",
        endpoints={
            "/api/agent/register": "Register this agent's own A2A card + declared code source",
            "/api/agent/code": "Static privacy scan of the agent's own source code",
            "/api/selftest": "Analyze a trace and score it (AgentRisk + compliance)",
            "/api/agent/improve": "Self-test + delta vs previous run + prioritised next steps",
            "/api/agent/status": "Latest run, score progression, compliance posture, next steps",
        },
        framework="agentleak",
        version=version,
        provider="agentleak-oss",
        privacy={
            "local_only": True,
            "network_calls": "opt-in only (GitHub source fetch, LLM-judge tier)",
            "auth": "X-AgentLeak-Key header or api_key in body (project-scoped ak_... key)",
        },
    )

