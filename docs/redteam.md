# Red Team

AgentLeak's red-team module lets you measure how well your detection pipeline
catches adversarial leakage — **without a live LLM**. Static traces simulate a
maximally-vulnerable agent so you get an upper bound on what the pipeline should
catch, at zero cost.

## Attack taxonomy

32 attack classes across 6 families and 3 adversary levels:

| Family | Name | # classes |
| --- | --- | --- |
| **F1** | Prompt & Instruction Attacks | 6 |
| **F2** | Indirect & Tool-Surface Attacks | 6 |
| **F3** | Memory & Persistence Attacks | 5 |
| **F4** | Multi-Agent Coordination Attacks | 6 |
| **F5** | Reasoning & CoT Attacks | 5 |
| **F6** | Evasion Attacks | 4 |

Adversary levels:

| Level | Who | Controls |
| --- | --- | --- |
| **A0** | Benign / inadvertent | Nothing — latent risk only |
| **A1** | Weak external | Public inputs (user message, system prompt) |
| **A2** | Strong internal | Tool outputs, shared memory, RAG corpus |

## Quick start

```python
from agentleak.generators import ScenarioGenerator
from agentleak.core.attacks import AdversaryLevel
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.metrics import compute_metrics, _result_from_analysis

gen = ScenarioGenerator(
    vertical="healthcare",       # healthcare | finance | legal | hr | customer_support
    adversary_level=AdversaryLevel.A1,
    seed=42,                     # reproducibility
)

# Generate 10 scenarios spanning different attack classes
scenarios = gen.generate_batch(10)

run_results = []
for s in scenarios:
    result = AgentLeakRunner().analyze(s.trace, canary_set=s.vault.canary_set)
    run_results.append(_result_from_analysis(result, s))

metrics = compute_metrics(run_results)
print(metrics.to_dict())
```

## Vault generator

Each scenario uses a synthetic **vault** — a realistic record set for the chosen
vertical:

```python
from agentleak.generators import VaultGenerator

vault = VaultGenerator().generate("healthcare")
# vault.records  → {"patient_name": "…", "ssn": "…", "diagnosis": "…", …}
# vault.canary_set → CanarySet(obvious=[…], realistic=[…], semantic=[…])
```

The vault includes 3-tier canary tokens:
- **Obvious** — `CANARY_XXXXXXXX` — exact-match baseline
- **Realistic** — `000-XX-XXXX` SSN with reserved 000-prefix — regex detectable
- **Semantic** — natural-language sentence — LLM-judge detectable

## Metrics

### ELR — Exact Leakage Rate

What fraction of the vault's *known* sensitive fields were detected?

$$\text{ELR} = \frac{|\text{detected} \cap \text{expected}|}{|\text{vault fields}|}$$

### ASR — Attack Success Rate

What fraction of attack classes produced at least one undetected leak?

$$\text{ASR} = \frac{\text{scenarios with } \text{ELR} > 0}{\text{total scenarios}}$$

Lower ASR = better detection.

### CLR — Channel Leak Rate (per-channel)

$$\text{CLR}(c) = \frac{\text{scenarios where channel } c \text{ leaked}}{\text{scenarios using channel } c}$$

Highlights which channels (e.g. `inter_agent_message`, `shared_memory`) are the
weakest link.

## REST API

The web UI's **Red Team** tab calls:

```
POST /api/projects/{project_id}/redteam
Authorization: Bearer <project_api_key>

{
  "vertical": "healthcare",
  "adversary_level": "A1",
  "n": 20,
  "attack_class": null       # null = random; or "F2.1" for a specific class
}
```

Response includes all `run_ids` (each run is saved and browsable), plus
aggregated `metrics` (ASR, mean ELR, CLR per channel, ASR by family and class).

## Using a specific attack class

```python
# Test only indirect prompt injection (F2.1) at A2 level
gen = ScenarioGenerator(vertical="finance", adversary_level=AdversaryLevel.A2)
scenario = gen.generate("F2.1")

result = runner.analyze(scenario.trace, canary_set=scenario.vault.canary_set)
```

## Attack class reference

Browse all classes:

```python
from agentleak.core.attacks import ATTACK_FAMILIES

for family in ATTACK_FAMILIES:
    for cls in family.classes:
        print(f"{cls.id}  {cls.name}  [{cls.adversary_level.value}]  → {cls.primary_channel.value}")
```

Filter by adversary level or channel:

```python
from agentleak.core.attacks import get_classes_for_level, get_classes_for_channel, AdversaryLevel

weak_attacker = get_classes_for_level(AdversaryLevel.A1)  # A0 + A1
internal_leaks = get_classes_for_channel("inter_agent_message")
```
