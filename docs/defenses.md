# Defenses

AgentLeak ships two complementary runtime defenses that can be combined with the
detection pipeline to **prevent** leakage rather than just detect it.

## Sanitizer

`agentleak.defenses.sanitizer` — redact sensitive patterns from text before it
is stored, forwarded, or returned.

### Redaction styles

Every example below is the real output for `SSN: 412-55-9087`:

| Style | Example output |
| --- | --- |
| `placeholder` | `[REDACTED_SSN]` (default) |
| `asterisk` | `***********` (one `*` per character) |
| `masked` | `XXXXXXX9087` (last 4 visible; the CLI also accepts `mask`) |
| `hash` | `1793fe1ffccd611f` (SHA-256, first 16 hex chars) |
| `category` | `[PII: SSN]` |
| `remove` | *(empty — removed entirely)* |

### What is removed

The sanitizer reads the same detector registry as the analysis, so anything
AgentLeak can find it can remove; `GET /api/meta` lists the split
(`redactable` vs `detect_only`). Two rules decide what a match covers:

- **Credentials are removed whole.** A private key is the full
  `BEGIN … END` block (or, when a log cut it off, the base64 lines after the
  header), not the header line alone. A URL with a password in it —
  `postgres://user:pass@host`, `https://bot:token@github.com/…` — goes as one
  unit, even though `pass@host` also looks like an email address.
- **Otherwise the most precise match wins.** A key-name match such as
  `ssn: 412-55-9087 and more text` locates the secret only roughly, so the SSN
  pattern inside it decides what is removed and the rest of the sentence stays.

Assigned secrets (`password: hunter2`, `DB_PASSWORD=…`,
`export OPENAI_API_KEY=…`) are redacted by value, so the key name — and the
code around it — survives. Reads from the environment or a config object
(`os.environ.get(...)`, `settings.API_KEY`, `response.next_page_token`) are
references, not secrets, and are left alone.

### Usage

```python
from agentleak.defenses.sanitizer import Sanitizer, RedactionStyle

san = Sanitizer(style=RedactionStyle.MASKED)
clean = san.sanitize("Patient SSN: 412-55-9087, email alice@example.com")
# → "Patient SSN: XXXXXXX9087, email XXXXXXXXXXXXX.com"

# Convenience function
from agentleak.defenses.sanitizer import sanitize_text
clean = sanitize_text(text, style="placeholder")
```

### Sanitize structured data

```python
data = {"patient": "Jane", "ssn": "412-55-9087", "notes": "allergic to penicillin"}
clean = san.sanitize_dict(data)
# → {"patient": "Jane", "ssn": "[REDACTED_SSN]", "notes": "allergic to penicillin"}
```

### Custom patterns

```python
san = Sanitizer(
    style=RedactionStyle.PLACEHOLDER,
    extra_patterns={"PROJ_ID": r"PROJ-\d{6}"},  # or [("PROJ_ID", r"PROJ-\d{6}")]
)
san.sanitize("see PROJ-123456")  # → "see [REDACTED_PROJ_ID]"
```

### Configure in agentleak.yaml

```yaml
defense:
  enabled: true
  style: masked
  channels: [final_output, inter_agent_message]  # empty = all channels
```

---

## InternalChannelGuard

`agentleak.defenses.internal_channel` — clearance-level access control on
`inter_agent_message` and `shared_memory`.

These internal channels leak ~2.6× more than external channels per the IEEE
benchmark, yet most output-only guardrails ignore them entirely.

### Clearance levels

| Level | Label | Maps to |
| --- | --- | --- |
| 1 | `PUBLIC` | AgentRisk L1 |
| 2 | `INTERNAL` | AgentRisk L2 |
| 3 | `CONFIDENTIAL` | AgentRisk L3 |
| 4 | `SECRET` | AgentRisk L4 (PHI, credentials) |

### Usage

```python
from agentleak.defenses.internal_channel import (
    AgentProfile,
    ClearanceLevel,
    InternalChannelGuard,
)
from agentleak.defenses.sanitizer import Sanitizer, RedactionStyle

sender = AgentProfile(
    name="orchestrator",
    clearance=ClearanceLevel.SECRET,
    allowed_channels=["inter_agent_message", "tool_call"],
)
recipient = AgentProfile(
    name="reporting_agent",
    clearance=ClearanceLevel.INTERNAL,    # lower clearance
)

guard = InternalChannelGuard(
    sender=sender,
    recipient=recipient,
    sanitizer=Sanitizer(style=RedactionStyle.PLACEHOLDER),
    block_on_secret=True,   # block instead of redact for L4 data
)

result = guard.check(
    text="Patient SSN: 412-55-9087",
    channel="inter_agent_message",
    data_level=ClearanceLevel.SECRET,
)

print(result.decision)          # GuardDecision.BLOCK or REDACT or WARN or ALLOW
print(result.sanitized_text)    # redacted version (if REDACT)
print(result.reason)
```

### Guard decisions

| Decision | When |
| --- | --- |
| `ALLOW` | data_level ≤ recipient.clearance |
| `WARN` | data_level > recipient.clearance and block_on_secret=False |
| `REDACT` | data_level > recipient.clearance (content is sanitized) |
| `BLOCK` | block_on_secret=True and data_level==SECRET |

Non-internal channels (e.g. `final_output`, `tool_call`) always return `ALLOW` —
the guard only applies to the internal-channel attack surface.

### Level estimation

If you don't know the data level in advance, use automatic estimation:

```python
level = guard.estimate_data_level(text)
result = guard.check(text, channel="inter_agent_message", data_level=level)
```

Estimation is based on the number of sensitive patterns the Sanitizer would
redact: 0 → PUBLIC, 1–2 → INTERNAL, 3–5 → CONFIDENTIAL, 6+ → SECRET.
