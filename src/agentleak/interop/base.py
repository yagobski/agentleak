# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Shared plumbing for the importers: safe reading, provenance, observation.

An imported file is data. Nothing here executes, fetches or follows anything a
file contains: no URL is opened, no path inside a file is dereferenced, nothing
is evaluated or unpickled. Every read is bounded in size and nesting depth, and
an archive is read member by member in memory, never extracted.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .. import __version__
from ..core.trace import CHANNELS, MAX_CONTENT_DEPTH, Trace, _depth

#: Largest file an importer reads.
MAX_FILE_BYTES = 256 * 1024 * 1024
#: Largest single member read out of an archive, and the sum of all members read.
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
#: Deepest JSON nesting accepted in a source document.
MAX_JSON_DEPTH = MAX_CONTENT_DEPTH
#: Most traces one import produces.
MAX_TRACES = 50_000

#: Channels that only a white-box source (one that sees the agent's internals) can show.
INTERNAL_CHANNELS = [c for c in CHANNELS if c not in ("user_input", "final_output")]


class InteropError(ValueError):
    """The file cannot be imported. The message says why, precisely."""


@dataclass
class ImportedTrace:
    """One trace produced from one record of the source (a row, a sample, an attempt)."""

    record_id: str
    trace: Trace


@dataclass
class ImportResult:
    """Everything one import produced, with where it came from."""

    tool: str
    tool_version: str | None
    source_file: str
    source_sha256: str
    detected_because: str
    verification: str
    observable_channels: list[str]
    traces: list[ImportedTrace] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "tool_version": self.tool_version,
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "detected_because": self.detected_because,
            "verification": self.verification,
            "traces": len(self.traces),
            "events": sum(len(t.trace.events) for t in self.traces),
            "skipped_records": self.skipped,
            "observable_channels": self.observable_channels,
            "unobserved_channels": [c for c in CHANNELS if c not in self.observable_channels],
            "notes": self.notes,
        }


# ----------------------------------------------------------------------
# reading
# ----------------------------------------------------------------------
def read_bytes(path: Path, *, limit: int | None = None) -> bytes:
    """The file's bytes, refusing anything larger than ``limit`` (default
    :data:`MAX_FILE_BYTES`)."""
    limit = MAX_FILE_BYTES if limit is None else limit
    if not path.is_file():
        raise InteropError(f"no such file: {path}")
    size = path.stat().st_size
    if size > limit:
        raise InteropError(f"{path.name} is {size} bytes; the limit is {limit} bytes")
    with path.open("rb") as fh:
        data = fh.read(limit + 1)
    if len(data) > limit:
        raise InteropError(f"{path.name} grew past {limit} bytes while being read")
    return data


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InteropError(f"{label} is not UTF-8 text (byte {exc.start})") from exc


def check_depth(value: Any, label: str) -> Any:
    if _depth(value) > MAX_JSON_DEPTH:
        raise InteropError(f"{label} is nested more than {MAX_JSON_DEPTH} levels deep")
    return value


def parse_json(text: str, label: str) -> Any:
    """Parse one JSON document with a clear error and a nesting cap."""
    try:
        value = json.loads(text)
    except RecursionError as exc:
        raise InteropError(f"{label} is nested too deeply to parse") from exc
    except json.JSONDecodeError as exc:
        raise InteropError(f"{label} is not valid JSON (line {exc.lineno}, column {exc.colno}: "
                           f"{exc.msg})") from exc
    return check_depth(value, label)


def parse_jsonl(text: str, label: str) -> list[Any]:
    """Parse JSON lines. A line that is not JSON is an error that names it."""
    rows: list[Any] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except RecursionError as exc:
            raise InteropError(f"{label} line {number} is nested too deeply to parse") from exc
        except json.JSONDecodeError as exc:
            raise InteropError(f"{label} line {number} is not JSON ({exc.msg})") from exc
        rows.append(check_depth(value, f"{label} line {number}"))
    return rows


def safe_member_name(name: str) -> bool:
    """A member name that cannot point outside the archive (zip-slip)."""
    if not name or "\\" in name or "\x00" in name or name.startswith("/"):
        return False
    parts = PurePosixPath(name).parts
    return ".." not in parts and not (parts and parts[0].endswith(":"))


class SafeZip:
    """Read selected JSON members of a zip archive in memory, within limits.

    Nothing is ever written to disk. Members with unsafe names are refused,
    sizes are checked against both the declared size and what decompression
    actually yields, and zstd-compressed members (Inspect AI writes those) are
    read when the running Python can decompress them.
    """

    def __init__(self, data: bytes, label: str) -> None:
        import io

        self.label = label
        self._read_total = 0
        try:
            self._zip = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise InteropError(f"{label} is not a readable zip archive ({exc})") from exc
        infos = self._zip.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise InteropError(f"{label} has {len(infos)} members; the limit is {MAX_ARCHIVE_MEMBERS}")
        bad = [i.filename for i in infos if not safe_member_name(i.filename)]
        if bad:
            raise InteropError(f"{label} has a member name that points outside the archive: {bad[0]!r}")
        self.names = [i.filename for i in infos]

    def read(self, name: str) -> bytes:
        info = self._zip.getinfo(name)
        if info.file_size > MAX_MEMBER_BYTES:
            raise InteropError(f"{self.label}: member {name} declares {info.file_size} bytes; "
                               f"the limit is {MAX_MEMBER_BYTES}")
        if info.compress_type == 93 and not _zip_supports_zstd():
            data = _read_zstd_member(self._zip, info, self.label)
        else:
            try:
                with self._zip.open(info) as fh:
                    data = fh.read(MAX_MEMBER_BYTES + 1)
            except NotImplementedError as exc:
                raise InteropError(f"{self.label}: member {name} uses an unsupported "
                                   f"compression method ({info.compress_type})") from exc
            except (zipfile.BadZipFile, OSError, EOFError) as exc:
                raise InteropError(f"{self.label}: member {name} is corrupt ({exc})") from exc
        if len(data) > MAX_MEMBER_BYTES:
            raise InteropError(f"{self.label}: member {name} decompresses past {MAX_MEMBER_BYTES} bytes")
        self._read_total += len(data)
        if self._read_total > MAX_ARCHIVE_BYTES:
            raise InteropError(f"{self.label}: members decompress past {MAX_ARCHIVE_BYTES} bytes in total")
        return data

    def read_json(self, name: str) -> Any:
        label = f"{self.label}:{name}"
        return parse_json(decode(self.read(name), label), label)


def _zip_supports_zstd() -> bool:
    return getattr(zipfile, "ZIP_ZSTANDARD", None) == 93


def _read_zstd_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, label: str) -> bytes:
    """Decompress a zstd member with the optional ``zstandard`` package.

    Python before 3.14 cannot read these members on its own. The raw bytes are
    located through the member's local header, in memory.
    """
    try:
        import zstandard  # type: ignore[import-not-found,import-untyped,unused-ignore]
    except ImportError as exc:
        raise InteropError(
            f"{label}: this Inspect log compresses its members with zstd, which this Python "
            "cannot read. Use Python 3.14+, install the optional 'zstandard' package, or "
            "convert the log first with `inspect log convert --to json`."
        ) from exc
    import io
    import struct

    fp = zf.fp
    if fp is None:  # pragma: no cover - the archive is open
        raise InteropError(f"{label}: archive is closed")
    fp.seek(info.header_offset)
    header = fp.read(30)
    if len(header) != 30 or header[:4] != b"PK\x03\x04":
        raise InteropError(f"{label}: member {info.filename} has a corrupt local header")
    name_len, extra_len = struct.unpack("<HH", header[26:30])
    fp.seek(info.header_offset + 30 + name_len + extra_len)
    raw = fp.read(info.compress_size)
    try:
        reader = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw))
        data: bytes = reader.read(MAX_MEMBER_BYTES + 1)
    except zstandard.ZstdError as exc:
        raise InteropError(f"{label}: member {info.filename} is corrupt ({exc})") from exc
    return data


# ----------------------------------------------------------------------
# provenance and observation
# ----------------------------------------------------------------------
def observation(tool: str, observable: list[str], note: str) -> dict[str, Any]:
    """What the source could see. Stored in ``trace.metadata["observation"]``."""
    unobserved = [c for c in CHANNELS if c not in observable]
    return {
        "source": tool,
        "observable_channels": list(observable),
        "unobserved_channels": unobserved,
        "black_box": not any(c in observable for c in INTERNAL_CHANNELS),
        "note": note,
    }


def stamp(trace: Trace, *, tool: str, tool_version: str | None, source_file: str,
          source_sha256: str, record_id: str, observation_: dict[str, Any],
          labels: dict[str, Any] | None = None) -> Trace:
    """Record provenance, observation and the source's own labels on a trace."""
    trace.metadata["provenance"] = {
        "tool": tool,
        "tool_version": tool_version,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "record_id": record_id,
        "importer": f"agentleak.interop.{tool}",
        "agentleak_version": __version__,
    }
    trace.metadata["observation"] = dict(observation_)
    if labels:
        trace.metadata["source_labels"] = labels
    return trace


def obj(value: Any) -> dict[str, Any]:
    """``value`` when it is a JSON object, else an empty one."""
    return value if isinstance(value, dict) else {}


def short(value: Any, limit: int = 200) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def safe_id(value: Any, fallback: str) -> str:
    """A run id made of safe characters (it becomes a report file name)."""
    text = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value or ""))
    text = text.strip("._")[:120]
    return text or fallback
