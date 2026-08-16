# Concepts

AgentLeak has a deliberately small vocabulary: **traces**, **events**,
**channels**, **detectors**, **findings**, and a **score**.

## Trace

A `Trace` is a normalized recording of one agent run. Everything — framework
callbacks, JSON files, SDK calls — is converted into this single format, so the
detection engine never deals with framework-specific structures.

```json
{
  "run_id": "run_001",
  "agent_name": "patient_summary_agent",
  "scenario_id": "healthcare_patient_summary",
  "events": [ ... ]
}
```

## Event

An `Event` is one observable thing that happened, on a specific **channel**:

```json
{
  "event_id": "evt_002",
  "channel": "tool_call",
  "source": "orchestrator",
  "target": "ehr_database",
  "content": { "patient_name": "Jean Tremblay", "nam": "TREM12345678" },
  "metadata": { "tool_name": "get_patient_record" }
}
```

`content` can be a string or a structured object. Structured content is
flattened into readable `key: value` text for detection, so both pattern
detectors and keyword detectors work on tool arguments.

## Channels

The eight normalized channels:

| Channel | What it is |
| --- | --- |
| `user_input` | what the user gave the agent (baseline — not a leak) |
| `final_output` | the answer returned to the user |
| `inter_agent_message` | messages passed between agents |
| `shared_memory` | values written to shared/persistent memory |
| `tool_call` | arguments sent to a tool |
| `tool_response` | data returned by a tool |
| `log` | framework / application logs |
| `generated_file` | files or documents the agent produced |

The product thesis: the **internal** channels (tool calls, memory, logs) are
where the real leakage happens, and output-only audits miss it.

## Detectors

A detector scans text and emits matches. The pipeline runs up to three tiers:

| Tier | What runs | Default |
| --- | --- | --- |
| **Tier 1+2 — Regex** | Built-in pattern matchers: `pii`, `secrets`, `healthcare`, `finance`, `hr`, custom rules | Always |
| **Tier 2b — Presidio** | Presidio + 12 domain-specific recognizers (VIN, IMEI, GPS, CVV, …) | `pip install agentleak[presidio]` |
| **Tier 3 — LLM-judge** | Semantic detector: calls an OpenAI-compatible endpoint to catch paraphrased / inferred leaks | Requires API key + config |

See [Detection pipeline](detection.md) for configuration details.

## Canary tokens

A **canary token** is a synthetic secret planted in the vault before a test run.
If a canary appears in the trace AgentLeak has unambiguous, zero-false-positive
proof of a verbatim leak. Three tiers:

- **Obvious** — `CANARY_ABCD1234` (clearly fake, for baseline testing)
- **Realistic** — `000-12-3456` (valid SSN format, recognizable by detectors)
- **Semantic** — natural-language sentence (detectable only by LLM-judge)

Canary matching runs first in the pipeline, at `confidence=1.0`.

## Finding

A `Finding` is one detected leak with full context, including its AgentRisk
severity `level` (1–4):

```json
{
  "finding_id": "finding_001",
  "channel": "tool_call",
  "data_type": "health_identifier",
  "level": 4,
  "level_label": "L4",
  "severity": "critical",
  "confidence": 0.85,
  "redacted_value": "TR********78",
  "detector": "healthcare_nam_detector",
  "recommendation": "Remove or mask health identifiers before calling external tools."
}
```

Reports show the **redacted** value by default; the raw value is never written
unless you explicitly disable redaction.

## Score

Findings are combined into the **AgentRisk Risk Index** (`RI ∈ [0,1]`), a
per-channel RI breakdown, an L1–L4 severity profile, and a derived 0–100 privacy
score with a verdict. See [Scoring](scoring.md).

## Red Team

AgentLeak includes a structured adversarial test harness. A **red team run**
generates synthetic traces from a vault and injects attack payloads, then
measures how well the detection pipeline catches the leaks.

Key concepts:

- **Attack family** (F1–F6): prompt injection, indirect/tool-surface, memory,
  multi-agent, reasoning, evasion
- **Adversary level** (A0–A2): inadvertent → weak external → strong internal
- **Vault**: synthetic PII / PHI / PFI record set with 3-tier canaries
- **Metrics**: ASR (Attack Success Rate), ELR (Exact Leakage Rate), CLR
  (per-Channel Leak Rate)

See [Red Team](redteam.md).

## Defenses

The `[guardrails]` module provides two complementary runtime defenses:

- **Sanitizer** — redacts sensitive patterns from text before storage or
  forwarding. Six redaction styles: placeholder, asterisk, masked, hash,
  category, remove.
- **InternalChannelGuard** — clearance-level access control on
  `inter_agent_message` and `shared_memory` channels (which leak ~2.6× more than
  external channels per the IEEE benchmark).

See [Defenses](defenses.md).
