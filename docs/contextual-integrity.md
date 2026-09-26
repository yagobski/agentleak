<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Contextual integrity: judging the flow, not the presence

Every rule AgentLeak shipped before 0.13 answers one question: *was this kind of
data on this kind of channel?* `forbid_data_types`, `forbid_channels`,
`forbid_levels`, `max_risk_index` — all of them measure presence.

Presence is not what privacy law turns on. Consider one SIN:

| Flow | Data type | Channel | Severity | Appropriate? |
|---|---|---|---|---|
| agent → KYC vendor, for identity verification | `sin` | `tool_call` | L4 | **yes** |
| agent → analytics sink, for usage metrics | `sin` | `tool_call` | L4 | **no** |

Identical under every rule above. Opposite under GDPR purpose limitation
(Art. 5(1)(b)), under Law 25's consent-to-purpose requirement, and under any
auditor's reading. A tool that cannot tell them apart is measuring the wrong
thing — and it is the thing Presidio and the observability platforms already
measure, so it is also where AgentLeak stops being distinctive.

Helen Nissenbaum's framing is the one the 2026 literature converged on: privacy
is a property of *information flows*, and a flow is appropriate or not according
to the norms of the context the data came from. The unit is a quadruple.

```
(data type, sender, recipient, purpose)
```

AgentLeak already carried three quarters of it. Every event records its `source`
and `target`, and every finding inherits them. Purpose was the missing piece.

## Writing rules

```yaml
privacy_policy:
  flows:
    - data_type: sin
      to: kyc-vendor
      for: identity_check

    - data_type: [health_condition, medication]
      to: [clinician, ehr]

    - data_type: "*"
      to: analytics
      deny: true
      description: "Nothing personal reaches the analytics sink."
```

| Key | Meaning | Default |
|---|---|---|
| `data_type` | One type or a list. `*` matches any. **Required.** | — |
| `from` | Permitted sender(s), matched against the event `source`. | any |
| `to` | Permitted recipient(s), matched against the event `target`. | any |
| `for` | Permitted purpose(s), matched against `metadata["purpose"]`. | any |
| `deny` | Make this a prohibition instead of a permission. | `false` |
| `description` | What the rule is protecting, shown in violations. | generated |

`senders`, `recipients`, `purposes` and `data_types` are accepted as aliases, so
a generated config need not be written as prose.

## Declaring purpose

Purpose comes from event metadata, which the SDK already passes through:

```python
with agentleak.watch("kyc-bot") as run:
    run.tool_call(
        {"sin": customer.sin},
        target="kyc-vendor",
        metadata={"purpose": "identity_check"},
    )
```

**A flow that declares no purpose fails a rule that requires one.** That is
deliberate: an undeclared purpose is exactly the case the rule exists to catch,
so silence must not read as compliance. Rules that name no `for` are unaffected.

## Two design decisions worth knowing about

**Allow rules are *scoped* default-deny.** Writing one rule for `sin` means SIN
may reach the recipients you named and nowhere else — but data types you have
said nothing about stay unjudged, and produce neither a pass nor a failure. The
strict reading of contextual integrity (enumerate every legitimate flow, deny
the rest) is right in theory and unusable as a default on a system nobody has
finished modelling: it would flood an existing project with violations about
data it was never asked about, and the feature would be switched off in a day.
You buy strictness one data type at a time.

**Deny beats allow.** `to: "*"` next to a `deny` for one recipient is how you
write "anywhere except there", and the order of the rules does not matter.

## Reading a violation

```
Privacy policy: failed · 1 violation(s)
  - flows: 1 inappropriate flow(s): sin from agent to analytics for
    usage_metrics — no rule permits this flow, and sin is governed by 1 allow
    rule(s). Permitted recipients: kyc-vendor.
      sin -> analytics (usage_metrics)
```

The violation names the recipient, the purpose and the permitted alternatives,
because those are what an operator changes. The JSON report carries the same
detail under `privacy_policy.flows.violations`, one entry per flow, and the
Markdown report renders it as a table.

## Enforcing it at runtime

Rules here are evaluated **after** a run, as a gate. The same rules decide a
flow **before** it happens in [`agentleak proxy`](runtime-gateway.md), which
allows, redacts or blocks each MCP tool call and records the decision in a
hash-chained evidence log. A policy written for the gate carries over
unchanged.

## What this does not do yet

Recipients are matched as literal node names. There is no grouping yet
(`to: group:third-parties`), and no inheritance between environments.
