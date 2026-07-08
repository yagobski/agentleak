"""Thin HTTP client to connect an agent to a running AgentLeak platform.

Lets your agent push traces to ``agentleak serve`` so runs show up in the web
UI under a project. Uses only the standard library (urllib) — no new deps.

Example::

    from agentleak import AgentLeakClient, capture, monitor

    @monitor(channel="tool_call")
    def call_crm(cid):
        return {"customer_email": "a@b.com", "account_id": "ACC-12345"}

    client = AgentLeakClient(project="support-bot")   # get-or-create by name
    with capture(run_id="run_001") as cap:
        call_crm(42)
    run = client.submit(cap.trace)        # appears in the platform
    print(run["risk_index"], run["verdict"])
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class AgentLeakError(RuntimeError):
    pass


def _http_request(
    base_url: str,
    method: str,
    path: str,
    body: Any | None = None,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    """One JSON request against a running AgentLeak platform (stdlib only).

    Shared by every client class — single place for encoding, error mapping,
    and the “is the server running?” hint.
    """
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for name, value in (headers or {}).items():
        req.add_header(name, value)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except Exception:  # noqa: BLE001
            pass
        raise AgentLeakError(f"{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise AgentLeakError(
            f"Could not reach AgentLeak at {base_url} — is `agentleak serve` running? ({exc.reason})"
        ) from exc


class AgentLeakClient:
    def __init__(
        self,
        project: str | None = None,
        *,
        base_url: str = "http://127.0.0.1:8000",
        agent_type: str = "generic",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._agent_type = agent_type
        self._project_id: str | None = None
        if project is not None:
            self._project_id = self.ensure_project(project, agent_type=agent_type)["id"]

    # -- low level ------------------------------------------------------
    def _request(self, method: str, path: str, body: Any | None = None) -> Any:
        return _http_request(self.base_url, method, path, body, timeout=self.timeout)

    # -- projects -------------------------------------------------------
    def list_projects(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/projects")

    def create_project(self, name: str, *, agent_type: str = "generic", **config: Any) -> dict[str, Any]:
        return self._request("POST", "/api/projects", {"name": name, "agent_type": agent_type, **config})

    def ensure_project(self, name: str, *, agent_type: str = "generic", **config: Any) -> dict[str, Any]:
        for p in self.list_projects():
            if p["name"] == name:
                return p
        return self.create_project(name, agent_type=agent_type, **config)

    # -- runs -----------------------------------------------------------
    def submit(self, trace: Any, *, project: str | None = None, source: str = "sdk") -> dict[str, Any]:
        """Analyze a trace on the server and store it as a run. Returns the run
        (including the full report). ``trace`` may be a Trace, a dict, or JSON.
        """
        pid = self._resolve_project(project)
        payload = {"trace": self._trace_payload(trace), "source": source}
        return self._request("POST", f"/api/projects/{pid}/runs", payload)

    def submit_capture(self, capture: Any, *, project: str | None = None) -> dict[str, Any]:
        return self.submit(capture.trace, project=project, source="sdk")

    def runs(self, *, project: str | None = None) -> list[dict[str, Any]]:
        pid = self._resolve_project(project)
        return self._request("GET", f"/api/projects/{pid}/runs")

    # -- helpers --------------------------------------------------------
    def _resolve_project(self, project: str | None) -> str:
        if project is not None:
            # treat as id if it looks like one, else get-or-create by name
            if project.startswith("proj_"):
                return project
            return self.ensure_project(project, agent_type=self._agent_type)["id"]
        if self._project_id is None:
            raise AgentLeakError("No project set. Pass project=... or construct the client with one.")
        return self._project_id

    @staticmethod
    def _trace_payload(trace: Any) -> Any:
        if hasattr(trace, "to_dict"):
            return trace.to_dict()
        if isinstance(trace, str):
            return json.loads(trace)
        return trace


class AgentSelfClient:
    """API-key client for *autonomous agents* — the self-improvement loop.

    No browser session needed: every call authenticates with the project's
    ``ak_...`` key (X-AgentLeak-Key). An agent can register its agent card,
    submit its own source code for a static scan, check its compliance
    status, and iterate on its AgentRisk score::

        from agentleak import AgentSelfClient

        me = AgentSelfClient(api_key="ak_...")
        me.register(card={
            "name": "support-bot",
            "capabilities": ["ticket_triage"],
            "source": {"type": "github", "repo": "acme/support-bot"},
        })
        me.scan_code()                       # scans the declared repo
        step = me.improve(trace)             # analyze + save + next steps
        for todo in step["next_steps"]:
            print(todo["priority"], todo["action"])
        print(me.status()["progression"])
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise AgentLeakError("An API key (ak_...) is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, body: Any | None = None) -> Any:
        return _http_request(
            self.base_url, method, path, body,
            headers={"X-AgentLeak-Key": self.api_key},
            timeout=self.timeout,
        )

    # -- identity ---------------------------------------------------------
    def register(self, card: dict[str, Any]) -> dict[str, Any]:
        """Upsert this agent's A2A-style agent card on its project."""
        return self._request("POST", "/api/agent/register", {"agent_card": card})

    def card(self) -> dict[str, Any]:
        return self._request("GET", "/api/agent/card")

    # -- code -------------------------------------------------------------
    def scan_code(self, **payload: Any) -> dict[str, Any]:
        """Static-scan this agent's source code.

        With no arguments, re-scans the source declared in the agent card.
        Otherwise pass ``source=\"github\", repo=\"owner/name\"`` or
        ``source=\"files\", files=[{\"path\": ..., \"content\": ...}]``.
        """
        return self._request("POST", "/api/agent/code", payload)

    # -- self-test / improvement loop --------------------------------------
    def selftest(self, trace: Any = None, *, scenario_id: str | None = None) -> dict[str, Any]:
        """Run one self-test (report + passed/compliant, run auto-saved)."""
        return self._request("POST", "/api/selftest-header", self._test_body(trace, scenario_id))

    def improve(self, trace: Any = None, *, scenario_id: str | None = None) -> dict[str, Any]:
        """One self-improvement step: selftest + delta vs previous run +
        prioritised ``next_steps`` the agent can act on."""
        return self._request("POST", "/api/agent/improve", self._test_body(trace, scenario_id))

    def status(self) -> dict[str, Any]:
        """Where do I stand? Latest run, progression, compliance, code scan."""
        return self._request("GET", "/api/agent/status")

    @staticmethod
    def _test_body(trace: Any, scenario_id: str | None) -> dict[str, Any]:
        if trace is not None:
            return {"trace": AgentLeakClient._trace_payload(trace)}
        if scenario_id:
            return {"scenario_id": scenario_id}
        raise AgentLeakError("Provide a trace or a scenario_id.")


def connect(project: str, *, base_url: str = "http://127.0.0.1:8000", agent_type: str = "generic") -> AgentLeakClient:
    """Convenience: ``client = agentleak.connect("my-agent")``."""
    return AgentLeakClient(project, base_url=base_url, agent_type=agent_type)
