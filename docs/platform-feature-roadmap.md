# AgentLeak Platform: feature list and priority roadmap

This roadmap translates the paper's evidence model into product features. The
priority order follows reviewer risk first, then user value: provenance and
measurement must be trustworthy before hosted convenience or growth features.

## P0 — Release and research credibility (ship before SoftwareX submission)

### Artifact identity and provenance

- **Release evidence page** — show version, dereferenced tag commit, Git content
  tree, wheel/sdist SHA-256, CI run, Zenodo version DOI and paper DOI in one
  verifiable view.
- **Fixture provenance registry** — every pack displays source, source URL,
  license, attribution, modifications and scenario count; export as JSON.
- **REUSE/SPDX status** — repository scan with per-file license coverage and a
  failing gate for missing declarations.
- **Reproduction bundle** — one command downloads the archived wheel, runs the
  quickstart, replay, counterpart evaluation and microbenchmark, then compares
  hashes and expected results.

### Evaluation integrity

- **Metric taxonomy in the UI/API** — distinguish `detection_performance`,
  `fixture_integrity`, `specificity`, `policy_outcome` and `performance`; never
  render the exact-canary integrity check as model recall.
- **Positive/negative pairing** — scenario records can link a leaking fixture to
  its compliant counterpart; list both in every benchmark report.
- **Specificity dashboard** — report false blocks over original clean fixtures
  and derived counterparts separately, with Wilson confidence intervals and a
  clear `derived` badge.
- **Scope-rule ablation** — one-click analysis showing what changes when
  accessible-input events are treated as emission channels.
- **Detector tier labels** — every result states requested tier, tiers actually
  run, degraded mode, canary assistance and whether a semantic judge was used.

## P1 — Core platform workflow (highest user value after submission)

### Capture and trace exploration

- **Unified trace explorer** — timeline, channel filters, source-to-target graph,
  masked payload viewer and finding-to-event navigation for all eight channels.
- **Leak-path reconstruction** — interactive path from accessible source through
  tools, memory and agents to the eventual sink; export as SVG/PNG/JSON.
- **Live framework capture** — first-class setup wizards for LangGraph, CrewAI,
  OpenAI Agents, AutoGen and MCP, then OpenTelemetry/OpenInference ingestion.
- **Trace comparison** — diff two runs by event topology, leaked secrets,
  channels, RI/WSL and policy outcome; designed for mitigation regression.
- **Reachable-data manifest** — explicit vault editor/importer so release
  comparisons use a stable denominator rather than the observed-vault fallback.

### Detection and triage

- **Tiered scan control** — Fast (patterns), Standard (patterns + Presidio) and
  Hybrid (patterns + NER + semantic judge), with cost/privacy warnings before a
  remote tier runs.
- **Finding triage** — mark true positive, false positive, accepted risk or
  needs-review; capture reviewer, rationale and expiry.
- **Custom detector studio** — safely test regex, dictionaries, key-name rules
  and semantic policies against a local trace set before activation.
- **Detector evaluation workspace** — precision/recall/F1 by detector, data type,
  channel, domain and language, with held-out split enforcement.
- **Multilingual and structured-data detectors** — language-tagged NER plus
  JSON/schema-aware key-value detection.

### Policies, CI and release gates

- **Policy builder** — controls for RI, WSL, severity, data type, channel,
  recipient, finding count, required vault and detector tier.
- **Baseline-aware gates** — block regressions relative to an approved baseline,
  not only absolute thresholds.
- **GitHub checks UI** — concise PR annotation with new/resolved findings,
  channel paths and masked evidence; link to the exact trace.
- **Policy-as-code registry** — versioned policies with review/approval, semantic
  diff, rollback and environment promotion.
- **Waivers with expiry** — scoped exceptions tied to a finding fingerprint,
  owner, justification and deadline.

## P1 — Research and publication support

- **Experiment manifests** — pin software version, detector config, model,
  recipient framing, scenario split, random seed, dependencies and artifact
  hashes.
- **Benchmark runner** — execute positive fixtures, original clean controls and
  compliant counterparts in one job; export row-level CSV and aggregate JSON.
- **Paper-ready exports** — reproducible LaTeX/CSV tables with metric definitions,
  denominator, confidence interval and provenance footnotes.
- **Statistical comparison** — paired bootstrap or McNemar tests across two
  detector/configuration runs; no unqualified percentage deltas.
- **Capsule builder** — produce a Zenodo-ready archive containing artifacts,
  manifests, scripts, logs, checksums, citation metadata and licenses.

## P2 — Continuous assurance and operations

- **Projects and environments** — separate development, staging and production
  policies, secrets, retention and access controls.
- **Trend dashboard** — RI/WSL, leak prevalence, false blocks, detector tier and
  channel distribution over time, always with denominator and version markers.
- **Alert routing** — Slack, email, webhook, Jira and PagerDuty by severity,
  channel, data type and production environment.
- **Data minimization controls** — configurable retention, payload hashing,
  client-side masking, field-level encryption and local-only analysis mode.
- **Audit log** — immutable record of uploads, scans, policy changes, waivers,
  exports and evidence access.
- **Scheduled campaigns** — recurring scenario packs and protected-branch hybrid
  scans, with budget and rate controls.

## P2 — Runtime protection

- **Preflight API/MCP tool** — an agent checks a proposed tool call, message or
  file before emission and receives allow/block/sanitize plus structured reason.
- **Channel sanitizer policies** — redact or transform selected data types per
  target/channel while preserving task-relevant context.
- **Recipient-aware rules** — contextual-integrity constraints over sender,
  subject, recipient and transmission principle.
- **Runtime kill switch** — block high-severity emissions and persist a masked
  incident trace for review.
- **Defense evaluation** — compare leakage reduction against task-success cost,
  latency and false blocks.

## P3 — Enterprise and ecosystem

- **SSO/RBAC/SCIM** — organization, project and evidence roles; sensitive-payload
  access separated from report access.
- **Private deployment** — Docker Compose and Kubernetes/Helm with external
  Postgres, object storage and customer-managed keys.
- **Integration SDK** — stable adapter protocol, conformance tests and a public
  registry for community frameworks/detectors.
- **Compliance evidence packs** — map concrete findings and controls to GDPR,
  HIPAA, PCI DSS, NIST AI RMF and ISO/IEC 42001 without claiming certification.
- **Signed reports and attestations** — provenance-signed JSON reports and
  release attestations suitable for supply-chain verification.

## Product guardrails

- Never display an exact-canary integrity result as detector accuracy.
- Never combine derived negatives and independent production negatives without
  labeling both denominators.
- Never call a clean fast-tier result “safe”; say “no finding from enabled
  deterministic detectors.”
- Every public number must expose numerator, denominator, software version,
  detector tier and data provenance.
- Remote semantic analysis is opt-in, with endpoint, retention and redaction
  disclosed before data leaves the local environment.
