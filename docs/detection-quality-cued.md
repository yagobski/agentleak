<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Detection quality in cued prose

[Detection quality](detection-quality.md) reports two conditions: a value under
the field name that labels it (**structured**), and a value in a sentence with
no cue at all, "The record shows 555-0152 for this case." (**prose**, called
*uncued* here). The second is a floor: no deterministic rule can or should
call a bare `555-0152` a phone number, because it is also a part number.

Agents rarely write that way. They write "you can reach her at 555-0152",
"his date of birth is 1994-10-17", "her salary is $128,000". This page adds that
third condition, **cued prose**, for English, French and Spanish, and reports
all three conditions with a development half and a held-out half side by side.

## What is measured

- **Values**: the same labelled values as the three quality pages (378 English
  values from the bundled packs, 114 French, 110 Spanish).
- **Templates**: six natural sentences per data type and language, each with a
  cue ("You can reach her at {value} after six.", "Elle est née à Lyon le
  {value}.", "Su sueldo es de {value}."). They are in
  `scripts/detection_quality_cued.json`, written and committed **before any
  context-window rule existed** and not edited since.
- **Split**: per language and data type, values are sorted by
  `sha256("20261115|<language>|<type>|<value>")` and the first half (rounded
  up) is the development half. The first three templates of each type are the
  development templates, the last three the held-out ones. Development values
  meet development templates; held-out values meet held-out templates.
- **Scoring**: each (value, template) pair is one instance. It counts as found
  only when a finding of the expected type **overlaps the value's position** in
  the sentence; a finding elsewhere in the sentence, or of another type, is a
  miss. This is stricter than the structured and uncued conditions, which keep
  the original method (expected type among the detected types, any carrier) so
  that their numbers stay comparable with the published ones.
- **Tier**: fast (regex and dictionaries). Presidio and the semantic judge are
  not run.

## How to read the result

**The held-out column is the estimate; the development column is not.** The
rules in `detectors/context.py` were written by reading development misses
only, and frozen in a commit before the held-out half was counted. Two caveats
remain and are stated, not hidden:

- The same person wrote the templates and the rules, on the same day, so the
  held-out templates are unseen by the tuning loop but not by the author.
  Where a held-out phrasing would have needed a rule written only for it (a
  cue *after* the value, "He gave 1994-10-17 as his birth date"; "they are
  paying him $X a year"), the rule was not written, and those instances miss.
- The English values come from the bundled packs, which had been printed in
  full before the split. The address shapes added for them (a US street with
  its city, state and ZIP; APO/FPO/DPO military mail) are generic USPS formats,
  but the English `address` held-out figure is not blind.

| Language | Uncued prose, before → after (all values) | Cued prose, held-out, before → after |
| --- | --- | --- |
| English | 0.574 (217/378) → 0.627 (237/378) | 0.604 (339/561) → 0.881 (494/561) |
| French | 0.860 (98/114) → 0.860 (98/114) | 0.883 (151/171) → 0.918 (157/171) |
| Spanish | 0.746 (82/110) → 0.754 (83/110) | 0.697 (115/165) → 0.758 (125/165) |

"Before" is AgentLeak 0.19.0, "after" this tree; the version string still reads
0.19.0 because nothing has been released. The uncued gain in English is the
two address shapes (`address` 33/52 → 52/52) and one health condition
(`health_condition` 3/15 → 4/15, "opioid addiction" after "recovering from",
which sits inside the value itself); in Spanish it is one medication
(`enalapril`) added to the dictionary. Phone numbers, dates of birth, account
numbers and salaries stay at 0 in uncued prose, by design.

**What the held-out half still misses**, by cause (counted, not tuned):

- `date_of_birth` (12 EN, 2 FR, 4 ES instances): the cue comes after the value
  ("He gave {value} as his birth date", "Indicó {value} como fecha de
  nacimiento"); the rules only look before the value.
- `salary` (17 EN, 4 FR, 8 ES): a verb outside the cue list ("They are paying
  him $…", "Sa paie s'élève à", "On lui propose", "Su nómina asciende a", "Le
  ofrecen").
- `health_condition` (14 EN, 3 ES): "He mentioned his {value}" has no clinical
  cue; "treating her for" is not in the cue list ("treated for" is); and
  "fatigue", "shortness of breath", "surgery", "dependency" and "insuficiencia"
  are not in the clinical word list.
- `phone_number` (ES): "Llámala mañana al", "Mándame un mensaje al", "contactarlo
  es el" put words outside the glue list between cue and number, and the 3-3-3
  grouping is then read as a SIN.
- `medication` (ES): `salbutamol` is not in the dictionary.
- `address` (ES), `person_name`: unchanged by this work.

## False positives

The new rules were checked on four negative sets. None is pooled with recall.

| Negative set | Before | After |
| --- | --- | --- |
| Benign controls, EN/FR/ES (15 + 20 + 20 texts) | 0 / 0 / 0 detections | 0 / 0 / 0 |
| Hard negatives of round one (82 texts) | 0/82 flagged | 0/82 |
| Context look-alikes, development (52 texts) | 0/52 | 0/52 |
| Context look-alikes, held-out (52 texts) | 2/52 | 2/52 |
| CPython 3.12 standard library (196 files, 5.2 MB, 20,540 chunks) | 385 detections | 385, none from a new rule |

The context look-alikes (`scripts/detection_hard_negatives_context.json`) were
written with the templates, before any rule: an order number after "call", a
year after "born", a price after "pay", a version or job id after "account",
ISO dates in logs, timestamps, "the server suffers from…". The two held-out
texts flagged are flagged by rules that predate this work, before and after:
"The idea was born on 2021-03-04 during a hackathon" (the original birth-keyword
rule) and a log line `date de naissance: champ optionnel` (the key-name
detector).

## Results

Generated by `python scripts/detection_quality_cued.py --markdown`.

AgentLeak 0.19.0 · tier: fast (deterministic: regex + dictionaries)
Not run: presidio, semantic judge. Split seed 20261115.

| Language | Condition | Development | Held-out | All |
|---|---|---:|---:|---:|
| en | structured | 1.000 (191/191) | 1.000 (187/187) | 1.000 (378/378) |
| en | prose_uncued | 0.623 (119/191) | 0.631 (118/187) | 0.627 (237/378) |
| en | prose_cued | 0.963 (552/573) | 0.881 (494/561) | 0.922 (1046/1134) |
| fr | structured | 1.000 (57/57) | 1.000 (57/57) | 1.000 (114/114) |
| fr | prose_uncued | 0.860 (49/57) | 0.860 (49/57) | 0.860 (98/114) |
| fr | prose_cued | 0.983 (168/171) | 0.918 (157/171) | 0.950 (325/342) |
| es | structured | 1.000 (55/55) | 1.000 (55/55) | 1.000 (110/110) |
| es | prose_uncued | 0.836 (46/55) | 0.673 (37/55) | 0.754 (83/110) |
| es | prose_cued | 0.982 (162/165) | 0.758 (125/165) | 0.870 (287/330) |

### Cued prose by data type

| Language | Data type | Development | Held-out |
|---|---|---:|---:|
| en | `account_number` | 1.000 (18/18) | 1.000 (18/18) |
| en | `address` | 1.000 (78/78) | 1.000 (78/78) |
| en | `date_of_birth` | 1.000 (39/39) | 0.667 (24/36) |
| en | `email` | 1.000 (99/99) | 1.000 (99/99) |
| en | `health_condition` | 1.000 (24/24) | 0.333 (7/21) |
| en | `person_name` | 0.854 (123/144) | 0.833 (120/144) |
| en | `phone_number` | 1.000 (66/66) | 1.000 (63/63) |
| en | `salary` | 1.000 (54/54) | 0.667 (34/51) |
| en | `ssn` | 1.000 (51/51) | 1.000 (51/51) |
| fr | `address` | 1.000 (15/15) | 1.000 (15/15) |
| fr | `credit_card` | 1.000 (12/12) | 1.000 (12/12) |
| fr | `date_of_birth` | 1.000 (12/12) | 0.667 (8/12) |
| fr | `email` | 1.000 (15/15) | 1.000 (15/15) |
| fr | `health_condition` | 1.000 (15/15) | 1.000 (15/15) |
| fr | `health_identifier` | 1.000 (9/9) | 1.000 (9/9) |
| fr | `iban` | 1.000 (12/12) | 1.000 (12/12) |
| fr | `medication` | 1.000 (12/12) | 1.000 (12/12) |
| fr | `national_id` | 1.000 (12/12) | 1.000 (12/12) |
| fr | `person_name` | 0.833 (15/18) | 0.667 (12/18) |
| fr | `phone_number` | 1.000 (15/15) | 1.000 (15/15) |
| fr | `salary` | 1.000 (12/12) | 0.667 (8/12) |
| fr | `sin` | 1.000 (12/12) | 1.000 (12/12) |
| es | `address` | 1.000 (15/15) | 0.600 (9/15) |
| es | `credit_card` | 1.000 (12/12) | 1.000 (12/12) |
| es | `date_of_birth` | 1.000 (12/12) | 0.667 (8/12) |
| es | `email` | 1.000 (15/15) | 1.000 (15/15) |
| es | `health_condition` | 1.000 (15/15) | 0.800 (12/15) |
| es | `iban` | 1.000 (12/12) | 1.000 (12/12) |
| es | `medication` | 1.000 (12/12) | 0.750 (9/12) |
| es | `person_name` | 0.833 (15/18) | 0.500 (9/18) |
| es | `phone_number` | 1.000 (15/15) | 0.533 (8/15) |
| es | `salary` | 1.000 (12/12) | 0.333 (4/12) |
| es | `spanish_national_id` | 1.000 (15/15) | 1.000 (15/15) |
| es | `spanish_social_security_number` | 1.000 (12/12) | 1.000 (12/12) |

### False positives

| Negative set | Flagged |
|---|---:|
| benign controls (en) | 0 detections / 15 texts |
| benign controls (fr) | 0 detections / 20 texts |
| benign controls (es) | 0 detections / 20 texts |
| hard negatives (82, round one) | 0/82 |
| context look-alikes, development | 0/52 |
| context look-alikes, held-out | 2/52 |
- held_out: `date_of_birth` (default) matched `2021-03-04` in: The idea was born on 2021-03-04 during a hackathon.
- held_out: `date_of_birth` (default) matched `champ optionnel` in: 2024-01-31 00:00:00 INFO date de naissance: champ optionnel

Reproduce with `python scripts/detection_quality_cued.py`.

## Reproducing

```bash
python scripts/detection_quality_cued.py                        # this table
python scripts/detection_quality_cued.py --json out.json        # every number
python scripts/detection_quality_cued.py --misses development   # the tuning view
python scripts/detection_stdlib_check.py                        # the stdlib count
```

`docs/detection-quality-cued.json` is the full machine-readable report.
