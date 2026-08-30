<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# The runtime gateway: deciding before emission

Everything else in AgentLeak reads a trace that already happened. That is the
right shape for a CI gate — you learn before you ship — and the wrong shape for
the question deployers have been asked since the Commission's enforcement powers
over general-purpose AI became applicable on 2 August 2026:

> Is this agent staying inside its approved bounds right now, and can you show
> me?

A report generated on request cannot answer that, because it is generated on
request — nothing stops it being generated differently tomorrow. The gateway is
the other half: it decides at the moment of emission, and writes what it decided
to a hash-chained log as it goes.

## `agentleak proxy`

MCP is where agents reach the outside world, and where this year's incidents
happened: tool poisoning, name collisions routing calls to the wrong tool,
confused parameter mapping posting a record to the wrong endpoint. Each is the
same sentence — *sensitive data went to the wrong recipient through a tool call*.

Put the proxy in front of the server. Your agent launches it; it launches the
real server as a child and forwards the JSON-RPC between them.

```bash
agentleak proxy \
  --config agentleak.yaml \
  --evidence evidence.jsonl \
  -- npx -y @modelcontextprotocol/server-github
```

In an MCP client configuration:

```json
{
  "mcpServers": {
    "github": {
      "command": "agentleak",
      "args": ["proxy", "--config", "agentleak.yaml", "--evidence",
               "evidence.jsonl", "--",
               "npx", "-y", "@modelcontextprotocol/server-github"]
    }
  }
}
```

Every message except `tools/call` crosses untouched. `tools/call` goes to the
policy first.

| Option | Meaning |
|---|---|
| `--config` | The `agentleak.yaml` holding `privacy_policy.flows`. Without it nothing is refused — calls are still recorded. |
| `--evidence` | Where the decision log goes. Default `agentleak-evidence.jsonl`. |
| `--recipient` | What this server is called in flow rules. Guessed from the command; pass it when the guess is wrong. |
| `--block` | Refuse every inappropriate flow instead of redacting it. |
| `--quiet` | Stop narrating decisions on stderr. |

## The three answers

The policy is the same [contextual-integrity](contextual-integrity.md) grammar
the CI gate reads, so a policy written for the gate carries over unchanged.

```yaml
privacy_policy:
  flows:
    - data_type: sin
      to: server-github
      for: identity_check
    - data_type: health_condition
      to: "*"
      deny: true
```

| Answer | When | What the server receives |
|---|---|---|
| **allow** | Nothing sensitive, or every flow permitted | The call, unchanged |
| **redact** | A flow is not permitted | The call, with *only* the offending values replaced |
| **block** | A `deny` rule names the flow | Nothing — the agent gets a readable refusal |

**Redact is the default for a refusal, and that is a deliberate bias.** A
gateway that blocks whatever it dislikes breaks the agent, gets switched off
within the week, and then protects nothing. One that redacts keeps the task
working while removing what should not have gone. Blocking is reserved for flows
a `deny` rule names, because a deny rule is somebody saying *not this, ever*.

**Redaction is surgical.** Only the types whose flow was refused are removed:

```json
{"sin": "[REDACTED_SIN]", "order": "ORD-7781", "page": "/pricing"}
```

Stripping everything findable would take the order number out with the SIN and
the call would fail for a reason nobody could see.

## Declaring purpose

The proxy reads purpose from the call's `_meta`:

```json
{"method": "tools/call",
 "params": {"name": "verify", "arguments": {...},
            "_meta": {"purpose": "identity_check"}}}
```

A call that declares no purpose fails a rule that requires one. That is
deliberate — an undeclared purpose is the case the rule exists to catch.

## A refusal the agent can act on

A blocked call comes back as a tool result with `isError`, not a JSON-RPC
protocol error. An agent that receives a broken frame retries or dies; one that
receives an error result reads the reason and adapts.

```json
{"jsonrpc": "2.0", "id": 4,
 "result": {"isError": true,
   "content": [{"type": "text",
     "text": "Blocked by AgentLeak privacy policy: health_condition from
              mcp-client to server-github for billing — forbidden by rule…
              This call was not sent."}],
   "_meta": {"agentleak": {"action": "block", "data_types": ["health_condition"], …}}}}
```

## The evidence log

Every decision is one line, and each line carries the hash of the line before
it:

```bash
$ agentleak evidence evidence.jsonl
✓ 4 entries, chain intact

  allow    2
  block    1
  redact   1

Data types seen:
  sin                    2
  health_condition       1
```

Editing, removing or reordering any entry breaks every hash after it, and the
command says which one:

```
⛔ entry 2 (line 3) was modified: its contents hash to 907dd9ce8565…,
   not the d585319553c4… recorded
```

`agentleak evidence --verify` exits non-zero on a broken chain, which is what
you want in a nightly job.

**No secret values are ever written to the log.** It records what was found,
where it was going and what was decided — never the value. This is the file most
likely to end up in a ticket or a bucket, and writing the secret into it would
make the log the leak it exists to prevent.

**Tamper-evident, not tamper-proof.** Anyone who can write the file can rewrite
the whole chain. That is still the property an auditor needs and a plain log does
not have; pair it with append-only storage or an external anchor if you need the
stronger claim.

## Using the gateway directly

The proxy is one caller. The decision engine is public:

```python
from agentleak.defenses import Gateway

gateway = Gateway(
    flows=[{"data_type": "sin", "to": "kyc-vendor", "for": "identity_check"}],
    evidence="evidence.jsonl",
)

decision = gateway.check(
    {"sin": customer.sin},
    tool="verify_identity",
    recipient="kyc-vendor",
    purpose="identity_check",
)

if decision.blocked:
    raise PolicyError(decision.reason)
send(decision.arguments)          # redacted if the policy said so
```

## What this does not do yet

Recipients are matched as literal names — no grouping (`to: group:third-parties`)
and no inheritance between environments. The proxy covers MCP stdio; HTTP/SSE
MCP transports are not wrapped. Server→client responses are pure passthrough:
data coming *in* is scored by the analysis pipeline, and rewriting it here would
corrupt results the agent is waiting on.
