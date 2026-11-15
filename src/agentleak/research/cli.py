# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak bench``: the researcher workflow on the command line.

init -> run -> compare -> export -> capsule -> verify, plus score-corpus,
properties and ablate-scope for AgentRisk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from .bench import RunError, load_run, run_benchmark
from .manifest import Manifest, ManifestError, render_template
from .stats import fmt_p

bench_app = typer.Typer(
    help="Research workflow: experiment manifests, benchmark runs, paired comparisons, "
    "paper-ready exports and reproducibility capsules. Start with `agentleak bench init`.",
    no_args_is_help=True,
)


def _rel(path: Path | str) -> str:
    """A path relative to the working directory when it is inside it."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(p)


def _fail(message: str, code: int = 2) -> typer.Exit:
    typer.secho(f"✗ {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(code=code)


def _line(record: dict[str, Any] | None, label: str) -> None:
    if not record:
        return
    est = record.get("estimate")
    if est is None:
        typer.echo(f"  {label:<44} n/a ({record.get('numerator')}/{record.get('denominator')})")
        return
    frac = (f"{record['numerator']}/{record['denominator']}"
            if record.get("numerator") is not None and record.get("denominator") is not None
            and float(record["numerator"]).is_integer() else f"n={record.get('n')}")
    typer.echo(
        f"  {label:<44} {est:.3f}  {frac:>9}  CI {record['ci_low']:.3f}-{record['ci_high']:.3f}"
    )


class _Progress:
    def __init__(self, quiet: bool) -> None:
        self.quiet = quiet
        self.tty = sys.stderr.isatty()
        self.last_pct = -1

    def __call__(self, done: int, total: int, unit: str) -> None:
        if self.quiet:
            return
        if self.tty:
            sys.stderr.write(f"\r  analyzing {done}/{total}  {unit[:60]:<60}")
            if done == total:
                sys.stderr.write("\n")
            sys.stderr.flush()
            return
        pct = done * 100 // total
        if pct // 25 > self.last_pct // 25 or done == total:
            self.last_pct = pct
            typer.echo(f"  analyzing {done}/{total} ({pct}%)", err=True)


# ---------------------------------------------------------------------------
@bench_app.command("init")
def init_cmd(
    path: str = typer.Argument("bench.yaml", help="Where to write the manifest."),
    name: str | None = typer.Option(None, "--name", help="Experiment name (default: file name)."),
    quick: bool = typer.Option(False, "--quick", help="Sample 10 leaking fixtures per source."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing manifest."),
) -> None:
    """Write a commented experiment manifest, pinned to the installed version."""
    p = Path(path)
    if p.exists() and not force:
        raise _fail(f"{p} already exists (use --force to overwrite)")
    exp = name or p.stem.replace("_", "-")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_template(exp, quick=quick, filename=str(p)), encoding="utf-8")
    m = Manifest.load(p)
    typer.secho(f"✓ wrote {p}", fg=typer.colors.GREEN)
    typer.echo(f"  sources: {', '.join(m.scenarios.sources)} · detection: {m.detection.mode} · "
               f"seed {m.seed} · output: {m.resolved_output_dir()}")
    typer.echo("")
    typer.echo("Next:")
    typer.echo(f"  agentleak bench run {p}")


@bench_app.command("repin")
def repin_cmd(manifest: str = typer.Argument(..., help="Experiment manifest (YAML).")) -> None:
    """Update a manifest's pins to the installed version and scenario hashes."""
    from .manifest import repin

    try:
        drift = repin(manifest)
    except ManifestError as exc:
        raise _fail(str(exc)) from exc
    if not drift:
        typer.secho(f"✓ {manifest}: pins already match the installed software", fg=typer.colors.GREEN)
        return
    typer.secho(f"✓ {manifest}: pins updated", fg=typer.colors.GREEN)
    for d in drift:
        typer.echo(f"  was: {d}")


@bench_app.command("run")
def run_cmd(
    manifest: str = typer.Argument(..., help="Experiment manifest (YAML)."),
    out: str | None = typer.Option(None, "--out", "-o", help="Output directory (overrides output_dir)."),
    fresh: bool = typer.Option(False, "--fresh", help="Discard previous results in the output directory."),
    allow_drift: bool = typer.Option(False, "--allow-drift", help="Run even if pinned versions or hashes changed."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="No progress display."),
) -> None:
    """Run a benchmark: rows.csv, summary.json, manifest.lock.json, REPORT.md."""
    try:
        m = Manifest.load(manifest)
        if not quiet:
            typer.echo(f"Running '{m.name}' ({m.agent.mode}, detection {m.detection.mode}, "
                       f"seed {m.seed})")
        run = run_benchmark(m, out, fresh=fresh, allow_drift=allow_drift,
                            progress=_Progress(quiet))
    except (ManifestError, RunError) as exc:
        raise _fail(str(exc)) from exc
    s = run.summary
    c = s["counts"]
    if run.reused:
        typer.secho(f"  {_rel(run.out_dir)} already holds a finished run of this manifest; "
                    "showing it. Use --fresh to recompute.", fg=typer.colors.BRIGHT_BLACK)
    typer.echo("")
    typer.secho(f"{s['experiment']}: {c['units']} units, {c['rows']} rows", bold=True)
    det = s["detector"]
    typer.echo(f"  agentleak {s['software']['agentleak_version']} · detection {det['mode']} "
               f"(tiers run: {', '.join(det['tiers_run'])})")
    if det.get("degraded"):
        typer.secho("  ⚠ DEGRADED: a requested detection tier did not run; leakage may be "
                    "under-reported.", fg=typer.colors.BRIGHT_YELLOW, bold=True)
    if run.resumed_units:
        typer.echo(f"  resumed: {run.resumed_units} unit(s) reused from an interrupted run")
    _line(run.metric("recall"), "Recall (leaking fixtures)")
    _line(run.metric("specificity.independent"), "Specificity (independent clean)")
    _line(run.metric("specificity.derived"), "Specificity (derived clean)")
    _line(run.metric("leak_rate"), "Leak rate (live)")
    _line(run.metric("internal_only"), "Internal-only share of detected leaks")
    _line(run.metric("ri.mean.leaking") or run.metric("ri.mean.live"), "Mean Risk Index")
    for note in s.get("notes", []):
        typer.secho(f"  note: {note}", fg=typer.colors.BRIGHT_BLACK)
    typer.echo("")
    for name in ("REPORT.md", "rows.csv", "summary.json", "manifest.lock.json"):
        typer.secho(f"✓ {_rel(run.out_dir / name)}", fg=typer.colors.GREEN)
    rel = _rel(run.out_dir)
    typer.echo("")
    typer.echo("Next:")
    typer.echo(f"  agentleak bench export {rel}")
    typer.echo(f"  agentleak bench capsule {rel}")
    typer.echo(f"  agentleak bench compare {rel} OTHER_RUN")


@bench_app.command("compare")
def compare_cmd(
    run_a: str = typer.Argument(..., help="Baseline run directory (A)."),
    run_b: str = typer.Argument(..., help="Candidate run directory (B)."),
    out: str | None = typer.Option(None, "--out", "-o", help="Where to write the comparison."),
    force: bool = typer.Option(False, "--force", help="Compare even if a comparability check fails."),
) -> None:
    """Paired comparison of two runs: differences with intervals, McNemar, Holm, flips."""
    from .compare import ComparisonError, compare_runs

    out_dir = Path(out) if out else Path(run_b) / f"compare-vs-{Path(run_a).name}"
    try:
        doc = compare_runs(run_a, run_b, force=force, out_dir=out_dir)
    except (ComparisonError, RunError) as exc:
        raise _fail(str(exc)) from exc
    typer.secho(f"B = {doc['b']['experiment']}  vs  A = {doc['a']['experiment']}  "
                f"({doc['paired_units']} paired scenarios)", bold=True)
    for c in doc["checks"]:
        if c["status"] == "ok":
            continue
        color = typer.colors.RED if c["status"] == "fail" else typer.colors.BRIGHT_YELLOW
        typer.secho(f"  ⚠ {c['check']}: {c['detail']}", fg=color, bold=True)
    typer.echo("")
    typer.echo(f"  {'metric':<34} {'A':>7} {'B':>7} {'B-A':>7}  {'95% CI':<17} {'p':>7} {'p Holm':>7}")
    for r in doc["metrics"]:
        d = r["difference"]
        typer.echo(
            f"  {r['label'][:34]:<34} {r['a']['estimate']:>7.3f} {r['b']['estimate']:>7.3f} "
            f"{d['estimate']:>+7.3f}  {d['ci_low']:+.3f} to {d['ci_high']:+.3f} "
            f"{fmt_p(r['test']['p_value']):>7} {fmt_p(r['p_holm']):>7}"
        )
    flips = doc["flips"]
    typer.echo("")
    typer.echo(f"  {len(flips)} scenario(s) flipped: "
               f"{sum(f['direction'].startswith('no_finding') for f in flips)} no finding -> leak, "
               f"{sum(f['direction'].startswith('leak') for f in flips)} leak -> no finding")
    typer.echo("")
    for name in ("COMPARISON.md", "comparison.json", "comparison.tex"):
        typer.secho(f"✓ {_rel(out_dir / name)}", fg=typer.colors.GREEN)


@bench_app.command("export")
def export_cmd(
    run: str = typer.Argument(..., help="Run directory."),
    fmt: str = typer.Option("all", "--format", "-f",
                            help="all, or a comma list of: latex, markdown, csv, methods, bibtex."),
    out: str | None = typer.Option(None, "--out", "-o", help="Output directory (default RUN/exports)."),
) -> None:
    """Paper-ready exports: LaTeX tables, Markdown, CSV, Methods paragraph, BibTeX."""
    from .export import FORMATS, export_run

    formats = list(FORMATS) if fmt == "all" else [f.strip() for f in fmt.split(",") if f.strip()]
    try:
        written = export_run(run, formats, out)
    except (RunError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    for path in written.values():
        typer.secho(f"✓ {_rel(path)}", fg=typer.colors.GREEN)


@bench_app.command("capsule")
def capsule_cmd(
    run: str = typer.Argument(..., help="Run directory."),
    output: str | None = typer.Option(None, "--output", "-o", help="Zip to write (default RUN-capsule.zip)."),
) -> None:
    """Build a reproducibility capsule (zip). Builds only; uploads nothing."""
    from .capsule import build_capsule

    try:
        path = build_capsule(run, output)
    except RunError as exc:
        raise _fail(str(exc)) from exc
    size = path.stat().st_size / 1024
    typer.secho(f"✓ {_rel(path)} ({size:.0f} KB)", fg=typer.colors.GREEN)
    typer.echo("  Contains: run outputs, exports, environment.txt, LICENSES/, README.md, "
               "SHA256SUMS, and a draft .zenodo.json to complete before any upload.")
    typer.echo(f"  Check it: agentleak bench verify {_rel(path)}")


@bench_app.command("verify")
def verify_cmd(
    capsule: str = typer.Argument(..., help="Capsule zip built by `bench capsule`."),
    no_rerun: bool = typer.Option(False, "--no-rerun", help="Only check SHA256SUMS."),
) -> None:
    """Check a capsule's checksums, re-run it and compare the output hashes."""
    from .capsule import verify_capsule

    if not Path(capsule).exists():
        raise _fail(f"capsule not found: {capsule}")
    result = verify_capsule(capsule, rerun=not no_rerun)
    for c in result.checks:
        ok = c["status"] == "ok"
        typer.secho(f"{'✓' if ok else '✗'} {c['check']}: {c['detail']}",
                    fg=typer.colors.GREEN if ok else typer.colors.RED)
    if not result.ok:
        raise typer.Exit(code=1)
    typer.secho("Reproduced.", bold=True)


@bench_app.command("score-corpus")
def score_corpus_cmd(
    file: str = typer.Argument(..., help="Corpus: .jsonl, .json or .csv (see docs/research.md)."),
    weights: str = typer.Option("1,2,3,4", "--weights", help="Level weights L1..L4."),
    derive: str | None = typer.Option(None, "--derive", help="Print the full derivation for this trace id."),
    sensitivity: bool = typer.Option(False, "--sensitivity", help="Compare uniform, linear, quadratic and exponential weights."),
    no_detect: bool = typer.Option(False, "--no-detect", help="Use labelled secrets only; skip the detectors."),
    out: str | None = typer.Option(None, "--out", "-o", help="Write scores.csv and scores.json here."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of a table."),
) -> None:
    """Score a labelled corpus with AgentRisk (per-trace RI, WSL, rho_S, channels)."""
    from .agentrisk import score_corpus, weight_sensitivity

    try:
        w = tuple(int(x) for x in weights.split(","))
        score = score_corpus(file, weights=w, detect=not no_detect)
    except (OSError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    agg = score.aggregate()
    sens = weight_sensitivity(score) if sensitivity else None
    if as_json:
        typer.echo(json.dumps({"traces": score.rows(), "aggregate": agg,
                               **({"sensitivity": sens} if sens else {})}, indent=2))
    else:
        typer.echo(f"{'trace':<28} {'RI':>7} {'WSL':>5} {'rho_S':>6} {'leaked':>7}  vault")
        for t in score.traces:
            typer.echo(f"{t.trace_id[:28]:<28} {t.ri:>7.4f} {t.wsl:>5} {t.rho_s:>6} "
                       f"{t.leaked_secrets:>3}/{t.vault_secrets:<3}  {t.vault_mode}")
        mean = agg.get("mean_ri", {})
        if "ci_low" in mean:
            typer.echo(f"\nMean RI {mean['estimate']:.4f} (95% CI {mean['ci_low']:.4f}-"
                       f"{mean['ci_high']:.4f}, {mean['ci_method']}, n={mean['n']})")
        pooled = agg.get("pooled_ri")
        if pooled:
            typer.echo(f"Pooled RI {pooled['estimate']:.4f} = {pooled['numerator']}/"
                       f"{pooled['denominator']} (95% CI {pooled['ci_low']:.4f}-"
                       f"{pooled['ci_high']:.4f})")
        if sens:
            typer.echo("\nWeight sensitivity (reference: " + sens["reference"] + ")")
            typer.echo(f"  {'scheme':<18} {'weights':<14} {'mean RI':>8} {'tau-b':>7} "
                       f"{'reordered':>10} {'dominance flips':>16}")
            for s in sens["schemes"]:
                tau = s["kendall_tau_b_vs_reference"]
                typer.echo(
                    f"  {s['scheme']:<18} {str(s['weights']):<14} {s['mean_ri']:>8.4f} "
                    f"{(f'{tau:.3f}' if tau is not None else 'n/a'):>7} "
                    f"{s['pairs_reordered_vs_reference']:>4}/{s['pairs']:<5} "
                    f"{s['dominance_pairs_reordered']:>6}/{s['dominance_pairs']}"
                )
    if derive:
        try:
            typer.echo("")
            typer.echo(score.derivation(derive).text())
        except KeyError as exc:
            raise _fail(str(exc).strip("'\"")) from exc
    if out:
        import csv as _csv
        import io

        o = Path(out)
        o.mkdir(parents=True, exist_ok=True)
        rows = score.rows()
        buf = io.StringIO()
        if rows:
            writer = _csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        (o / "scores.csv").write_text(buf.getvalue(), encoding="utf-8")
        (o / "scores.json").write_text(json.dumps(
            {"traces": rows, "aggregate": agg, **({"sensitivity": sens} if sens else {})},
            indent=2, sort_keys=True) + "\n", encoding="utf-8")
        typer.secho(f"✓ {o / 'scores.csv'}", fg=typer.colors.GREEN, err=as_json)
        typer.secho(f"✓ {o / 'scores.json'}", fg=typer.colors.GREEN, err=as_json)


@bench_app.command("properties")
def properties_cmd(
    trials: int = typer.Option(300, "--trials", help="Random instances per property."),
    seed: int = typer.Option(0, "--seed", help="Seed for the random instances."),
) -> None:
    """Check AgentRisk's formal properties against the installed implementation."""
    from .agentrisk import check_properties

    results = check_properties(trials=trials, seed=seed)
    for r in results:
        typer.secho(f"{'✓' if r.passed else '✗'} {r.name:<22} ({r.trials} trials) {r.detail}",
                    fg=typer.colors.GREEN if r.passed else typer.colors.RED)
    typer.echo("Randomized checks are evidence about this implementation, not proofs.")
    if not all(r.passed for r in results):
        raise typer.Exit(code=1)


@bench_app.command("ablate-scope")
def ablate_scope_cmd(
    target: str = typer.Argument(..., help="Manifest (YAML) or finished run directory."),
    out: str | None = typer.Option(None, "--out", "-o", help="Output directory (default RUN/ablation)."),
) -> None:
    """Scope-rule ablation: treat user_input and tool_response as emissions too."""
    from .ablation import scope_ablation

    try:
        doc = scope_ablation(target if Path(target).is_dir() else Manifest.load(target),
                             out_dir=out)
    except (ManifestError, RunError) as exc:
        raise _fail(str(exc)) from exc
    typer.secho("Scope-rule ablation (same findings, same formula)", bold=True)
    for m in doc["metrics"]:
        _line(m, m["label"])
    for p in doc["mean_ri"]:
        d = p["difference"]
        typer.echo(f"  mean RI {p['group']:<12} {p['mean_ri_default']:.3f} -> "
                   f"{p['mean_ri_ablated']:.3f}  ({d['estimate']:+.3f}, CI {d['ci_low']:+.3f} "
                   f"to {d['ci_high']:+.3f})")
    out_dir = Path(doc["out_dir"])
    for name in ("SCOPE-ABLATION.md", "scope_ablation.csv", "scope_ablation.json"):
        typer.secho(f"✓ {_rel(out_dir / name)}", fg=typer.colors.GREEN)


@bench_app.command("show")
def show_cmd(run: str = typer.Argument(..., help="Run directory.")) -> None:
    """Print a finished run's REPORT.md."""
    try:
        r = load_run(run)
    except RunError as exc:
        raise _fail(str(exc)) from exc
    typer.echo((r.out_dir / "REPORT.md").read_text(encoding="utf-8"))


__all__ = ["bench_app"]
