# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Reproducibility capsules: one zip that holds a run and how to redo it.

``build_capsule`` packs a finished run with its exports, an environment
freeze, the licences of every data source used, a README stating the one
command that reproduces it, a draft ``.zenodo.json`` for the researcher to
complete, and a ``SHA256SUMS`` file. Nothing is uploaded anywhere.

``verify_capsule`` checks the checksums, re-runs the capsule's manifest in a
temporary directory and compares the new ``rows.csv`` and ``summary.json``
(timestamp blanked) with the archived ones.

The zip itself is deterministic: entries are sorted and carry a fixed
timestamp, so the same run always gives the same capsule bytes.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from .bench import BenchRun, dump_json, load_run, run_benchmark, summary_digest
from .citation import load_citation
from .export import export_run, methods_paragraph
from .manifest import Manifest, freeze

_FIXED_TIME = (1980, 1, 1, 0, 0, 0)
_RUN_FILES = ("manifest.yaml", "manifest.lock.json", "rows.csv", "summary.json", "REPORT.md")
_LICENSE_FILES = {"MIT": "MIT.txt", "CC-BY-4.0": "CC-BY-4.0.txt"}


def _license_text(spdx: str) -> str | None:
    """The licence text, from the installed wheel or the source checkout."""
    name = _LICENSE_FILES.get(spdx)
    if not name:
        return None
    try:
        res = resources.files("agentleak").joinpath("licenses").joinpath(name)
        if res.is_file():
            return res.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        pass
    repo = Path(__file__).resolve().parents[3] / "LICENSES" / name
    return repo.read_text(encoding="utf-8") if repo.exists() else None


def _notice_text() -> str | None:
    try:
        res = resources.files("agentleak.scenarios.packs").joinpath("NOTICE.md")
        return res.read_text(encoding="utf-8") if res.is_file() else None
    except FileNotFoundError:
        return None


def _readme(run: BenchRun) -> str:
    s = run.summary
    sources = "\n".join(
        f"- `{p['source']}`: {p.get('name', '')}, licence {p.get('license') or 'not stated'}, "
        f"sha256 `{p['sha256']}`" + (f", {p['source_url']}" if p.get("source_url") else "")
        for p in run.lock.get("sources", [])
    )
    version = s.get("software", {}).get("agentleak_version", "?")
    git = run.lock.get("environment", {}).get("git") or {}
    cff, _ = load_citation()
    source_install = ""
    if git.get("commit") and cff.get("repository-code"):
        source_install = (
            "\n# or the exact source commit the run used"
            + (" (it had uncommitted changes)" if git.get("dirty") else "")
            + f":\npip install \"git+{cff['repository-code']}@{git['commit']}\""
        )
    return f"""\
# {s.get('experiment')}: reproducibility capsule

Produced by AgentLeak {version} (`agentleak bench capsule`). Everything needed
to check or redo this benchmark is in this archive.

## Reproduce

```bash
pip install "agentleak=={version}"{source_install}
agentleak bench verify capsule.zip     # checksums + re-run + hash comparison
```

or by hand, from the unzipped folder:

```bash
agentleak bench run run/manifest.yaml --out replay
```

`replay/rows.csv` must be byte-identical to `run/rows.csv`, and
`replay/summary.json` identical to `run/summary.json` except `generated_at`.

## Contents

- `run/`: the run as written (`rows.csv` row-level results, `summary.json`
  metrics with numerators, denominators and intervals, `manifest.yaml`,
  `manifest.lock.json` with environment and hashes, `REPORT.md`).
- `run/exports/`: LaTeX and Markdown tables, metric CSVs, a Methods
  paragraph, BibTeX.
- `environment.txt`: every installed Python distribution at build time.
- `LICENSES/`: licence texts of the software and of each data source.
- `.zenodo.json`: a **draft** metadata file. Fill in creators, licence and
  description before any upload; nothing has been uploaded.
- `SHA256SUMS`: checksums of every other file (`sha256sum -c SHA256SUMS`).

## Data sources

{sources}

## Limitations

Labels are defined by construction of the fixtures; derived clean
counterparts are generated, not observed. A unit with no finding means no
finding from the enabled detectors, not that it is safe. See `run/REPORT.md`.
"""


def _zenodo_draft(run: BenchRun) -> dict[str, Any]:
    cff, _ = load_citation()
    licences = sorted({p.get("license") for p in run.lock.get("sources", []) if p.get("license")})
    related = []
    doi = (cff.get("preferred-citation") or {}).get("doi")
    if doi:
        related.append({"identifier": doi, "relation": "references",
                        "resource_type": "publication-article"})
    if cff.get("repository-code"):
        related.append({"identifier": cff["repository-code"], "relation": "isDerivedFrom",
                        "resource_type": "software"})
    for p in run.lock.get("sources", []):
        if p.get("source_url"):
            related.append({"identifier": p["source_url"], "relation": "isDerivedFrom",
                            "resource_type": "dataset"})
    return {
        "_comment": "DRAFT generated by agentleak bench capsule. Review every field; "
                    "replace FILL-IN values. Nothing has been uploaded.",
        "title": f"{run.summary.get('experiment')}: AgentLeak benchmark capsule",
        "upload_type": "dataset",
        "description": methods_paragraph(run).strip(),
        "creators": [{"name": "FILL-IN, Family name, Given name", "affiliation": "FILL-IN"}],
        "license": "FILL-IN (data sources in this capsule are licensed: "
                   + ", ".join(licences) + ")",
        "keywords": ["privacy", "AI agents", "data leakage", "AgentLeak", "benchmark"],
        "related_identifiers": related,
        "notes": f"Generated with agentleak {run.summary.get('software', {}).get('agentleak_version')}.",
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_capsule(run: BenchRun | str | Path, output: str | Path | None = None) -> Path:
    """Build the capsule zip for a finished run and return its path."""
    r = run if isinstance(run, BenchRun) else load_run(run)
    out_path = Path(output) if output else r.out_dir.with_name(f"{r.out_dir.name}-capsule.zip")
    exports = export_run(r)

    files: dict[str, bytes] = {}
    for name in _RUN_FILES:
        path = r.out_dir / name
        if path.exists():
            files[f"run/{name}"] = path.read_bytes()
    for name, path in sorted(exports.items()):
        files[f"run/exports/{name}"] = path.read_bytes()
    traces = r.out_dir / "traces"
    if traces.is_dir():
        for path in sorted(traces.glob("*.json")):
            files[f"run/traces/{path.name}"] = path.read_bytes()
    files["environment.txt"] = freeze().encode("utf-8")
    licences = {"MIT"} | {p.get("license") or "" for p in r.lock.get("sources", [])}
    missing = []
    for spdx in sorted(x for x in licences if x):
        text = _license_text(spdx)
        if text is None:
            missing.append(spdx)
        else:
            files[f"LICENSES/{_LICENSE_FILES[spdx]}"] = text.encode("utf-8")
    notice = _notice_text()
    if notice:
        files["LICENSES/NOTICE-scenario-packs.md"] = notice.encode("utf-8")
    if missing:
        files["LICENSES/MISSING.txt"] = (
            "No licence text available in this installation for: " + ", ".join(missing) + "\n"
        ).encode("utf-8")
    cff = Path(__file__).resolve().parents[3] / "CITATION.cff"
    if cff.exists():
        files["CITATION.cff"] = cff.read_bytes()
    files["README.md"] = _readme(r).encode("utf-8")
    files[".zenodo.json"] = dump_json(_zenodo_draft(r)).encode("utf-8")
    sums = "".join(f"{_sha256(data)}  {name}\n" for name, data in sorted(files.items()))
    files["SHA256SUMS"] = sums.encode("utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, files[name])
    return out_path


@dataclass
class VerifyResult:
    """Outcome of :func:`verify_capsule`. ``ok`` is True only if every check passed."""

    ok: bool
    checks: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checks": self.checks}


def verify_capsule(path: str | Path, *, rerun: bool = True) -> VerifyResult:
    """Check a capsule's checksums and, with ``rerun``, reproduce the run."""
    checks: list[dict[str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "ok" if ok else "fail", "detail": detail})

    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "SHA256SUMS" not in names:
            add("checksums", False, "SHA256SUMS is missing")
            return VerifyResult(False, checks)
        bad = []
        listed = 0
        for line in zf.read("SHA256SUMS").decode("utf-8").splitlines():
            if not line.strip():
                continue
            digest, name = line.split("  ", 1)
            listed += 1
            if name not in names or _sha256(zf.read(name)) != digest:
                bad.append(name)
        add("checksums", not bad,
            f"{listed} files match SHA256SUMS" if not bad else f"mismatch: {', '.join(bad)}")
        if not rerun:
            return VerifyResult(all(c["status"] == "ok" for c in checks), checks)
        lock = json.loads(zf.read("run/manifest.lock.json"))
        archived_rows = zf.read("run/rows.csv")
        archived_summary = json.loads(zf.read("run/summary.json"))
        traces = {n: zf.read(n) for n in names if n.startswith("run/traces/")}

    manifest = Manifest.from_dict(lock["manifest"], where="capsule manifest")
    drift = manifest.check_pins()
    add("software", not drift,
        "installed software matches the capsule's pins" if not drift else "; ".join(drift))
    with tempfile.TemporaryDirectory(prefix="agentleak-verify-") as tmp:
        traces_from = None
        if manifest.agent.mode == "live":
            # Re-analyze the archived traces; calling the model again would not
            # reproduce them.
            traces_from = Path(tmp) / "traces"
            traces_from.mkdir()
            for name, data in traces.items():
                (traces_from / Path(name).name).write_bytes(data)
        replay = run_benchmark(manifest, Path(tmp) / "replay", allow_drift=True,
                               traces_from=traces_from)
        rows_now = (replay.out_dir / "rows.csv").read_bytes()
        same_rows = rows_now == archived_rows
        add("rows.csv", same_rows,
            f"byte-identical (sha256 {_sha256(rows_now)[:16]})" if same_rows else
            f"differs: archived {_sha256(archived_rows)[:16]}, re-run {_sha256(rows_now)[:16]}")
        a, b = summary_digest(archived_summary), summary_digest(replay.summary)
        add("summary.json", a == b,
            "identical apart from generated_at" if a == b else
            f"differs: archived {a[:16]}, re-run {b[:16]}")
    return VerifyResult(all(c["status"] == "ok" for c in checks), checks)


__all__ = ["VerifyResult", "build_capsule", "verify_capsule"]
