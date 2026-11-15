# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Experiment manifests: one YAML file that says exactly what a benchmark runs.

A manifest names the scenarios, the detector configuration, the seed and the
output directory, and pins the software version and the SHA-256 of every
scenario source it uses. ``agentleak bench init`` writes a commented one with
the pins filled in for the installed version; ``agentleak bench run`` refuses
to start when a pin no longer matches, so a result cannot silently change
because a pack or the analyzer did.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml

from .. import __version__
from .corpus import available_sources, source_provenance

SCHEMA = "agentleak.bench/1"

_DETECTION_MODES = ("fast", "standard", "hybrid")
_AGENT_MODES = ("replay", "live")
_INTERVALS = ("wilson", "clopper-pearson")
_LABELS = ("leaking", "clean")
_FAILURE_MODES = ("pattern", "norm", "hijack")


class ManifestError(ValueError):
    """A manifest that cannot be run as written. The message says how to fix it."""


@dataclass
class ScenarioSelection:
    sources: list[str] = field(default_factory=lambda: available_sources())
    domains: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=lambda: list(_LABELS))
    ids: list[str] = field(default_factory=list)
    max_per_source: int | None = None
    counterparts: str = "derived"


@dataclass
class DetectionSettings:
    mode: str = "fast"
    #: ``"all"`` runs every built-in detector (what ``agentleak run`` does
    #: without a config); a mapping toggles detectors individually.
    detectors: str | dict[str, bool] = "all"
    obscured_copies: bool = True
    presidio: dict[str, Any] = field(default_factory=dict)
    llm_judge: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSettings:
    mode: str = "replay"
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""
    temperature: float = 0.0
    max_steps: int = 8


@dataclass
class StatisticsSettings:
    confidence: float = 0.95
    interval: str = "wilson"
    bootstrap_resamples: int = 2000


@dataclass
class Manifest:
    """A parsed, validated experiment manifest."""

    name: str = "agentleak-benchmark"
    description: str = ""
    seed: int = 20261114
    repetitions: int = 1
    scenarios: ScenarioSelection = field(default_factory=ScenarioSelection)
    detection: DetectionSettings = field(default_factory=DetectionSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    statistics: StatisticsSettings = field(default_factory=StatisticsSettings)
    output_dir: str = ""
    pins: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA
    #: Directory a relative ``output_dir`` is resolved against: the manifest
    #: file's folder when loaded from a file. Not part of the manifest itself.
    base_dir: str = ""

    # -- construction ----------------------------------------------------
    @classmethod
    def load(cls, path: str | Path) -> Manifest:
        p = Path(path)
        if not p.exists():
            raise ManifestError(
                f"manifest not found: {p}. Create one with `agentleak bench init {p}`."
            )
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ManifestError(f"{p} is not valid YAML: {exc}") from exc
        m = cls.from_dict(data, where=str(p))
        m.base_dir = str(p.resolve().parent)
        return m

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, where: str = "manifest") -> Manifest:
        if not isinstance(data, dict):
            raise ManifestError(f"{where}: top level must be a mapping")
        _reject_unknown(data, cls, where)
        m = cls()
        for key in ("name", "description", "output_dir", "schema"):
            if key in data and data[key] is not None:
                setattr(m, key, str(data[key]))
        if "seed" in data:
            m.seed = _int(data["seed"], "seed", where)
        if "repetitions" in data:
            m.repetitions = _int(data["repetitions"], "repetitions", where)
        m.scenarios = _section(data.get("scenarios"), ScenarioSelection, f"{where}: scenarios")
        m.detection = _section(data.get("detection"), DetectionSettings, f"{where}: detection")
        m.agent = _section(data.get("agent"), AgentSettings, f"{where}: agent")
        m.statistics = _section(data.get("statistics"), StatisticsSettings, f"{where}: statistics")
        m.pins = dict(data.get("pins") or {})
        m.validate(where)
        return m

    def validate(self, where: str = "manifest") -> None:
        if self.schema != SCHEMA:
            raise ManifestError(f"{where}: schema must be '{SCHEMA}', got '{self.schema}'")
        if not self.name.strip():
            raise ManifestError(f"{where}: name must not be empty")
        if self.repetitions < 1:
            raise ManifestError(f"{where}: repetitions must be >= 1")
        if self.agent.mode not in _AGENT_MODES:
            raise ManifestError(f"{where}: agent.mode must be one of {_AGENT_MODES}")
        if self.agent.mode == "replay" and self.repetitions != 1:
            raise ManifestError(
                f"{where}: repetitions is {self.repetitions}, but replay mode re-analyzes "
                "fixed traces and gives identical results every time. Set repetitions: 1, "
                "or use agent.mode: live to sample a model several times."
            )
        if self.agent.mode == "live" and not self.agent.model:
            raise ManifestError(f"{where}: agent.mode is live but agent.model is empty")
        if self.detection.mode not in _DETECTION_MODES:
            raise ManifestError(f"{where}: detection.mode must be one of {_DETECTION_MODES}")
        dets = self.detection.detectors
        if isinstance(dets, str) and dets != "all":
            raise ManifestError(f"{where}: detection.detectors must be 'all' or a mapping")
        if self.statistics.interval not in _INTERVALS:
            raise ManifestError(f"{where}: statistics.interval must be one of {_INTERVALS}")
        if not 0.5 <= self.statistics.confidence < 1.0:
            raise ManifestError(f"{where}: statistics.confidence must be in [0.5, 1)")
        if self.statistics.bootstrap_resamples < 200:
            raise ManifestError(f"{where}: statistics.bootstrap_resamples must be >= 200")
        sel = self.scenarios
        if not sel.sources:
            raise ManifestError(f"{where}: scenarios.sources is empty")
        unknown = [s for s in sel.sources if s not in available_sources()]
        if unknown:
            raise ManifestError(
                f"{where}: unknown scenario source(s) {unknown}. "
                f"Available: {', '.join(available_sources())}"
            )
        bad = [lab for lab in sel.labels if lab not in _LABELS]
        if bad:
            raise ManifestError(f"{where}: scenarios.labels may only contain {_LABELS}")
        bad = [f for f in sel.failure_modes if f not in _FAILURE_MODES]
        if bad:
            raise ManifestError(f"{where}: scenarios.failure_modes may only contain {_FAILURE_MODES}")
        if sel.counterparts not in ("derived", "none"):
            raise ManifestError(f"{where}: scenarios.counterparts must be 'derived' or 'none'")
        if sel.max_per_source is not None and sel.max_per_source < 1:
            raise ManifestError(f"{where}: scenarios.max_per_source must be >= 1 or null")

    # -- serialization ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        # Keep a stable key order matching the template.
        order = ["schema", "name", "description", "seed", "repetitions", "scenarios",
                 "detection", "agent", "statistics", "output_dir", "pins"]
        return {k: out[k] for k in order}

    def digest(self) -> str:
        """SHA-256 of the resolved manifest (what the run actually used)."""
        blob = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def resolved_output_dir(self) -> str:
        """``output_dir``, relative paths taken from the manifest file's folder."""
        out = Path(self.output_dir or f"runs/{_slug(self.name)}")
        if not out.is_absolute() and self.base_dir:
            out = Path(self.base_dir) / out
        return str(out)

    # -- pins --------------------------------------------------------------
    def current_pins(self) -> dict[str, Any]:
        return {
            "agentleak_version": __version__,
            "sources": {s: source_provenance(s)["sha256"] for s in self.scenarios.sources},
        }

    def check_pins(self) -> list[str]:
        """Differences between the manifest's pins and the installed software."""
        if not self.pins:
            return []
        problems = []
        current = self.current_pins()
        want_version = self.pins.get("agentleak_version")
        if want_version and str(want_version) != current["agentleak_version"]:
            problems.append(
                f"agentleak version is {current['agentleak_version']}, manifest pins {want_version}"
            )
        for source, digest in (self.pins.get("sources") or {}).items():
            have = current["sources"].get(source)
            if have is None:
                continue
            if have != digest:
                problems.append(
                    f"source '{source}' sha256 is {have[:12]}..., manifest pins {str(digest)[:12]}..."
                )
        return problems


def _slug(name: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in name.strip()]
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "benchmark"


def _int(value: Any, key: str, where: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"{where}: {key} must be an integer, got {value!r}") from exc


def _reject_unknown(data: dict[str, Any], cls: type, where: str) -> None:
    allowed = set(cls.__dataclass_fields__) - {"base_dir"}  # type: ignore[attr-defined]
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ManifestError(
            f"{where}: unknown key(s) {unknown}. Allowed: {', '.join(sorted(allowed))}"
        )


def _section(data: Any, cls: type, where: str) -> Any:
    obj = cls()
    if data is None:
        return obj
    if not isinstance(data, dict):
        raise ManifestError(f"{where} must be a mapping")
    _reject_unknown(data, cls, where)
    for key, value in data.items():
        default = getattr(obj, key)
        if value is None:
            if key == "max_per_source":
                setattr(obj, key, None)
            continue
        if isinstance(default, list):
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list):
                raise ManifestError(f"{where}.{key} must be a list")
            value = [str(v) for v in value]
        elif isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int) and not isinstance(default, bool):
            value = _int(value, key, where)
        elif isinstance(default, float):
            value = float(value)
        elif key == "max_per_source":
            value = _int(value, key, where)
        setattr(obj, key, value)
    return obj


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------
def render_template(
    name: str = "my-experiment", *, quick: bool = False, filename: str = "this-file.yaml"
) -> str:
    """The commented YAML that ``agentleak bench init`` writes."""
    m = Manifest(name=name)
    if quick:
        m.scenarios.max_per_source = 10
    pins = m.current_pins()
    sources = "\n".join(f"    - {s}" for s in m.scenarios.sources)
    pin_lines = "\n".join(f"    {s}: {h}" for s, h in pins["sources"].items())
    mps = "null" if m.scenarios.max_per_source is None else str(m.scenarios.max_per_source)
    return f"""\
# AgentLeak experiment manifest. Run it with:  agentleak bench run {filename}
# Every field is documented in docs/research.md. Edit freely; unknown keys are
# rejected so a typo cannot be silently ignored.
schema: {SCHEMA}
name: {name}
description: ""

# Seed for every random step (scenario sampling, bootstrap intervals).
# Same manifest + same seed -> byte-identical rows.csv and summary.json.
seed: {m.seed}

# Replay mode analyzes fixed traces, so it must be 1. Raise it only with
# agent.mode: live, to sample a model several times per scenario.
repetitions: 1

scenarios:
  # builtin = the 10 packaged scenarios (5 leak demos + 5 clean controls);
  # the others are the bundled research packs.
  sources:
{sources}
  domains: []           # e.g. [healthcare, finance]; empty = all
  failure_modes: []     # pattern | norm | hijack; empty = all
  labels: [leaking, clean]
  ids: []               # restrict to these scenario ids; empty = all
  max_per_source: {mps}  # seeded random sample of leaking fixtures per source; null = all
  # derived = also run a compliant counterpart of each pack fixture (the leaking
  # emissions removed). Reported separately from the independent clean controls.
  counterparts: derived

detection:
  mode: fast            # fast (regex + dictionaries) | standard (+ Presidio) | hybrid (+ LLM judge)
  detectors: all        # or a mapping, e.g. {{pii: true, secrets: true, healthcare: true,
                        #   finance: true, hr: true, keyname: false}}
  obscured_copies: true # also catch reversed / rotated / split copies of exposed values
  presidio: {{}}          # passed to detection.presidio (e.g. {{score_threshold: 0.5}})
  llm_judge: {{}}         # passed to detection.llm_judge (base_url, model, api_key_env)

agent:
  # replay = analyze the bundled traces (offline, no key, deterministic).
  # live   = run a model against each scenario (BYOK; set model and base_url).
  mode: replay
  base_url: ""          # e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1
  model: ""
  api_key_env: ""       # name of the environment variable holding the key
  temperature: 0.0
  max_steps: 8

statistics:
  confidence: 0.95
  interval: wilson      # wilson | clopper-pearson
  bootstrap_resamples: 2000

# Where rows.csv, summary.json, manifest.lock.json and REPORT.md are written.
# A relative path is taken from this file's folder.
output_dir: runs/{_slug(name)}

# Written by `agentleak bench init` for the installed version. A run refuses to
# start if they no longer match (pass --allow-drift to run anyway; the drift is
# recorded in manifest.lock.json). Delete this block to disable the check.
pins:
  agentleak_version: "{pins['agentleak_version']}"
  sources:
{pin_lines}
"""


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
_CORE_DEPENDENCIES = ("typer", "pydantic", "PyYAML", "Jinja2")
_OPTIONAL_DEPENDENCIES = ("presidio-analyzer", "spacy", "fastapi", "mcp", "cryptography")


def _dist_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def git_commit() -> dict[str, Any]:
    """The commit of the AgentLeak checkout, when installed from one."""
    root = Path(__file__).resolve().parents[3]
    if not (root / ".git").exists():
        return {"commit": None, "dirty": None, "note": "not installed from a git checkout"}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            timeout=5, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root,
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None, "note": "git not available"}
    return {"commit": commit, "dirty": bool(status)}


def environment() -> dict[str, Any]:
    """Software and platform facts recorded in ``manifest.lock.json``."""
    deps = {name: _dist_version(name) for name in _CORE_DEPENDENCIES}
    optional = {
        name: version
        for name in _OPTIONAL_DEPENDENCIES
        if (version := _dist_version(name)) is not None
    }
    return {
        "agentleak_version": __version__,
        "git": git_commit(),
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "dependencies": deps,
        "optional_dependencies_installed": optional,
    }


def freeze() -> str:
    """``name==version`` for every installed distribution, sorted (like pip freeze)."""
    lines = set()
    for dist in metadata.distributions():
        name = dist.metadata["Name"] if "Name" in dist.metadata else None
        if name:
            lines.add(f"{name}=={dist.version}")
    return "\n".join(sorted(lines, key=str.lower)) + "\n"


__all__ = [
    "SCHEMA",
    "AgentSettings",
    "DetectionSettings",
    "Manifest",
    "ManifestError",
    "ScenarioSelection",
    "StatisticsSettings",
    "environment",
    "freeze",
    "git_commit",
    "render_template",
]
