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
| `--inspect-responses` | Also judge each tool **result** on its way back to the agent. Off by default; see [Responses](#responses-data-coming-in). |
| `--style token` | Replace a refused value with a stable pseudonym instead of a placeholder, and restore it in the response. See [Tokens](#tokens-a-reference-without-the-value). |
| `--agent` | What the agent is called in flow rules, for responses. Default `mcp-client`. |
| `--pins` | Tool fingerprints, pinned on first use. Default `.agentleak/mcp-pins.json`; `''` disables. See [Tool pinning](#tool-pinning). |
| `--block-changed-tools` / `--repin` | Hide and refuse a tool whose definition changed; accept the current definitions. |
| `--sign-key` | Ed25519 key that signs every evidence entry (`agentleak[sign]`). See [Signing](#signing-the-log). |

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

**Encoding does not get a value past it.** The gateway decodes base64, hex,
URL-encoded and letter-spaced arguments before judging them, so a base64 SIN
is redacted exactly like a plaintext one and a hex-encoded diagnosis that a
`deny` rule names is blocked. See [encoded-leaks.md](encoded-leaks.md).

## What passes unjudged

Allow rules are [scoped default-deny](contextual-integrity.md#two-design-decisions-worth-knowing-about).
A data type that no rule names is recorded in the evidence log and then
**forwarded as is**. That includes credentials: with only the policy above, a
`postgres://user:password@host` argument reaches the server unchanged.

That is the right default for a database or a deployment server, which needs
the credential it is sent. For every other server, say so:

```yaml
privacy_policy:
  flows:
    - data_type: group:credentials   # every credential type the detectors know
      to: "*"
      deny: true
```

`group:credentials` follows the detectors, so a credential type added in a
later release is covered without editing the rule. See
[groups](contextual-integrity.md#groups).

Deny beats allow, so an allow rule next to this deny would never apply. Give the
one server that needs a credential its own proxy instance with its own config.

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

**Tamper-evident, and signable.** Without a key, anyone who can write the file
can rewrite the whole chain. That is still the property an auditor needs and a
plain log does not have; [sign it](#signing-the-log) for the stronger claim.

## Responses: data coming in

A tool's result is data flowing *into* the agent's context, and minimisation
has to happen there too. With `--inspect-responses`, each `tools/call` result is
judged as a flow **from the server to the agent** under the same rules:
refused values are redacted, a type a `deny` rule names is withheld (the agent
gets a readable `isError` result saying the tool ran and its result was
withheld), and every decision is logged with `direction: response`.

It is opt-in because it changes what an existing policy means. `sin to:
kyc-vendor` permits sending a SIN to the vendor; with inspection on, the SIN
the vendor sends back to `mcp-client` is a flow no rule permits, and gets
redacted. Write the return flow when you turn it on:

```yaml
    - data_type: sin
      from: kyc-vendor
      to: mcp-client
```

## Tokens: a reference without the value

`[REDACTED_SIN]` in a lookup and `[REDACTED_SIN]` in the update are the same
string for two different customers, and the second call fails for a reason
nobody can see. `--style token` replaces a refused value with a keyed
pseudonym instead:

```json
{"sin": "[[SIN:3f9a1c2e40]]", "order": "ORD-7781"}
```

The same value gets the same token for the life of the process (set
`AGENTLEAK_TOKEN_KEY` to keep tokens stable across processes), so the server can
match on it without ever holding it. When the server's response mentions a
token this proxy issued, the proxy puts the real value back before the agent
sees it — the agent sent that value, so it is not new data reaching it.

The token-to-value map lives **in memory only** and is never written. A file
mapping tokens to values would be exactly the leak this project exists to find.

## Tool pinning

A tool's description is read by the model as instructions, so a server that
ships an innocent description and later a poisoned one changes what the agent
does without a line of your code changing. The proxy fingerprints every tool in
each `tools/list` the first time it sees it (SHA-256 of name, description and
input schema — nothing else is stored) and reports any tool whose definition
later differs, on stderr and in the evidence log as `tool_changed`.

A changed tool stays reported until you accept it with `--repin`; it is never
re-trusted silently, because a pin that follows the server's changes pins
nothing. `--block-changed-tools` goes further: the changed tool is removed from
the list the agent sees, and a call to it is refused.

## Signing the log

The hash chain is tamper-evident: anyone who can write the file can still
recompute every hash. Sign it and a rewrite needs the private key:

```bash
pip install "agentleak[sign]"
agentleak evidence --keygen keys/evidence.key          # private key at mode 600, plus .pub
agentleak proxy --sign-key keys/evidence.key -- npx -y @modelcontextprotocol/server-github
agentleak evidence evidence.jsonl --public-key keys/evidence.key.pub
```

Verification with a public key fails on a forged signature, on another key's
signature, and on an entry whose signature was stripped. Keep the private key
where the gateway can read it and the log's other writers cannot; the key is the
whole guarantee. Timestamping by an external authority (RFC 3161) is not done.

## The model is the other exit

`agentleak proxy` guards the tools. The same rules can guard the model:
`agentleak llm-proxy` is an OpenAI-compatible proxy, and
`agentleak.integrations.litellm_guardrail` plugs into LiteLLM. See
[integrations](integrations.md#5-on-the-traffic-path-model-gateways-and-eval-harnesses).

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

There is no inheritance between environments. The proxy covers MCP stdio;
HTTP/SSE MCP transports are not wrapped. Each proxy guards one server, so a flow
rule with an `origin` (where the data first entered) is enforced by the CI gate
on a full trace, not at runtime: one proxy cannot see what another server
returned. Tokens and pins are per proxy process.
