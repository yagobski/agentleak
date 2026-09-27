# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A signed evidence log: rewriting the chain now needs the private key.

The hash chain alone is tamper-evident, not tamper-resistant — anyone who can
write the file can recompute every hash. Signing each entry's hash moves the
forgery cost from "can write a file" to "holds the key".
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

pytest.importorskip("cryptography")

from agentleak.core.evidence import EvidenceLog, chain_hash, verify  # noqa: E402
from agentleak.core.signing import Signer, generate_keypair, load_public_key  # noqa: E402


@pytest.fixture
def keys(tmp_path):
    return generate_keypair(tmp_path / "evidence.key")


def _write(path, signer, n=3):
    log = EvidenceLog(path, signer=signer)
    for i in range(n):
        log.append(action="allow", tool=f"t{i}", data_types=["email"])
    return log


def test_private_key_is_mode_600(keys):
    private, _public = keys
    assert (private.stat().st_mode & 0o777) == 0o600


def test_a_signed_log_verifies(tmp_path, keys):
    private, public = keys
    _write(tmp_path / "e.jsonl", Signer(private))
    result = verify(tmp_path / "e.jsonl", public_key=load_public_key(public))
    assert result.ok and "signed" in result.detail


def test_a_rewritten_chain_passes_hashes_but_fails_signatures(tmp_path, keys):
    private, public = keys
    path = tmp_path / "e.jsonl"
    _write(path, Signer(private))
    # Forge: change an entry and recompute every hash, as a writer without the key could.
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    lines[1]["action"] = "block"
    previous = "0" * 64
    for line in lines:
        line["previous"] = previous
        body = {k: v for k, v in line.items() if k not in ("hash", "signature", "key_id")}
        line["hash"] = previous = chain_hash(body)
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert verify(path).ok                                  # the chain alone is fooled
    assert not verify(path, public_key=load_public_key(public)).ok


def test_stripping_signatures_fails(tmp_path, keys):
    private, public = keys
    path = tmp_path / "e.jsonl"
    _write(path, Signer(private))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    for line in lines:
        line.pop("signature")
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    result = verify(path, public_key=load_public_key(public))
    assert not result.ok and "not signed" in result.detail


def test_another_key_fails(tmp_path, keys):
    private, _ = keys
    _, other_public = generate_keypair(tmp_path / "other.key")
    _write(tmp_path / "e.jsonl", Signer(private))
    assert not verify(tmp_path / "e.jsonl", public_key=load_public_key(other_public)).ok


def test_cli_keygen_sign_verify(tmp_path):
    key = tmp_path / "k.pem"
    run = [sys.executable, "-m", "agentleak"]
    assert subprocess.run([*run, "evidence", "--keygen", str(key)], capture_output=True).returncode == 0
    _write(tmp_path / "e.jsonl", Signer(key))
    ok = subprocess.run([*run, "evidence", str(tmp_path / "e.jsonl"), "--verify",
                         "--public-key", f"{key}.pub"], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
