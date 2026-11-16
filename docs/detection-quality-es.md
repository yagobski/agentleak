<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Detection quality in Spanish

[Detection quality](detection-quality.md) counts what the deterministic tier
finds in the bundled scenario packs, which are in English. The roadmap asks for
precision and recall by language. This page is the Spanish count, measured the
same way so the two can be read side by side, and it prints the misses next to
the hits.

## What is measured, and what differs

The method is the English one: the same detector chain (deterministic tier
only, no Presidio, no semantic judge), the same structured carriers, a value
counted as found if any carrier finds it as the expected type, type confusion
counted as a miss, Wilson intervals, and false positives counted on
independent benign controls, never pooled with recall.

Three things differ:

| | English page | This page |
|---|---|---|
| Ground truth | `private_vault` records in the packs | 110 made-up values in `scripts/detection_quality_es.json` |
| Field names (structured) | English (`phone`, `salary`…) | Spanish (`telefono`, `salario`…) |
| Prose carriers | English sentences | Spanish sentences |

The controls are the fifteen English controls translated, plus five ordinary
Spanish sentences, some with the words the detectors could trip on ("Sin
embargo, el informe llegó sin anexos y sin firma").

Identifiers in the set carry valid check digits (DNI/NIE modulo 23, IBAN
modulo 97 with the CCC control digits, NUSS modulo 97, public test card
numbers that pass Luhn), so a detector that validates them can find them, and
`tests/test_detection_quality_es.py` checks the fixture itself so a miss is
never the fixture's fault. No value belongs to a real person.

## How to read the result

**Structured recall is 1.000** (110/110) and **prose recall 0.754** (83/110;
0.746, 82/110, in the 0.19.0 release: `enalapril` was added to the medication
dictionary). Cued prose, with a development and a held-out half, is on
[its own page](detection-quality-cued.md).
In 0.18.0 both were 0.727 (80/110): the Spanish field name gave no lift,
because the key-name detector only read English stems. It now reads the main
sensitive field names in French, Spanish, German, Portuguese and Italian
(`telefono`, `salario`, `fecha_nacimiento`, `direccion`, `diagnostico`…), which
is all of the structured gain. Those stems were written knowing this set's
field names, so the structured figure confirms the stems are in place; it is
not an independent estimate.

**Prose moved by two values, both salaries:** "1.800 € netos" and "45.000
euros brutos" say they are pay, which the new gross/net rule reads. Phone recall
is unchanged at 6/10, but one fewer phone comes out as the wrong type: a
space-separated 3-3-3 run (`922 123 456`) must now pass the SIN's Luhn check
to be called a SIN, so it is a plain miss rather than a mislabelled finding.
The hyphenated `628-111-222` is still reported as a SIN, because that is the
SIN's own print format. Without the country code or the word "teléfono", a bare
Spanish number is not found, which is the documented choice.

**Types that validate themselves are language-independent:** email, card,
IBAN, DNI/NIE and NUSS are at 1.000 in both conditions.

**False positives: zero** across the twenty Spanish controls, and zero across
the language-neutral hard negatives on the
[English page](detection-quality.md#hard-negatives).

The remaining prose misses, by cause:

- `date_of_birth` 0/8 and `salary` 2/8: a bare date or amount with no
  cue is indistinguishable from any other, by design.
- `phone_number`: national numbers with no `+34`/`0034` and no label.
- `person_name`: the gazetteer does not fold accents, and some common Spanish
  given names are not in it.
- `health_condition` and `medication`: dictionary gaps (`asma` and `litio` are
  left out on purpose, see `detectors/healthcare.py`).

**Small samples.** With eight to twelve values per type the intervals are
wide (a 1.000 on eight values has a lower bound of 0.676). The page is useful
for the shape of the result (which types, which causes), not for decimals.

## Results

AgentLeak 0.19.0 · language: es · tier: fast (deterministic: regex + dictionaries)
Not run: presidio, semantic judge.
Ground truth: made-up labelled Spanish values in scripts/detection_quality_es.json.

### Structured

**Recall 1.000** (110/110, 95% CI 0.966–1.000)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `address` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `credit_card` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `date_of_birth` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `email` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_condition` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `iban` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `medication` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `person_name` | 1.000 | 0.757–1.000 | 12 | 0 | 0 | 12 |
| `phone_number` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `salary` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `spanish_national_id` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `spanish_social_security_number` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |

### Prose

**Recall 0.754** (83/110, 95% CI 0.666–0.826)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `address` | 0.800 | 0.490–0.943 | 8 | 0 | 2 | 10 |
| `credit_card` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `date_of_birth` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |
| `email` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_condition` | 0.800 | 0.490–0.943 | 8 | 0 | 2 | 10 |
| `iban` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `medication` | 0.875 | 0.529–0.978 | 7 | 0 | 1 | 8 |
| `person_name` | 0.667 | 0.391–0.862 | 8 | 0 | 4 | 12 |
| `phone_number` | 0.600 | 0.313–0.832 | 6 | 1 (`sin`) | 3 | 10 |
| `salary` | 0.250 | 0.071–0.591 | 2 | 0 | 6 | 8 |
| `spanish_national_id` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `spanish_social_security_number` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |

### False positives

0 detection(s) across 20 benign control texts (0.0 per text). Independent negatives: the English controls translated, plus ordinary Spanish sentences. Never pool them with recall.

Reproduce with `python scripts/detection_quality_es.py`.

## Reproducing

```bash
python scripts/detection_quality_es.py                         # table
python scripts/detection_quality_es.py --json report.json      # every number
```

`docs/detection-quality-es.json` is the full machine-readable report for the
version named at the top of it. When a detector change moves these numbers,
regenerate it in the same commit.
