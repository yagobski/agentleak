# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Drive `agentleak mcp` over stdio with raw JSON-RPC, the way an MCP client does.

Shows the self-test loop through MCP only: list tools, score a trace, explain a
finding, score again, read the status. No MCP SDK needed on the client side.

    python examples/selftest/mcp_session.py examples/healthcare_trace.json examples/healthcare_clean_trace.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


class Client:
    def __init__(self) -> None:
        self.proc = subprocess.Popen([sys.executable, "-m", "agentleak", "mcp"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.n = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self.n += 1
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method,
                                          "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        while True:
            message = json.loads(self.proc.stdout.readline())
            if message.get("id") == self.n:
                return message["result"]

    def call(self, name: str, **arguments: Any) -> dict[str, Any]:
        result: dict[str, Any] = self.request("tools/call", {"name": name, "arguments": arguments})
        return result["structuredContent"]  # type: ignore[no-any-return]


def main() -> None:
    leaky, fixed = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
    c = Client()
    info = c.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "demo", "version": "0"}})
    assert c.proc.stdin
    c.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    c.proc.stdin.flush()
    print("server:", info["serverInfo"])
    print("tools:", [t["name"] for t in c.request("tools/list")["tools"]])
    doc = c.call("privacy_selftest", trace=leaky)
    print("selftest #1:", {k: doc[k] for k in ("passed", "outcome", "verdict", "risk_index")})
    print("next_steps[0]:", doc["next_steps"][0]["channel"], "->", doc["next_steps"][0]["fix"]["defense"])
    ex = c.call("privacy_explain_finding", fingerprint=doc["findings"][0]["fingerprint"])
    print("explain:", ex["why"][:110] + "...")
    doc = c.call("privacy_selftest", trace=fixed)
    print("selftest #2:", {k: doc[k] for k in ("passed", "outcome", "verdict", "risk_index")},
          "delta:", {k: doc["delta"][k] for k in ("direction", "delta_score")},
          f"{len(doc['delta']['fixed'])} fixed")
    st = c.call("privacy_selftest_status")
    print("status:", st["next_step"])
    c.proc.terminate()


if __name__ == "__main__":
    main()
