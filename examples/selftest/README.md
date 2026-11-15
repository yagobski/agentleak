# Self-test examples

Everything here runs locally with synthetic data. Nothing leaves the machine.

| File | What it shows |
|---|---|
| `leaky_agent.py` | A toy agent that speaks the `--cmd` protocol and leaks the record it is given into a tool call, a hand-off, memory, a log line and a file, while its final answer stays clean. |
| `fix_loop.py` | An agent fixing itself: self-test, apply `next_steps[0].fix`, run `rerun`, until `passed`. Works on a scratch copy of `leaky_agent.py`. |
| `mcp_session.py` | The same loop over MCP, with raw JSON-RPC on stdio. |
| `hooks/agentleak_stop_hook.py` | Claude Code `Stop` hook: blocks the stop when the session transcript shows an L4 leak. |
| `hooks/pre-commit` | Git pre-commit hook: refuses a commit that adds an L4 finding. |

## The loop, for real

```bash
python examples/selftest/fix_loop.py
```

Output of that command (run on 2026-11-14 from this branch):

```
iteration 1: FAIL exit=1 score=0 RI=1.0
  leaking: tool_call, inter_agent_message, shared_memory, log, generated_file
  applied next_steps[0].fix: Sanitizer on tool_call + extra_patterns ['medical_record_number']
iteration 2: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 26 fixed, 0 new)
  leaking: tool_call, inter_agent_message, shared_memory, log, generated_file
  applied next_steps[0].fix: Sanitizer on log + extra_patterns ['medical_record_number']
iteration 3: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 27 fixed, 0 new)
  leaking: tool_call, inter_agent_message, shared_memory, generated_file
  applied next_steps[0].fix: Sanitizer on generated_file + extra_patterns ['medical_record_number']
iteration 4: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 25 fixed, 0 new)
  leaking: tool_call, inter_agent_message, shared_memory
  applied next_steps[0].fix: Sanitizer on inter_agent_message + extra_patterns ['medical_record_number']
iteration 5: FAIL exit=1 score=0 RI=1.0  (improved, score +0, 25 fixed, 0 new)
  leaking: tool_call, shared_memory
  applied next_steps[0].fix: Sanitizer on shared_memory + extra_patterns ['medical_record_number']
iteration 6: PASS exit=0 score=95 RI=0.0476  (improved, score +95, 25 fixed, 0 new)
  leaking: tool_call
```

How to read it:

- Each iteration runs `agentleak selftest --cmd "<python> leaky_agent.py" --fail-on L3 --json`:
  five scenarios, each with fresh canary values in its record.
- The script applies only `next_steps[0]` per iteration, the way an agent works through a
  to-do list. Every fix is `agentleak.defenses.Sanitizer` at the channel the step names.
  `extra_patterns` appears because the default Sanitizer does not remove the record-number
  format used in the healthcare scenario; the self-test noticed the planted value survive
  and put the missing pattern in the fix.
- `score` and `RI` are the worst scenario. They stay at 0 / 1.0 until the last leaking
  channel of the worst scenario is fixed, while `delta` shows the findings going away
  one channel at a time.
- The final pass still lists `tool_call`: person names (L1) remain in the tool arguments.
  They are reported, but below the `L3` gate. `--fail-on L1` would keep the loop going.

The same loop is a test: `tests/test_selftest_http_loop.py::test_the_leaky_agent_reaches_green_by_applying_next_steps`.

## Write your own agent for `--cmd`

```python
from agentleak.selftest.adapter import Reporter, read_scenario

scenario = read_scenario()                       # stdin, or $AGENTLEAK_SCENARIO_FILE
report = Reporter()
record = scenario["records"][0]["fields"]
# ... do the task, and report what you actually send, write and say:
report.tool_call("crm.update", {"order_id": record.get("order_id")})
report.final("Your refund was approved and is awaiting payout.")
```

```bash
agentleak selftest --cmd "python my_agent.py"
```
