# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Which environment variable may be sent as an API key, and to which host.

A configuration file names the endpoint of the LLM judge, of a live agent or
of a benchmark agent, and the environment variable that holds its key. In CI
that file is often part of the repository, so a pull request can edit it. If
any name could go to any URL, a pull request could have AgentLeak read a
secret the job exposes (a deploy token, another provider's key) and send it
to a host the pull request chose.

The rule, applied everywhere a key is read from the environment for an
outbound model call:

* a known provider's key goes only to that provider's host
  (``OPENAI_API_KEY`` to ``api.openai.com`` and its subdomains, and so on);
* a variable named ``*_API_KEY`` may also go to a server on this machine
  (``localhost``, ``127.0.0.1``, ``::1``);
* anything else must be allowed by the operator in the process environment,
  never by a configuration file: ``AGENTLEAK_KEY_ENVS`` holds comma-separated
  entries ``NAME@host`` (that host and its subdomains) or ``NAME`` (any host).

Refusals are explained, so a user who meant it knows the one line to add.
"""

from __future__ import annotations

import os
import re
import urllib.parse

#: Environment variable the operator uses to allow more names or hosts.
ALLOW_ENV = "AGENTLEAK_KEY_ENVS"

#: Key variable -> hosts it may be sent to (the host itself or a subdomain).
PROVIDER_KEY_HOSTS: dict[str, tuple[str, ...]] = {
    "OPENAI_API_KEY": ("api.openai.com",),
    "OPENROUTER_API_KEY": ("openrouter.ai",),
    "ANTHROPIC_API_KEY": ("api.anthropic.com",),
    "GROQ_API_KEY": ("api.groq.com",),
    "TOGETHER_API_KEY": ("api.together.xyz",),
}

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

_NAME_RE = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_LOCAL_NAME_RE = re.compile(r"[A-Z][A-Z0-9_]*_API_KEY\Z")


def host_of(base_url: str) -> str:
    """Lower-cased host name of ``base_url``, without a trailing dot."""
    try:
        host = urllib.parse.urlparse(base_url).hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".")


def _host_matches(host: str, allowed: str) -> bool:
    allowed = allowed.lower().rstrip(".")
    return bool(host) and (host == allowed or host.endswith("." + allowed))


def _operator_allows(name: str, host: str) -> bool:
    for entry in os.environ.get(ALLOW_ENV, "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        entry_name, _, entry_host = entry.partition("@")
        if entry_name.strip() != name:
            continue
        if not entry_host.strip() or _host_matches(host, entry_host.strip()):
            return True
    return False


def refusal(name: str, base_url: str) -> str | None:
    """Why the key in ``$name`` may not be sent to ``base_url``, or None."""
    if not _NAME_RE.match(name or ""):
        return f"{name!r} is not an environment variable name AgentLeak reads keys from."
    host = host_of(base_url)
    if _operator_allows(name, host):
        return None
    hosts = PROVIDER_KEY_HOSTS.get(name)
    if hosts and any(_host_matches(host, allowed) for allowed in hosts):
        return None
    if host in LOCAL_HOSTS and _LOCAL_NAME_RE.match(name):
        return None
    if hosts:
        why = f"${name} is only sent to {', '.join(hosts)}"
    else:
        why = (
            f"${name} is not a known provider key; a configuration may send it "
            "only to a server on this machine, and only if its name ends in _API_KEY"
        )
    return (
        f"{why}, not to {host or base_url!r}. A configuration file cannot widen "
        f"this. If you mean it, set {ALLOW_ENV}={name}@{host or '<host>'} in the "
        "environment."
    )


def key_for(name: str, base_url: str) -> tuple[str, str | None]:
    """Return ``(value, refusal)`` for the key in ``$name`` bound for ``base_url``.

    ``value`` is empty when the variable is unset or the pair is refused; the
    variable is not read at all when it is refused.
    """
    if not name:
        return "", None
    why = refusal(name, base_url)
    if why:
        return "", why
    return os.environ.get(name, ""), None


def default_key(base_url: str, candidates: tuple[str, ...] | None = None) -> str:
    """The first set key, among ``candidates``, that may go to ``base_url``.

    Replaces "use OPENAI_API_KEY for any host we do not recognise": a host
    nobody vouched for gets no key.
    """
    for name in candidates or tuple(PROVIDER_KEY_HOSTS):
        value, why = key_for(name, base_url)
        if value and why is None:
            return value
    for entry in os.environ.get(ALLOW_ENV, "").split(","):
        name = entry.partition("@")[0].strip()
        if name and name not in (candidates or ()):
            value, why = key_for(name, base_url)
            if value and why is None:
                return value
    return ""
