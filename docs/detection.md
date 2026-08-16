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

Five built-in detector groups, all pure Python regex, zero network calls:

| Group | Data types |
| --- | --- |
| `pii` | SSN, email, phone, credit card, IBAN, address, date of birth, person name |
| `secrets` | API keys, JWTs, AWS keys, private keys, bearer tokens |
| `healthcare` | NAM (health identifier), health conditions, medications, dosages |
| `finance` | account numbers, routing numbers, SWIFTs, IBAN variants |
| `hr` | salary, employee ID, NDA references, employment contracts |

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

## Tier 2b — Presidio

Presidio with 20+ entity recognizers, plus 12 domain-specific
recognizers added by AgentLeak:

`PatientIDRecognizer` · `MedicalLicenseRecognizer` · `InsuranceIDRecognizer` ·
`IMEIRecognizer` · `VINRecognizer` · `CryptoAddressRecognizer` · `BICRecognizer` ·
`CVVRecognizer` · `PINRecognizer` · `MACAddressRecognizer` · `GPSCoordRecognizer` ·
`VRMRecognizer`

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
