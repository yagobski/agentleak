<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Detection sources

Every external source used by the detectors, the quality sets and the scenario
packs, with its licence and what was taken from it. Licences were read from the
source itself on the retrieval date. AgentLeak is MIT-licensed; a source is
used only when its licence allows redistribution inside an MIT package, or when
nothing but a public fact (an algorithm, a length, a prefix) is taken from it.

## Used

| Source | Licence | Retrieved | What AgentLeak took | Where |
|---|---|---|---|---|
| [InjecAgent](https://github.com/uiuc-kang-lab/InjecAgent), Zhan et al., Findings of ACL 2024, commit `f19c9f2` | MIT (Copyright (c) 2023 Qiusi Zhan) | 2026-11-14 | 96 of 544 data-stealing cases and the simulated private data from `attacker_simulated_responses.json`, reshaped into traces with an added exfiltration step; canaries extracted from the private data | `scenarios/packs/injecagent_ds.json`, built by `scripts/packs/build_injecagent_pack.py` |
| [gitleaks](https://github.com/gitleaks/gitleaks) `config/gitleaks.toml` | MIT | 2026-11-14 | Cross-check of which providers to cover and of prefix/length facts. No rule text copied; every regex was written for AgentLeak with boundaries and bounded lengths | `detectors/secret_rules.py` |
| [detect-secrets](https://github.com/Yelp/detect-secrets) `detect_secrets/plugins/` | Apache-2.0 | 2026-11-14 | Same cross-check, and the idea of a keyword-gated assignment rule with an entropy floor. No code copied | `detectors/secret_rules.py`, `detectors/secrets.py` |
| Vendor token documentation (GitHub, GitLab, Slack, Stripe, npm, PyPI, Docker, Hugging Face, Shopify, DigitalOcean, Databricks, Cloudflare, Twilio, SendGrid, Atlassian, Grafana, Sentry, HashiCorp, age, Azure, Google Cloud, AWS) | Documentation (facts only) | 2026-11-14 | Token prefixes, lengths and alphabets; GitHub's CRC32 checksum on `gh*_` tokens (also used by npm) | `detectors/secret_rules.py`, `detectors/checksums.py` |
| ISO/IEC 7812 (Luhn), ISO 7064 (MOD 97-10, MOD 11,10), ISO 13616 / SWIFT IBAN registry (country lengths), Verhoeff 1969 | Standards (algorithms and lengths are facts) | — | Check-digit algorithms and the IBAN length table, implemented from the specification | `detectors/checksums.py` |
| National identifier specifications: INSEE (NIR), Agenzia delle Entrate DM 23/12/1976 (codice fiscale), §139b AO (Steuer-ID), NHS Data Dictionary (NHS number), Dutch 11-proef (BSN), Belgian national register, PESEL, Skatteverket (personnummer), Receita Federal (CPF, CNPJ), UIDAI (Aadhaar), ATO (TFN), ESDC (SIN), SSA (SSN issuance) | Public specifications (facts) | — | Check-digit and structure rules, implemented from the description | `detectors/checksums.py`, `detectors/national_ids.py` |
| Card network IIN ranges (Visa, Mastercard, Amex, Discover, JCB, Diners, UnionPay, Maestro) | Publicly documented ranges (facts) | — | Prefix and length table | `detectors/checksums.py` |
| ITU-T E.164 country calling codes | Public assignment list (facts) | — | Calling-code list for international phone numbers | `detectors/pii.py` |
| Unicode confusables | Facts (a hand-written subset, not the Unicode data file) | — | Cyrillic and Greek look-alikes of Latin letters | `core/transforms.py` |

Already bundled before this work and unchanged: PrivacyLens (CC-BY-4.0) and
AgentDojo (MIT); see `src/agentleak/scenarios/packs/NOTICE.md`.

## Used as an outside check only, never shipped

| Source | Licence | Use |
|---|---|---|
| [python-stdnum](https://github.com/arthurdejong/python-stdnum) 2.x | LGPL-2.1+ | Installed in a scratch directory, outside the repository, as a differential oracle: 200,000 random inputs per format compared with `checksums.py`. Not imported, not copied, not a dependency. Disagreements that remain are deliberate and listed in `DETECTION-REPORT.md` |
| CPython 3.12 standard library sources | PSF | Read locally as text not written for AgentLeak, to count detections before and after (false-positive check) |

## Evaluated and not used

| Source | Licence found | Why not |
|---|---|---|
| AgentDAM ([facebookresearch/ai-agent-privacy](https://github.com/facebookresearch/ai-agent-privacy)) | CC-BY-NC-4.0 (`LICENSE`, read 2026-11-14) | Non-commercial |
| WASP ([facebookresearch/wasp](https://github.com/facebookresearch/wasp)) | CC-BY-NC-4.0 (`LICENSE`, read 2026-11-14) | Non-commercial |
| ai4privacy pii-masking-300k / 400k / open-500k | Custom terms forbidding redistribution, or contradictory terms | Only the format converter exists; users bring their own copy |
| TruffleHog detectors | AGPL-3.0 | Copyleft; nothing taken, not even as a reference |
| secrets-patterns-db | CC-BY-SA-4.0 with AGPL-derived rows | ShareAlike and copyleft; not consulted for rules |
| AgentHarm | MIT plus a use-restriction clause | Harmfulness, not privacy; the extra clause would travel with it |
| TAB (Text Anonymization Benchmark) | MIT | Licence fine, but the documents are real court judgments naming real people; this project ships synthetic data only |
| ConfAIde, Agent Security Bench | MIT | Licence fine; ConfAIde overlaps PrivacyLens (contextual integrity, model-only), ASB overlaps AgentDojo/InjecAgent. Left for a later pack |
| PiSAs, MCP-SafetyBench | No licence file | No licence, no redistribution |
| WHO ICD-10/11 | CC BY-ND 3.0 IGO | No-derivatives; the medical dictionaries are hand-written instead |
