# Bundled research fixture notices

AgentLeak-authored software and scenarios are licensed under MIT.

## PrivacyLens-derived fixtures

`privacylens_ci.json` contains 120 records derived from PrivacyLens by Shao et
al. (NeurIPS 2024 Datasets & Benchmarks), licensed under CC-BY-4.0.

Source: https://huggingface.co/datasets/SALT-NLP/PrivacyLens

The records were selected and reshaped into AgentLeak traces. The upstream
source, attribution, license, and modification statement are also stored in the
pack metadata. The canonical CC-BY-4.0 text is distributed at
`agentleak/licenses/CC-BY-4.0.txt`.

## AgentDojo-derived fixtures

`agentdojo_exfil.json` contains 100 records derived from AgentDojo by
Debenedetti et al. (NeurIPS 2024 Datasets & Benchmarks), licensed under MIT.

Source: https://github.com/ethz-spylab/agentdojo

The records were converted into AgentLeak traces. The upstream source,
attribution, license, and conversion statement are also stored in the pack
metadata. The canonical MIT text is distributed at `agentleak/licenses/MIT.txt`.

## InjecAgent-derived fixtures

`injecagent_ds.json` contains 96 records derived from InjecAgent by Zhan,
Liang, Ying and Kang (Findings of ACL 2024), licensed under MIT
(Copyright (c) 2023 Qiusi Zhan).

Source: https://github.com/uiuc-kang-lab/InjecAgent (commit
f19c9f2c79a41046eb13c03c51a24c567a8ffa07, retrieved 2026-11-14)

96 of the 544 data-stealing cases (`test_cases_ds_base.json`,
`test_cases_ds_enhanced.json`) were selected, paired with the private data in
`attacker_simulated_responses.json`, and reshaped into AgentLeak traces; an
explicit `GmailSendEmail` exfiltration step carrying that data was added, and
the stolen values were extracted as canaries. The build script is
`scripts/packs/build_injecagent_pack.py`. The canonical MIT text is
distributed at `agentleak/licenses/MIT.txt`.

## Detection rules informed by public rule sets

`agentleak/detectors/secret_rules.py` was written from vendor documentation of
each token format. Which providers to cover, and several prefix and length
facts, were cross-checked against:

- gitleaks, https://github.com/gitleaks/gitleaks, MIT, Copyright (c) 2019
  Zachary Rice (`config/gitleaks.toml`, retrieved 2026-11-14);
- detect-secrets, https://github.com/Yelp/detect-secrets, Apache-2.0,
  Copyright 2018 Yelp, Inc. (`detect_secrets/plugins/`, retrieved 2026-11-14).

No rule text or code was copied from either; the regexes were written for
AgentLeak. Check-digit algorithms in `agentleak/detectors/checksums.py` are
implemented from the public specifications they name. Full list:
`docs/detection-sources.md`.
