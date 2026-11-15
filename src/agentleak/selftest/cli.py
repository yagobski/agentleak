# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak selftest`` — registered on the main Typer app by :func:`register`."""

from __future__ import annotations

import json
import os
import shlex
import sys
from typing import Any

import typer

from .document import EXIT_CODES, SCHEMA_VERSION, parse_level
from .runner import DEFAULT_FAIL_ON, DEFAULT_TIMEOUT, SelftestOptions

_HELP = """Test an agent for privacy leaks, locally, and get one JSON document back.

\b
  agentleak selftest                      check the engine works here (seconds, offline)
  agentleak selftest --trace run.json     score a trace your agent recorded (file, dir, or -)
  agentleak selftest --cmd "python a.py"  run your agent on the canary battery
  agentleak selftest --code .             scan your agent's source
  agentleak selftest --status             where you stand across self-tests

\b
Output is JSON when --json is given, when stdout is not a terminal, or when
AGENTLEAK_JSON=1. Exit codes: 0 pass, 1 finding at or above --fail-on,
2 usage error, 3 incomplete (agent crashed, timed out, reported nothing),
4 AgentLeak internal error. AgentLeak makes no network call unless your
--config enables the LLM judge.
"""


def _want_json(flag: bool | None) -> bool:
    if flag is not None:
        return flag
    if os.environ.get("AGENTLEAK_JSON", "").strip().lower() in {"1", "true", "yes"}:
        return True
    return not sys.stdout.isatty()


def _emit_error(as_json: bool, outcome: str, message: str, hint: str = "") -> None:
    code = EXIT_CODES[outcome]
    if as_json:
        typer.echo(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "kind": "agentleak.selftest.error",
            "passed": False,
            "outcome": "usage" if outcome == "usage" else outcome,
            "exit_code": code,
            "error": message,
            "hint": hint,
        }, indent=2))
    else:
        typer.secho(f"✗ {message}", fg=typer.colors.RED, err=True)
        if hint:
            typer.echo(f"  {hint}", err=True)
    raise typer.Exit(code=code)


def _rerun(argv: list[str]) -> dict[str, Any]:
    return {"cli": shlex.join(argv), "argv": argv}


def _render_human(doc: dict[str, Any]) -> None:
    color = {"pass": typer.colors.GREEN, "fail": typer.colors.RED,
             "incomplete": typer.colors.YELLOW, "error": typer.colors.RED}[doc["outcome"]]
    typer.secho(f"\nAgentLeak self-test · {doc['mode']} · {doc['run_id']}", bold=True)
    typer.secho(doc["summary"], fg=color, bold=True)
    if doc.get("risk_index") is not None:
        typer.echo(f"Risk Index {doc['risk_index']:.3f} · privacy {doc['privacy_score']}/100 · "
                   f"verdict {doc['verdict']} · fail-on {doc['threshold']['fail_on']}")
    det = doc["detection"]
    tiers = ", ".join(det["tiers"] or det.get("code_tiers") or []) or "none"
    typer.secho(f"Detection tiers: {tiers}" + (" (degraded)" if det["degraded"] else ""),
                fg=typer.colors.BRIGHT_BLACK)
    for check in doc.get("checks") or []:
        mark = "✓" if check["passed"] else "✗"
        typer.secho(f"  {mark} {check['name']}: {check['detail']}",
                    fg=typer.colors.GREEN if check["passed"] else typer.colors.RED)
    if doc.get("inputs"):
        typer.echo("")
        for item in doc["inputs"]:
            if item.get("error"):
                typer.secho(f"  ! {item['label']}: {item['error']}", fg=typer.colors.YELLOW)
            else:
                typer.echo(f"  {item['label']}: {item['format']}, {item['events']} events, "
                           f"{item['verdict']}" + (f", {item['canaries_planted']} canaries"
                                                   if item.get("canaries_planted") else ""))
    leaking = [c for c in doc["channels"] if c["status"] in ("leak", "clean")]
    if leaking:
        typer.echo("")
        for c in doc["channels"]:
            if c["role"] != "disclosure":
                continue
            label = {"leak": f"LEAK {c['worst_level']}", "clean": "clean",
                     "not_observed": "not recorded"}[c["status"]]
            fg = typer.colors.RED if c["status"] == "leak" else (
                typer.colors.GREEN if c["status"] == "clean" else typer.colors.BRIGHT_BLACK)
            typer.echo(f"  {c['channel']:<22}", nl=False)
            typer.secho(f"{label:<14}", fg=fg, nl=False)
            typer.echo(f"{c['finding_count']} finding(s)")
    delta = doc.get("delta")
    if delta:
        typer.echo("")
        typer.echo(f"Since last self-test: {delta['direction']}"
                   + (f", score {delta['delta_score']:+d}" if delta.get("delta_score") is not None else "")
                   + f", {len(delta['new'])} new, {len(delta['fixed'])} fixed")
    steps = [s for s in doc["next_steps"] if s["kind"] != "rerun"]
    if steps:
        typer.echo("")
        typer.secho("Next steps:", bold=True)
        for i, step in enumerate(steps[:6], 1):
            where = f" [{step['channel']}]" if step.get("channel") else ""
            typer.echo(f"  {i}. ({step['priority']}){where} {step['action']}")
            if step.get("command"):
                typer.echo(f"     $ {step['command']}")
            fix = step.get("fix") or {}
            if fix.get("type") == "apply_defense":
                typer.echo(f"     fix: {fix['defense']} at {fix['where']}")
    if doc.get("rerun"):
        typer.echo("")
        typer.echo(f"Re-run: {doc['rerun']['cli']}")
    typer.secho("Not a certification: a pass means no finding from the tiers listed above.",
                fg=typer.colors.BRIGHT_BLACK)


def register(app: typer.Typer) -> None:
    """Add the ``selftest`` command to ``app``."""

    @app.command("selftest", help=_HELP)
    def selftest(  # noqa: PLR0913 - one flag per documented option
        trace: list[str] = typer.Option(
            None, "--trace", "-t",
            help="Trace file, directory of .json/.jsonl files, or - for stdin. Repeatable.",
        ),
        trace_format: str | None = typer.Option(
            None, "--trace-format",
            help="Skip auto-detection: agentleak_trace, agentleak_events, openai_chat, "
                 "openai_responses, claude_code, otel_genai, otel_openinference, agent_steps.",
        ),
        cmd: str | None = typer.Option(
            None, "--cmd",
            help="Run this agent command once per built-in scenario (stdin/stdout JSON protocol).",
        ),
        shell: bool = typer.Option(
            False, "--shell", help="Run --cmd through the shell (off by default: argv, no shell).",
        ),
        timeout: float = typer.Option(DEFAULT_TIMEOUT, "--timeout", help="Seconds per scenario for --cmd."),
        scenarios: str | None = typer.Option(
            None, "--scenarios", help="Comma-separated subset of the battery for --cmd.",
        ),
        code: str | None = typer.Option(None, "--code", help="Also statically scan this source path."),
        as_json: bool | None = typer.Option(
            None, "--json/--human", help="Force JSON or human output (default: JSON when piped).",
        ),
        fail_on: str = typer.Option(
            f"L{DEFAULT_FAIL_ON}", "--fail-on",
            help="Fail on a finding at or above this level: L1, L2, L3 or L4.",
        ),
        fail_under: int | None = typer.Option(
            None, "--fail-under", min=0, max=100,
            help="Also fail when the privacy score is below this, 0-100 (default 40).",
        ),
        config: str | None = typer.Option(None, "--config", "-c", help="agentleak.yaml to honor."),
        state_dir: str | None = typer.Option(
            None, "--state-dir", help="Where history lives (default ./.agentleak or $AGENTLEAK_STATE_DIR).",
        ),
        no_history: bool = typer.Option(False, "--no-history", help="Do not record this self-test."),
        show_values: bool = typer.Option(
            False, "--show-values", help="Include raw matched values in findings (off by default).",
        ),
        scenario_instance: str | None = typer.Option(
            None, "--scenario-instance",
            help="Check canaries of a scenario issued with --get-scenario (default: the trace's scenario_id).",
        ),
        status_flag: bool = typer.Option(False, "--status", help="Show where you stand and exit."),
        list_flag: bool = typer.Option(False, "--list-scenarios", help="List the built-in battery."),
        get_scenario: str | None = typer.Option(
            None, "--get-scenario", help="Issue one scenario (fresh canaries) to run yourself.",
        ),
        explain_fp: str | None = typer.Option(
            None, "--explain", help="Explain a finding by its fingerprint.",
        ),
    ) -> None:
        want_json = _want_json(as_json)
        try:
            level = parse_level(fail_on)
        except ValueError as exc:
            _emit_error(want_json, "usage", str(exc), "Use --fail-on L1, L2, L3 or L4.")
            return
        opts = SelftestOptions(
            fail_on=level, fail_under=fail_under, config=config, state_dir=state_dir,
            record_history=not no_history, show_values=show_values,
        )

        from . import battery, runner
        from .explain import explain
        from .formats import FORMATS, TraceFormatError

        if status_flag:
            _print(runner.status(opts), want_json, human=_render_status)
            return
        if list_flag:
            _print({"schema_version": SCHEMA_VERSION, "kind": "agentleak.selftest.scenarios",
                    "protocol": battery.PROTOCOL, "scenarios": battery.catalog()},
                   want_json, human=_render_catalog)
            return
        if get_scenario:
            if get_scenario not in battery.TEMPLATE_BY_ID:
                _emit_error(want_json, "usage", f"unknown scenario {get_scenario!r}",
                            "List them with: agentleak selftest --list-scenarios")
            typer.echo(json.dumps(runner.issue_scenario(get_scenario, opts), indent=2))
            return
        if explain_fp:
            _print(explain(explain_fp, state_dir=state_dir), want_json, human=_render_explain)
            return
        if trace and cmd:
            _emit_error(want_json, "usage", "--trace and --cmd are separate modes; pick one.")
        if trace_format and trace_format not in FORMATS:
            _emit_error(want_json, "usage", f"unknown --trace-format {trace_format!r}",
                        "Known: " + ", ".join(FORMATS))

        argv = ["agentleak", "selftest"]
        for t in trace or []:
            argv += ["--trace", t]
        if trace_format:
            argv += ["--trace-format", trace_format]
        if cmd:
            argv += ["--cmd", cmd]
        if shell:
            argv.append("--shell")
        if scenarios:
            argv += ["--scenarios", scenarios]
        if code:
            argv += ["--code", code]
        if fail_on.upper() != f"L{DEFAULT_FAIL_ON}":
            argv += ["--fail-on", f"L{level}"]
        if fail_under is not None:
            argv += ["--fail-under", str(fail_under)]
        if config:
            argv += ["--config", config]
        if state_dir:
            argv += ["--state-dir", state_dir]
        argv.append("--json")
        rerun = _rerun(argv)

        try:
            if cmd:
                typer.secho(
                    "Running your agent command once per scenario, on this machine, with "
                    "synthetic data only. AgentLeak itself makes no network call; if your "
                    "agent calls a remote model, the synthetic data goes where your agent sends it.",
                    fg=typer.colors.BRIGHT_BLACK, err=True,
                )
                doc = runner.selftest_command(
                    cmd, opts, scenarios=[s.strip() for s in scenarios.split(",") if s.strip()]
                    if scenarios else None, timeout=timeout, use_shell=shell, code=code,
                    rerun=rerun,
                    progress=(None if want_json else
                              lambda sid: typer.secho(f"  · {sid}", fg=typer.colors.BRIGHT_BLACK, err=True)),
                )
            elif trace:
                if "-" in trace and sys.stdin.isatty():
                    _emit_error(want_json, "usage", "--trace - reads stdin, but stdin is a terminal.",
                                "Pipe a trace in: cat run.json | agentleak selftest --trace -")
                doc = runner.selftest_traces(list(trace), opts, fmt=trace_format,
                                             scenario_instance=scenario_instance, code=code,
                                             rerun=rerun)
            elif code:
                doc = runner.selftest_code(code, opts, rerun=rerun)
            else:
                doc = runner.run_engine_check(opts)
        except (FileNotFoundError, TraceFormatError, ValueError) as exc:
            _emit_error(want_json, "usage", str(exc),
                        "See: agentleak selftest --help, or agentleak schema trace")
            return
        except typer.Exit:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as a stable exit code, not a traceback
            _emit_error(want_json, "error", f"internal error: {type(exc).__name__}: {exc}",
                        "Please report this with the command you ran.")
            return

        if want_json:
            typer.echo(json.dumps(doc, indent=2, ensure_ascii=False))
        else:
            _render_human(doc)
        raise typer.Exit(code=doc["exit_code"])


def _print(payload: dict[str, Any], as_json: bool, *, human: Any) -> None:
    if as_json:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        human(payload)


def _render_status(st: dict[str, Any]) -> None:
    typer.secho(f"Self-test history: {st['history_path']} ({st['entries']} entries)", bold=True)
    for row in st["targets"]:
        mark = "pass" if row["passed"] else row["outcome"]
        typer.echo(f"  {row['latest_at']}  {row['mode']:<10} {mark:<10} "
                   f"score {row['privacy_score']}  runs {row['runs']}  "
                   f"open findings {row['open_findings']}  {', '.join(row['inputs'] or [])}")
    typer.echo(st["next_step"])


def _render_catalog(cat: dict[str, Any]) -> None:
    typer.secho(f"Built-in battery (protocol {cat['protocol']}):", bold=True)
    for s in cat["scenarios"]:
        typer.echo(f"  {s['id']:<22} {s['title']}  (canaries: {', '.join(s['canary_fields'])})")


def _render_explain(ex: dict[str, Any]) -> None:
    if not ex["found"]:
        typer.echo(ex["explanation"])
        return
    typer.secho(f"Finding {ex['fingerprint']}", bold=True)
    typer.echo(ex["why"])
    typer.echo(f"Rule: {ex['rule']['detector']} — {ex['rule']['what_it_matches']}")
    typer.echo(f"Severity: {ex['severity']['meaning']}")
    fix = ex.get("fix") or {}
    if fix:
        typer.echo("Fix:")
        typer.echo(fix.get("code") or fix.get("suggestion") or "")


__all__ = ["register"]
