# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Report renderers and a small dispatcher."""

from __future__ import annotations

import os
from typing import Any

from ..core.report import AnalysisResult
from . import html_reporter, json_reporter, markdown_reporter

# Normalize user-facing format names.
_ALIASES = {"md": "markdown", "markdown": "markdown", "json": "json", "html": "html",
            "sarif": "sarif"}
_EXTENSIONS = {"json": "json", "html": "html", "markdown": "md", "sarif": "sarif"}


def normalize_formats(formats: list[str]) -> list[str]:
    out: list[str] = []
    for f in formats:
        key = _ALIASES.get(f.strip().lower())
        if key is None:
            raise ValueError(f"Unknown report format: {f!r} (use json, html, markdown, sarif)")
        if key not in out:
            out.append(key)
    return out


def render(data: dict[str, Any], fmt: str, *, trace_path: str | None = None) -> str:
    """Render a report dict into the requested format string.

    ``trace_path`` (SARIF only) locates each finding in the trace file.
    """
    fmt = _ALIASES.get(fmt.lower(), fmt.lower())
    if fmt == "sarif":
        from ..interop.sarif import render_sarif

        return render_sarif(data, trace_path=trace_path)
    if fmt == "json":
        return json_reporter.render_dict(data)
    if fmt == "html":
        return html_reporter.render(data)
    if fmt == "markdown":
        return markdown_reporter.render(data)
    raise ValueError(f"Unknown report format: {fmt!r}")


def write_reports(
    result: AnalysisResult | dict[str, Any],
    output_dir: str,
    formats: list[str],
    *,
    basename: str = "result",
    trace_path: str | None = None,
) -> dict[str, str]:
    """Write each requested format to ``output_dir`` and return the paths."""
    data = result.to_dict() if isinstance(result, AnalysisResult) else result
    os.makedirs(output_dir, exist_ok=True)
    written: dict[str, str] = {}
    for fmt in normalize_formats(formats):
        content = render(data, fmt, trace_path=trace_path)
        path = os.path.join(output_dir, f"{basename}.{_EXTENSIONS[fmt]}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written[fmt] = path
    return written


__all__ = [
    "render",
    "write_reports",
    "normalize_formats",
    "json_reporter",
    "html_reporter",
    "markdown_reporter",
]
