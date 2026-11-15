# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Outbound-request guard for model endpoints a user supplies.

A project's agent endpoint, an account's model key and the red-team override
all carry a ``base_url`` that the *server* then calls. On a hosted,
multi-account deployment that is a server-side request forgery vector: an
account can point the URL at the cloud metadata service or at another service
on the host's private network and read the answer back through the error
message or the model reply.

On a laptop or a self-hosted install the same feature is the point: the model
usually *is* on ``localhost`` (Ollama, LM Studio, vLLM). So the guard is off by
default and the web app turns it on only in public mode
(``AGENTLEAK_PUBLIC_MODE=1``). The CLI, the SDK and a self-hosted platform are
unaffected.

When the guard is on, a URL must be http(s), carry no embedded credentials and
resolve only to public addresses, and every redirect hop is checked again. The
checks are the ones the agent-card fetch already applies.
"""
from __future__ import annotations

import urllib.request
from typing import Any

from .agentcard import _SAFE_OPENER, UnsafeURLError, _assert_safe_http_url

__all__ = ["UnsafeURLError", "guard_enabled", "open_model_url", "set_outbound_guard"]

_enabled = False


def set_outbound_guard(enabled: bool) -> None:
    """Turn the guard on or off for this process (the web app calls this)."""
    global _enabled
    _enabled = bool(enabled)


def guard_enabled() -> bool:
    return _enabled


def open_model_url(request: urllib.request.Request, *, timeout: float) -> Any:
    """``urlopen`` for a user-supplied model endpoint.

    With the guard off this is exactly ``urllib.request.urlopen``. With it on,
    the target must be a public address (:class:`UnsafeURLError` otherwise) and
    redirects are re-validated hop by hop.
    """
    if not _enabled:
        return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
    try:
        _assert_safe_http_url(request.full_url)
    except UnsafeURLError as exc:
        raise UnsafeURLError(
            "This deployment only calls model endpoints on public addresses: "
            f"{str(exc).replace('Agent card URL', 'the URL')}"
        ) from exc
    return _SAFE_OPENER.open(request, timeout=timeout)
