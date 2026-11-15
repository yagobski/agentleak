<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Scenario packs and security-framework mapping (next2/packs)

Branch `next2/packs`, based on v0.19.0. Sources retrieved on 2026-11-15.

## Summary

| Pack | Scenarios | Clean counterparts | Channel(s) | Licence |
|---|---:|---:|---|---|
| `agentsocialbench_ma` | 105 | 105 (shipped, abstraction) | 50 `inter_agent_message`, 55 `shared_memory` | MIT |
| `mcptox_recipient_hijack` | 24 | 24 (shipped, recorded model call) | 24 `tool_call` | CC-BY-4.0 |

Bundled total: 362 → **491** (10 built-in + 36 + 120 + 100 + 96 + 105 + 24).
The corpus had 13 scenarios with an `inter_agent_message` leak; it now has 63,
and 55 more on `shared_memory`.

## Sources used

### AgentSocialBench — MIT, used

- Repository: https://github.com/kingofspace0wzz/agentsocialbench
- Commit: `6d8497c05dbab812714b2545a563e6fe7d4160ec` (2026-06-19)
- Licence file: `LICENSE`, MIT, "Copyright (c) 2026 Prince Zizhuang Wang, Shuli
  Jiang". Data lives in the same repository (`prism/data/scenarios/`), so the
  repository licence covers it. Verdict: redistributable inside an MIT package
  with the copyright notice.
- Personal data: the scenarios are model-generated personas (each file records
  `generated_by`, e.g. `gpt-5.2`). No real person's record. Real institutions
  appear as places (a university, a county court) but not as data subjects.
- Selection (reproducible, in the build script): five categories with a
  per-category quota (cross_user 25, cross_domain 25, multi_party_group 20,
  hub_and_spoke 15, affinity_modulated 20); files ordered by SHA-256 of
  `scenario_id`; unparseable files and repeated ids skipped; a scenario is kept
  when its sender has two `must_not_cross` statements of at least 20 characters
  that are absent from everything the clean counterpart emits and not
  credential-shaped. 107 scenarios were examined to keep 105 (two
  hub_and_spoke scenarios lacked usable statements).
- Left out: `mediated_comm` (agent to human, not agent to agent; PrivacyLens
  already covers that shape) and `competitive` (self-disclosure; 92 of 100
  participant boundaries lack an abstraction for every item, so no clean
  counterpart).
- Construction: the sender's private context arrives on `tool_response`; the
  hand-off carries the two statements verbatim (the canaries); the clean
  counterpart carries the source's abstraction for each. The hand-off wording
  is modelled by AgentLeak: the repository ships norms, not conversations.
  Each record carries sender, recipient (and audience for group spaces), data
  subject and the source's privacy criterion as `transmission_principle`; the
  affinity scenarios also record the closest and least-close tier present.

### MCPTox — data CC-BY-4.0, used

- Repository: https://github.com/zhiqiangwang4/MCPTox-Benchmark
- Commit: `630121b3275f74cc72d000a7a056e4d3c68648ef` (2026-11-15, the licence
  and citation merge)
- Licence file: `LICENSE` puts `def_tool/`, `pure_tool.json` and
  `response_all.json` under CC BY 4.0 and `analysis.ipynb` under MIT, and
  notes that third-party materials keep their own terms. Verdict: the MCPTox
  data is redistributable with attribution and a statement of changes. The
  legitimate tools' descriptions inside the system prompts are copied from
  third-party MCP servers, so they were **not** copied; the traces list those
  tools by name only. The poisoned descriptions and the user requests are
  MCPTox's own; the tool calls are model outputs recorded by MCPTox.
- Selection (in the build script, counts stored in the pack under
  `selection`): of 1,348 malicious instances, 913 carry an integrity or
  availability label (tampering, damage, disruption, manipulation) and are out;
  61 have no parsable successful call to a legitimate tool; 68 have no parsable
  ignored call to build a counterpart from; 280 have no recipient argument
  named by the poisoned description; 1 carries no user data in the redirected
  call; 1 repeats an earlier description and request. **24 kept**, from four
  servers (Email 6, Claude Post 3, Commander 14, Codacy 1) and six distinct
  poisoned instructions.
- Why so few: MCPTox executes no tool, so no tool ever returns private data.
  In most privacy-labelled cases the attacker's goal is access (read
  `~/.ssh/id_rsa`, `/etc/shadow`, list every Slack user), and the recorded call
  contains a path, not a private value. Converting those would have meant
  inventing the private data. The cases kept are the ones where the recorded
  call carries data the user handed to the agent (an e-mail body, a private
  repository name, the request itself) to a recipient the description named.
- No credential-shaped string is in the selected records; the builder refuses
  to emit one and a test scans both pack files.

## Sources evaluated and rejected

| Source | Licence checked (commit) | Verdict |
|---|---|---|
| PrivaCI-Bench, github.com/HKUST-KnowComp/PrivaCI-Bench | code MIT (`cb49d187095062bfff554121d4fa31440a32578e`) | **Rejected.** The `cases` are real GDPR/HIPAA enforcement decisions and ACLU court cases naming real companies and courts (real court content is excluded). The knowledge-base files carry no licence of their own; not used either. |
| MAGPIE, github.com/gurusha01/magpie | `LICENSE` is Apache-2.0 while the README says MIT (`e1e01b7235e6c9229f0327c90e1f6342eeba8f7a`) | Permissive either way, **not converted** this round: negotiation scenarios with private leverage; AgentSocialBench covered the agent-to-agent mode with norms and abstractions. |
| ConfAIde, github.com/skywalker023/confaide | MIT (`3174c63e689226189675a740b7bf9053f10bae50`) | Usable, **not converted**: tiered questions for a single model, not agent traces. |
| Agent Security Bench, github.com/agiresearch/ASB | MIT (`544540ff0788998072f7df463056fd17e62cc9f4`) | Usable, **not converted**: attack tools and memory-poisoning cases carry no private values, so there is no ground truth to score. |
| AgentDAM, WASP | CC-BY-NC-4.0 (per catalog; not fetched) | Not used: non-commercial. |
| ai4privacy, AgentHarm, TAB | per instructions | Not used, not fetched. |

## Measurements (pattern tier, `fast` mode, no model)

`agentleak bench run` on a manifest with the two new sources (258 units:
129 leaking, 129 derived counterparts; agentleak 0.19.0 code on this branch):

| Metric | Estimate | n/N | 95% CI (Wilson) |
|---|---:|---:|---|
| Recall, both packs | 0.411 | 53/129 | 0.330–0.497 |
| Recall, agentsocialbench_ma | 0.419 | 44/105 | 0.329–0.515 |
| Recall, mcptox_recipient_hijack | 0.375 | 9/24 | 0.212–0.573 |
| Recall, `inter_agent_message` hand-offs | 0.380 | 19/50 | 0.259–0.518 |
| Recall, `shared_memory` hand-offs | 0.455 | 25/55 | 0.330–0.585 |
| Specificity, derived counterparts | 1.000 | 129/129 | 0.971–1.000 |
| Fixture integrity: canary on a disclosure channel | 1.000 | 129/129 | 0.971–1.000 |
| Internal-only share of detected leaks | 1.000 | 53/53 | 0.932–1.000 |

The derived counterpart removes the hand-off entirely, so its specificity is
trivially high. The shipped counterparts keep the hand-off and are the honest
negative (`python scripts/packs/measure_new_packs.py`):

| Pack | Metric | Estimate | n/N | 95% CI |
|---|---|---:|---:|---|
| agentsocialbench_ma | Recall without ground truth | 0.419 | 44/105 | 0.329–0.515 |
| | Recall with canaries | 1.000 | 105/105 | 0.965–1.000 |
| | Specificity on shipped counterparts, pattern tier | 0.952 | 100/105 | 0.893–0.979 |
| | Specificity on shipped counterparts, canaries | 1.000 | 105/105 | 0.965–1.000 |
| mcptox_recipient_hijack | Recall without ground truth | 0.375 | 9/24 | 0.212–0.573 |
| | Recall with canaries | 1.000 | 24/24 | 0.862–1.000 |
| | Specificity on shipped counterparts, pattern tier | 0.750 | 18/24 | 0.551–0.880 |
| | Specificity on shipped counterparts, canaries | 0.708 | 17/24 | 0.508–0.851 |
| | Flow preset flags the leak | 1.000 | 24/24 | 0.862–1.000 |
| | Flow preset passes the counterpart | 1.000 | 24/24 | 0.862–1.000 |

How to read it:

- On AgentSocialBench the pattern tier finds a leak in 44 of 105 hand-offs,
  almost all through the health dictionary (`health_condition` on 36,
  `medication` on 7, a few names and HR terms). The other 61 are facts with no
  pattern ("he works in child protective services", "she is considering early
  retirement"). That is the measured limit of a regex tier on norm violations;
  no rule was added to raise it.
- On MCPTox the pattern tier sees the e-mail cases (9/24, the addresses) and
  nothing in the Commander cases (the user's request written to a hidden log).
  With canaries, 7 counterparts still score a leak: the user asked for that
  e-mail to be sent, so the same text goes to the right recipient. Presence
  cannot separate those pairs; the flow preset (deny canary data to the five
  recipients named by the descriptions) separates all 24.
- MCPTox intervals are wide (n = 24). Read the interval.

## Flow-rule presets

- **MCPTox**: shipped in the pack as `flow_preset` (`privacy_policy.flows`, one
  deny rule over five recipients), generated by the build script from the
  selected records; tested to flag every leak and no counterpart.
- **AgentSocialBench**: not shipped. Every canary finding has the data type
  `canary`, so a pack-wide rule cannot say which fact may go where; per-fact
  rules would need per-canary data types, which AgentLeak does not have. The
  affinity scenarios record the tiers needed to build such rules later.

## Security-framework mapping

New module `src/agentleak/core/security_frameworks.py`; reports gain
`security_frameworks`, `/api/meta` gains `security_frameworks`. The 14 privacy
frameworks, every existing report key and every existing count are unchanged:
`tests/test_security_frameworks.py` compares a report of
`healthcare_patient_summary` with a copy pinned from the 0.19.0 code before the
change.

| Identifier | Source checked |
|---|---|
| ASI01–ASI10 | OWASP Top 10 for Agentic Applications for 2026, PDF from genai.owasp.org (download 52117, SHA-256 `a2db94cd00b08e0b3a5e5b619afe024bdbcd74503111085705e4f3dd886fcb5c`). Identifiers only; summaries are ours (the text is CC BY-SA 4.0). |
| AML.T0051.000, AML.T0051.001, AML.T0080.000, AML.T0085.002, AML.T0085.003, AML.T0086, AML.T0110.000 | `mitre-atlas/atlas-data` `dist/v6/ATLAS-latest.yaml`, collection 2026.10, commit `f56c1468731d6428e5bf875263b4643b46d67437` (Apache-2.0). Names copied as published. |
| NISTAML.015, NISTAML.018, NISTAML.03, NISTAML.035, NISTAML.039 | NIST AI 100-2e2025 (March 2025), taxonomy index pp. x–xi and section 3.4.3 (PDF SHA-256 `4811fb6ad73f9c9121843ab77e029b5adc6f2c86d33c2fc5b2099ef133847646`). |

Mapping by leak channel: `tool_call` → ASI02, AML.T0086, NISTAML.03;
`inter_agent_message` → ASI07, NISTAML.03; `shared_memory` → ASI07,
AML.T0085.002, NISTAML.03; `log`, `generated_file`, `final_output` →
NISTAML.03. Ten attack classes are mapped (F1.1, F1.7, F1.8, F2.1, F2.5,
F2.14, F3.1, F3.3, F4.1, F4.4); the others map to nothing.

Left out because the primary source did not confirm them:

- **AML.T0057 "LLM Data Leakage"** and **AML.T0056 "Extract LLM System
  Prompt"**: present in the deprecated `dist/ATLAS.yaml` (v5.6.0) but absent
  from the current v6 data (2026.10). Not used.
- ISO/IEC 42001 clause IDs: not attempted (no primary source opened).

## Not done

- The public benchmark file (`src/agentleak/web/frontend/src/data/benchmark.json`,
  GUI area) was not regenerated; `python scripts/build_benchmark.py` will pick
  up the new packs with their `LEAK_MODE`.
- `injecagent_ds` is still missing from `research.corpus.FAILURE_MODES`
  (`bench` reports it as `unspecified`); left for the owner of that file.
- No third pack: Agent Security Bench and MAGPIE were the candidates; neither
  added a failure mode with scoreable ground truth in the time available.
