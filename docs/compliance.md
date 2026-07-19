# Privacy compliance evidence

Every AgentLeak report maps observed disclosures to regulatory and security
controls, then links those controls back to the exact redacted finding IDs. This
goes beyond a generic LLM grader: the evidence records the execution channel,
data type, severity, policy rule, leak path, and tested scope.

> This flags controls to review — it is **not** legal advice, legal
> certification, a compliance attestation, or proof that untested behavior is
> safe.

## Why AgentLeak is privacy-specific

Prompt-security tools are optimized for generating attacks and grading model
answers. Privacy compliance also needs to answer:

1. Where did the personal data enter the workflow?
2. Which tool, memory, agent, log, file, or recipient received it?
3. Was that destination prohibited by the declared privacy contract?
4. Which stable finding proves the event?
5. Which controls and frameworks require review?
6. Can CI and an auditor reproduce the same evidence index?

AgentLeak answers these questions from the normalized full trace. Its local
deterministic pipeline does not require sending trace content to a remote grader.
Presidio and the BYOK semantic judge remain optional.

## Frameworks

| Framework | Example controls AgentLeak maps to |
| --- | --- |
| **GDPR** (EU 2016/679) | Art. 5(1)(c) minimisation · Art. 5(1)(f) confidentiality · Art. 9 special category · Art. 32 security |
| **Québec Law 25** | Sensitive personal information · Confidentiality by default |
| **NIST AI RMF** (AI 100-1) | MEASURE 2.7 privacy measured · Privacy-Enhanced characteristic · MANAGE 1.3 risk treated |
| **OWASP LLM Top 10** (2025) | LLM02 Sensitive Information Disclosure · LLM06 Excessive Agency |
| **EU AI Act** (2024/1689) | Art. 10 Data governance |
| **HIPAA** (45 CFR 164) | §164.502(b) minimum necessary · §164.312(a) access/transmission security · §164.514 de-identification |
| **PCI-DSS v4.0** | Req. 3 protect stored account data · Req. 4 protect data in transmission · Req. 3.4 PAN not exposed in logs/tools |

Framework mappings are engineering aids. Applicability, lawful basis,
retention, DPIA requirements, data-subject rights, contractual duties, and the
legal interpretation of each control remain the responsibility of the system
owner and qualified counsel.

## How it works

Each control is a small, explainable predicate over the **leaked** findings and
configured privacy assertions:

- **severity levels** leaked (L1–L4),
- **data types** leaked (e.g. health, credentials),
- **channels** leaked on (tool_call, log, …),
- the run's **Risk Index** and whether it is **blocked**,
- violated policy assertions such as forbidden channels, forbidden data types,
  or a missing explicit vault scope.

A control returns *evidence* (the data types / channels / levels that triggered
it); empty evidence means compliant. Example: a leaked health identifier trips
**GDPR Art. 9** with evidence `health_identifier`; a leaked AWS key trips **GDPR
Art. 32**; an elevated Risk Index trips **NIST – Privacy-Enhanced**. A finding
crossing a forbidden channel also trips **GDPR Art. 5(1)(b) purpose
limitation**; a required explicit vault that is missing trips **GDPR Art. 25
privacy by design and by default**.

## Assurance model

`compliance.assurance` makes the strength of the evidence explicit:

| Value | Meaning |
| --- | --- |
| `trace_only` | Leak detectors and channel analysis ran, but no governance assertions were configured. |
| `trace_and_policy` | The trace was evaluated together with explicit privacy-policy assertions. |
| `observed_clear` | No assessed control was triggered in this trace. This is not an organization-wide compliance result. |
| `controls_at_risk` | At least one mapped control was triggered by observed evidence. |
| `not_assessed` (control status) | The control requires an assertion that was not configured. It is an evidence gap, not a pass. |

The existing framework `compliant` / `non_compliant` status remains available
for backward-compatible CI gates. For reporting, always present it together
with `assurance.evidence_grade` and `summary.controls_not_assessed`.

## Finding-to-control evidence matrix

Every control now contains an `evidence_details` object:

```json
{
  "id": "gdpr.art5.1b",
  "status": "at_risk",
  "evidence": ["policy:forbid_channels"],
  "evidence_details": {
    "finding_ids": ["fnd_7ac1"],
    "channels": ["log"],
    "data_types": ["email"],
    "levels": [2],
    "policy_rules": ["forbid_channels"]
  },
  "assessment_basis": "trace_and_policy"
}
```

The inverse index is available at `compliance.evidence_matrix`:

```json
[
  {
    "finding_id": "fnd_7ac1",
    "frameworks": ["gdpr", "law25"],
    "controls": [
      "gdpr.art5.1b",
      "gdpr.art5.1f",
      "law25.confidentiality"
    ]
  }
]
```

This matrix intentionally excludes raw matched values. Join the IDs to the
redacted `findings` array and `leak_paths` when investigating a control.

## Evidence integrity manifest

`compliance.integrity` contains a canonical SHA-256 digest over the run ID,
generation timestamp, Risk Index, privacy score, and evidence matrix:

```json
{
  "algorithm": "sha256",
  "digest": "d6f6...",
  "canonical_fields": [
    "evidence_matrix",
    "generated_at",
    "privacy_score",
    "risk_index",
    "run_id"
  ],
  "signed": false
}
```

The digest is useful for reproducible artifact comparison. It is **not** a
digital signature or tamper-proof attestation because it is unsigned and stored
beside the report. Sign and timestamp exported evidence in your controlled
deployment if legal provenance is required.

## Configure governance assertions

```yaml
privacy_policy:
  max_risk_index: 0.20
  max_findings: 0
  forbid_levels: [4]
  forbid_channels: [log, shared_memory, generated_file]
  forbid_data_types: [llm_api_key, credit_card]
  require_explicit_vault: true
```

- `forbid_channels` and `forbid_data_types` provide a deterministic purpose and
  destination boundary.
- `forbid_levels` makes critical or special-category disclosure release-blocking.
- `require_explicit_vault` prevents a production comparison from using only the
  secrets observed in one trace as its AgentRisk denominator.
- `max_risk_index` and `max_findings` establish quantitative release limits.

Only configure obligations the owner can state and defend. AgentLeak does not
infer consent, lawful basis, retention periods, residency, or processor terms
from a model response.

The result appears in:

- the **web UI** (a Compliance section on every run, framework cards with
  per-control status),
- the **HTML / Markdown exports**,
- the **CLI** summary line (`Compliance: 5/7 frameworks clear …`),
- the **JSON report** under `compliance` (for CI gating).

The JSON report also carries a machine-readable `compliance.disclaimer` object
(`is_legal_certification: false`, `is_compliance_attestation: false`, plus a
`text`/`scope` summary) — so an automated consumer doesn't have to parse this
page's prose to learn that a "compliant" verdict is not a legal guarantee.

## Recommended DPO and engineering workflow

1. Define the purpose, reachable-data vault, authorized recipients, forbidden
   channels and prohibited data types.
2. Run baseline scenarios and red-team plugins that match the target's tools,
   RAG, memory, roles, MCP servers and network access.
3. Review at-risk controls and open their linked finding IDs and leak paths.
4. Minimize tool schemas, isolate memory, redact persistence channels, enforce
   authorization, and repeat the same test matrix.
5. Retain redacted JSON plus the HTML or Markdown report according to the
   organization's evidence-retention policy.
6. Record unassessed controls and untested workflows as explicit audit gaps.

The red-team API and Playground expose a `compliance_core` preset for a concise
high-signal campaign covering regulated data, authorization, session isolation,
RAG disclosure, and exfiltration. It is a starting point—not a substitute for
architecture-specific plugin selection.

For the hosted documentation, see
[`/docs/privacy-compliance`](https://agents.fomox.com/docs/privacy-compliance).

## Add or adjust a framework

Frameworks live in [`agentleak/core/compliance.py`](../agentleak/core/compliance.py)
as data. Append a `Framework` with `Control`s — each control's `detect(ctx)`
returns evidence tokens (empty = compliant). Add a case to
`tests/test_compliance.py`. See [AGENTS.md](../AGENTS.md) §6c.
