<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Cross-session leaks: whose data is this?

Every other part of AgentLeak scores one trace against itself. That misses the
failure mode that matters most in a deployment serving more than one person:

```
run 1   shared_memory   {"user": "alice", "diagnosis": "HIV positive"}    RI 1.0
run 2   final_output    "Previously stored: alice, HIV positive"          RI 1.0
```

Two runs, each scored independently, each perfectly correct about itself — and
nothing anywhere saying the second one disclosed the first one's data. The leak
lives in the gap between two traces, which is exactly where nobody was looking.

This is what the 2026 literature spent the year on: **PersistBench** on
cross-task leakage through persistent memory, **CIMemories** on attributes
surfacing across tasks as context accumulates, **PiSAs** on data spillage
through shared agents and shared memory in multi-user systems.

## Naming the subject

A run says whose data it is about:

```python
import agentleak

with agentleak.watch("triage-bot", subject="patient-8814") as run:
    ...
```

or, building a trace directly:

```python
trace = Trace(run_id="r-1", agent_name="triage", subject="patient-8814")
```

One run can legitimately touch several people's records, so an event may
override it:

```python
trace.add_event(channel="shared_memory", content=record,
                metadata={"subject": "patient-9021"})
```

**A run that declares no subject is not judged.** An undeclared subject cannot
be compared against anything, and guessing would invent an owner for data whose
owner nobody stated — the same rule as an undeclared purpose in
[contextual integrity](contextual-integrity.md).

## Turning it on

```yaml
privacy:
  subject_ledger: .agentleak/subjects.jsonl

privacy_policy:
  forbid_cross_subject: true      # fail CI on a cross-subject disclosure
```

Opt-in on purpose: enabling it by default would mean a privacy tool quietly
starting to accumulate data about people in a location nobody chose.

## What you get

```
Risk Index: 0.870   High risk   (privacy 13/100)
Cross-session: 2 disclosure(s) of another subject's data
  - health_condition: belongs to 'patient-8814', disclosed on final_output while serving 'patient-9021'
  - health_identifier: belongs to 'patient-8814', disclosed on final_output while serving 'patient-9021'
```

The JSON report carries the same under `cross_session`, and
`agentleak subjects` summarises the ledger.

**Attribution does not move the score.** The secret genuinely leaked in this
trace and AgentRisk already counts it; what this adds is *whose* it was, and
whose is a different claim from how severe. A test pins that the Risk Index is
identical with and without a ledger.

**Arriving is not disclosing.** A record reaching the agent on `user_input` or
`tool_response` attributes the secret to a subject but never accuses the run on
its own — otherwise every legitimate lookup of somebody's file would be a
violation.

## The ledger, and why it is safe to keep

A file recording who owns which secret is precisely the file you least want
readable. So it does not contain secrets:

```json
{"fingerprint":"a3f2…","data_type":"health_condition","subject":"patient-8814",
 "run_id":"r-1","first_seen_at":1788052846.78}
```

Fingerprints are **salted per ledger**, with the salt written once beside it at
mode 600. Unsalted, they would be a dictionary attack away from the values they
stand for — the space of SINs is small enough to enumerate — and a ledger
stolen from one deployment would work against another. Salted, it is useless
anywhere but where it was written. That is the most a local file can honestly
offer.

## Erasure

```bash
agentleak subjects --forget patient-8814
```

Erasure is a right, not a feature request: GDPR Article 17 and Law 25's
equivalent both mean a subject can require their data gone, and a fingerprint of
somebody's SIN is still about them. The ledger is rewritten without them, and
they stop being reported as an owner.

```bash
agentleak subjects                    # who is tracked, and how much
agentleak subjects --format json      # the same, machine-readable
```

## What this does not do yet

The ledger is per-project and local — there is no shared store across machines
or CI runners, so a leak is only caught where both runs were analysed by the
same checkout. Subjects are compared as literal strings: no aliasing, no notion
that `patient-8814` and `8814` are the same person. And attribution is
first-seen-wins, so a secret genuinely shared between two subjects (a household
address, a joint account) is attributed to whoever's run reached it first and
will read as a cross-subject disclosure afterwards.
