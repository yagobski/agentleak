# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Provider token formats: prefix, length and alphabet, per vendor.

Each rule is written from the vendor's own documentation of its token format.
The choice of *which* providers to cover, and several prefix/length facts, were
cross-checked against two public rule sets:

* gitleaks (MIT, https://github.com/gitleaks/gitleaks, ``config/gitleaks.toml``)
* detect-secrets (Apache-2.0, https://github.com/Yelp/detect-secrets,
  ``detect_secrets/plugins/``)

No rule text was copied; the regexes below are written for this module, with
word boundaries on both sides and fixed or bounded lengths so none can
backtrack. Attribution and the full list of what was derived are in
``docs/detection-sources.md`` and ``src/agentleak/scenarios/packs/NOTICE.md``.

Every rule matches a *distinctive* prefix. Formats with no prefix (a Twilio
auth token, a Cloudflare global key, an AWS secret access key) are left to the
generic ``KEY = value`` rule in :mod:`.secrets`, which needs the key name.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from . import checksums


@dataclass(frozen=True)
class SecretRule:
    """One provider token format."""

    rule: str
    provider: str
    data_type: str
    pattern: re.Pattern[str]
    confidence: float
    # Raises confidence when the format carries its own checksum and it holds;
    # never required, because synthetic test tokens do not carry one.
    checksum: Callable[[str], bool] | None = None
    # A severity of "high" instead of "critical" for tokens that are not
    # credentials on their own (a webhook URL still lets anyone post).
    high_only: bool = False
    # Literal substrings at least one of which every match contains. Checked
    # with ``in`` before the regex runs, so the forty-odd rules cost a handful
    # of substring searches on the events that hold none of them.
    hints: tuple[str, ...] = ()

    @property
    def recommendation(self) -> str:
        return (f"Revoke the {self.provider} credential and inject it at the runtime "
                "boundary; never pass it through prompts, memory or tool arguments.")


def _r(body: str) -> re.Pattern[str]:
    """Boundary-wrapped: not glued to a longer token on either side."""
    return re.compile(r"(?<![A-Za-z0-9_-])" + body + r"(?![A-Za-z0-9_-])")


RULES: tuple[SecretRule, ...] = (
    # --- Cloud providers --------------------------------------------------
    SecretRule("aws_temporary_access_key", "AWS (temporary/STS key)", "aws_access_key",
               _r(r"(?:ASIA|ABIA|ACCA|A3T[A-Z0-9])[A-Z2-7]{16}"), 0.93,
               hints=('ASIA', 'ABIA', 'ACCA', 'A3T')),
    SecretRule("gcp_oauth_client_secret", "Google Cloud OAuth client", "api_key",
               _r(r"GOCSPX-[A-Za-z0-9_-]{28}"), 0.95,
               hints=('GOCSPX-',)),
    SecretRule("google_oauth_access_token", "Google OAuth", "bearer_token",
               _r(r"ya29\.[A-Za-z0-9_-]{30,}"), 0.9,
               hints=('ya29.',)),
    SecretRule("azure_ad_client_secret", "Azure AD application", "api_key",
               re.compile(r"(?<![A-Za-z0-9_~.-])[A-Za-z0-9_~.]{3}\dQ~[A-Za-z0-9_~.-]{31,34}"
                          r"(?![A-Za-z0-9_~.-])"), 0.9,
               hints=('Q~',)),
    SecretRule("azure_storage_account_key", "Azure Storage", "connection_string",
               re.compile(r"(?i)AccountKey=[A-Za-z0-9+/]{86}=="), 0.95,
               hints=('ccountKey=', 'CCOUNTKEY=', 'ccountkey=')),
    SecretRule("digitalocean_token", "DigitalOcean", "api_key",
               _r(r"do[opr]_v1_[a-f0-9]{64}"), 0.97,
               hints=('_v1_',)),
    SecretRule("cloudflare_origin_ca_key", "Cloudflare Origin CA", "api_key",
               _r(r"v1\.0-[a-f0-9]{24}-[a-f0-9]{146}"), 0.95,
               hints=('v1.0-',)),
    SecretRule("databricks_token", "Databricks", "api_key",
               _r(r"dapi[a-f0-9]{32}(?:-\d)?"), 0.93,
               hints=('dapi',)),
    SecretRule("heroku_api_key", "Heroku", "api_key",
               _r(r"HRKU-[A-Za-z0-9_-]{60}"), 0.95,
               hints=('HRKU-',)),
    SecretRule("supabase_access_token", "Supabase", "api_key",
               _r(r"sbp_[a-f0-9]{40}"), 0.93,
               hints=('sbp_',)),
    SecretRule("vault_token", "HashiCorp Vault", "api_key",
               _r(r"hv[sb]\.[A-Za-z0-9_-]{90,}"), 0.93,
               hints=('hvs.', 'hvb.')),
    # --- Code hosting and package registries ------------------------------
    SecretRule("gitlab_token", "GitLab", "api_key",
               _r(r"gl(?:pat|dt|rt|ptt|ft|imt|oas|cbt|soat|ffct)-[A-Za-z0-9_-]{20,}"), 0.95,
               hints=('gl',)),
    SecretRule("gitlab_runner_registration", "GitLab runner registration", "api_key",
               _r(r"GR1348941[A-Za-z0-9_-]{20}"), 0.95,
               hints=('GR1348941',)),
    SecretRule("npm_token", "npm", "api_key",
               _r(r"npm_[A-Za-z0-9]{36}"), 0.95, checksum=checksums.crc32_token,
               hints=('npm_',)),
    SecretRule("pypi_token", "PyPI", "api_key",
               _r(r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}"), 0.98,
               hints=('pypi-',)),
    SecretRule("docker_hub_token", "Docker Hub", "api_key",
               _r(r"dckr_(?:pat|oat)_[A-Za-z0-9_-]{27,}"), 0.95,
               hints=('dckr_',)),
    SecretRule("atlassian_api_token", "Atlassian", "api_key",
               _r(r"ATATT3[A-Za-z0-9_=-]{180,}"), 0.95,
               hints=('ATATT3',)),
    SecretRule("linear_api_key", "Linear", "api_key",
               _r(r"lin_api_[A-Za-z0-9]{40}"), 0.95,
               hints=('lin_api_',)),
    SecretRule("postman_api_key", "Postman", "api_key",
               _r(r"PMAK-[a-f0-9]{24}-[a-f0-9]{34}"), 0.95,
               hints=('PMAK-',)),
    # --- Messaging ---------------------------------------------------------
    SecretRule("slack_app_token", "Slack", "slack_token",
               _r(r"xapp-\d-[A-Z0-9]{9,12}-\d{10,16}-[a-f0-9]{32,80}"), 0.95,
               hints=('xapp-',)),
    SecretRule("slack_config_token", "Slack", "slack_token",
               _r(r"xoxe(?:\.xox[bp])?-\d-[A-Za-z0-9]{100,}"), 0.95,
               hints=('xoxe',)),
    SecretRule("slack_webhook", "Slack incoming webhook", "slack_token",
               re.compile(r"https://hooks\.slack\.com/(?:services|workflows|triggers)/"
                          r"T[A-Z0-9]{6,12}/[A-Z0-9]{6,14}/[A-Za-z0-9]{20,40}"), 0.95,
               high_only=True,
               hints=('hooks.slack.com',)),
    SecretRule("discord_webhook", "Discord webhook", "api_key",
               re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/"
                          r"\d{17,20}/[A-Za-z0-9_-]{60,70}"), 0.95, high_only=True,
               hints=('/api/webhooks/',)),
    SecretRule("discord_bot_token", "Discord bot", "api_key",
               _r(r"[MNO][A-Za-z0-9_-]{23,25}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,38}"), 0.85,
               hints=('.',)),
    SecretRule("telegram_bot_token", "Telegram bot", "api_key",
               re.compile(r"(?<![\w:])\d{8,10}:AA[A-Za-z0-9_-]{33}(?![\w-])"), 0.93,
               hints=(':AA',)),
    SecretRule("twilio_api_key", "Twilio", "api_key",
               _r(r"SK[0-9a-f]{32}"), 0.85,
               hints=('SK',)),
    SecretRule("sendgrid_api_key", "SendGrid", "api_key",
               _r(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"), 0.97,
               hints=('SG.',)),
    SecretRule("mailgun_api_key", "Mailgun", "api_key",
               _r(r"key-[a-f0-9]{32}"), 0.85,
               hints=('key-',)),
    SecretRule("mailchimp_api_key", "Mailchimp", "api_key",
               _r(r"[a-f0-9]{32}-us\d{1,2}"), 0.9,
               hints=('-us',)),
    # --- Payments and commerce --------------------------------------------
    SecretRule("stripe_webhook_secret", "Stripe webhook signing", "stripe_key",
               _r(r"whsec_[A-Za-z0-9]{32,}"), 0.9,
               hints=('whsec_',)),
    SecretRule("square_token", "Square", "api_key",
               _r(r"(?:sq0atp|sq0csp|EAAA)[A-Za-z0-9_-]{22,60}"), 0.88,
               hints=('sq0', 'EAAA')),
    SecretRule("shopify_token", "Shopify", "api_key",
               _r(r"shp(?:at|ca|pa|ss)_[a-fA-F0-9]{32}"), 0.97,
               hints=('shp',)),
    # --- AI providers (OpenAI/Anthropic keys are LLM_API_KEY_RE in secrets.py)
    SecretRule("huggingface_token", "Hugging Face", "api_key",
               _r(r"(?:hf|api_org)_[A-Za-z0-9]{34}"), 0.93,
               hints=('hf_', 'api_org_')),
    SecretRule("groq_api_key", "Groq", "api_key",
               _r(r"gsk_[A-Za-z0-9]{52}"), 0.95,
               hints=('gsk_',)),
    SecretRule("xai_api_key", "xAI", "api_key",
               _r(r"xai-[A-Za-z0-9]{80}"), 0.95,
               hints=('xai-',)),
    SecretRule("replicate_api_token", "Replicate", "api_key",
               _r(r"r8_[A-Za-z0-9]{37}"), 0.93,
               hints=('r8_',)),
    SecretRule("perplexity_api_key", "Perplexity", "api_key",
               _r(r"pplx-[A-Za-z0-9]{48}"), 0.95,
               hints=('pplx-',)),
    # --- Observability -----------------------------------------------------
    SecretRule("grafana_token", "Grafana", "api_key",
               _r(r"(?:glsa_[A-Za-z0-9]{32}_[A-Fa-f0-9]{8}|glc_[A-Za-z0-9+/]{32,400}={0,2})"), 0.93,
               hints=('glsa_', 'glc_')),
    SecretRule("new_relic_key", "New Relic", "api_key",
               _r(r"NR(?:AK|AA|II)-[A-Z0-9]{27}"), 0.93,
               hints=('NRAK-', 'NRAA-', 'NRII-')),
    SecretRule("sentry_token", "Sentry", "api_key",
               _r(r"sntr[ysu]s?_[A-Za-z0-9_=+/-]{40,}"), 0.93,
               hints=('sntr',)),
    # --- Keys and encryption ----------------------------------------------
    SecretRule("age_secret_key", "age encryption", "private_key",
               _r(r"AGE-SECRET-KEY-1[QPZRY9X8GF2TVDW0S3JN54KHCE6MUA7L]{58}"), 0.99,
               hints=('AGE-SECRET-KEY-1',)),
    SecretRule("putty_private_key", "PuTTY", "private_key",
               re.compile(r"PuTTY-User-Key-File-[23]: [a-z0-9-]+"), 0.97,
               hints=('PuTTY-User-Key-File-',)),
)


__all__ = ["RULES", "SecretRule"]
