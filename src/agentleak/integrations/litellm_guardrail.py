# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AgentLeak as a LiteLLM guardrail.

LiteLLM is where many teams already route model traffic; this puts AgentLeak's
flow rules on that path without a second proxy. Unlike the rest of this
package, the module imports LiteLLM when it is imported, because the class has
to subclass LiteLLM's ``CustomGuardrail`` — import it only from a LiteLLM
config, never from code that must run without LiteLLM installed.

LiteLLM proxy ``config.yaml``::

    guardrails:
      - guardrail_name: agentleak
        litellm_params:
          guardrail: agentleak.integrations.litellm_guardrail.AgentLeakGuardrail
          mode: pre_call
          default_on: true

Configure it with environment variables, so the LiteLLM config stays LiteLLM's:
``AGENTLEAK_CONFIG`` (an ``agentleak.yaml`` with ``privacy_policy.flows``),
``AGENTLEAK_EVIDENCE`` (the decision log), ``AGENTLEAK_STYLE`` (``placeholder``
or ``token``), ``AGENTLEAK_RECIPIENT`` (the name the provider goes by in flow
rules; defaults to the request's model) and ``AGENTLEAK_AGENT``.

A request whose flow a ``deny`` rule names is refused by raising, which LiteLLM
returns to the caller as an error; a refused value is redacted in place and
the request continues. With ``AGENTLEAK_STYLE=token``, tokens in the model's
answer are put back before it reaches the caller.
"""

from __future__ import annotations

import os
from typing import Any

from litellm.integrations.custom_guardrail import CustomGuardrail

from ..core.config import Config
from ..defenses.gateway import Action, Gateway
from ..llm_proxy import judged_fields

__all__ = ["AgentLeakGuardrail"]


class AgentLeakGuardrail(CustomGuardrail):
    """Judge each model request against AgentLeak flow rules before it is sent."""

    def __init__(
        self,
        *,
        config: str | None = None,
        evidence: str | None = None,
        style: str | None = None,
        recipient: str | None = None,
        agent: str | None = None,
        flows: Any = None,
        groups: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        config = config or os.environ.get("AGENTLEAK_CONFIG")
        if flows is None and config:
            policy = Config.load(config).privacy_policy
            flows, groups = list(policy.flows), dict(policy.groups)
        self.recipient = recipient or os.environ.get("AGENTLEAK_RECIPIENT", "")
        self.agent = agent or os.environ.get("AGENTLEAK_AGENT", "litellm-client")
        self.gateway = Gateway(
            flows=flows, groups=groups,
            evidence=evidence or os.environ.get("AGENTLEAK_EVIDENCE") or None,
            redaction_style=style or os.environ.get("AGENTLEAK_STYLE", "placeholder"),
            agent=self.agent,
        )

    async def async_pre_call_hook(
        self, user_api_key_dict: Any, cache: Any, data: dict, call_type: Any,
    ) -> Any:
        content = judged_fields(data)
        if not content:
            return data
        model = str(data.get("model") or "")
        recipient = self.recipient or model or "llm"
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        decision = self.gateway.check(
            content, tool=f"{recipient}/{model}", recipient=recipient, sender=self.agent,
            purpose=str((metadata or {}).get("purpose") or ""),
        )
        if decision.action == Action.BLOCK:
            raise ValueError(f"Blocked by AgentLeak privacy policy: {decision.reason}")
        if decision.action == Action.REDACT:
            data.update(decision.arguments)
        return data

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict: Any, response: Any) -> Any:
        tokenizer = self.gateway.sanitizer.tokenizer
        if tokenizer is None or len(tokenizer) == 0:
            return response
        for choice in getattr(response, "choices", None) or []:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if message is not None and isinstance(content, str):
                message.content = tokenizer.restore(content)
        return response
