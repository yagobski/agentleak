"""The one-import, one-context-manager way to test any agent for privacy leaks.

`watch()` unifies every framework path (LangChain, LangGraph, CrewAI, OpenAI
Swarm / Agents SDK, Google ADK, or plain Python) behind a single object. You
open one ``with`` block, attach whatever your framework gives you, and on exit
the trace is analyzed automatically — and submitted to a running platform if a
project name was given.

Plain Python (no framework)::

    import agentleak

    with agentleak.watch("support-bot") as run:
        run.tool_call({"email": "a@b.com", "ssn": "123-45-6789"}, target="crm")
        run.inter_agent_message("forwarding full profile to billing agent")
        run.final_output("All set!")

    print(run.report.verdict, run.report.risk_index)

LangChain / LangGraph — attach ``run.callback``::

    with agentleak.watch("support-bot") as run:
        chain.invoke(inputs, config={"callbacks": [run.callback]})

CrewAI — attach the step/task callbacks::

    with agentleak.watch("support-bot") as run:
        Crew(..., step_callback=run.crew.step_callback,
                  task_callback=run.crew.task_callback).kickoff()

OpenAI Swarm / Agents SDK — hand back the message list::

    with agentleak.watch("support-bot") as run:
        resp = client.run(agent=triage, messages=msgs)
        run.ingest_messages(resp.messages)

Google ADK — hand back the event list::

    with agentleak.watch("support-bot") as run:
        run.ingest_adk(list(adk_runner.run(...)))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.config import Config
from .core.report import AnalysisResult
from .core.runner import AgentLeakRunner
from .core.trace import Channel, Content, Trace
from .sdk import _local  # shared active-capture state (record()/@monitor work inside watch())


def _resolve_config(config: Config | str | None) -> Config | None:
    """Accept a Config, a path to ``agentleak.yaml``, or None (auto-discover)."""
    if isinstance(config, Config):
        return config
    if isinstance(config, str):
        return Config.load(config)
    # Auto-discover an agentleak.yaml beside the caller's cwd.
    for name in ("agentleak.yaml", "agentleak.yml"):
        p = Path.cwd() / name
        if p.exists():
            try:
                return Config.load(str(p))
            except Exception:  # noqa: BLE001 — config is best-effort here
                return None
    return None


class Run:
    """A single live capture-and-analyze session.

    A ``Run`` is the universal recorder. It records events directly
    (:meth:`tool_call`, :meth:`inter_agent_message`, ...), and exposes a hook for
    every supported framework so you never have to learn a per-framework API:

    - :attr:`callback`  — a LangChain / LangGraph callback bound to this run.
    - :attr:`crew`      — a CrewAI callback (``.step_callback`` / ``.task_callback``).
    - :meth:`ingest_messages` — OpenAI Swarm / Agents SDK message lists.
    - :meth:`ingest_adk`      — Google ADK event lists.

    On ``with`` exit the trace is analyzed into :attr:`report` and, if the run was
    created with a ``project`` and a reachable platform, submitted automatically.
    """

    def __init__(
        self,
        *,
        run_id: str = "run",
        agent_name: str = "agent",
        config: Config | None = None,
        project: str | None = None,
        base_url: str = "http://127.0.0.1:8000",
        submit: bool | None = None,
        print_summary: bool = True,
    ) -> None:
        self.trace = Trace(run_id=run_id, agent_name=agent_name)
        self.config = config
        self.project = project
        self.base_url = base_url
        self.print_summary = print_summary
        # submit=None → auto: submit when a project name was given.
        self._submit = (project is not None) if submit is None else submit
        self.report: AnalysisResult | None = None
        self.submitted: dict[str, Any] | None = None
        # Set when platform submission was attempted but failed (e.g. the
        # platform isn't running) — the local analysis in ``report`` is never
        # discarded because of this, but the failure is surfaced here instead
        # of being swallowed silently.
        self.submit_error: str | None = None
        self._token: Any = None
        self._callback: Any = None
        self._crew: Any = None

    # -- recording ------------------------------------------------------
    def record(
        self,
        channel: str | Channel,
        content: Content,
        *,
        source: str = "agent",
        target: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.trace.add_event(
            channel=channel, content=content, source=source, target=target,
            metadata=metadata or {},
        )

    def user_input(self, content: Content, **kw: Any) -> None:
        self.record(Channel.USER_INPUT, content, **kw)

    def tool_call(self, content: Content, **kw: Any) -> None:
        self.record(Channel.TOOL_CALL, content, **kw)

    def tool_response(self, content: Content, **kw: Any) -> None:
        self.record(Channel.TOOL_RESPONSE, content, **kw)

    def inter_agent_message(self, content: Content, **kw: Any) -> None:
        self.record(Channel.INTER_AGENT_MESSAGE, content, **kw)

    def shared_memory(self, content: Content, **kw: Any) -> None:
        self.record(Channel.SHARED_MEMORY, content, **kw)

    def log(self, content: Content, **kw: Any) -> None:
        self.record(Channel.LOG, content, **kw)

    def final_output(self, content: Content, **kw: Any) -> None:
        self.record(Channel.FINAL_OUTPUT, content, **kw)

    # -- framework hooks ------------------------------------------------
    @property
    def callback(self) -> Any:
        """A LangChain / LangGraph callback that writes into this run's trace."""
        if self._callback is None:
            from .integrations.langchain import LangChainCallback
            cb = LangChainCallback(run_id=self.trace.run_id, config=self.config)
            cb.trace = self.trace  # share the single trace
            self._callback = cb
        return self._callback

    @property
    def crew(self) -> Any:
        """A CrewAI callback (use ``.step_callback`` / ``.task_callback``)."""
        if self._crew is None:
            from .integrations.crewai import CrewAICallback
            cb = CrewAICallback(run_id=self.trace.run_id, config=self.config)
            cb.trace = self.trace  # share the single trace
            self._crew = cb
        return self._crew

    def ingest_messages(self, messages: list[Any]) -> None:
        """Ingest an OpenAI Swarm / Agents SDK message list (handoffs included)."""
        from .integrations.openai_swarm import trace_from_messages
        self._extend(trace_from_messages(messages, run_id=self.trace.run_id))

    def ingest_adk(self, events: list[Any]) -> None:
        """Ingest a Google ADK event list (sub-agent routing included)."""
        from .integrations.google_adk import trace_from_events
        self._extend(trace_from_events(events, run_id=self.trace.run_id))

    def ingest_steps(self, steps: list[Any]) -> None:
        """Ingest a computer-use / coding-agent action-observation step list
        (OpenHands, Open Interpreter, Cline, SWE-agent, browser-use)."""
        from .integrations.computer_use import trace_from_steps
        self._extend(trace_from_steps(steps, run_id=self.trace.run_id))

    def ingest_spans(self, spans: Any) -> None:
        """Ingest OpenInference / OpenTelemetry GenAI spans (Arize Phoenix,
        OpenLLMetry). Accepts a span list or a raw OTLP ``{resourceSpans}`` dict."""
        from .integrations.otel import trace_from_spans
        self._extend(trace_from_spans(spans, run_id=self.trace.run_id))

    def ingest(self, trace_or_events: Any) -> None:
        """Merge a Trace (or list of event dicts) into this run."""
        if isinstance(trace_or_events, Trace):
            self._extend(trace_or_events)
        else:
            for ev in trace_or_events:
                self.trace.add_event(**ev)

    def _extend(self, other: Trace) -> None:
        for ev in other.events:
            self.trace.events.append(ev)

    # -- analysis -------------------------------------------------------
    def analyze(self) -> AnalysisResult:
        """Run detection now (also called automatically on ``with`` exit)."""
        self.report = AgentLeakRunner(self.config).analyze(self.trace)
        return self.report

    # -- context manager ------------------------------------------------
    def __enter__(self) -> Run:
        # Register as the active capture so module-level record()/@monitor work.
        self._token = getattr(_local, "active", None)
        _local.active = self
        return self

    def __exit__(self, *exc: object) -> None:
        _local.active = self._token
        if exc and exc[0] is not None:
            return  # don't mask the user's exception with analysis
        self.analyze()
        if self._submit:
            self._try_submit()
        if self.print_summary:
            print(self.summary())

    def _try_submit(self) -> None:
        """Best-effort platform submission — never destroys the local report.

        The trace has already been analyzed into ``self.report`` before this
        runs, so a submission failure (platform not running, network error,
        server-side error) only means ``self.submitted`` stays ``None``; it is
        recorded on ``self.submit_error`` (surfaced in :meth:`summary`) rather
        than swallowed. Anything other than the expected client error is a bug
        and still propagates.
        """
        try:
            from .client import AgentLeakClient, AgentLeakError
            client = AgentLeakClient(self.project, base_url=self.base_url)
            self.submitted = client.submit(self.trace)
        except Exception as exc:  # noqa: BLE001 — submission is best-effort
            # Most common case: the platform isn't running. Keep local analysis.
            if not isinstance(exc, AgentLeakError):
                raise
            self.submit_error = str(exc)

    # -- presentation ---------------------------------------------------
    def summary(self) -> str:
        if self.report is None:
            return f"<agentleak.Run {self.trace.run_id!r} — not analyzed yet>"
        r = self.report
        leaked = r.leaked_findings()
        head = (
            f"AgentLeak · {self.trace.run_id} · RI {r.risk_index:.2f}/1.0 "
            f"· {r.verdict} · {len(leaked)} leak(s)"
        )
        lines = [head]
        # Group leaks by channel for an at-a-glance internal-channel view.
        by_channel: dict[str, list[str]] = {}
        for f in leaked:
            by_channel.setdefault(f.channel, []).append(f.data_type)
        for ch, types in by_channel.items():
            uniq = ", ".join(sorted(set(types)))
            lines.append(f"  {ch:<20} {uniq}")
        if self.submitted:
            lines.append(f"  → submitted to platform (run {self.submitted.get('id', '?')})")
        elif self.submit_error:
            lines.append(f"  ⚠ platform submission failed (local analysis above is unaffected): {self.submit_error}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.summary()


def watch(
    project: str | None = None,
    *,
    run_id: str = "run",
    agent_name: str = "agent",
    config: Config | str | None = None,
    submit: bool | None = None,
    base_url: str = "http://127.0.0.1:8000",
    print_summary: bool = True,
) -> Run:
    """Open a privacy-leak capture session for any agent.

    Args:
        project: Platform project name. If given (and a platform is reachable),
            the run is submitted automatically on exit. Omit for purely local
            analysis.
        run_id: Identifier for this run.
        agent_name: Name recorded on the trace.
        config: A :class:`~agentleak.Config`, a path to ``agentleak.yaml``, or
            ``None`` to auto-discover one in the current directory.
        submit: Force-enable/disable platform submission. ``None`` = auto
            (submit when ``project`` is given).
        base_url: Platform URL for submission.
        print_summary: Print a one-glance leak summary when the block exits.

    Returns:
        A :class:`Run` to use as a ``with`` block. After the block,
        ``run.report`` holds the :class:`~agentleak.AnalysisResult`.
    """
    return Run(
        run_id=run_id,
        agent_name=agent_name,
        config=_resolve_config(config),
        project=project,
        base_url=base_url,
        submit=submit,
        print_summary=print_summary,
    )


def active_run() -> Run | None:
    """The currently-open :class:`Run`, if any (used by ``record``/``monitor``)."""
    obj = getattr(_local, "active", None)
    return obj if isinstance(obj, Run) else None


__all__ = ["Run", "watch", "active_run"]
