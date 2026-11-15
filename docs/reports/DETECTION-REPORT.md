<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Detection report: `next/detection`

What changed in the deterministic tier on branch `next/detection`, measured
before and after with the same scripts. "Before" is `main` at `c8260cf`
(AgentLeak 0.18.0 plus two docs PRs); "after" is this branch. `agentleak.__version__`
still reads `0.18.0` on both sides because nothing has been released; every
number below names its numerator, denominator, the tier (fast: regex and
dictionaries only, no Presidio, no LLM judge) and the data it was measured on.
A clean fast-tier result means "no finding from the enabled deterministic
detectors", never "safe".

## How "before" is measured

The scripts are run from this branch against the 0.18.0 source tree, so both
columns come from one method on one input:

```bash
mkdir -p /tmp/al-before && git archive c8260cf src | tar -x -C /tmp/al-before
mkdir -p /tmp/al-before/scripts && cp scripts/detection_quality*.py scripts/detection_quality_*.json \
    scripts/detection_hard_negatives.json /tmp/al-before/scripts/
python /tmp/al-before/scripts/detection_quality.py --json before-en.json      # 0.18.0 source
python scripts/detection_quality.py --json after-en.json                      # this branch
# same pattern for _es and _fr; for the scripts that take --installed:
PYTHONPATH=/tmp/al-before/src python scripts/detection_quality_secrets.py --installed
PYTHONPATH=/tmp/al-before/src python scripts/encoded_leaks.py --installed
PYTHONPATH=/tmp/al-before/src python scripts/detection_throughput.py --installed --repeat 10
```

`detection_quality*.py` put the `src/` next to them first on `sys.path`, which
is why they are copied into the 0.18.0 tree rather than run with `--installed`.

## Summary

| Measure | Before (0.18.0) | After | Command |
|---|---:|---:|---|
| EN recall, structured | 0.926 (350/378) | 1.000 (378/378) | `python scripts/detection_quality.py` |
| EN recall, prose | 0.574 (217/378) | 0.574 (217/378) | same |
| ES recall, structured | 0.727 (80/110) | 1.000 (110/110) | `python scripts/detection_quality_es.py` |
| ES recall, prose | 0.727 (80/110) | 0.746 (82/110) | same |
| FR recall, structured | 0.684 (78/114) | 1.000 (114/114) | `python scripts/detection_quality_fr.py` |
| FR recall, prose | 0.623 (71/114) | 0.860 (98/114) | same |
| False positives, benign controls (EN 15, ES 20, FR 20 texts) | 0 / 0 / 0 | 0 / 0 / 0 | the three scripts above |
| Hard negatives flagged (texts with ≥1 finding, full fast pipeline) | 25/82 (0.305) | 0/82 (0.000, 95% CI 0.000–0.045) | `python scripts/detection_quality.py` (section "Hard negatives") |
| Credential formats recognised (3 generated tokens × 53 formats) | 36/159 tokens, 12/53 formats | 159/159, 53/53 | `python scripts/detection_quality_secrets.py` |
| Hard negatives flagged with a credential type | 8/82 | 0/82 | same |
| Encoded copies, original 9 transformations | 46/46 | 46/46 | `python scripts/encoded_leaks.py` |
| Encoded copies, 7 added transformations | 7/40 (3 trivially: leetspeak of a number is the number) | 40/40 | same |
| Bundled scenarios with an unchanged verdict (0.18.0 packs + built-ins) | — | 239/266 | see "Score shifts" |
| Held-out stdlib text: detections on 194 CPython modules, 5.2 MB | 379 | 366 | see "Held-out check" |
| Detector throughput, 0.18.0 corpus (2,164 events, 513,628 chars) | 2,606–2,732 events/s (0.62–0.65 MB/s) | 2,314–2,351 events/s (0.55–0.56 MB/s) | `python scripts/detection_throughput.py --repeat 10` |
| `analyze()` throughput, same corpus (266 traces) | 254–262 traces/s | 222–225 traces/s | same |

Throughput is three runs of best-of-10 on one x86_64 machine (Python 3.12.15)
in one session; read the ratio (about 13% slower), not the absolute numbers.

**Precision and F1 are not reported per type**, on purpose. Positives (the
labelled sets) and negatives (benign controls, hard negatives) are separate
corpora of arbitrary relative size; a precision computed by pooling them would
depend on that ratio, not on the detectors, which the project's guardrail on
numbers forbids. What is reported instead: recall per type on positives, and
the false-positive count per type on negatives, which is **zero for every type
on every negative set after** (before: `ip_address` 7, `phone_number` 7,
`secret_assignment` 3, `connection_string` 2, `ssn` 2, `credit_card` 2,
`llm_api_key` 1, `github_token` 1, `stripe_key` 1, `iban` 1 on the hard
negatives).

## Recall per data type

Counts are found / labelled values. Type confusion counts as a miss.

### English (`private_vault` records in the bundled packs)

| Data type | Structured before | Structured after | Prose before | Prose after |
|---|---:|---:|---:|---:|
| `account_number` | 12/12 | 12/12 | 0/12 | 0/12 |
| `address` | 52/52 | 52/52 | 33/52 | 33/52 |
| `date_of_birth` | 25/25 | 25/25 | 0/25 | 0/25 |
| `email` | 66/66 | 66/66 | 66/66 | 66/66 |
| `health_condition` | 10/15 | 15/15 | 3/15 | 3/15 |
| `person_name` | 96/96 | 96/96 | 81/96 | 81/96 |
| `phone_number` | 43/43 | 43/43 | 0/43 | 0/43 |
| `salary` | 12/35 | 35/35 | 0/35 | 0/35 |
| `ssn` | 34/34 | 34/34 | 34/34 | 34/34 |

### Spanish (`scripts/detection_quality_es.json`)

| Data type | Structured before | Structured after | Prose before | Prose after |
|---|---:|---:|---:|---:|
| `address` | 8/10 | 10/10 | 8/10 | 8/10 |
| `credit_card` | 8/8 | 8/8 | 8/8 | 8/8 |
| `date_of_birth` | 0/8 | 8/8 | 0/8 | 0/8 |
| `email` | 10/10 | 10/10 | 10/10 | 10/10 |
| `health_condition` | 8/10 | 10/10 | 8/10 | 8/10 |
| `iban` | 8/8 | 8/8 | 8/8 | 8/8 |
| `medication` | 6/8 | 8/8 | 6/8 | 6/8 |
| `person_name` | 8/12 | 12/12 | 8/12 | 8/12 |
| `phone_number` | 6/10 | 10/10 | 6/10 | 6/10 |
| `salary` | 0/8 | 8/8 | 0/8 | 2/8 |
| `spanish_national_id` | 10/10 | 10/10 | 10/10 | 10/10 |
| `spanish_social_security_number` | 8/8 | 8/8 | 8/8 | 8/8 |

### French (`scripts/detection_quality_fr.json`, new)

| Data type | Structured before | Structured after | Prose before | Prose after |
|---|---:|---:|---:|---:|
| `address` | 10/10 | 10/10 | 10/10 | 10/10 |
| `credit_card` | 8/8 | 8/8 | 8/8 | 8/8 |
| `date_of_birth` | 0/8 | 8/8 | 0/8 | 0/8 |
| `email` | 10/10 | 10/10 | 10/10 | 10/10 |
| `health_condition` | 5/10 | 10/10 | 5/10 | 10/10 |
| `health_identifier` | 6/6 | 6/6 | 6/6 | 6/6 |
| `iban` | 8/8 | 8/8 | 8/8 | 8/8 |
| `medication` | 3/8 | 8/8 | 3/8 | 8/8 |
| `national_id` | 0/8 | 8/8 | 0/8 | 8/8 |
| `person_name` | 9/12 | 12/12 | 9/12 | 9/12 |
| `phone_number` | 10/10 | 10/10 | 4/10 | 10/10 |
| `salary` | 1/8 | 8/8 | 0/8 | 3/8 |
| `sin` | 8/8 | 8/8 | 8/8 | 8/8 |

## How to read these numbers

- **Structured recall is the field name doing the work.** In the structured
  condition the value arrives under the key that labels it, and the key-name
  detector reads keys. The EN gains (`salary`, `health_condition`) come from
  two rules written after looking at those misses (snake_case prefixes such as
  `current_salary`; symptom fields such as `chief_complaint`). The ES/FR gains
  come from FR/ES/DE/PT/IT stems written knowing the sets' field names. They
  show the stems are in place, not an independent estimate.
- **The French set was written after the multilingual stems and before the
  French lexicon.** Measured at that point: 1.000 structured, 0.746 prose
  (85/114). The French medical terms and the gross/net salary rule then moved
  prose to 0.860. The 0.746 is the closer-to-blind figure.
- **English prose is unchanged by design.** Its carriers have no cue word, and
  a bare `555-0152`, `1985-03-12` or `125000` is not recognisable. The new
  context rules (phone keyword in six languages, birth keywords in six
  languages, gross/net pay) act on real prose that names what it is.
- **Hard negatives were written with the fixes.** 0/82 shows those cases are
  handled. The held-out check below is the independent evidence.
- **Credential coverage is generated by the same author as the rules.** It
  shows which formats are known; behaviour on real-world keys cannot be
  measured from a public repository.
- **Documented test values are positives.** `4111 1111 1111 1111`, `046 454
  286`, `AKIAIOSFODNN7EXAMPLE` are how synthetic data is planted in an agent
  under test, and the repository's own tests and benchmarks use them, so they
  are deliberately not in the hard-negative set and are still flagged. The
  brief listed provider test card numbers as hard negatives; this is a
  deliberate deviation.

## Held-out check

The detectors were run over 194 CPython 3.12 standard-library modules (5.2 MB,
split on blank lines), text nobody wrote for AgentLeak, before and after. It
found three regressions in this branch, fixed before the final count:
the snake_case key prefix read `ip_address = …`/`source_address` code as home
addresses, code references (`self.x`, `IPv4Address(`, `_private`) were taken as
field values, and a signed decimal (`+35236450.6`) read as an international
phone number. Final: 379 → 366 detections, no data type that 0.18.0 did not
already report there; the one card-number match 0.18.0 reported
(`9468822170900693`, no network IIN) is gone.

The InjecAgent pack, also not written for AgentLeak, surfaced a 0.18.0 false
positive: `2022-02-22:11:30:00` timestamps were reported as IPv6 addresses,
which was every IPv6 finding in that pack. Fixed, and added to the hard
negatives.

## Score shifts on bundled scenarios

Built-in scenarios: identical verdict, risk index and finding count, including
the quickstart's 0.44. Packs that existed in 0.18.0:

| Pack | Verdict changes | Cause |
|---|---|---|
| `agentdojo_exfil` | 23 High risk → Conditional pass; 2 High risk → Fail | IBAN validation. The attacker's account `US13 3000 0001 2121 2121 212` (and the user's `US12 2000 …` counterparty) are not IBANs: the US has none. They were being counted as leaked level-4 secrets. The canary leak is still detected in every scenario. `tests/test_agentdojo.py` now asserts "not Pass" instead of "Fail or High risk". |
| `agentleak_bench` | 2 High risk → Conditional pass (`agentleak_hea_00055`, `agentleak_hea_00155`) | `chief_complaint` symptoms are now health data. They sit only in the tool response, so they grow the observed vault (ρ_S) without leaking, which lowers RI. |
| `privacylens_ci` | none | |

Risk indexes moved in 50 AgentDojo and 14 bench scenarios in total. The
AgentRisk formula, levels and weights are unchanged; only what the detectors
find changed. If any published figure was computed on these packs, it needs
recomputing.

## Validators checked against an outside oracle

python-stdnum (LGPL-2.1+) was installed in a scratch directory outside the
repository and used only as an oracle: 200,000 random inputs per format.
Zero disagreements for NHS, BSN, PESEL, CPF, CNPJ, Aadhaar, TFN, Steuer-ID,
NIR, Belgian national number, Luhn and Verhoeff. Remaining disagreements are
deliberate:

- **SIN**: stdnum rejects a leading 0; AgentLeak accepts it, because
  `046 454 286`, the standard synthetic SIN, starts with 0.
- **Swedish personnummer**: stdnum rejects coordination numbers (day + 60);
  AgentLeak accepts them.
- **Codice fiscale**: stdnum accepts day 90 written with omocodia letters;
  AgentLeak requires a real day (1–31 or 41–71).
- **IBAN**: stdnum also checks some national BBAN check digits (BE, ES, IT…);
  AgentLeak checks the registry length, the bank-code letters for GB/IE/NL/BG/
  RO/MT/GI/VG, the CIN letter for IT/SM, and mod 97, not national BBAN keys.

## Counts (read from the code)

| What | Count | Where |
|---|---:|---|
| Provider token rules | 42 (41 providers) | `len(agentleak.detectors.secret_rules.RULES)` |
| Other new secret rules | 2 (`kv_connection_string`, `key_material_assignment`) | `detectors/secrets.py` |
| Identifier rules with a check digit | 15 (13 formats, 12 countries) | `len(agentleak.detectors.national_ids.RULES)` |
| Boolean validators | 20 | `detectors/checksums.py` (luhn, verhoeff, iso7064_mod97, iban, payment_card, us_ssn, ca_sin, fr_nir, it_codice_fiscale, de_steuer_id, uk_nhs, nl_bsn, be_national_number, pl_pesel, se_personnummer, br_cpf, br_cnpj, in_aadhaar, au_tfn, crc32_token) |
| Validators newly applied to existing detectors | 5 (IBAN, card, SSN, SIN, GitHub CRC32) | `pii.py`, `finance.py`, `secrets.py` |
| New phone / pay / DOB rules | 3 phone (`phone_international`, `phone_fr`, `phone_labelled`), 1 pay (`salary_gross_net`), DOB keywords in DE/PT/IT and month names | `pii.py`, `hr.py` |
| Key-name stems | 17 (one new: `national_id`), all extended to FR/ES/DE/PT/IT | `keyname._SENSITIVE_KEYS` |
| New decoders | 6 (HTML entities, unicode escapes, zero-width, homoglyph/fullwidth, gzip/zlib in base64, leetspeak) | `core/transforms.py` |
| New data types | 2 (`national_id` level 4, `business_identifier` level 1) | `core/agentrisk.DATA_TYPE_LEVELS` |
| Built-in detector groups | 6 (unchanged) | `agentleak.detectors.BUILTIN_DETECTORS` |
| Bundled scenarios | 362 (266 + 96 InjecAgent) | `/api/meta` → `scenarios.total` |

## Sources

See `docs/detection-sources.md` for every source, its licence, what was taken
and what was rejected. In short: InjecAgent (MIT) is bundled as a pack; gitleaks
(MIT) and detect-secrets (Apache-2.0) were a cross-check for which providers to
cover, with no rule text copied; every algorithm was implemented from its public
specification.
