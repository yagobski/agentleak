"""``agentleak`` command-line interface.

Commands: init, run, report, validate, scenarios, version.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer

from . import __version__
from .core.config import DEFAULT_CONFIG_YAML, Config
from .core.report import AnalysisResult
from .core.runner import AgentLeakRunner
from .core.trace import Trace
from .reporters import normalize_formats, render, write_reports
from .scenarios import list_scenarios, load_example_trace

app = typer.Typer(
    add_completion=False,
    help="AgentLeak OSS — local privacy-leakage testing for AI agents.",
    no_args_is_help=True,
)

_VERDICT_COLORS = {
    "Pass": typer.colors.GREEN,
    "Conditional pass": typer.colors.YELLOW,
    "High risk": typer.colors.BRIGHT_YELLOW,
    "Fail": typer.colors.RED,
}
_LEVEL_COLORS = {
    "critical": typer.colors.RED,
    "high": typer.colors.BRIGHT_YELLOW,
    "medium": typer.colors.YELLOW,
    "low": typer.colors.GREEN,
    "none": typer.colors.WHITE,
}
_INTERNAL_CHANNELS = {
    "tool_call", "shared_memory", "log", "inter_agent_message", "generated_file",
}


# ----------------------------------------------------------------------
# version
# ----------------------------------------------------------------------
@app.command()
def version() -> None:
    """Print the AgentLeak version."""
    typer.echo(f"agentleak {__version__}")


# ----------------------------------------------------------------------
# init
# ----------------------------------------------------------------------
@app.command()
def init(
    path: str = typer.Argument(".", help="Directory to initialize."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config."),
) -> None:
    """Scaffold an AgentLeak project (config + folders + a sample trace)."""
    root = os.path.abspath(path)
    os.makedirs(root, exist_ok=True)
    for sub in ("scenarios", "reports", "traces"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)

    config_path = os.path.join(root, "agentleak.yaml")
    if os.path.exists(config_path) and not force:
        typer.secho(f"! {config_path} already exists (use --force to overwrite).", fg=typer.colors.YELLOW)
    else:
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write(DEFAULT_CONFIG_YAML)
        typer.secho(f"✓ wrote {config_path}", fg=typer.colors.GREEN)

    # Drop a runnable sample trace so `agentleak run` works immediately.
    sample = load_example_trace("healthcare_patient_summary")
    sample_path = os.path.join(root, "traces", "example_trace.json")
    with open(sample_path, "w", encoding="utf-8") as fh:
        json.dump(sample.to_dict(), fh, indent=2)
    typer.secho(f"✓ wrote {sample_path}", fg=typer.colors.GREEN)

    typer.echo("")
    typer.echo("Next steps:")
    typer.echo("  agentleak run --trace traces/example_trace.json")
    typer.echo("  agentleak run --scenario healthcare_patient_summary")


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------
@app.command()
def validate(
    config: str = typer.Argument("agentleak.yaml", help="Path to the config file."),
    trace: str | None = typer.Option(None, "--trace", "-t", help="Also validate a trace file."),
) -> None:
    """Validate a configuration (and optionally a trace) file."""
    ok = True
    try:
        cfg = Config.load(config)
        typer.secho(f"✓ config valid: {config}", fg=typer.colors.GREEN)
        typer.echo(f"  detectors: {', '.join(k for k, v in cfg.detectors.as_dict().items() if v) or 'none'}")
        typer.echo(f"  channels:  {len(cfg.channels)} · scenarios: {len(cfg.scenarios)}")
        normalize_formats(cfg.reports.formats)
    except FileNotFoundError:
        typer.secho(f"✗ config not found: {config}", fg=typer.colors.RED)
        ok = False
    except Exception as exc:  # noqa: BLE001 - surface any validation error
        typer.secho(f"✗ invalid config: {exc}", fg=typer.colors.RED)
        ok = False

    if trace:
        try:
            t = Trace.from_json_file(trace)
            typer.secho(f"✓ trace valid: {trace} ({len(t.events)} events)", fg=typer.colors.GREEN)
        except Exception as exc:  # noqa: BLE001
            typer.secho(f"✗ invalid trace: {exc}", fg=typer.colors.RED)
            ok = False

    raise typer.Exit(code=0 if ok else 1)


# ----------------------------------------------------------------------
# scenarios
# ----------------------------------------------------------------------
@app.command()
def scenarios(
    packs: bool = typer.Option(False, "--packs", help="List bundled scenario packs (research benchmarks) instead."),
    pack: str | None = typer.Option(None, "--pack", help="List the scenarios inside one pack, e.g. agentleak_bench."),
) -> None:
    """List the scenarios you can run: built-ins, or a bundled research pack.

    Built-ins are the quick leak/clean pairs per domain. The packs ship the
    published benchmark suites; run any of their scenarios directly with
    ``agentleak run --pack <pack_id> --scenario <id>``.
    """
    from .scenarios.packs import expand_pack, list_packs

    if packs:
        for entry in list_packs():
            typer.secho(entry["id"], fg=typer.colors.CYAN, bold=True)
            typer.echo(f"  {entry['description'] or entry['name']}")
            typer.echo(f"  {entry['count']} scenario(s) · source: {entry['source'] or 'bundled'}")
            typer.echo(f"  run one: agentleak run --pack {entry['id']} --scenario <id>")
        return

    if pack:
        try:
            entries = expand_pack(pack)
        except (KeyError, FileNotFoundError, ValueError) as exc:
            typer.secho(f"✗ unknown pack: {pack}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        for meta, _trace in entries:
            typer.secho(meta.get("origin_id") or meta.get("name", "?"), fg=typer.colors.CYAN, bold=True)
            if meta.get("description"):
                typer.echo(f"  {meta['description']}")
        typer.echo(f"\n{len(entries)} scenario(s) in {pack}.")
        return

    for s in list_scenarios():
        typer.secho(s.id, fg=typer.colors.CYAN, bold=True)
        typer.echo(f"  {s.description}")
        typer.echo(f"  domain: {s.domain} · sensitive: {', '.join(s.sensitive_data)}")
    typer.echo("\nAlso available: agentleak scenarios --packs  (research benchmark suites)")


# ----------------------------------------------------------------------
# agent-card (offline A2A discovery card for THIS AgentLeak instance)
# ----------------------------------------------------------------------
@app.command(name="agent-card")
def agent_card_cmd() -> None:
    """Print AgentLeak's own A2A/Nasiko agent card (no server needed).

    The same document is served unauthenticated at
    ``/.well-known/agent-card.json`` by ``agentleak serve`` — this command
    lets an agent (or a human) discover AgentLeak's capabilities offline.
    """
    from .core.agentcard import platform_card

    typer.echo(json.dumps(platform_card(__version__).to_dict(), indent=2))


@app.command()
def schema(
    name: str = typer.Argument("catalog", help="Schema name, or 'catalog'."),
) -> None:
    """Print a public AgentLeak JSON Schema for IDEs, CI, or agents."""
    from .core.schemas import get_schema, schema_catalog

    try:
        payload = schema_catalog() if name == "catalog" else get_schema(name)
    except KeyError as exc:
        typer.secho(f"✗ {exc.args[0]}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(payload, indent=2))


# ----------------------------------------------------------------------
# skill (register AgentLeak with coding agents)
# ----------------------------------------------------------------------
_SKILL_STATUS_COLORS = {
    "current": typer.colors.GREEN,
    "installed": typer.colors.GREEN,
    "updated": typer.colors.GREEN,
    "unchanged": typer.colors.BRIGHT_BLACK,
    "stale": typer.colors.YELLOW,
    "conflict": typer.colors.RED,
    "missing": typer.colors.YELLOW,
    "removed": typer.colors.GREEN,
    "absent": typer.colors.BRIGHT_BLACK,
}
_SKILL_STATUS_LABELS = {
    "current": "up to date",
    "installed": "installed",
    "updated": "updated",
    "unchanged": "already up to date",
    "stale": "outdated — rerun with --install --force",
    "conflict": "differs from ours — use --force to overwrite",
    "missing": "not installed",
    "removed": "removed",
    "absent": "agent not detected",
}


@app.command()
def skill(
    install: bool = typer.Option(False, "--install", help="Write SKILL.md into agent skills directories."),
    uninstall: bool = typer.Option(False, "--uninstall", help="Remove a previously installed skill."),
    show: bool = typer.Option(False, "--print", help="Print the SKILL.md text to stdout."),
    target: list[str] = typer.Option(
        None, "--target", "-t", help="Limit to specific agents (repeatable). Default: all detected."
    ),
    path: str | None = typer.Option(
        None, "--path", help="Install into an explicit skills directory instead of auto-detecting."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite a skill file that differs from ours."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen, write nothing."),
) -> None:
    """Register AgentLeak as a skill so coding agents discover it on their own.

    With no flags, reports where the skill is installed.
    """
    from . import skill as skill_mod

    if show:
        typer.echo(skill_mod.skill_text())
        return

    if install and uninstall:
        typer.secho("✗ --install and --uninstall are mutually exclusive.", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    # --- resolve which locations we operate on --------------------------------
    if path is not None:
        locations = [(Path(path).expanduser(), path)]
    else:
        if target:
            try:
                targets = [skill_mod.target_by_id(t) for t in target]
            except KeyError as exc:
                typer.secho(f"✗ {exc.args[0]}", fg=typer.colors.RED)
                raise typer.Exit(code=2) from exc
        else:
            targets = skill_mod.detect_targets()
        locations = [(t.skills_path(), t.label) for t in targets]

    # --- status (no flags) ----------------------------------------------------
    if not install and not uninstall:
        rows = skill_mod.status()
        typer.echo("")
        typer.secho("👁️  AgentLeak skill", bold=True)
        typer.echo("")
        for tgt, state in rows:
            typer.secho(
                f"  {tgt.label:<14} {_SKILL_STATUS_LABELS[state]}",
                fg=_SKILL_STATUS_COLORS[state],
            )
        typer.echo("")
        if any(state in {"missing", "stale"} for _, state in rows):
            typer.echo("  Install with:  agentleak skill --install")
        elif not any(state != "absent" for _, state in rows):
            typer.echo("  No supported agent detected. Use --path <skills-dir> to install anyway.")
        return

    if not locations:
        typer.secho(
            "✗ No supported agent detected (Claude Code, OpenClaw, Cursor, Windsurf, Codex CLI).",
            fg=typer.colors.RED,
        )
        typer.echo("  Install into an explicit directory with:  agentleak skill --install --path <dir>")
        raise typer.Exit(code=1)

    # --- act ------------------------------------------------------------------
    outcomes = []
    for destination, label in locations:
        if uninstall:
            outcomes.append(skill_mod.uninstall(destination, label=label, dry_run=dry_run))
        else:
            outcomes.append(
                skill_mod.install(destination, force=force, label=label, dry_run=dry_run)
            )

    prefix = "[dry-run] " if dry_run else ""
    typer.echo("")
    for outcome in outcomes:
        mark = "✓" if outcome.ok else "✗"
        typer.secho(
            f"  {mark} {outcome.label or outcome.path.parent.name}: "
            f"{prefix}{_SKILL_STATUS_LABELS[outcome.status]}",
            fg=_SKILL_STATUS_COLORS[outcome.status],
        )
        if outcome.changed or outcome.status == "unchanged":
            typer.secho(f"      {outcome.path}", fg=typer.colors.BRIGHT_BLACK)
    typer.echo("")

    if any(not o.ok for o in outcomes):
        raise typer.Exit(code=1)
    if install and not dry_run:
        typer.echo("  Start a new agent session for the skill to be picked up.")


# ----------------------------------------------------------------------
# scan (static code privacy scan)
# ----------------------------------------------------------------------
@app.command()
def scan(
    path: str = typer.Argument(".", help="File, directory or zip archive to scan."),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Scan a GitHub repo (owner/name) instead of a path."),
    branch: str = typer.Option("main", "--branch", help="Branch to scan with --repo."),
    config: str | None = typer.Option(None, "--config", "-c", help="agentleak.yaml (detector toggles, custom rules, detection mode)."),
    mode: str | None = typer.Option(None, "--mode", "-m", help="Detection mode: fast | standard (Presidio) | hybrid (Presidio + LLM-judge)."),
    output: str | None = typer.Option(None, "--output", "-o", help="Write the full result to a file."),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json | sarif."),
    fail_under: int | None = typer.Option(None, "--fail-under", help="Exit non-zero when the code score is below this value."),
) -> None:
    """Static privacy scan of agent source code (file, dir, zip, or GitHub repo).

    Runs the same 3-tier hybrid pipeline as trace analysis (regex detectors,
    Presidio, LLM-judge) plus code-specific layers: entropy analysis,
    de-obfuscation of decomposed PII, and quasi-identifier correlation.
    """
    from .core.codescan import scan_github_repo, scan_path

    fmt = fmt.lower().strip()
    if fmt not in {"json", "sarif"}:
        typer.secho("✗ format must be 'json' or 'sarif'", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    cfg: Config | None = None
    if config:
        try:
            cfg = Config.load(config)
        except (OSError, ValueError) as exc:
            typer.secho(f"✗ could not load config: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
    if mode:
        # Mode override: standard enables Presidio, hybrid also enables the
        # LLM-judge (endpoint from AGENTLEAK_LLM_BASE_URL / _MODEL env vars).
        det: dict[str, object] = {
            "mode": mode,
            "presidio": {"enabled": mode in ("standard", "hybrid")},
            "llm_judge": {
                "enabled": mode in ("hybrid", "llm_only"),
                "base_url": os.environ.get("AGENTLEAK_LLM_BASE_URL", ""),
                "model": os.environ.get("AGENTLEAK_LLM_MODEL", ""),
            },
        }
        base = cfg.model_dump() if cfg else {}
        base["detection"] = {**base.get("detection", {}), **det}
        cfg = Config.from_dict(base)

    try:
        if repo:
            typer.echo(f"Fetching {repo}@{branch} …")
            result = scan_github_repo(repo, branch=branch, config=cfg)
        else:
            # scan_path dispatches on what the argument actually is: a single
            # file, a directory tree or a zip archive.
            result = scan_path(path, config=cfg)
    except (ValueError, OSError) as exc:
        typer.secho(f"✗ {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    summary = result.summary()
    color = typer.colors.GREEN if result.score >= 90 else (
        typer.colors.YELLOW if result.score >= 70 else typer.colors.RED
    )
    typer.secho(f"Code privacy score: {result.score}/100 — {result.verdict}", fg=color, bold=True)
    typer.echo(
        f"  mode: {result.detection_mode} · tiers: {', '.join(result.tiers)}\n"
        f"  files scanned: {summary['files_scanned']} · findings: {summary['total_findings']}"
        f" · levels: {summary['level_profile']}"
    )
    for f in result.findings[:25]:
        typer.echo(f"  [L{f.level}] {f.file}:{f.line} {f.rule} ({f.data_type}, {f.tier})")
        typer.echo(f"        {f.snippet}")
    if len(result.findings) > 25:
        typer.echo(f"  … and {len(result.findings) - 25} more (use --output for the full list)")

    if output:
        payload = result.to_sarif() if fmt == "sarif" else result.to_dict()
        Path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        typer.secho(f"✓ wrote {output}", fg=typer.colors.GREEN)

    if fail_under is not None and result.score < fail_under:
        typer.secho(f"✗ score {result.score} < fail-under {fail_under}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# redact (runtime defense: sanitize before the data ever moves)
# ----------------------------------------------------------------------
@app.command()
def redact(
    path: str | None = typer.Argument(None, help="File to sanitize. Omit to read stdin."),
    style: str = typer.Option("placeholder", "--style", help="placeholder | mask | hash | remove."),
    output: str | None = typer.Option(None, "--output", "-o", help="Write to a file instead of stdout."),
) -> None:
    """Redact sensitive values from text, so a leak never happens in the first place.

    Detection tells you what leaked; this is the other half: the same rules
    applied as a defense. Pipe logs, prompts or tool payloads through it, or
    use ``agentleak.defenses.Sanitizer`` in-process for the same result.
    """
    from .defenses import RedactionStyle, sanitize_text

    valid = {s.value for s in RedactionStyle}
    if style not in valid:
        typer.secho(f"✗ style must be one of: {', '.join(sorted(valid))}", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    try:
        text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    except OSError as exc:
        typer.secho(f"✗ {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    cleaned = sanitize_text(text, style=style)
    if output:
        Path(output).write_text(cleaned, encoding="utf-8")
        typer.secho(f"✓ redacted → {output}", fg=typer.colors.GREEN)
    else:
        typer.echo(cleaned)


# ----------------------------------------------------------------------
# serve (web GUI)
# ----------------------------------------------------------------------
@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser."),
) -> None:
    """Launch the local web GUI (requires the [gui] extra)."""
    try:
        from .web import run_server
    except Exception as exc:  # noqa: BLE001
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"AgentLeak GUI → http://{host}:{port}  (Ctrl+C to stop)", fg=typer.colors.GREEN)
    try:
        run_server(host=host, port=port, open_browser=not no_browser)
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


# ----------------------------------------------------------------------
# run
# ----------------------------------------------------------------------
@app.command()
def run(
    config: str | None = typer.Option(None, "--config", "-c", help="Config file (honors detector/scoring settings)."),
    scenario: str | None = typer.Option(None, "--scenario", "-s", help="Run a built-in scenario (or 'all')."),
    pack: str | None = typer.Option(None, "--pack", help="Take --scenario from a bundled pack (e.g. agentleak_bench), or run 'all' of it."),
    trace: str | None = typer.Option(None, "--trace", "-t", help="Analyze a trace JSON file."),
    output: str | None = typer.Option(None, "--output", "-o", help="Report output directory."),
    fmt: str = typer.Option("json,html,markdown", "--format", "-f", help="Comma-separated formats."),
    fail_under: int | None = typer.Option(None, "--fail-under", help="Exit non-zero if a score is below this."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Less console output."),
) -> None:
    """Analyze a trace (or scenario) and write privacy reports."""
    cfg: Config | None = None
    if config:
        try:
            cfg = Config.load(config)
        except Exception as exc:  # noqa: BLE001
            typer.secho(f"✗ could not load config: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=2) from exc

    traces = _resolve_traces(trace, scenario, cfg, pack=pack)
    if not traces:
        typer.secho(
            "Nothing to run. Provide --trace, --scenario, or scenarios in --config.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)

    out_dir = output or (cfg.reports.output_dir if cfg else "reports")
    formats = [f for f in fmt.split(",") if f.strip()]
    runner = AgentLeakRunner(cfg)

    worst_blocked = False
    for _label, t in traces:
        result = runner.analyze(t)
        if fail_under is not None:
            result.fail_below = fail_under
        written = write_reports(result, out_dir, formats, basename=result.run_id)
        if not quiet:
            _print_result(result, written)
        elif result.warnings:
            # Degradation warnings are safety-critical — surface them even in
            # --quiet mode so a degraded run is never mistaken for a clean pass.
            typer.secho(
                f"⚠ {result.run_id}: degraded run — a requested detection tier "
                "did not run; score may under-report leakage.",
                fg=typer.colors.BRIGHT_YELLOW, bold=True,
            )
            for w in result.warnings:
                typer.secho(f"  · {w}", fg=typer.colors.BRIGHT_YELLOW)
        worst_blocked = worst_blocked or result.blocked

    raise typer.Exit(code=1 if worst_blocked else 0)


# ----------------------------------------------------------------------
# report
# ----------------------------------------------------------------------
@app.command()
def report(
    input: str = typer.Option(..., "--input", "-i", help="A result.json produced by `run`."),
    fmt: str = typer.Option("html", "--format", "-f", help="Comma-separated formats to render."),
    output: str | None = typer.Option(None, "--output", "-o", help="Output directory."),
) -> None:
    """Re-render a saved JSON report into other formats."""
    try:
        with open(input, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"✗ could not read report: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc

    out_dir = output or os.path.dirname(os.path.abspath(input))
    basename = os.path.splitext(os.path.basename(input))[0]
    os.makedirs(out_dir, exist_ok=True)
    from .reporters import _EXTENSIONS  # local import: internal mapping

    for f in normalize_formats([x for x in fmt.split(",") if x.strip()]):
        content = render(data, f)
        path = os.path.join(out_dir, f"{basename}.{_EXTENSIONS[f]}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        typer.secho(f"✓ {f}: {path}", fg=typer.colors.GREEN)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _resolve_traces(
    trace: str | None, scenario: str | None, cfg: Config | None, *, pack: str | None = None
) -> list[tuple[str, Trace]]:
    if trace:
        return [(trace, Trace.from_json_file(trace))]
    if pack:
        # A bundled research pack: the whole suite, or one scenario from it.
        # This is what makes the published benchmark one command away.
        from .scenarios.packs import expand_pack

        try:
            entries = expand_pack(pack)
        except (KeyError, FileNotFoundError, ValueError) as exc:
            raise typer.BadParameter(f"unknown pack: {pack}") from exc
        if not scenario or scenario == "all":
            return [(meta.get("origin_id") or meta.get("name", "?"), tr) for meta, tr in entries]
        for meta, tr in entries:
            if scenario in (meta.get("origin_id"), meta.get("name")):
                return [(scenario, tr)]
        raise typer.BadParameter(f"scenario '{scenario}' not found in pack '{pack}'")
    if scenario:
        if scenario == "all":
            return [(s.id, load_example_trace(s.id)) for s in list_scenarios() if s.example_trace]
        return [(scenario, load_example_trace(scenario))]
    if cfg and cfg.scenarios:
        out: list[tuple[str, Trace]] = []
        for ref in cfg.scenarios:
            if ref.enabled:
                try:
                    out.append((ref.id, load_example_trace(ref.id)))
                except (KeyError, ValueError):
                    typer.secho(f"! skipping unknown scenario '{ref.id}'", fg=typer.colors.YELLOW)
        return out
    return []


def _print_result(result: AnalysisResult, written: dict[str, str]) -> None:
    data = result.to_dict()
    verdict_color = _VERDICT_COLORS.get(result.verdict, typer.colors.WHITE)

    typer.echo("")
    typer.secho("AgentLeak Privacy Report (AgentRisk scoring)", bold=True)
    typer.echo(f"Agent: {result.agent_name} · run: {result.run_id} · events: {result.event_count}")
    typer.echo("")
    typer.secho(
        f"Risk Index: {data['risk_index']:.3f}   {result.verdict}   "
        f"(privacy {result.privacy_score}/100)",
        fg=verdict_color, bold=True,
    )
    lp = data["summary"]["level_profile"]
    s = data["summary"]
    typer.echo(
        f"WSL {data['wsl']} / ρ_S {data['rho_s']}  ·  "
        f"{s['leaked_secrets']} of {s['vault_secrets']} secrets leaked  "
        f"(L4 {lp['L4']}, L3 {lp['L3']}, L2 {lp['L2']}, L1 {lp['L1']})"
    )
    cs = data.get("compliance", {}).get("summary")
    if cs:
        color = typer.colors.GREEN if cs["non_compliant"] == 0 else typer.colors.BRIGHT_YELLOW
        typer.secho(
            f"Compliance: {cs['compliant']}/{cs['total']} frameworks clear "
            f"({cs['controls_at_risk']} control(s) at risk)",
            fg=color,
        )
    if result.warnings:
        typer.echo("")
        typer.secho(
            "⚠ Degraded run — a requested detection tier did not run. "
            "This score may under-report leakage; do not read it as a clean pass.",
            fg=typer.colors.BRIGHT_YELLOW, bold=True,
        )
        for w in result.warnings:
            typer.secho(f"  · {w}", fg=typer.colors.BRIGHT_YELLOW)

    policy = data.get("privacy_policy", {})
    if policy.get("enabled"):
        color = typer.colors.GREEN if policy.get("passed") else typer.colors.RED
        status = "passed" if policy.get("passed") else "failed"
        typer.secho(
            f"Privacy policy: {status} · {len(policy.get('violations', []))} violation(s)",
            fg=color,
        )
        for violation in policy.get("violations", []):
            typer.echo(f"  - {violation['rule']}: {violation['message']}")

    if data["channel_risks"]:
        typer.echo("")
        typer.echo("Risk by channel:")
        for cr in data["channel_risks"]:
            color = _LEVEL_COLORS.get(cr["level"], typer.colors.WHITE)
            typer.echo("  " + f"{cr['channel']:<22} ", nl=False)
            typer.secho(f"{cr['level_label']:<4}", fg=color, nl=False)
            typer.echo(f" RI {cr['ri']:.3f}  {cr['finding_count']} finding(s)")

    insight = _console_insight(data)
    if insight:
        typer.echo("")
        typer.secho("Key insight: ", fg=typer.colors.CYAN, bold=True, nl=False)
        typer.echo(insight)

    if result.blocked:
        typer.echo("")
        typer.secho("⛔ Blocked — this run would fail a CI privacy gate.", fg=typer.colors.RED, bold=True)

    if written:
        typer.echo("")
        for f, path in written.items():
            typer.secho(f"✓ {f:<8} {path}", fg=typer.colors.GREEN)


def _console_insight(data: dict) -> str | None:
    levels = {cr["channel"]: cr["level"] for cr in data.get("channel_risks", [])}
    output_level = levels.get("final_output", "none")
    internal = [c for c, lvl in levels.items() if c in _INTERNAL_CHANNELS and lvl != "none"]
    if output_level in {"none", "low"} and internal:
        return (
            "the final answer appears safe, but sensitive data leaked through "
            f"internal channels ({', '.join(internal)})."
        )
    return None


# ----------------------------------------------------------------------
# history
# ----------------------------------------------------------------------
@app.command()
def history(
    project: str = typer.Argument(..., help="Project name."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max runs to show."),
    db_path: str | None = typer.Option(None, "--db", help="Path to agentleak.db (default: ~/.agentleak/)."),
) -> None:
    """Show the score progression history for a project."""
    import datetime

    from .core.store import Store

    store = Store(db_path) if db_path else Store()
    proj = store.get_project_by_name(project)
    if not proj:
        typer.secho(f"✗ Project '{project}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    runs = store.run_history(proj["id"], limit=limit)
    if not runs:
        typer.secho(f"No runs found for project '{project}'.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"\nHistory — {project}  ({len(runs)} runs)\n", bold=True)
    typer.echo(
        f"  {'#':<4}  {'Run ID':<18}  {'Date':<20}  {'Score':>5}  {'Δ':>5}  "
        f"{'RI':>6}  {'ΔRI':>7}  {'Verdict':<18}  Label"
    )
    typer.echo("  " + "─" * 95)
    for r in runs:
        d_score = r["delta_score"]
        d_ri = r["delta_ri"]
        delta_str = f"{d_score:>+5}" if d_score is not None else f"{'—':>5}"
        dri_str = f"{d_ri:>+.3f}" if d_ri is not None else f"{'—':>7}"
        dt = datetime.datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M")
        blocked_flag = " ⛔" if r["blocked"] else ""
        label = r.get("label") or ""
        score_color = (
            typer.colors.GREEN if r["privacy_score"] >= 80
            else typer.colors.YELLOW if r["privacy_score"] >= 50
            else typer.colors.RED
        )
        delta_color = (
            typer.colors.GREEN if (d_score or 0) > 0
            else typer.colors.RED if (d_score or 0) < 0
            else typer.colors.WHITE
        )
        typer.echo(f"  {r['rank']:<4}  {r['id']:<18}  {dt:<20}  ", nl=False)
        typer.secho(f"{r['privacy_score']:>5}", fg=score_color, nl=False)
        typer.echo("  ", nl=False)
        typer.secho(delta_str, fg=delta_color, nl=False)
        typer.echo(f"  {r['risk_index']:>6.3f}  {dri_str:>7}  {r['verdict']:<18}{blocked_flag}  {label}")

    if len(runs) > 1:
        first, last = runs[0], runs[-1]
        total = last["privacy_score"] - first["privacy_score"]
        total_color = typer.colors.GREEN if total > 0 else typer.colors.RED if total < 0 else typer.colors.WHITE
        best = max(runs, key=lambda r: r["privacy_score"])
        typer.echo("")
        typer.echo("  Total improvement : ", nl=False)
        typer.secho(f"{total:+d} pts", fg=total_color, bold=True)
        typer.echo(f"  Best run          : {best['id']}  ({best['privacy_score']}/100)")
        typer.echo(f"  Blocked runs      : {sum(1 for r in runs if r['blocked'])}/{len(runs)}")
    typer.echo("")


# ----------------------------------------------------------------------
# compare
# ----------------------------------------------------------------------
@app.command()
def compare(
    run_a: str = typer.Argument(..., help="First run ID (baseline)."),
    run_b: str = typer.Argument(..., help="Second run ID (comparison)."),
    db_path: str | None = typer.Option(None, "--db", help="Path to agentleak.db."),
) -> None:
    """Compare two runs side by side and show score/RI/compliance deltas."""
    from typing import Any as _Any

    from .core.store import Store

    store = Store(db_path) if db_path else Store()
    result = store.compare_runs(run_a, run_b)
    if result is None:
        typer.secho("✗ One or both run IDs not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    a, b, diff = result["run_a"], result["run_b"], result["diff"]

    typer.secho("\nRun comparison", bold=True)
    typer.echo(f"  A (baseline) : {a['id']}  {a.get('label') or ''}".rstrip())
    typer.echo(f"  B (current)  : {b['id']}  {b.get('label') or ''}".rstrip())
    typer.echo("")

    typer.echo(f"  {'Metric':<24}  {'A':>8}  {'B':>8}  {'Delta':>8}")
    typer.echo("  " + "─" * 56)

    def _row(name: str, val_a: _Any, val_b: _Any, delta: _Any, *, invert: bool = False) -> None:
        if delta is None:
            delta_str, delta_color = "—", typer.colors.WHITE
        else:
            delta_str = f"{delta:+.3f}" if isinstance(delta, float) else f"{delta:+d}"
            positive_is_good = (delta > 0) ^ invert
            delta_color = (
                typer.colors.GREEN if positive_is_good
                else typer.colors.RED if delta != 0
                else typer.colors.WHITE
            )
        va = f"{val_a:.3f}" if isinstance(val_a, float) else str(val_a)
        vb = f"{val_b:.3f}" if isinstance(val_b, float) else str(val_b)
        typer.echo(f"  {name:<24}  {va:>8}  {vb:>8}  ", nl=False)
        typer.secho(f"{delta_str:>8}", fg=delta_color)

    _row("Privacy score", a["privacy_score"], b["privacy_score"], diff["delta_score"])
    _row("Risk Index (RI)", a["risk_index"], b["risk_index"], diff["delta_ri"], invert=True)
    _row("Leaked secrets", a["leaked_secrets"], b["leaked_secrets"], diff["delta_leaked"], invert=True)
    total_a = a.get("report", {}).get("summary", {}).get("total_findings", 0)
    total_b = b.get("report", {}).get("summary", {}).get("total_findings", 0)
    _row("Total findings", total_a, total_b, diff["delta_findings"], invert=True)
    _row("Blocked", "yes" if a["blocked"] else "no", "yes" if b["blocked"] else "no", None)

    fws = diff.get("frameworks", [])
    if fws:
        typer.echo("")
        typer.secho("  Compliance frameworks:", bold=True)
        for fw in fws:
            icon = {"fixed": "✓", "regressed": "✗", "same": " "}.get(fw["change"], " ")
            color = {"fixed": typer.colors.GREEN, "regressed": typer.colors.RED}.get(fw["change"])
            line = f"  {icon} [{fw['id']:<14}]  {fw['before']:<12} → {fw['after']}"
            if color:
                typer.secho(line, fg=color)
            else:
                typer.echo(line)

    typer.echo("")
    direction = diff.get("score_direction", "unchanged")
    dcolor = {"improved": typer.colors.GREEN, "regressed": typer.colors.RED}.get(direction, typer.colors.WHITE)
    typer.secho(f"  Overall: {direction.upper()}", fg=dcolor, bold=True)
    if diff.get("blocked_resolved"):
        typer.secho("  Blocker resolved — run B passes the privacy gate.", fg=typer.colors.GREEN)
    typer.echo("")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
