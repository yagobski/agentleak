# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Synthetic, obviously fake credentials in each provider's token format.

Used by ``scripts/detection_quality_secrets.py`` and the tests. Tokens are
built at run time from a seeded random generator, and every prefix is split
by concatenation, so no complete token-shaped string exists in the
repository for a secret scanner (or GitHub push protection) to trip on. None
of these values is, or was ever, a live credential.

Each sample is ``(rule_id, expected_data_type, token)``. ``rule_id`` names the
rule in ``agentleak.detectors`` that should fire.
"""

from __future__ import annotations

import base64
import random
import string
import zlib
from collections.abc import Callable

_ALNUM = string.ascii_letters + string.digits
_UPPER_ALNUM = string.ascii_uppercase + string.digits
_HEX = "0123456789abcdef"
_URLSAFE = _ALNUM + "_-"
_B62 = string.digits + string.ascii_uppercase + string.ascii_lowercase


def _crc_token(rng: random.Random, prefix: str) -> str:
    body = "".join(rng.choice(_ALNUM) for _ in range(30))
    n, out = zlib.crc32(body.encode()), ""
    while n:
        n, r = divmod(n, 62)
        out = _B62[r] + out
    return prefix + body + out.rjust(6, "0")


def _s(rng: random.Random, alphabet: str, n: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(n))


# rule id -> (expected data type, builder)
BUILDERS: dict[str, tuple[str, Callable[[random.Random], str]]] = {
    "aws_access_key": ("aws_access_key", lambda r: "AK" + "IA" + _s(r, "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", 16)),
    "aws_temporary_access_key": ("aws_access_key", lambda r: "AS" + "IA" + _s(r, "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", 16)),
    "github_token": ("github_token", lambda r: _crc_token(r, "gh" + "p_")),
    "github_pat": ("github_token", lambda r: "github" + "_pat_" + _s(r, _ALNUM, 22) + "_" + _s(r, _ALNUM, 59)),
    "gitlab_token": ("api_key", lambda r: "gl" + "pat-" + _s(r, _URLSAFE, 20)),
    "gitlab_runner_registration": ("api_key", lambda r: "GR13" + "48941" + _s(r, _URLSAFE, 20)),
    "slack_token": ("slack_token", lambda r: "xo" + "xb-" + _s(r, string.digits, 12) + "-" + _s(r, _ALNUM, 24)),
    "slack_app_token": ("slack_token", lambda r: "xa" + "pp-1-A" + _s(r, _UPPER_ALNUM, 10) + "-" + _s(r, string.digits, 13) + "-" + _s(r, _HEX, 64)),
    "slack_config_token": ("slack_token", lambda r: "xo" + "xe.xoxp-1-" + _s(r, _ALNUM, 140)),
    "slack_webhook": ("slack_token", lambda r: "https://hooks." + "slack.com/services/T" + _s(r, _UPPER_ALNUM, 8) + "/B" + _s(r, _UPPER_ALNUM, 8) + "/" + _s(r, _ALNUM, 24)),
    "stripe_key": ("stripe_key", lambda r: "sk" + "_live_" + _s(r, _ALNUM, 24)),
    "stripe_webhook_secret": ("stripe_key", lambda r: "wh" + "sec_" + _s(r, _ALNUM, 32)),
    "llm_api_key_openai": ("llm_api_key", lambda r: "sk" + "-proj-" + _s(r, _URLSAFE, 48)),
    "llm_api_key_anthropic": ("llm_api_key", lambda r: "sk" + "-ant-api03-" + _s(r, _URLSAFE, 40)),
    "google_api_key": ("google_api_key", lambda r: "AI" + "za" + _s(r, _URLSAFE, 35)),
    "gcp_oauth_client_secret": ("api_key", lambda r: "GOC" + "SPX-" + _s(r, _URLSAFE, 28)),
    "google_oauth_access_token": ("bearer_token", lambda r: "ya" + "29." + _s(r, _URLSAFE, 60)),
    "azure_ad_client_secret": ("api_key", lambda r: _s(r, _ALNUM, 3) + "8Q" + "~" + _s(r, _ALNUM, 34)),
    "azure_storage_account_key": ("connection_string", lambda r: "Account" + "Key=" + _s(r, _ALNUM + "+/", 86) + "=="),
    "digitalocean_token": ("api_key", lambda r: "do" + "p_v1_" + _s(r, _HEX, 64)),
    "cloudflare_origin_ca_key": ("api_key", lambda r: "v1" + ".0-" + _s(r, _HEX, 24) + "-" + _s(r, _HEX, 146)),
    "databricks_token": ("api_key", lambda r: "da" + "pi" + _s(r, _HEX, 32)),
    "heroku_api_key": ("api_key", lambda r: "HR" + "KU-" + _s(r, _URLSAFE, 60)),
    "supabase_access_token": ("api_key", lambda r: "sb" + "p_" + _s(r, _HEX, 40)),
    "vault_token": ("api_key", lambda r: "hv" + "s." + _s(r, _URLSAFE, 95)),
    "npm_token": ("api_key", lambda r: _crc_token(r, "np" + "m_")),
    "pypi_token": ("api_key", lambda r: "py" + "pi-AgEIcHlwaS5vcmc" + _s(r, _URLSAFE, 60)),
    "docker_hub_token": ("api_key", lambda r: "dc" + "kr_pat_" + _s(r, _URLSAFE, 27)),
    "atlassian_api_token": ("api_key", lambda r: "AT" + "ATT3" + _s(r, _URLSAFE, 186)),
    "linear_api_key": ("api_key", lambda r: "lin" + "_api_" + _s(r, _ALNUM, 40)),
    "postman_api_key": ("api_key", lambda r: "PM" + "AK-" + _s(r, _HEX, 24) + "-" + _s(r, _HEX, 34)),
    "discord_webhook": ("api_key", lambda r: "https://discord" + ".com/api/webhooks/" + _s(r, string.digits, 18) + "/" + _s(r, _URLSAFE, 68)),
    "discord_bot_token": ("api_key", lambda r: "M" + _s(r, _ALNUM, 23) + "." + _s(r, _ALNUM, 6) + "." + _s(r, _URLSAFE, 27)),
    "telegram_bot_token": ("api_key", lambda r: _s(r, string.digits, 9) + ":" + "AA" + _s(r, _URLSAFE, 33)),
    "twilio_api_key": ("api_key", lambda r: "S" + "K" + _s(r, _HEX, 32)),
    "sendgrid_api_key": ("api_key", lambda r: "S" + "G." + _s(r, _URLSAFE, 22) + "." + _s(r, _URLSAFE, 43)),
    "mailgun_api_key": ("api_key", lambda r: "ke" + "y-" + _s(r, _HEX, 32)),
    "mailchimp_api_key": ("api_key", lambda r: _s(r, _HEX, 32) + "-u" + "s14"),
    "square_token": ("api_key", lambda r: "sq0" + "atp-" + _s(r, _URLSAFE, 22)),
    "shopify_token": ("api_key", lambda r: "sh" + "pat_" + _s(r, _HEX, 32)),
    "huggingface_token": ("api_key", lambda r: "h" + "f_" + _s(r, _ALNUM, 34)),
    "groq_api_key": ("api_key", lambda r: "gs" + "k_" + _s(r, _ALNUM, 52)),
    "xai_api_key": ("api_key", lambda r: "xa" + "i-" + _s(r, _ALNUM, 80)),
    "replicate_api_token": ("api_key", lambda r: "r" + "8_" + _s(r, _ALNUM, 37)),
    "perplexity_api_key": ("api_key", lambda r: "pp" + "lx-" + _s(r, _ALNUM, 48)),
    "grafana_token": ("api_key", lambda r: "gl" + "sa_" + _s(r, _ALNUM, 32) + "_" + _s(r, _HEX, 8)),
    "new_relic_key": ("api_key", lambda r: "NR" + "AK-" + _s(r, _UPPER_ALNUM, 27)),
    "sentry_token": ("api_key", lambda r: "sn" + "trys_" + _s(r, _URLSAFE, 60)),
    "age_secret_key": ("private_key", lambda r: "AGE-SECRET" + "-KEY-1" + _s(r, "QPZRY9X8GF2TVDW0S3JN54KHCE6MUA7L", 58)),
    "jwt": ("jwt", lambda r: "ey" + "J" + base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")[3:]
            + "." + base64.urlsafe_b64encode(b'{"sub":"synthetic-user"}').decode().rstrip("=") + "." + _s(r, _URLSAFE, 43)),
    "private_key": ("private_key", lambda r: "-----BEGIN " + "RSA PRIVATE KEY-----\n" + "\n".join(
        _s(r, _ALNUM + "+/", 64) for _ in range(4)) + "\n-----END RSA " + "PRIVATE KEY-----"),
    "connection_string": ("connection_string", lambda r: "postgres" + "ql://app:" + _s(r, _ALNUM, 16) + "@db.internal:5432/prod"),
    "kv_connection_string": ("connection_string", lambda r: "Server=" + "db.internal;Database=app;User Id=app;Pass" + "word=" + _s(r, _ALNUM, 14) + ";"),
}


def samples(per_rule: int = 3, seed: int = 20261114) -> list[tuple[str, str, str]]:
    """``per_rule`` fake tokens for every format, deterministic for a seed."""
    rng = random.Random(seed)
    out: list[tuple[str, str, str]] = []
    for rule, (data_type, build) in BUILDERS.items():
        for _ in range(per_rule):
            out.append((rule, data_type, build(rng)))
    return out


__all__ = ["BUILDERS", "samples"]
