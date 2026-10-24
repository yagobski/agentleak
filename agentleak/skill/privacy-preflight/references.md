# AgentLeak — reference sheet

## The paper

**AgentLeak: A Benchmark for Internal-Channel Privacy Leakage in
Multi-Agent LLM Systems**

Faouzi El Yagoubi, Godwin Badu-Marfo, Ranwa Al Mallah.
*IEEE Access*, vol. 14, pp. 94960–94978, 2026.
DOI: [10.1109/ACCESS.2026.3704541](https://doi.org/10.1109/ACCESS.2026.3704541)
(arXiv: [2602.11510](https://arxiv.org/abs/2602.11510)). Open access, CC-BY 4.0.

Correct BibTeX (use the published version, not the preprint):

```bibtex
@article{elyagoubi2026agentleak,
  author  = {El Yagoubi, Faouzi and Badu-Marfo, Godwin and Al Mallah, Ranwa},
  journal = {IEEE Access},
  title   = {AgentLeak: A Benchmark for Internal-Channel Privacy Leakage in
             Multi-Agent LLM Systems},
  year    = {2026},
  volume  = {14},
  pages   = {94960--94978},
  doi     = {10.1109/ACCESS.2026.3704541}
}
```

## Scale

7 communication pathways · 1,000 scenarios · 4 domains · 5 models ·
**4,979 validated traces**.

## Key figures (paper v3, verified)

| Finding | Figure |
|---|---|
| C1 single-agent leakage | 43.2% |
| C1 multi-agent final-output leakage | 27.2% |
| C2 inter-agent message leakage | **68.8%** |
| OR-aggregated C1/C2/C5 exposure | 68.9% |
| Violations missed by output-only audits | **41.7%** |

Reading: the final answer is the *safest* channel. Inter-agent traffic
leaks at 2.5× the rate of final outputs.

## What the tool inspects

Eight normalized channels: `user_input`, `final_output`,
`inter_agent_message`, `shared_memory`, `tool_call`, `tool_response`,
`log`, `generated_file`.

Nine detectors (six always-on regex/dictionary, three optional):
`pii`, `secrets`, `healthcare`, `finance`, `hr`, `keyname`, `custom`,
`presidio` (optional), `llm_judge` (optional, BYOK).

Severity taxonomy (GDPR Art. 9 / Québec Law 25 grounded):

| Level | Weight | Examples |
|---|---|---|
| L4 | 4 | health data, SIN/SSN, cards, credentials |
| L3 | 3 | income, salary, address, DOB |
| L2 | 2 | email, phone, contact data |
| L1 | 1 | names, organizational identifiers |

Scoring: `RI = WSL / ρ_S ∈ [0,1]` — severity-weighted leakage normalized
by the density of the audited vault. Reported globally and per channel.

## Links

- Tool (this skill's engine): https://github.com/yagobski/agentleak
- Benchmark (paper artifacts): https://github.com/Privatris/AgentLeak
- Paper (HF): https://huggingface.co/papers/2602.11510
- Docs: https://www.agentleak.org/docs
