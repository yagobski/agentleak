# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The benchmark corpus: which fixtures exist, how they are labelled, and how
clean counterparts are derived.

A *unit* is one trace the benchmark analyzes. Every unit carries a label that
is defined **by construction**, never by the detectors under test:

* ``leaking`` — a bundled fixture built to disclose sensitive data (the
  built-in leak demos and every pack scenario).
* ``clean`` / ``independent`` — a hand-authored clean control that ships with
  the package (the five built-in ``*_clean_*`` scenarios).
* ``clean`` / ``derived`` — a compliant counterpart generated here from a
  leaking pack fixture: every disclosure-channel event that carries one of the
  fixture's ground-truth values is removed, as if the agent had not emitted it.

Independent and derived negatives answer different questions and are never
pooled; every report lists both denominators.

Ground truth per source
-----------------------
* ``privacylens_ci`` / ``agentdojo_exfil`` — the pack's canaries (the exact
  facts or values that must not travel).
* ``agentleak_bench`` — every field value in the scenario's ``private_vault``
  (string form, at least four characters).
* ``builtin`` — none recorded; built-ins are paired with their independent
  clean controls instead and get no derived counterpart.

Matching a ground-truth value is an exact, case-sensitive substring test on
the event's searchable text, the same rule AgentLeak uses for canaries.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from ..core.agentrisk import BASELINE_CHANNELS
from ..core.trace import Trace
from ..scenarios import list_scenarios, load_example_trace
from ..scenarios.packs import expand_pack, list_packs, load_pack

#: Disclosure channels, in the fixed order used for every row-level output.
DISCLOSURE_CHANNELS: tuple[str, ...] = (
    "tool_call",
    "shared_memory",
    "inter_agent_message",
    "log",
    "generated_file",
    "final_output",
)

#: Which leak mechanism each source exercises. An editorial classification of
#: the corpus (also used by ``scripts/build_benchmark.py``), not pack metadata.
FAILURE_MODES: dict[str, str] = {
    "builtin": "pattern",
    "agentleak_bench": "pattern",
    "privacylens_ci": "norm",
    "agentdojo_exfil": "hijack",
}

BUILTIN_SOURCE = "builtin"
_MIN_GT_LEN = 4


@dataclass
class Unit:
    """One trace to analyze, with its construction-time label."""

    unit_id: str
    source: str
    origin_id: str
    domain: str
    failure_mode: str
    adversary: str
    label: str  # "leaking" | "clean"
    negative_kind: str  # "" | "independent" | "derived"
    counterpart_of: str
    trace: Trace
    ground_truth: list[str] = field(default_factory=list)
    spec: dict[str, Any] | None = None
    description: str = ""

    def reference_channels(self, trace: Trace | None = None) -> set[str]:
        """Disclosure channels on which a ground-truth value appears verbatim."""
        if not self.ground_truth:
            return set()
        hit: set[str] = set()
        for event in (trace or self.trace).events:
            channel = event.channel_value
            if channel in BASELINE_CHANNELS or channel in hit:
                continue
            text = event.searchable_text
            if any(value in text for value in self.ground_truth):
                hit.add(channel)
        return hit


def trace_digest(trace: Trace) -> str:
    """SHA-256 of a trace's content, ignoring wall-clock timestamps.

    Timestamps are filled with "now" when a fixture is converted, so they are
    excluded; everything that the detectors read is included.
    """
    events = [
        {
            "channel": e.channel_value,
            "source": e.source,
            "target": e.target,
            "content": e.content,
            "metadata": e.metadata,
        }
        for e in trace.events
    ]
    blob = json.dumps(events, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _scalar_values(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for value in obj.values():
            out.extend(_scalar_values(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(_scalar_values(value))
    elif obj is not None and not isinstance(obj, bool):
        text = str(obj).strip()
        if len(text) >= _MIN_GT_LEN:
            out.append(text)
    return out


def _ground_truth(meta: dict[str, Any]) -> list[str]:
    values: set[str] = set()
    canaries = meta.get("canaries") or {}
    if isinstance(canaries, dict):
        for tier in ("obvious", "realistic", "semantic"):
            values.update(str(v) for v in canaries.get(tier) or [] if str(v).strip())
    spec = meta.get("spec") or {}
    for record in (spec.get("private_vault") or {}).get("records", []) or []:
        values.update(_scalar_values(record.get("fields") or {}))
    # Longest first so reports list the most specific value first.
    return sorted(values, key=lambda v: (-len(v), v))


def derive_counterpart(unit: Unit) -> Unit | None:
    """The compliant counterpart of a leaking unit, or ``None`` without ground truth.

    Every disclosure-channel event whose text contains a ground-truth value is
    dropped; baseline events (``user_input``, ``tool_response``) are kept, so
    the sensitive data still enters the run and the vault is unchanged.
    """
    if unit.label != "leaking" or not unit.ground_truth:
        return None
    data = unit.trace.to_dict()
    kept = []
    for raw, event in zip(data["events"], unit.trace.events, strict=True):
        if event.channel_value not in BASELINE_CHANNELS and any(
            value in event.searchable_text for value in unit.ground_truth
        ):
            continue
        kept.append(raw)
    data["events"] = kept
    data["run_id"] = f"{data.get('run_id') or unit.origin_id}__derived_clean"
    return Unit(
        unit_id=f"{unit.unit_id}#derived-clean",
        source=unit.source,
        origin_id=unit.origin_id,
        domain=unit.domain,
        failure_mode=unit.failure_mode,
        adversary=unit.adversary,
        label="clean",
        negative_kind="derived",
        counterpart_of=unit.unit_id,
        trace=Trace.from_dict(data),
        ground_truth=list(unit.ground_truth),
        spec=None,
        description=f"Derived compliant counterpart of {unit.unit_id}.",
    )


def _adversary(tags: list[str]) -> str:
    for tag in tags:
        if isinstance(tag, str) and tag.startswith("adversary:"):
            return tag.split(":", 1)[1]
    return ""


def builtin_units() -> list[Unit]:
    """The packaged scenarios: leak demos and their independent clean controls."""
    scenarios = [s for s in list_scenarios() if s.example_trace]
    leak_by_domain = {s.domain: s.id for s in scenarios if s.expected_outcome == "leak"}
    units = []
    for s in scenarios:
        clean = s.expected_outcome == "clean"
        units.append(Unit(
            unit_id=f"{BUILTIN_SOURCE}/{s.id}",
            source=BUILTIN_SOURCE,
            origin_id=s.id,
            domain=s.domain,
            failure_mode=FAILURE_MODES[BUILTIN_SOURCE],
            adversary="",
            label="clean" if clean else "leaking",
            negative_kind="independent" if clean else "",
            counterpart_of=(
                f"{BUILTIN_SOURCE}/{leak_by_domain[s.domain]}"
                if clean and s.domain in leak_by_domain else ""
            ),
            trace=load_example_trace(s.id),
            description=s.description,
        ))
    return units


def pack_units(pack_id: str) -> list[Unit]:
    """Every scenario of a bundled pack, as leaking units."""
    units = []
    for meta, trace in expand_pack(pack_id):
        origin = str(meta.get("origin_id") or meta.get("name") or "")
        units.append(Unit(
            unit_id=f"{pack_id}/{origin}",
            source=pack_id,
            origin_id=origin,
            domain=str(meta.get("domain") or ""),
            failure_mode=FAILURE_MODES.get(pack_id, "unspecified"),
            adversary=_adversary(list(meta.get("tags") or [])),
            label="leaking",
            negative_kind="",
            counterpart_of="",
            trace=trace,
            ground_truth=_ground_truth(meta),
            spec=meta.get("spec"),
            description=str(meta.get("description") or ""),
        ))
    return units


def available_sources() -> list[str]:
    """Source ids a manifest may select: ``builtin`` plus every bundled pack."""
    return [BUILTIN_SOURCE, *[p["id"] for p in list_packs()]]


def select_units(
    *,
    sources: list[str],
    domains: list[str] | None = None,
    failure_modes: list[str] | None = None,
    labels: list[str] | None = None,
    ids: list[str] | None = None,
    max_per_source: int | None = None,
    counterparts: str = "derived",
    seed: int = 0,
) -> list[Unit]:
    """Resolve a manifest's scenario selection into an ordered list of units.

    Filters apply to the leaking fixtures; a derived counterpart is kept when
    its leaking parent is kept. ``max_per_source`` draws a seeded random
    sample of leaking fixtures per source (independent clean controls are
    always kept for the selected built-ins). The order is deterministic:
    sources in the order given, then fixture order within each source, each
    derived counterpart right after its parent.
    """
    known = available_sources()
    unknown = [s for s in sources if s not in known]
    if unknown:
        raise ValueError(f"unknown source(s) {unknown}; available: {', '.join(known)}")
    if counterparts not in ("derived", "none"):
        raise ValueError("counterparts must be 'derived' or 'none'")
    want_labels = set(labels or ["leaking", "clean"])
    rng = random.Random(seed)
    out: list[Unit] = []
    for source in sources:
        units = builtin_units() if source == BUILTIN_SOURCE else pack_units(source)
        if domains:
            units = [u for u in units if u.domain in domains]
        if failure_modes:
            units = [u for u in units if u.failure_mode in failure_modes]
        if ids:
            units = [u for u in units if u.unit_id in ids or u.origin_id in ids]
        if max_per_source is not None:
            leaking = [u for u in units if u.label == "leaking"]
            if len(leaking) > max_per_source:
                keep = set(rng.sample(range(len(leaking)), max_per_source))
                chosen = {leaking[i].unit_id for i in keep}
                units = [u for u in units if u.label != "leaking" or u.unit_id in chosen]
        for unit in units:
            if unit.label in want_labels:
                out.append(unit)
            if counterparts == "derived" and "clean" in want_labels:
                twin = derive_counterpart(unit)
                if twin is not None:
                    out.append(twin)
    return out


def source_provenance(source: str) -> dict[str, Any]:
    """Licence, attribution and SHA-256 of one source's bundled files."""
    if source == BUILTIN_SOURCE:
        digest = hashlib.sha256()
        files = sorted(s.example_trace for s in list_scenarios() if s.example_trace)
        for name in files:
            assert name is not None
            data = resources.files("agentleak.examples").joinpath(name).read_bytes()
            digest.update(name.encode("utf-8") + b"\0" + data + b"\0")
        registry = json.dumps([s.to_dict() for s in list_scenarios()], sort_keys=True)
        digest.update(registry.encode("utf-8"))
        return {
            "source": BUILTIN_SOURCE,
            "name": "AgentLeak built-in scenarios",
            "license": "MIT",
            "attribution": "AgentLeak-authored synthetic scenarios (repository MIT License).",
            "source_url": "",
            "sha256": digest.hexdigest(),
            "files": files,
        }
    raw = (
        resources.files("agentleak.scenarios.packs").joinpath(f"{source}.json").read_bytes()
    )
    pack = load_pack(source)
    return {
        "source": source,
        "name": pack.get("name", source),
        "license": pack.get("license", ""),
        "attribution": pack.get("attribution", ""),
        "source_url": pack.get("source_url", ""),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "files": [f"{source}.json"],
    }


__all__ = [
    "DISCLOSURE_CHANNELS",
    "FAILURE_MODES",
    "Unit",
    "available_sources",
    "builtin_units",
    "derive_counterpart",
    "pack_units",
    "select_units",
    "source_provenance",
    "trace_digest",
]
