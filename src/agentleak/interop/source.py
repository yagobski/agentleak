# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Load an input file once, in the shape every importer sniffs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import InteropError, SafeZip, decode, parse_json, parse_jsonl, read_bytes, sha256_of


@dataclass
class Source:
    """A file read and parsed once: ``kind`` is ``zip``, ``json`` or ``jsonl``."""

    path: Path
    name: str
    sha256: str
    kind: str
    value: Any = None
    archive: SafeZip | None = None


def load_source(path: str | Path) -> Source:
    """Read and parse a file without interpreting it.

    A zip archive is opened in memory (members are read on demand by the
    importer that claims it); text is parsed as JSON, then as JSON lines.
    """
    path = Path(path)
    data = read_bytes(path)
    digest = sha256_of(data)
    if not data.strip():
        raise InteropError(f"{path.name} is empty")
    if data[:4] == b"PK\x03\x04":
        return Source(path, path.name, digest, "zip", archive=SafeZip(data, path.name))
    text = decode(data, path.name)
    stripped = text.lstrip()
    if stripped[:1] in ("{", "["):
        try:
            return Source(path, path.name, digest, "json", value=parse_json(text, path.name))
        except InteropError as exc:
            # A JSON-lines file also starts with "{"; only fall through when
            # the whole text is not one document.
            if "nested" in str(exc):
                raise
            if "\n" not in text.strip():
                raise
    return Source(path, path.name, digest, "jsonl", value=parse_jsonl(text, path.name))
