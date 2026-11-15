<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Detection quality in French

[Detection quality](detection-quality.md) counts what the deterministic tier
finds in the bundled scenario packs, in English, and
[the Spanish page](detection-quality-es.md) does the same in Spanish. This is
the French count, measured the same way. French matters most for this
project: it is aligned with GDPR and Québec Law 25, and a Québec agent writes
French field names and French sentences.

## What is measured, and what differs

The method is the English one: the deterministic tier only (no Presidio, no
semantic judge), the same structured carriers, a value counted as found if any
carrier finds it as the expected type, type confusion counted as a miss,
Wilson intervals, and false positives counted on independent benign controls,
never pooled with recall.

| | English page | This page |
|---|---|---|
| Ground truth | `private_vault` records in the packs | 114 made-up values in `scripts/detection_quality_fr.json` |
| Field names (structured) | English (`phone`, `salary`…) | French (`telephone`, `salaire`, `date_de_naissance`, `numero_securite_sociale`…) |
| Prose carriers | English sentences | French sentences |
| Formats | US/Canadian | France and Québec: `+33`/`06 …` phones, NIR, NAS, RAMQ NAM, FR IBAN, `12 rue de la Paix, 75002 Paris` |

The controls are the fifteen English controls translated, plus five French
sentences built to trip the detectors: an order number written in pairs like a
French phone number, street names in a sentence about a walk, a floor and door
number.

Identifiers carry valid check digits (NIR key modulo 97, NAS Luhn, IBAN modulo
97, public test card numbers that pass Luhn); `tests/test_detection_quality_fr.py`
checks the fixture itself so a miss is never the fixture's fault. RAMQ NAM
values follow the published shape only; the RAMQ check is not public. No value
belongs to a real person.

## How to read the result

**Structured recall is 1.000** (114/114) and **prose recall 0.860** (98/114).
On 0.18.0 the same set gives 0.684 (78/114) and 0.623 (71/114).

Read the sequence, because the set and the rules were written by the same hand.
The French field names were added to the key-name detector first; the set was
written next, and measured before anything else changed: **1.000 structured,
0.746 prose** (85/114). The French medical terms and the gross/net salary rule
were added after that measurement, and moved prose from 0.746 to 0.860
(`health_condition` 5/10 → 10/10, `medication` 3/8 → 8/8, `salary` 0/8 → 3/8).
Those dictionary entries are general French clinical vocabulary, not the set's
values alone, but the 0.860 is not a blind figure; the 0.746 is the closer one.

**Types that validate themselves are language-independent:** email, card,
IBAN, NIR, NAS and the NAM shape are at 1.000 in both conditions. Phone numbers
are too, because French numbers carry their own shape (`+33 6 …`, `06 12 34 56
78`).

**False positives: zero** across the twenty French controls, including the
order number written like a phone number.

The remaining prose misses, by cause:

- `date_of_birth` 0/8: a bare date, by design, as in English and Spanish.
- `salary` 3/8: the five amounts that do not say gross or net ("4 100 € par
  mois", "65000 EUR", "71 000 $") are indistinguishable from a rent or a price.
- `person_name` 9/12: hyphenated or compound given names not in the gazetteer.

**Small samples.** Six to twelve values per type; a 1.000 on eight values has a
lower bound of 0.676. Read the page for which types and which causes, not for
decimals.

## Results

AgentLeak 0.18.0 · language: fr · tier: fast (deterministic: regex + dictionaries)
Not run: presidio, semantic judge.
Ground truth: made-up labelled French values in scripts/detection_quality_fr.json.

### Structured

**Recall 1.000** (114/114, 95% CI 0.967–1.000)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `address` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `credit_card` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `date_of_birth` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `email` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_condition` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_identifier` | 1.000 | 0.610–1.000 | 6 | 0 | 0 | 6 |
| `iban` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `medication` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `national_id` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `person_name` | 1.000 | 0.757–1.000 | 12 | 0 | 0 | 12 |
| `phone_number` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `salary` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `sin` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |

### Prose

**Recall 0.860** (98/114, 95% CI 0.784–0.912)

| Data type | Recall | 95% CI | Found | Wrong type | Missed | n |
|---|---:|---|---:|---:|---:|---:|
| `address` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `credit_card` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `date_of_birth` | 0.000 | 0.000–0.324 | 0 | 0 | 8 | 8 |
| `email` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_condition` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `health_identifier` | 1.000 | 0.610–1.000 | 6 | 0 | 0 | 6 |
| `iban` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `medication` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `national_id` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |
| `person_name` | 0.750 | 0.468–0.911 | 9 | 0 | 3 | 12 |
| `phone_number` | 1.000 | 0.723–1.000 | 10 | 0 | 0 | 10 |
| `salary` | 0.375 | 0.137–0.694 | 3 | 0 | 5 | 8 |
| `sin` | 1.000 | 0.676–1.000 | 8 | 0 | 0 | 8 |

### False positives

0 detection(s) across 20 benign control texts (0.0 per text). Independent negatives: the English controls translated, plus ordinary French sentences. Never pool them with recall.

Reproduce with `python scripts/detection_quality_fr.py`.

## Reproducing

```bash
python scripts/detection_quality_fr.py                      # table
python scripts/detection_quality_fr.py --json report.json   # every number
```

`docs/detection-quality-fr.json` is the full machine-readable report.
