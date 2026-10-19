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

**Recall is 0.582 in both conditions** (64/110). The structured figure is not
a rounding coincidence: it is the same values found and the same values
missed. In English the field name lifts recall from 0.574 (prose) to 0.926
(structured), because the key-name detector reads `phone`, `salary`,
`date_of_birth`, `address`. Its stems are English, so a Spanish-language
agent's tool call (`{"telefono": …}`, `{"salario": …}`,
`{"fecha_nacimiento": …}`) gets none of that lift. That is the largest single
gap on this page.

**Types that validate themselves are language-independent:** email, card,
IBAN and DNI/NIE are at 1.000 in both conditions.

**False positives: zero** across the twenty Spanish controls.

The misses, by cause:

- `address` 0/10: a Spanish address puts the street type first and the number
  after the name ("Calle Alcalá 120"), which neither the USPS nor the Québec
  shape covers.
- `spanish_social_security_number` 0/8: no detector for the NUSS yet.
- `date_of_birth` 0/8 and `salary` 0/8: the same as English prose, by design (a
  bare date or amount is indistinguishable from any other), and here also in
  the structured condition because the key is Spanish.
- `phone_number` 6/10: with `+34`/`0034` every grouping is found. Without the
  country code, `612 34 56 78` and `655123456` give nothing, and the 3-3-3
  forms (`922 123 456`) come out as `sin`, which is the documented choice for
  an ambiguous bare run.
- `person_name` 8/12: two causes. The gazetteer does not fold accents, so
  "Maria Lopez Hernandez" is found and "María López Hernández" is not, and
  "José Antonio García Pérez" is found as "Antonio García Pérez". And some
  common Spanish given names are not in it (Lucía, Manuel, Pilar).
- `health_condition` 8/10 and `medication` 6/8: dictionary gaps (`asma`,
  `insuficiencia renal`; `enalapril`, `salbutamol`).

**What the open Spanish PRs would change.** With #27, #28 and #29 merged the
same set gives **0.727** (80/110) in both conditions, still with zero false
positives: `address` 8/10 (the two misses are `Pº de Gracia 21`, an
abbreviation it doesn't know, and `Calle Real s/n`, which has no number) and
`spanish_social_security_number` 8/8. #27 fixes a false positive and doesn't
move recall. Read the 8/8 with care: the NUSS values and that detector apply
the same published rule. The addresses were written independently of #28's
tests, but by the same hand.

**Small samples.** With eight to twelve values per type the intervals are
wide (a 1.000 on eight values has a lower bound of 0.676). The page is useful
for the shape of the result (which types, which causes), not for decimals.

## Results

AgentLeak 0.17.0 · language: es · tier: fast (deterministic: regex + dictionaries)
Not run: presidio, semantic judge.
Ground truth: made-up labelled Spanish values in `scripts/detection_quality_es.json`.

### Structured

**Recall 0.582** (64/110, 95% CI 0.488–0.670)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `address` | 0.000 | 0.000–0.278 | 0 | 0 | 10 | 10 |
| `credit_card` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `date_of_birth` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |
| `email` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_condition` | 0.800 | 0.490–0.943 | 8 | 0 | 2 | 10 |
| `iban` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `medication` | 0.750 | 0.409–0.928 | 6 | 0 | 2 | 8 |
| `person_name` | 0.667 | 0.391–0.862 | 8 | 0 | 4 | 12 |
| `phone_number` | 0.600 | 0.313–0.832 | 6 | 2 (`sin`) | 2 | 10 |
| `salary` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |
| `spanish_national_id` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `spanish_social_security_number` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |

### Prose

**Recall 0.582** (64/110, 95% CI 0.488–0.670)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `address` | 0.000 | 0.000–0.278 | 0 | 0 | 10 | 10 |
| `credit_card` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `date_of_birth` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |
| `email` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_condition` | 0.800 | 0.490–0.943 | 8 | 0 | 2 | 10 |
| `iban` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `medication` | 0.750 | 0.409–0.928 | 6 | 0 | 2 | 8 |
| `person_name` | 0.667 | 0.391–0.862 | 8 | 0 | 4 | 12 |
| `phone_number` | 0.600 | 0.313–0.832 | 6 | 2 (`sin`) | 2 | 10 |
| `salary` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |
| `spanish_national_id` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `spanish_social_security_number` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |

### False positives

0 detection(s) across 20 benign control texts (0.0 per text). Independent
negatives: the English controls translated, plus ordinary Spanish sentences.
Never pool them with recall.

## Reproducing

```bash
python scripts/detection_quality_es.py                         # table
python scripts/detection_quality_es.py --json report.json      # every number
```

`docs/detection-quality-es.json` is the full machine-readable report for the
version named at the top of it. When a detector change moves these numbers,
regenerate it in the same commit.
