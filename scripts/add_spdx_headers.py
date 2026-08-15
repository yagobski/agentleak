#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Add REUSE/SPDX headers to every source file that is missing one.

Idempotent: a file that already declares ``SPDX-License-Identifier`` is left
alone. Python headers go directly under the shebang when there is one, and
above the module docstring otherwise, so ``__doc__`` is unaffected.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

COPYRIGHT = "2026 AgentLeak contributors"
LICENSE = "MIT"

SKIP_DIRS = {".venv", ".git", "node_modules", "__pycache__", "dist", "build", ".mypy_cache", ".ruff_cache", ".pytest_cache"}

HASH_SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".toml"}
SLASH_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
BLOCK_SUFFIXES = {".css"}


def header(comment: str) -> str:
    return f"{comment} SPDX-FileCopyrightText: {COPYRIGHT}\n{comment} SPDX-License-Identifier: {LICENSE}\n"


def insert(text: str, suffix: str) -> str:
    if suffix in HASH_SUFFIXES:
        block = header("#")
        if text.startswith("#!"):
            shebang, _, rest = text.partition("\n")
            return f"{shebang}\n{block}{rest}"
        return block + text
    if suffix in BLOCK_SUFFIXES:
        return f"/* SPDX-FileCopyrightText: {COPYRIGHT}\n * SPDX-License-Identifier: {LICENSE} */\n" + text
    return header("//") + text


def candidates(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in HASH_SUFFIXES | SLASH_SUFFIXES | BLOCK_SUFFIXES:
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        if relative_parts[:3] == ("agentleak", "web", "static"):
            continue
        out.append(path)
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="Report missing headers without writing.")
    args = parser.parse_args()

    missing: list[Path] = []
    for path in candidates(args.root):
        text = path.read_text(encoding="utf-8")
        if "SPDX-License-Identifier" in text:
            continue
        missing.append(path)
        if not args.check:
            path.write_text(insert(text, path.suffix), encoding="utf-8")

    rel = [str(p.relative_to(args.root)) for p in missing]
    if args.check:
        for name in rel:
            print(f"missing SPDX header: {name}")
        print(f"{len(rel)} file(s) missing a header")
        return 1 if rel else 0

    print(f"Added headers to {len(rel)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
