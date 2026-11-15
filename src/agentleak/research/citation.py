# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Citation data for exports, read from ``CITATION.cff``.

From a source checkout the file itself is read. An installed wheel does not
ship it, so a copy of the fields used here is embedded below; a test keeps the
copy identical to the file. Nothing is added that the file does not state: no
journal, no year for the software, no DOI that is not there.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .. import __version__

_CFF = Path(__file__).resolve().parents[3] / "CITATION.cff"

#: The fields of CITATION.cff this module uses. Kept in sync by
#: tests/test_research_export.py::test_embedded_citation_matches_cff.
EMBEDDED: dict[str, Any] = {
    "title": "AgentLeak: privacy-leakage testing for agentic AI systems",
    "authors": [
        {"given-names": "Faouzi", "family-names": "El Yagoubi"},
        {"given-names": "José Alejandro", "family-names": "Quintero"},
        {"given-names": "Ranwa", "family-names": "Al Mallah"},
    ],
    "repository-code": "https://github.com/yagobski/agentleak",
    "url": "https://www.agentleak.org",
    "license": "MIT",
    "preferred-citation": {
        "type": "article",
        "title": "AgentLeak: A Benchmark for Internal-Channel Privacy Leakage in "
                 "Multi-Agent LLM Systems",
        "authors": [
            {"given-names": "Faouzi", "family-names": "El Yagoubi"},
            {"given-names": "Godwin", "family-names": "Badu-Marfo"},
            {"given-names": "Ranwa", "family-names": "Al Mallah"},
        ],
        "doi": "10.1109/ACCESS.2026.3704541",
        "year": 2026,
    },
}

_FIELDS = ("title", "authors", "repository-code", "url", "license", "preferred-citation")
_PREFERRED_FIELDS = ("type", "title", "authors", "doi", "year")


def _project(cff: dict[str, Any]) -> dict[str, Any]:
    out = {k: cff.get(k) for k in _FIELDS if k in cff}
    pref = cff.get("preferred-citation") or {}
    if pref:
        out["preferred-citation"] = {k: pref[k] for k in _PREFERRED_FIELDS if k in pref}
    for group in (out, out.get("preferred-citation") or {}):
        authors = group.get("authors") or []
        if authors:
            group["authors"] = [
                {k: a[k] for k in ("given-names", "family-names") if k in a} for a in authors
            ]
    return out


def load_citation() -> tuple[dict[str, Any], str]:
    """``(citation fields, where they came from)``."""
    if _CFF.exists():
        data = yaml.safe_load(_CFF.read_text(encoding="utf-8")) or {}
        return _project(data), str(_CFF.name)
    return dict(EMBEDDED), "embedded copy of CITATION.cff"


def _bib_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


def _authors(authors: list[dict[str, str]]) -> str:
    return " and ".join(f"{a['family-names']}, {a['given-names']}" for a in authors)


def _key(authors: list[dict[str, str]], year: Any, title: str) -> str:
    family = re.sub(r"[^a-z]", "", authors[0]["family-names"].lower()) if authors else "anon"
    word = re.sub(r"[^a-z]", "", title.split()[0].lower()) if title else "work"
    return f"{family}{year or ''}{word}"


def software_bibtex(cff: dict[str, Any], version: str = __version__) -> tuple[str, str]:
    """``(key, entry)`` for the software itself."""
    key = "agentleak_software"
    lines = [
        f"@software{{{key},",
        f"  title = {{{_bib_escape(cff['title'])}}},",
        f"  author = {{{_authors(cff['authors'])}}},",
        f"  version = {{{version}}},",
    ]
    if cff.get("repository-code"):
        lines.append(f"  url = {{{cff['repository-code']}}},")
    if cff.get("license"):
        lines.append(f"  license = {{{cff['license']}}},")
    lines.append("}")
    return key, "\n".join(lines)


def article_bibtex(cff: dict[str, Any]) -> tuple[str, str] | None:
    """``(key, entry)`` for the preferred citation, if the file has one."""
    pref = cff.get("preferred-citation")
    if not pref:
        return None
    key = _key(pref.get("authors", []), pref.get("year"), pref.get("title", ""))
    entry = "article" if pref.get("type") == "article" else "misc"
    lines = [
        f"@{entry}{{{key},",
        f"  title = {{{_bib_escape(pref['title'])}}},",
        f"  author = {{{_authors(pref.get('authors', []))}}},",
    ]
    if pref.get("year"):
        lines.append(f"  year = {{{pref['year']}}},")
    if pref.get("doi"):
        lines.append(f"  doi = {{{pref['doi']}}},")
    lines.append("}")
    return key, "\n".join(lines)


def references_bib(provenance: list[dict[str, Any]], version: str = __version__) -> str:
    """BibTeX for AgentLeak and for each data source of a run.

    A source is cited only with data the repository holds. The AgentLeak Bench
    pack points at the preferred-citation DOI, so it reuses that entry. Packs
    whose paper citation is not in the repository get a comment saying so, with
    their source URL and licence, instead of an invented entry.
    """
    cff, origin = load_citation()
    sw_key, sw = software_bibtex(cff, version)
    parts = [f"% Generated by agentleak {version} from {origin}.", "", sw, ""]
    article = article_bibtex(cff)
    article_doi = (cff.get("preferred-citation") or {}).get("doi", "")
    if article:
        parts += [article[1], ""]
    for p in provenance:
        src, url = p.get("source", ""), p.get("source_url", "") or ""
        if src == "builtin":
            parts.append(f"% builtin scenarios: part of the AgentLeak software ({sw_key}).")
        elif article and article_doi and article_doi in url:
            parts.append(f"% {src}: cite {article[0]} (pack source_url is its DOI).")
        else:
            parts.append(
                f"% {src}: no BibTeX entry is recorded in the AgentLeak repository. Cite the "
                f"dataset authors' own paper. Source: {url or 'not stated'}; licence: "
                f"{p.get('license') or 'not stated'}."
            )
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


__all__ = ["EMBEDDED", "article_bibtex", "load_citation", "references_bib", "software_bibtex"]
