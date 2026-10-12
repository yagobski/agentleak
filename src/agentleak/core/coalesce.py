# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Resolve overlapping detector matches into one secret each.

AgentRisk counts *distinct secrets, not occurrences* (Definition 1). It
identifies a secret by ``data_type`` plus the matched string, which is only the
same thing as "distinct secret" while every detector agrees on where the entity
starts and ends. They do not. A dictionary detector matches ``diabetes``; the
key-name detector, reading ``diagnosis: Type 2 diabetes``, matches the whole
field value. Two matches, two strings, one diagnosis — and the vault grew by
two.

That inflates both sides of the Risk Index: WSL over leaked secrets and ρ_S
over the reachable set. Worse, it makes the score depend on *phrasing* rather
than content, so the same secret written two ways scores differently and a
"deterministic, reproducible" number is neither.

This module runs over the whole trace before scoring and merges matches that
denote the same secret:

* **Same ``data_type``.** A name inside an address is not the address.
* **Containment at token boundaries.** ``diabetes`` inside ``Type 2 diabetes``
  is the same diagnosis. ``1234`` inside ``12345`` is a different account
  number, which is why bare substring containment is not enough.
* **Canonical form is the tightest span** — the entity, not the sentence around
  it, so the evidence stays readable and the identity stays stable no matter
  which detector happened to fire first.
* **Classification is the strongest in the cluster.** A value that a dictionary
  rates medium and a sensitive key rates critical is critical: the key name is
  the stronger signal about what the value *is*, and merging must never discard
  severity.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .detector import Finding, Severity, redact

__all__ = ["coalesce_findings", "canonical_form"]

_WS_RE = re.compile(r"\s+")


def canonical_form(value: str) -> str:
    """Comparison form of a matched value: case- and whitespace-insensitive."""
    return _WS_RE.sub(" ", str(value).strip()).casefold()


def _contains_at_boundaries(haystack: str, needle: str) -> bool:
    """Is ``needle`` present in ``haystack`` as a whole token run?

    Both arguments are already in canonical form. The boundary requirement is
    what separates "the same secret written with more context" from "a
    different secret that happens to share a prefix": ``diabetes`` sits inside
    ``type 2 diabetes`` bounded by a space and the end of string, while
    ``1234`` sits inside ``12345`` followed by another digit.
    """
    if not needle or len(needle) > len(haystack):
        return False
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return False
        before_ok = idx == 0 or not haystack[idx - 1].isalnum()
        after = idx + len(needle)
        after_ok = after == len(haystack) or not haystack[after].isalnum()
        if before_ok and after_ok:
            return True
        start = idx + 1


def _cluster(ordered: Sequence[str]) -> dict[str, str]:
    """Group canonical values that denote the same secret.

    ``ordered`` runs widest span first, so a cluster is seeded by the broadest
    match and absorbs the tighter ones it contains. Returns each value mapped
    to its cluster root.
    """
    parent: dict[str, str] = {key: key for key in ordered}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for i, wide in enumerate(ordered):
        for narrow in ordered[i + 1:]:
            if find(wide) != find(narrow) and _contains_at_boundaries(wide, narrow):
                parent[find(narrow)] = find(wide)

    return {key: find(key) for key in ordered}


def _representative(values: Iterable[str]) -> str:
    """The tightest span in a cluster, chosen deterministically.

    Shortest wins because the shorter match is the entity and the longer one is
    the entity plus surrounding text. Length ties break lexicographically so the
    canonical value never depends on detector ordering.
    """
    return min(values, key=lambda v: (len(canonical_form(v)), canonical_form(v)))


def coalesce_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Rewrite ``findings`` so each distinct secret carries one identity.

    Findings are mutated in place and returned. The count of findings is
    unchanged — every disclosure on every channel is still reported, which is
    what the per-channel view and the leak paths need. What changes is that
    disclosures of the same secret now agree on its value, so scoring counts
    the secret once.
    """
    by_type: dict[str, list[Finding]] = {}
    for finding in findings:
        by_type.setdefault(finding.data_type, []).append(finding)

    for group in by_type.values():
        # Distinct raw values in this data type, longest first: a cluster is
        # seeded by the widest span and absorbs the tighter ones inside it.
        distinct: dict[str, str] = {}
        for finding in group:
            distinct.setdefault(canonical_form(finding.matched_value), finding.matched_value)
        if len(distinct) < 2:
            continue

        root_of = _cluster(sorted(distinct, key=len, reverse=True))
        clusters: dict[str, list[str]] = {}
        for key, root in root_of.items():
            clusters.setdefault(root, []).append(key)
        if all(len(members) < 2 for members in clusters.values()):
            continue

        # Canonical value and strongest classification, per cluster.
        canonical: dict[str, str] = {}
        strongest: dict[str, tuple[Severity, int, float]] = {}
        for root, members in clusters.items():
            canonical[root] = _representative(distinct[key] for key in members)
            members_set = set(members)
            related = [f for f in group if canonical_form(f.matched_value) in members_set]
            strongest[root] = (
                max((f.severity for f in related), key=lambda s: s.rank),
                max(f.level for f in related),
                max(f.confidence for f in related),
            )

        for finding in group:
            root = root_of[canonical_form(finding.matched_value)]
            if len(clusters[root]) < 2:
                continue
            value = canonical[root]
            severity, level, confidence = strongest[root]
            if canonical_form(finding.matched_value) != canonical_form(value):
                finding.metadata = {
                    **finding.metadata,
                    "coalesced_from": finding.matched_value,
                }
            finding.matched_value = value
            finding.redacted_value = redact(value)
            finding.severity = severity
            finding.level = level
            finding.confidence = confidence

    return list(findings)
