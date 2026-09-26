<!--
SPDX-FileCopyrightText: 2026 AgentLeak contributors
SPDX-License-Identifier: MIT
-->
# Encoded and obscured leaks between agents

Agents in a multi-agent system pass each other whatever the task seems to need,
and nothing requires that to be readable. A planner base64-encodes a customer
record into a context blob. A worker hex-encodes an email into an identifier.
A SIN goes to the same recipient in two halves. Each of these is a disclosure,
and a detector that only reads plaintext misses every one.

Nobody has to be malicious for this to happen. Agents serialise, pack and
encode as a matter of course, and a prompt-injected agent that has been told to
exfiltrate data can do it on purpose.

## Measured

One trace per cell: the value arrives in a `tool_response`, then the next
`inter_agent_message` carries it transformed. A cell counts only when a finding
lands on that message **with the right type and the original value**. A
reversed SIN reported as some other SIN is a miss, because the report would name
the wrong secret.

| Transformation | `sin` | `credit_card` | `phone_number` | `email` | `llm_api_key` | `health_condition` |
|---|---|---|---|---|---|---|
| plaintext (control) | ✓ ✓ | ✓ ✓ | ✓ ✓ | ✓ ✓ | ✓ ✓ | ✓ ✓ |
| base64 | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ |
| base64 of base64 | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ |
| hex | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ |
| URL-encoded | ✗ ✓ | ✗ ✓ | ✓ ✓ | ✗ ✓ | ✓ ✓ | ✓ ✓ |
| letter-spaced | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ |
| reversed | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ |
| ROT13 | ✓\* ✓ | ✓\* ✓ | ✓\* ✓ | ✗ ✓ | ✗ ✓ | ✗ ✓ |
| split in two | ✗ ✓ | ✗ ✓ | ✗ ✓ | n/a | ✗ ✓ | n/a |

Each cell reads **0.14.1 → this release**: **6 of 46 → 46 of 46** obscured copies.

\* ROT13 leaves digits alone, so a ROT13 SIN *is* the plaintext SIN. Those three
cells were never evidence that 0.14.1 read ROT13.

**Read the 46/46 for what it is.** The benchmark was written alongside the
feature, so it shows that each transformation is covered. It does not show that
detection is robust against an adversary who designs an encoding to evade it.
The false-positive evidence comes from sources that were *not* written for this
feature:

- **All 266 bundled scenarios** (built-ins, `agentleak_bench`, `privacylens_ci`,
  `agentdojo_exfil`): identical score and finding count before and after.
  Before the rule below that restricts splitting to identifiers, two AgentDojo
  scenarios reported a false split. That is how the rule came to exist.
- **Encoded-looking benign text**: SHA-256 digests, git commits, UUIDs, a
  base64 PNG, a JWT with no personal data, a URL-encoded search, hex colours,
  base64 of an ordinary config line, and random ciphertext. No findings, and
  `redact` leaves every one unchanged.
- **`docs/detection-quality.md`**: every figure identical, including zero false
  positives on its fifteen benign controls.

Reproduce:

```bash
python scripts/encoded_leaks.py                 # this checkout
python scripts/encoded_leaks.py --installed     # whatever version is installed
```

## How it works

The transformations fall into two families that fail differently, so each
family is handled its own way.

### Self-announcing encodings: base64, hex, URL-encoding, letter spacing

The encoded form has a shape of its own and decodes to readable text or it
does not. Every such span is decoded, nested encodings are followed two levels
deep, and the ordinary detectors read the result. Anything that decodes to
binary is dropped before a detector sees it, which covers hashes, commit IDs,
images and ciphertext.

Because this needs no context, it works everywhere text is judged:

- **`agentleak run`** reports the finding with `metadata.transform` (`base64`,
  `hex`, `percent`, `spaced`, or a chain such as `base64>hex`).
- **`agentleak redact`** removes the encoded token whole. It is labelled by the
  worst thing inside, so a blob holding an email and an API key comes back as
  `[REDACTED_LLM_API_KEY]`. For a URL-encoded value, only that URL component is
  removed: `/users/[REDACTED_EMAIL]/orders?page=2`.
- **`agentleak proxy`** judges the decoded content against your flow rules. A
  base64 SIN is redacted surgically and a hex-encoded diagnosis that a `deny`
  rule names is blocked, while the rest of the call passes.

### Encodings that look like text: reversal, ROT13, splitting

Nothing about `682 454 640` says it was ever anything else. Running detectors
over every reversed or rotated event would report noise, so these copies are
matched only against **values the trace has already exposed in plaintext**,
under three rules:

- **Forward in time.** A copy counts only in an event *after* the value first
  appeared in plaintext. Without this rule, matching is symmetric: a SIN and
  its reversal each look like an obscured copy of the other, and the original
  gets relabelled as the copy.
- **Obscured means not also plain.** If the value is present in plaintext in
  that event, the event holds a plaintext occurrence, not an obscured copy.
  (ROT13 of a number is the number.)
- **Splitting is for identifiers only.** A split value is reassembled only from
  whole tokens, only in messages to **one recipient**, and only for values with
  at least four digits: SINs, card numbers, keys, account numbers. Split a
  phrase and you get its words, which appear in every message. That is exactly
  the false positive the AgentDojo pack produced.

## Identity: one secret, however it was written

An encoded copy is attributed to the **original** value. AgentRisk keys a
secret on its value, so the copy raises exposure on the channel where it
appeared without inventing a second secret, and never adds to the vault size
(ρ_S).

The same rule corrects a misattribution in 0.14.1. A reversed SIN still looks
like a SIN, so it was reported as a *different* SIN, which put a secret into the
vault that nobody holds. It is now reported as the original SIN, reversed.

It also applies to formatting lost in decoding. `4 1 1 1 1 1 1 1 …` reads back as
`4111111111111111`, and the finding is aligned to the `4111 1111 1111 1111`
already in the trace rather than counted twice.

Relatedly, a match *inside* a credential now belongs to that credential. In
`postgresql://app:P%40ss@db.internal`, the password followed by the host reads
as an email address. That used to be reported as a second, mislabelled secret
next to the `connection_string`. This is judged by position, not by substring:
a source file is scanned as one text, and `123` inside an API key on one line
says nothing about a `123` on another.

## Limits

- **ROT13, reversal and splitting need context.** They are found in trace
  analysis, where the whole trace is available. `redact` and `proxy` judge one
  piece of text at a time, so they catch the self-announcing encodings and not
  these.
- **Anchored means already seen.** An obscured value that never appears in
  plaintext anywhere in the trace is not found by the anchored rules. A value
  that reached the agent only through a channel AgentLeak does not see is
  invisible to them.
- **Paraphrase is not an encoding.** "The patient's blood sugar condition"
  carries a diagnosis in no recoverable form. That is the job of the optional
  LLM judge (`--mode hybrid`), and `docs/detection-quality.md` says how weak the
  deterministic tier is on prose.
- **A cipher with a key is encryption.** An agent that AES-encrypts a record
  and sends the key in another message is beyond any pattern matcher. What
  AgentLeak can show you is that a key and a ciphertext went to the same
  recipient, through the topology and the leak paths.
