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

This page is the count, and it prints the misses next to the hits. The same
count in Spanish is in [Detection quality in Spanish](detection-quality-es.md).

## What is measured

Every bundled pack scenario carries a `private_vault` of typed records. The
field name is the label, the field value is the item; 378 distinct labelled
values across the three packs that carry vaults survive de-duplication and the
integrity check below (the AgentDojo and InjecAgent packs carry canaries, not
vaults, and add nothing here).

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

**Structured recall is 1.000** (378/378; 0.926 in 0.18.0). That is the
condition covering the internal channels this project exists to audit. Read it
with its caveat: in this condition the value arrives under the field name that
labels it, and the key-name detector reads field names, so a high figure here
says the field names are known, not that the values are recognised. The two
types that moved were `salary` (0.343 → 1.000) and `health_condition`
(0.667 → 1.000): the fixtures name them `current_salary`, `expected_salary` and
`chief_complaint`, and the key-name detector now reads a snake_case prefix in
front of a known field and treats symptom fields as health data. Both rules
were written after looking at these misses.

**Prose recall is 0.574** (217/378), unchanged. With the field name gone the
deterministic tier finds emails, SSNs, most full names and most street
addresses — and still no phone numbers without an area code, no dates of
birth, no account numbers and no salaries in these carriers. The carriers carry
no cue word on purpose ("The record shows 555-0152 for this case."), and a bare
`555-0152`, `1985-03-12` or `125000` is indistinguishable from a serial number,
a date or a price. The context rules added since 0.18.0 — a phone number next
to the word for "phone" in six languages, a date after "born"/"né le"/
"geboren am", a pay figure that says gross or net — fire on real prose that
names what it is, and by design not on this benchmark. They are the concrete
argument for `--mode standard` (Presidio) or `--mode hybrid` (semantic judge)
when the channel you care about carries bare values in sentences.

It also means a clean fast-tier result on prose is **not** a statement that the
text is safe. It is "no finding from the enabled deterministic detectors", which
is what the reports say.

**False positives: zero** across the independent benign controls. These are
ordinary operational sentences, not clean counterparts derived from the leaking
fixtures — two different denominators that must never be pooled.

**Hard negatives: 0 of 82 texts flagged** (25 of 82 in 0.18.0): UUIDs, git
SHAs, version strings that look like IPs, phone-shaped order numbers,
placeholder keys (`sk-xxxx`, `<your-api-key>`, `${VAR}`), timestamps, hashes,
base64 of harmless text and prose full of place names, analysed as `log`
events by the whole fast pipeline, decoding included. The set was written
alongside the fixes it measures, so it shows those cases are handled; it says
nothing about cases nobody wrote down. As an outside check, the same detectors
over 194 CPython standard-library modules (5.2 MB not written for AgentLeak)
report 366 matches against 379 for 0.18.0, and no type that 0.18.0 did not
already report there.

Documented test card numbers (`4111 1111 1111 1111`, `4242 4242 4242 4242`) and
documentation example keys are **not** hard negatives. They are how synthetic
test data is planted in an agent under test, and AgentLeak flags them on
purpose. Placeholders that cannot be a value (`sk-xxxx…`, `****`) are not
flagged.

Credentials are measured on their own page,
[Credential coverage](detection-quality-secrets.md), and the same count in
Spanish and French is in [Detection quality in Spanish](detection-quality-es.md)
and [Detection quality in French](detection-quality-fr.md).

## Results

AgentLeak 0.18.0 · tier: fast (deterministic: regex + dictionaries)
Not run: presidio, semantic judge.
Ground truth: private_vault records in the bundled scenario packs.

Two conditions, because the deterministic tier reads field names as well
as values. **Structured** is how `tool_call`, `tool_response` and
`shared_memory` carry a value — with the key that names it. **Prose** is
how `final_output`, `log` and `inter_agent_message` carry it — in a
sentence, with the key gone.

## Structured

**Recall 1.000** (378/378, 95% CI 0.990–1.000)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `account_number` | 1.000 | 0.757–1.000 | 12 | 0 | 0 | 12 |
| `address` | 1.000 | 0.931–1.000 | 52 | 0 | 0 | 52 |
| `date_of_birth` | 1.000 | 0.867–1.000 | 25 | 0 | 0 | 25 |
| `email` | 1.000 | 0.945–1.000 | 66 | 0 | 0 | 66 |
| `health_condition` | 1.000 | 0.796–1.000 | 15 | 0 | 0 | 15 |
| `person_name` | 1.000 | 0.962–1.000 | 96 | 0 | 0 | 96 |
| `phone_number` | 1.000 | 0.918–1.000 | 43 | 0 | 0 | 43 |
| `salary` | 1.000 | 0.901–1.000 | 35 | 0 | 0 | 35 |
| `ssn` | 1.000 | 0.898–1.000 | 34 | 0 | 0 | 34 |

## Prose

**Recall 0.574** (217/378, 95% CI 0.524–0.623)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `account_number` | 0.000 | 0.000–0.242 | 0 | 0 | 12 | 12 |
| `address` | 0.635 | 0.499–0.752 | 33 | 0 | 19 | 52 |
| `date_of_birth` | 0.000 | 0.000–0.133 | 0 | 0 | 25 | 25 |
| `email` | 1.000 | 0.945–1.000 | 66 | 0 | 0 | 66 |
| `health_condition` | 0.200 | 0.070–0.452 | 3 | 0 | 12 | 15 |
| `person_name` | 0.844 | 0.758–0.903 | 81 | 0 | 15 | 96 |
| `phone_number` | 0.000 | 0.000–0.082 | 0 | 0 | 43 | 43 |
| `salary` | 0.000 | 0.000–0.099 | 0 | 0 | 35 | 35 |
| `ssn` | 1.000 | 0.898–1.000 | 34 | 0 | 0 | 34 |

## False positives

0 detection(s) across 15 benign control texts (0.0 per text). Independent negatives — ordinary operational text, not clean counterparts derived from the leaking fixtures. Never pool the two.

## Hard negatives

**0 of 82 texts flagged** (rate 0.000, 95% CI 0.000–0.045). Share of hard-negative texts with at least one finding from the full fast pipeline (decoding included). Written alongside the precision fixes it measures, so it shows those cases are handled, not that unseen ones are.

| Category | Flagged | Texts | Rate |
|---|---:|---:|---:|
| uuid | 0 | 5 | 0.000 |
| git_sha | 0 | 5 | 0.000 |
| version | 0 | 6 | 0.000 |
| timestamp | 0 | 7 | 0.000 |
| order_number | 0 | 9 | 0.000 |
| placeholder_secret | 0 | 12 | 0.000 |
| ip_like_version | 0 | 5 | 0.000 |
| phone_like_id | 0 | 5 | 0.000 |
| base64_harmless | 0 | 4 | 0.000 |
| hash | 0 | 4 | 0.000 |
| places_prose | 0 | 8 | 0.000 |
| numbers_misc | 0 | 8 | 0.000 |
| test_identifiers_obviously_fake | 0 | 4 | 0.000 |

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
