# Detection pipeline

AgentLeak uses a **3-tier hybrid pipeline** that escalates from fast deterministic
matching to optional semantic analysis. Every tier is independently useful; the
higher tiers are additive, not replacements.

## Tier overview

```
FAST ─────── Tier 1+2 ── Regex detectors (stdlib, always available)
STANDARD ─── + Tier 2b ── Presidio (optional, pip install agentleak[presidio])
HYBRID ───── + Tier 3 ─── LLM-judge (optional, requires API key)
LLM_ONLY ─── Tier 3 only (evaluation / ablation use-case)
```

## Tier 1+2 — Regex detectors

Six built-in detector groups, all pure Python regex and dictionaries, zero
network calls:

| Group | Data types |
| --- | --- |
| `pii` | email, phone (North American, international with an E.164 calling code, French national format, or any number next to the word for "phone" in EN/FR/ES/DE/PT/IT), SSN (SSA issuance rules), Canadian SIN (Luhn, or the hyphenated print format), payment card (Luhn plus a network's IIN range and length), IPv4/IPv6, date of birth (keywords in six languages, numeric and month-name dates), UK NINO, Spanish DNI/NIE and NUSS, address (USPS, French/Québec and Spanish shapes), person name, and the check-digit-validated national identifiers below |
| `secrets` | 42 provider token formats (below), OpenAI/Anthropic, Google, Stripe and AWS keys, GitHub tokens (classic with CRC32 check, and fine-grained `github_pat_`), Slack tokens, JWTs, bearer tokens, private-key blocks, URL and key=value connection strings with embedded passwords, assigned secrets (`DB_PASSWORD=…`, `mot_de_passe=…`, `contraseña: …`) |
| `healthcare` | NAM (health identifier), health conditions and medications (EN, FR, ES dictionaries) |
| `finance` | IBAN (ISO 13616: registered country, its exact length, mod-97 check), account numbers, credit scores, income, loans, balances |
| `hr` | salary (after a keyword, or an amount that says gross or net), sick leave, performance reviews, disciplinary actions, complaints |
| `keyname` | the value under a sensitive field name, in English, French, Spanish, German, Portuguese and Italian (`date_de_naissance`, `salario`, `Geburtsdatum`, `codice_fiscale`…), including snake_case prefixes (`current_salary`) |

### Identifiers validated by their check digit

A shape says a string looks like an identifier; a check digit says it was built
by the issuer's algorithm. `agentleak/detectors/checksums.py` implements the
algorithms from their public specifications, and `national_ids.py` holds 15
rules (13 formats, 12 countries). Where the shape alone is not distinctive —
nine or eleven bare digits are also order numbers — the rule also needs the
naming keyword a few characters before the value.

| Rule | Identifier | Check | Needs keyword |
| --- | --- | --- | --- |
| `fr_nir` | France, NIR (sécurité sociale) | 97 − (n mod 97), Corsica 2A/2B | no |
| `it_codice_fiscale` | Italy, codice fiscale | odd/even tables, mod 26 letter | no |
| `de_steuer_id` | Germany, Steuer-ID | ISO 7064 MOD 11,10 + digit-repetition rule | yes |
| `uk_nhs_number` | UK, NHS number (reported as `health_identifier`) | mod 11, weights 10..2 | yes |
| `nl_bsn` | Netherlands, BSN | 11-proef | yes |
| `be_national_number`, `…_labelled` | Belgium, national register number | 97 − (n mod 97), 2000+ variant | formatted: no; bare: yes |
| `pl_pesel` | Poland, PESEL | weights 1-3-7-9, month carries century | yes |
| `se_personnummer` | Sweden, personnummer | Luhn on 10 digits, coordination days 61–91 | yes |
| `br_cpf`, `br_cpf_labelled` | Brazil, CPF | two mod-11 digits | formatted: no; bare: yes |
| `br_cnpj` | Brazil, CNPJ (reported as `business_identifier`, level 1) | two mod-11 digits | no |
| `in_aadhaar` | India, Aadhaar | Verhoeff | yes |
| `au_tfn` | Australia, tax file number | weighted mod 11 | yes |
| `us_ssn_labelled` | US SSN written as nine bare digits | SSA issuance rules | yes |

National identifiers are reported as `national_id`, AgentRisk level 4, like
SSN and SIN. Every finding carries `metadata.rule`, so a report says which
rule and which validator produced it.

What validation does *not* do: it never rejects a value because it is a known
test value. `4111 1111 1111 1111` and `046 454 286` pass their checks and are
reported, because that is how synthetic test data is planted in an agent under
test. Placeholders that cannot be a value (`sk-xxxx…`, `****`, `<your-key>`,
`${VAR}`) are not reported.

### Provider token formats

`agentleak/detectors/secret_rules.py` holds 42 rules for 41 providers, each a
distinctive prefix with a fixed or bounded length and alphabet, written from
the vendor's documentation and cross-checked against gitleaks (MIT) and
detect-secrets (Apache-2.0); see [detection-sources.md](detection-sources.md).
Cloud: AWS temporary keys, GCP OAuth client secrets, Google OAuth access
tokens, Azure AD client secrets, Azure Storage account keys, DigitalOcean,
Cloudflare Origin CA, Databricks, Heroku, Supabase, HashiCorp Vault. Code and
packages: GitLab (all token types), GitLab runner registration, npm (CRC32),
PyPI, Docker Hub, Atlassian, Linear, Postman. Messaging: Slack app, config and
webhook tokens, Discord bot tokens and webhooks, Telegram bots, Twilio,
SendGrid, Mailgun, Mailchimp. Payments: Stripe webhook secrets, Square,
Shopify. AI: Hugging Face, Groq, xAI, Replicate, Perplexity. Observability:
Grafana, New Relic, Sentry. Keys: age secret keys, PuTTY private keys.

Formats without a prefix (an AWS secret access key, a Twilio auth token) are
found through the key that holds them by the generic assignment rule. Coverage
is measured in [Credential coverage](detection-quality-secrets.md).

Enable/disable per group in `agentleak.yaml`:

```yaml
detectors:
  pii: true
  secrets: true
  healthcare: true
  finance: false
  hr: false
```

Add custom regex rules:

```yaml
custom_detectors:
  - name: internal_project_id
    pattern: "PROJ-[0-9]{6}"
    data_type: project_id
    severity: medium
```

### Encoded and obscured copies

The same detectors also read decoded text. Base64 (nested up to two levels,
and gzip or zlib inside base64), hex, URL-encoded components, HTML character
references, JSON/Python unicode escapes, letter-spaced strings, values padded
with zero-width characters and values written with homoglyphs or fullwidth
forms are decoded before detection, and anything that decodes to binary is
dropped. Reversed, ROT13, leetspeak and split copies are matched only against
values the trace has already exposed in plaintext, and only after they
appeared. A finding from either path carries
`metadata.transform` and is attributed to the original value, so it is the same
secret to AgentRisk. See [encoded-leaks.md](encoded-leaks.md) for the
measurement and the limits. The anchored search compares each exposed value with
each later event, so it can dominate analysis time on traces with thousands of
distinct secrets; `detection.obscured_copies: false` turns it off.

## Tier 2b — Presidio

Presidio with 20+ entity recognizers, plus 12 domain-specific
recognizers added by AgentLeak:

`PatientIDRecognizer` · `MedicalLicenseRecognizer` · `InsuranceIDRecognizer` ·
`IMEIRecognizer` · `VINRecognizer` · `CryptoAddressRecognizer` · `BICRecognizer` ·
`CVVRecognizer` · `PINRecognizer` · `MACAddressRecognizer` · `GPSCoordRecognizer` ·
`VRMRecognizer` (class names carry an `AgentLeak` prefix). `CVVRecognizer`,
`PINRecognizer` and `BICRecognizer` only fire next to one of their context words
(for example "cvv", "pin", "swift"), because their patterns alone match any short
number or any eight- or eleven-letter word.

**Install:**

```bash
pip install 'agentleak[presidio]'
python -m spacy download en_core_web_lg
```

**Configure:**

```yaml
detection:
  mode: standard          # or hybrid
  presidio:
    enabled: true
    score_threshold: 0.5  # Presidio confidence floor
```

When `presidio_analyzer` is not installed, the runner silently falls back to
FAST mode — no crash, no config error.

## Tier 3 — LLM-judge

A structured prompt sent to any OpenAI-compatible endpoint. Catches:

- Paraphrased data: *"the patient was born in the spring of 1987"*
- Inferred data: *"given those lab values she likely has type-2 diabetes"*
- Context-dependent disclosures that no regex pattern fires on

The judge returns a JSON array of `{data_type, evidence, confidence}` objects.
Only hits above `threshold` (default 0.72, calibrated on the IEEE benchmark) are
promoted to findings.

A SHA-256 LRU cache (default size 256) avoids re-calling the LLM for identical
events.

**Configure:**

```yaml
detection:
  mode: hybrid
  llm_judge:
    enabled: true
    base_url: ""          # defaults to AGENTLEAK_LLM_URL or https://api.openai.com/v1
    model: ""             # defaults to AGENTLEAK_LLM_MODEL or gpt-4o-mini
    api_key_env: OPENAI_API_KEY
    threshold: 0.72
    timeout: 30.0
```

Supported key env vars (checked in order):
`OPENAI_API_KEY` · `OPENROUTER_API_KEY` · `ANTHROPIC_API_KEY` · `TOGETHER_API_KEY` · `GROQ_API_KEY`

On any error (network, missing key, bad JSON) the LLM-judge returns `[]` — the
pipeline continues without crashing.

## Canary tokens

Canary matching runs before all other tiers, at `confidence=1.0`.

```python
from agentleak.core.canary import CanarySet
from agentleak.core.runner import AgentLeakRunner

cs = CanarySet(
    obvious=["CANARY_ABCD1234"],
    realistic=["000-12-3456"],          # SSN with reserved 000-prefix
    semantic=["patient has Marfan syndrome"],
)
result = runner.analyze(trace, canary_set=cs)
canary_hits = [f for f in result.findings if f.data_type == "canary"]
```

## Choosing a mode

| Scenario | Recommended mode |
| --- | --- |
| CI / pre-merge gate | `fast` |
| Nightly regression | `standard` (add Presidio for broader entity coverage) |
| Red team / compliance audit | `hybrid` (full semantic coverage) |
| LLM-judge ablation study | `llm_only` |

## Policy gate

Fail a CI run based on compliance framework status:

```yaml
policy_gate:
  fail_on: [hipaa, gdpr]    # any non-compliant framework → blocked=True
  fail_on_any: false
```
