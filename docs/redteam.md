# Red Team

AgentLeak's red-team module attacks an agent **scripted or live**, stores every
probe as an auditable trace, and measures whether private data crossed a real
execution boundary. Scripted traces simulate a maximally-vulnerable agent for a
zero-cost detector baseline; live campaigns execute the configured model.

## Attack taxonomy

46 attack classes across 6 families and 3 adversary levels. The original
32-class benchmark taxonomy remains intact; 14 agent-application classes add
Promptfoo-compatible coverage for BOLA, BFLA, RBAC, SQL/shell injection, SSRF,
MCP tool shadowing, debug access, excessive agency, and related risks.

| Family | Name | # classes |
| --- | --- | --- |
| **F1** | Prompt & Instruction Attacks | 9 |
| **F2** | Indirect & Tool-Surface Attacks | 15 |
| **F3** | Memory & Persistence Attacks | 5 |
| **F4** | Multi-Agent Coordination Attacks | 9 |
| **F5** | Reasoning & CoT Attacks | 5 |
| **F6** | Evasion Attacks | 3 |

## Plugins and strategies

AgentLeak follows Promptfoo's useful separation without taking a runtime
dependency on Promptfoo:

- **Plugin — what to test.** Examples: `pii:direct`, `bola`, `ssrf`,
  `agentic:memory-poisoning`, `mcp`.
- **Strategy — how to deliver it.** Examples: direct baseline, jailbreak
  template, authoritative markup, Base64/hex/ROT13/leetspeak/homoglyph evasion,
  and four-turn Crescendo.
- **Target — what executes the attack.** The deterministic scripted target or
  the project's configured OpenAI-compatible live endpoint.
- **Evidence — what proves success.** AgentRisk findings on final output, tool
  calls, memory, inter-agent messages, logs, and files.

The catalog intentionally includes the Promptfoo plugins that map to observable
agent privacy and application-security behavior. Generic brand, political,
toxicity, and content-safety plugins are not presented as privacy leakage tests.
Use `GET /api/redteam/catalog` to inspect the current catalog, requirements,
presets, and strategy profiles.

Adversary levels:

| Level | Who | Controls |
| --- | --- | --- |
| **A0** | Benign / inadvertent | Nothing — latent risk only |
| **A1** | Weak external | Public inputs (user message, system prompt) |
| **A2** | Strong internal | Tool outputs, shared memory, RAG corpus |

## Quick start

This section is the shortest reproducible path. The detailed workflow below
explains how to choose a target, plugins, strategies, and a report policy.

```python
from agentleak.generators import ScenarioGenerator
from agentleak.core.attacks import AdversaryLevel, CLASS_TO_FAMILY
from agentleak.core.runner import AgentLeakRunner
from agentleak.core.metrics import compute_metrics, _result_from_analysis

gen = ScenarioGenerator(
    vertical="healthcare",       # healthcare | finance | legal | hr | customer_support
    adversary_level=AdversaryLevel.A1,
    seed=42,                     # reproducibility
    plugin_ids=["pii:direct", "bola", "data-exfil"],
    strategy_ids=["basic", "jailbreak-template", "crescendo"],
)

# Generate 10 scenarios spanning different attack classes
scenarios = gen.generate_batch(10)

run_results = []
for s in scenarios:
    result = AgentLeakRunner().analyze(s.trace, canary_set=s.vault.canary_set)
    run_results.append(_result_from_analysis(
        result,
        scenario_id=s.scenario_id,
        vertical=s.vertical,
        attack_class_id=s.attack_class.id,
        attack_family_id=CLASS_TO_FAMILY.get(s.attack_class.id, "unknown"),
        primary_channel=s.attack_class.primary_channel.value,
        adversary_level=s.attack_class.adversary_level.value,
        vault_field_count=len(s.vault.records),
        expected_leaks=s.expected_leaks,
    ))

metrics = compute_metrics(run_results)
print(metrics.to_dict())
```

The scripted path is deterministic, offline, and does not require an LLM key.
It is the recommended first run and the best fit for pull-request regression
tests.

## Five-minute campaign

### Prerequisites

Install AgentLeak locally and use synthetic or canary data whenever possible:

```bash
pip install "agentleak @ git+https://github.com/yagobski/agentleak-oss.git"
# Optional local UI and API server:
pip install 'agentleak[gui]'
```

You need a project to run a hosted campaign. On a self-hosted instance, create
an account, create a project, and open the **Red Team** tab. The tab loads the
live catalog from `GET /api/redteam/catalog`, so the choices shown in the UI
always match the installed server version.

### 1. Describe the target

Choose the vertical whose synthetic vault best matches the agent:

| Vertical | Typical protected data |
| --- | --- |
| `healthcare` | patient identity, diagnosis, medication, insurance |
| `finance` | account, transaction, tax and payment details |
| `legal` | client identity, matter, privileged case information |
| `hr` | employee identity, compensation and performance data |
| `customer_support` | account identity, contact details and ticket history |

Set the adversary level to match the access the attacker is allowed to have:

- `A0`: benign or inadvertent behavior;
- `A1`: external user input and prompt injection;
- `A2`: stronger internal access to tools, RAG, memory or hand-offs.

Start with `A1` for a public agent. Add `A2` only when the test fixture is
authorized to model compromised internal surfaces.

### 2. Choose what to test

Plugins describe the vulnerability objective. Use a preset for a first pass,
then narrow the campaign to the plugins that matter for the product:

| Preset | Use it for |
| --- | --- |
| `privacy_core` | direct PII, API/database, session and social extraction |
| `agent_core` | prompt extraction, indirect injection, exfiltration and excessive agency |
| `tool_security` | BOLA/BFLA/RBAC, injection, SSRF, tool discovery and MCP |
| `complete` | the full AgentLeak plugin catalog |

For a targeted campaign, pass plugin IDs such as `pii:direct`, `bola`, `ssrf`,
`mcp`, or `agentic:memory-poisoning`. The catalog is authoritative; use it to
discover the current descriptions, severity, required surface, and mapped
attack classes instead of hard-coding an ID list in a client.

### 3. Choose how to deliver the attack

Strategies are delivery transformations applied to each generated probe:

| Strategy | What it exercises |
| --- | --- |
| `basic` | direct baseline behavior |
| `jailbreak-template` | authority and resilience-drill framing |
| `authoritative-markup` | trusted-looking policy markup |
| `base64`, `hex`, `rot13` | decoding and input normalization |
| `leetspeak`, `homoglyph` | lexical and Unicode canonicalization |
| `crescendo` | four-turn context building and escalation |

Use `strategy_profile: balanced` for a practical default, `baseline` for a
fast regression check, `evasion` for normalization controls, or `complete` for
all nine strategies. A custom `strategies` list takes precedence over a profile.

### 4. Run the campaign

From the hosted dashboard, open a project, select **Red Team**, choose the
vertical, level, plugins and strategies, then click **Run**. The UI supports
both modes:

- **Scripted** generates a deterministic maximally-vulnerable trace and runs the
  detector baseline. It is free, offline, and useful for validating coverage.
- **Live** sends each generated scenario to the configured OpenAI-compatible
  agent endpoint. It tests the real agent behavior and requires a configured
  model/key (BYOK on the public service).

The API equivalent is:

```bash
curl -sS -X POST "$AGENTLEAK_BASE/api/projects/$PROJECT_ID/redteam" \
  -H 'content-type: application/json' \
  -H "Cookie: $AGENTLEAK_SESSION" \
  -d '{
    "vertical": "healthcare",
    "adversary_level": "A1",
    "n": 10,
    "plugin_preset": "agent_core",
    "strategy_profile": "balanced",
    "mode": "scripted"
  }'
```

The red-team endpoint is a human project endpoint and uses the authenticated
session cookie. Autonomous clients should first use the documented agent
onboarding flow, then submit traces to `/api/selftest`; a project-scoped key is
not a substitute for a browser session on this campaign endpoint.

### 5. Read and repeat

The response contains one saved `run_id` per executed scenario, an `attacks`
array, aggregate metrics, and a `coverage` object. Open the project runs to
inspect a probe's full trace and its AgentRisk findings. Fix the highest-risk
channel, rerun the same plugin/strategy selection, and compare the defense rate
and leakage metrics.

## Target modes and live configuration

### Scripted target

The scripted target is generated from a synthetic vault and the selected attack
class. It deliberately provides a strong detector baseline: if a detector or
report cannot identify the expected leak in this trace, the test setup itself
needs attention. Scripted results do not claim that a real model would behave
the same way.

### Live target

Live mode builds a real run context from the same scenario, sends the attack
turns to the configured agent, and analyzes the resulting trace. Configure an
OpenAI-compatible endpoint in the project settings or provide an override in
the request:

```json
{
  "mode": "live",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "openai/gpt-4o-mini",
  "api_key": "<BYOK key, never commit this>"
}
```

On the public deployment, live tests and LLM-judge detection are BYOK. The
deterministic regex, entropy and configured local detectors do not require a
platform key. Never send production credentials or real personal data to an
unauthorized target.

## Campaign sizing and coverage

`n` is capped at 20 scenarios per request. The generator de-duplicates attack
classes and combines selected plugins with selected strategies. A small `n`
may therefore exercise only part of a requested matrix. Always check:

```json
{
  "coverage": {
    "plugins_requested": [],
    "plugins_exercised": [],
    "plugins_not_exercised": [],
    "strategies_requested": [],
    "strategies_exercised": []
  }
}
```

For a complete matrix, either increase `n` across several authorized runs or
select one plugin at a time. Keep the catalog version and campaign payload with
the report so results remain reproducible after the catalog evolves.

## Understanding the report

The dashboard groups successful attacks by severity and shows a defense rate,
mean leakage, privacy score, top exposure channel, and attack method. The raw
response also exposes:

- `run_ids`: saved reports for drill-down and audit history;
- `attacks`: plugin, strategy, class, turns, success and redacted evidence;
- `metrics.overall_asr`: how often the intended attack succeeded;
- `metrics.mean_elr`: mean fraction of expected vault fields exposed;
- `metrics.clr_per_channel`: the weakest execution channels;
- ASR breakdowns by family and attack class.

Interpret the rates as security-test outcomes, not as probabilities that a
future attack will succeed. A high ASR or CLR identifies a regression and a
surface to fix; it is not a legal or compliance certification.

## CI and regression testing

Run a small scripted campaign in CI through a test that calls the same generator
and runner as the local quickstart. Fail the job when the campaign exceeds the
team's policy, for example:

```python
assert metrics.overall_asr <= 0.10
assert metrics.mean_elr <= 0.05
```

Keep the plugin IDs, strategy IDs, vertical, adversary level, seed, and policy
in version control. A useful CI split is:

1. `baseline` profile on every pull request;
2. `balanced` on the protected branch;
3. `complete` and `evasion` on a scheduled security run;
4. live BYOK campaigns only in a protected environment with an authorized
   test endpoint.

## REST reference

`GET /api/redteam/catalog` returns the catalog version, 46 attack classes, six
families, 24 native plugins, 38 Promptfoo privacy/security transpositions (62
executable plugin IDs total),
nine strategies, plugin presets, and strategy profiles.
`POST /api/projects/{project_id}/redteam` accepts the following optional fields:

| Field | Values | Default |
| --- | --- | --- |
| `vertical` | five supported vertical IDs | `healthcare` |
| `n` | integer, 1–20 | `5` |
| `adversary_level` | `A0`, `A1`, `A2` | `A1` |
| `attack_class` | class ID such as `F1.1` | balanced batch |
| `plugins` | plugin ID strings or `{id, numTests, config}` objects | preset |
| `plugin_preset` | `privacy_core`, `agent_core`, `tool_security`, `complete` | `agent_core` |
| `strategies` | strategy ID array | profile |
| `strategy_profile` | `baseline`, `balanced`, `evasion`, `complete` | `balanced` |
| `mode` | `auto`, `live`, `scripted` | `auto` |
| `base_url`, `model`, `api_key` | live endpoint override | project settings |

The endpoint returns `400` for unknown plugin/strategy IDs or a live campaign
without a configured endpoint, and `502` when the live target cannot be
reached. Treat those as setup/target failures rather than defended attacks.

## Safe operating boundary

Only test agents and data for which you have authorization. Prefer synthetic
vaults and canaries; redact reports before sharing them. A passing scripted run
proves detector coverage, and a passing live run is evidence for the tested
configuration and attack set only. It does not prove that untested prompts,
tools, memory paths, integrations, or future model versions are safe.

## Further reading

- [Quickstart](quickstart.md) — install AgentLeak and run a first analysis
- [Scoring](scoring.md) — AgentRisk, ASR, ELR and CLR definitions
- [Scenarios](scenarios.md) — built-in vaults and scenario coverage
- [Defenses](defenses.md) — sanitization and internal-channel controls
- [Integrations](integrations.md) — capture traces from supported frameworks
- [Hosted red-team feature](https://agentleak.org/features/red-team) — visual campaign workflow

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

What fraction of attack classes achieved their intended disclosure — i.e. at
least one expected leak was actually detected on the attack's **primary
channel** (the channel the attack class targets)?

$$\text{ASR} = \frac{|\{i : \text{detected\_on\_primary}_i \cap \text{expected}_i \neq \emptyset\}|}{N}$$

Higher ASR means more attacks succeeded in extracting the target secret on the
channel they were designed to exploit — **lower ASR is better** for the system
under test (fewer attacks worked).

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
  "adversary_level": "A2",
  "n": 20,
  "plugins": ["pii:direct", "bola", "mcp", "agentic:memory-poisoning"],
  "strategies": ["basic", "jailbreak-template", "crescendo"],
  "mode": "live"
}
```

Response includes all `run_ids` (each run is saved and browsable), plus
aggregated `metrics` (ASR, mean ELR, CLR per channel, ASR by family and class),
the result of each plugin/strategy pair, and a `coverage` object that explicitly
lists requested, exercised, and budget-limited plugins.

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
