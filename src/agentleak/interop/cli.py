# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak import``: turn a red-team or eval log into traces, and score it."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .._console import echo, secho
from ..core.trace import CHANNELS
from .base import ImportResult, InteropError

_HELP = (
    "Import the output of promptfoo, Inspect AI, garak or PyRIT as AgentLeak traces "
    "(and score them with --score). The file is data: nothing in it is executed or followed."
)


def write_traces(result: ImportResult, output: str) -> list[Path]:
    """Write the traces: one file when ``output`` ends in .json and there is
    one trace, otherwise one ``<run_id>.json`` per trace in the directory."""
    out = Path(output)
    if out.suffix == ".json" and len(result.traces) == 1:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.traces[0].trace.to_dict(), indent=2, ensure_ascii=False),
                       encoding="utf-8")
        return [out]
    if out.suffix == ".json":
        raise InteropError(f"{len(result.traces)} traces were imported; -o must name a directory, "
                           f"not the file {out.name}")
    out.mkdir(parents=True, exist_ok=True)
    written = []
    used: set[str] = set()
    for item in result.traces:
        name = item.trace.run_id
        stem, n = name, 2
        while name in used:
            name, n = f"{stem}_{n}", n + 1
        used.add(name)
        path = out / f"{name}.json"
        path.write_text(json.dumps(item.trace.to_dict(), indent=2, ensure_ascii=False),
                        encoding="utf-8")
        written.append(path)
    return written


def _echo_summary(result: ImportResult) -> None:
    version = result.tool_version or "version not recorded"
    secho(f"Recognised {result.tool} output ({version}): {result.detected_because}.", bold=True)
    events = sum(len(t.trace.events) for t in result.traces)
    echo(f"  {len(result.traces)} trace(s), {events} event(s); source sha256 "
               f"{result.source_sha256[:16]}…; verified against: {result.verification}")
    unobserved = [c for c in CHANNELS if c not in result.observable_channels]
    echo(f"  Observable channels: {', '.join(result.observable_channels)}")
    if unobserved:
        secho(f"  Not observed by {result.tool}: {', '.join(unobserved)}. A clean result on "
                    "those channels is not evidence: they were never seen.",
                    fg=typer.colors.BRIGHT_YELLOW)
    for note in result.notes:
        echo(f"  note: {note}")


def register(app: typer.Typer) -> None:
    """Add the ``import`` command to ``app``."""

    @app.command("import", help=_HELP)
    def import_cmd(  # noqa: PLR0913 - one flag per documented option
        file: str = typer.Argument(..., help="promptfoo results JSON, Inspect .eval/.json log, "
                                             "garak report.jsonl, or PyRIT conversation JSON."),
        source: str = typer.Option("auto", "--from", help="auto, promptfoo, inspect, garak or pyrit."),
        output: str = typer.Option("agentleak-imported", "--output", "-o",
                                   help="Directory for the traces, or a .json file when there is one."),
        score: bool = typer.Option(False, "--score", help="Analyze every imported trace now."),
        config: str | None = typer.Option(None, "--config", "-c", help="agentleak.yaml for --score."),
        report_dir: str = typer.Option("reports", "--report-dir",
                                       help="Where --score writes its reports."),
        fmt: str = typer.Option("json", "--format", "-f",
                                help="Report formats for --score: json, html, markdown, sarif."),
        fail_under: int | None = typer.Option(None, "--fail-under",
                                              help="With --score: exit 1 if a privacy score is below this."),
        quiet: bool = typer.Option(False, "--quiet", "-q", help="Only the summary lines."),
    ) -> None:
        from . import import_file

        try:
            result = import_file(file, source)
            written = write_traces(result, output)
        except (InteropError, OSError) as exc:
            secho(f"✗ {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=2) from exc
        _echo_summary(result)
        secho(f"✓ wrote {len(written)} trace file(s) to "
                    f"{written[0].parent if len(written) > 1 else written[0]}", fg=typer.colors.GREEN)
        if not score:
            return
        raise typer.Exit(code=_score(result, written, config, report_dir, fmt, fail_under, quiet))


def _score(result: ImportResult, written: list[Path], config: str | None, report_dir: str,
           fmt: str, fail_under: int | None, quiet: bool) -> int:
    from ..core.config import Config
    from ..core.runner import AgentLeakRunner
    from ..reporters import normalize_formats, write_reports

    try:
        cfg = Config.load(config) if config else None
        formats = normalize_formats([f for f in fmt.split(",") if f.strip()])
    except Exception as exc:  # noqa: BLE001 - any config/format error is a usage error
        secho(f"✗ {exc}", fg=typer.colors.RED)
        return 2
    runner = AgentLeakRunner(cfg)
    blocked = 0
    echo("")
    secho(f"{'record':<28} {'verdict':<17} {'score':>5}  leaked (data type @ channel)", bold=True)
    for item, path in zip(result.traces, written, strict=False):
        analysis = runner.analyze(item.trace)
        if fail_under is not None:
            analysis.fail_below = fail_under
        try:
            write_reports(analysis, report_dir, formats, basename=item.trace.run_id,
                          trace_path=str(path))
        except OSError as exc:
            secho(f"✗ could not write reports to {report_dir}: {exc}", fg=typer.colors.RED)
            return 1
        leaked = sorted({f"{f.data_type}@{f.channel}" for f in analysis.leaked_findings()})
        blocked += bool(analysis.blocked)
        if not quiet or analysis.blocked:
            echo(f"{item.record_id[:28]:<28} {analysis.verdict:<17} "
                       f"{analysis.privacy_score:>5}  {', '.join(leaked) or '-'}")
    echo("")
    echo(f"{len(result.traces)} trace(s) scored, {blocked} blocked. Reports in {report_dir}/.")
    if any(c not in result.observable_channels for c in CHANNELS):
        secho(f"Scored on what {result.tool} observed only; see 'observation' in each report.",
                    fg=typer.colors.BRIGHT_YELLOW)
    return 1 if blocked else 0
