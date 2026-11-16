# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Every bundled pack is classified in both leak-mode tables.

A pack missing from a table falls back silently: the InjecAgent pack shipped in
0.19.0 as "pattern" on the public benchmark and as "unspecified" in
`agentleak bench`, when it is a hijack.
"""
import importlib.util
from pathlib import Path

from agentleak.research.corpus import BUILTIN_SOURCE, FAILURE_MODES
from agentleak.scenarios.packs import list_packs

REPO_ROOT = Path(__file__).resolve().parents[1]


def _pack_ids() -> set[str]:
    return {pack["id"] if isinstance(pack, dict) else pack.id for pack in list_packs()}


def test_bench_classifies_every_pack() -> None:
    assert _pack_ids() | {BUILTIN_SOURCE} <= set(FAILURE_MODES)


def test_benchmark_script_classifies_every_pack() -> None:
    spec = importlib.util.spec_from_file_location("build_benchmark", REPO_ROOT / "scripts" / "build_benchmark.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _pack_ids() | {BUILTIN_SOURCE} <= set(module.LEAK_MODE)


def test_the_two_tables_agree() -> None:
    spec = importlib.util.spec_from_file_location("build_benchmark", REPO_ROOT / "scripts" / "build_benchmark.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shared = set(FAILURE_MODES) & set(module.LEAK_MODE)
    assert {k: FAILURE_MODES[k] for k in shared} == {k: module.LEAK_MODE[k] for k in shared}
