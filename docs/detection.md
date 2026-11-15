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
| `pii` | email, phone (North American, international with an E.164 calling code, French national format, or any number next to the word for "phone" in EN/FR/ES/DE/PT/IT), SSN (SSA issuance rules), Canadian SIN (Luhn, or the hyphenated print format), payment card (Luhn plus a network's IIN range and length), IPv4/IPv6, date of birth (keywords in six languages, numeric and month-name dates), UK NINO, Spanish DNI/NIE and NUSS, address (USPS, a US street with its city, state and ZIP, US military APO/FPO/DPO, French/Québec and Spanish shapes), person name, context-window rules for local phone numbers and dates of birth (below), and the check-digit-validated national identifiers below |
| `secrets` | 42 provider token formats (below), OpenAI/Anthropic, Google, Stripe and AWS keys, GitHub tokens (classic with CRC32 check, and fine-grained `github_pat_`), Slack tokens, JWTs, bearer tokens, private-key blocks, URL and key=value connection strings with embedded passwords, assigned secrets (`DB_PASSWORD=…`, `mot_de_passe=…`, `contraseña: …`) |
| `healthcare` | NAM and medical record numbers (`MRN 12345678`, `MRN-12345678`), health conditions and medications (EN, FR, ES dictionaries), and the phrase after a clinical cue (below) |
| `finance` | IBAN (ISO 13616: registered country, its exact length, mod-97 check), account numbers (after a keyword, or named by "account" a few words away, below), credit scores, income, loans, balances |
| `hr` | salary (after a keyword, an amount that says gross or net, or an amount a pay word names a few words away, below), sick leave, performance reviews, disciplinary actions, complaints |
| `keyname` | the value under a sensitive field name, in English, French, Spanish, German, Portuguese and Italian (`date_de_naissance`, `salario`, `Geburtsdatum`, `codice_fiscale`…), including snake_case prefixes (`current_salary`) |

### Context-window rules

Some values are ambiguous alone: `555-0152` is a phone number or a part
number, `1994-10-17` a birth date or a release date, `128000` a salary or a row
count. The fast tier does not claim them alone, and agents rarely write them
alone. `detectors/context.py` reports such a value only when a cue word in
English, French or Spanish stands a few words before it, and the words between
cue and value are glue ("is", "at", "on", "number", "est", "de", "es", "el"…)
that never cross a sentence break. A cue with no plausible value is nothing too.

| Rule | Data type | Value | Cue (examples) | Confidence |
| --- | --- | --- | --- | --- |
| `ctx_phone_local` | `phone_number` | `555-0152`, a Spanish national number without +34 | call, reach, phone, text; joindre, appelez, téléphone; llámale, teléfono, móvil | 0.55 |
| `ctx_dob` | `date_of_birth` | ISO, numeric or month-name date, plausible, not a timestamp | born, birthday, DOB; née, naissance; nació, nacimiento (up to five words between) | 0.60 |
| `ctx_account_number` | `account_number` | 6 to 20 digits, grouped or not | account, checking, savings; compte; cuenta (not after "ticket", "job", "incident"…) | 0.60 |
| `ctx_salary` | `salary` | an amount, optional currency and period | salary, wage, compensation, base pay; salaire, rémunération; sueldo, salario | 0.60 |
| `ctx_salary_verb` | `salary` | an amount *with* a currency or a period | earns, makes; gagne, touche; cobra, gana | 0.55 |
| `ctx_health_diagnosis` | `health_condition` | the noun phrase after the cue, not one opening with a determiner unless it holds a clinical word | diagnosed with; diagnostiqué; le diagnosticaron | 0.60 |
| `ctx_health_symptom` | `health_condition` | the noun phrase after the cue, only when it holds a clinical word or suffix (-itis, -osis, -algia…) | suffers from, treated for, history of; souffre de, suivi pour; padece, tratamiento por | 0.50 |

Every finding carries `metadata.rule`, and the confidence is below that of a
shape-validated match, because the type comes from the context. The cued-prose
measurement, with a development and a held-out half, is in
[Detection quality in cued prose](detection-quality-cued.md).

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

**Agreement with human labels is not published yet.** The 0.72 threshold
comes from the IEEE benchmark; how often this judge agrees with a labelled set
has not been measured. `scripts/judge_agreement.py` is the harness that will
measure it: it sends each `sensitive_info_items` fact of the PrivacyLens pack
(and seeded, derived negatives) to a judge endpoint you name, with the prompt
above, and reports Cohen's kappa with a cluster-bootstrap 95% interval, the
confusion table, the model the endpoint reported and the SHA-256 of the prompt.
It is off by default and sends nothing without `--endpoint`:

```bash
export JUDGE_KEY=...    # your own key; never on the command line
python scripts/judge_agreement.py --endpoint https://api.openai.com/v1 \
    --model gpt-4o-mini --api-key-env JUDGE_KEY --json judge-agreement.json
```

Its arithmetic is tested against a fake local judge
(`tests/test_judge_agreement.py`); no model has been run through it.

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
