<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Detection quality

AgentLeak scores. A scoring product lives on measured trust, and for a year
this one published none: the gap was named in its own August 2025 audit
(*"Detection quality is unpublished. We claim severities and a score, but no
public precision/recall against a labeled set. For a scoring product,
credibility is the product."*) and stayed open.

It stayed open while the deterministic tier shipped a redactor that could not
remove a Canadian SIN, a key-name capture that ran to the end of the sentence,
and a code scan that reported a bracket as a leaked identifier. None of those
needed clever analysis. They needed somebody to count.

This page is the count, and it prints the misses next to the hits.

## What is measured

Every bundled pack scenario carries a `private_vault` of typed records. The
field name is the label, the field value is the item; 378 distinct labelled
values across the three packs survive de-duplication and the integrity check
below.

Each value is run through the **deterministic tier only** — regex and
dictionaries, the tier that runs for everyone with no API key and no extra
install. Presidio and the semantic judge are not run. A number from this page
is a floor, not a ceiling.

Two conditions are reported separately, because the deterministic tier reads
field *names* as well as values, and the two halves of the trace model differ:

| Condition | Carrier | The channels that look like this |
|---|---|---|
| **Structured** | `{"phone": "555-0152"}` | `tool_call`, `tool_response`, `shared_memory` |
| **Prose** | `The record shows 555-0152 for this case.` | `final_output`, `log`, `inter_agent_message` |

Collapsing them into one figure would hide the finding that matters most.

## How to read the result

**Structured recall is 0.926.** That is the condition covering the internal
channels this project exists to audit, and it is the number that supports the
product's claim.

**Prose recall is 0.275.** With the field name gone, the deterministic tier
finds emails and SSNs and very little else — no names, no phone numbers, no
dates of birth. This is a real limit, it is a property of regex-and-dictionary
detection rather than a defect, and it is the concrete argument for running
`--mode standard` (Presidio) or `--mode hybrid` (semantic judge) when the
channel you care about carries sentences.

It also means a clean fast-tier result on prose is **not** a statement that the
text is safe. It is "no finding from the enabled deterministic detectors", which
is what the reports say.

**False positives: zero** across the independent benign controls. These are
ordinary operational sentences, not clean counterparts derived from the leaking
fixtures — two different denominators that must never be pooled.

Two weak spots are visible even in the strong condition and are worth fixing:
`salary` at 0.343 and `health_condition` at 0.667.

## Results

AgentLeak 0.11.10 · tier: fast (deterministic: regex + dictionaries)
Not run: presidio, semantic judge.
Ground truth: private_vault records in the bundled scenario packs.

Two conditions, because the deterministic tier reads field names as well
as values. **Structured** is how `tool_call`, `tool_response` and
`shared_memory` carry a value — with the key that names it. **Prose** is
how `final_output`, `log` and `inter_agent_message` carry it — in a
sentence, with the key gone.

## Structured

**Recall 0.926** (350/378, 95% CI 0.895–0.948)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `account_number` | 1.000 | 0.757–1.000 | 12 | 0 | 0 | 12 |
| `address` | 1.000 | 0.931–1.000 | 52 | 0 | 0 | 52 |
| `date_of_birth` | 1.000 | 0.867–1.000 | 25 | 0 | 0 | 25 |
| `email` | 1.000 | 0.945–1.000 | 66 | 0 | 0 | 66 |
| `health_condition` | 0.667 | 0.417–0.848 | 10 | 0 | 5 | 15 |
| `person_name` | 1.000 | 0.962–1.000 | 96 | 0 | 0 | 96 |
| `phone_number` | 1.000 | 0.918–1.000 | 43 | 0 | 0 | 43 |
| `salary` | 0.343 | 0.208–0.508 | 12 | 0 | 23 | 35 |
| `ssn` | 1.000 | 0.898–1.000 | 34 | 0 | 0 | 34 |

## Prose

**Recall 0.275** (104/378, 95% CI 0.233–0.322)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `account_number` | 0.000 | 0.000–0.242 | 0 | 0 | 12 | 12 |
| `address` | 0.019 | 0.003–0.101 | 1 | 0 | 51 | 52 |
| `date_of_birth` | 0.000 | 0.000–0.133 | 0 | 0 | 25 | 25 |
| `email` | 1.000 | 0.945–1.000 | 66 | 0 | 0 | 66 |
| `health_condition` | 0.200 | 0.070–0.452 | 3 | 0 | 12 | 15 |
| `person_name` | 0.000 | 0.000–0.038 | 0 | 0 | 96 | 96 |
| `phone_number` | 0.000 | 0.000–0.082 | 0 | 0 | 43 | 43 |
| `salary` | 0.000 | 0.000–0.099 | 0 | 0 | 35 | 35 |
| `ssn` | 1.000 | 0.898–1.000 | 34 | 0 | 0 | 34 |

## False positives

0 detection(s) across 15 benign control texts (0.0 per text). Independent negatives — ordinary operational text, not clean counterparts derived from the leaking fixtures. Never pool the two.

## Fixture integrity

9 labelled value(s) excluded. Bundled records whose value contradicts its own field name (e.g. an 'ssn' field holding a sentence about a diagnosis). An upstream generation artefact, not a detector result; excluded from recall so the exclusion is visible.

Reproduce with `python scripts/detection_quality.py`.

## Reproducing

```bash
python scripts/detection_quality.py                      # table
python scripts/detection_quality.py --json report.json   # every number, per value
```

`docs/detection-quality.json` in this repository is the full machine-readable
report for the version named at the top of it. Every figure above carries its
numerator, its denominator, the software version, the detector tier that
produced it, and the provenance of the data it was measured on.
