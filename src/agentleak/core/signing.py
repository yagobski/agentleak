# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Ed25519 signatures for the evidence log.

The hash chain makes the log tamper-*evident*: change a line and every hash
after it breaks. It does not make it tamper-*resistant*, because anyone who can
write the file can recompute the whole chain. A signature closes that gap for
anyone who does not hold the private key: each entry's hash is signed as it is
written, and ``agentleak evidence --public-key`` checks every signature, so a
rewritten chain fails unless it was re-signed with the same key.

The key is the whole guarantee, so keep it where the gateway can read it and
the log's other writers cannot. Needs ``pip install 'agentleak[sign]'``.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any

__all__ = ["Signer", "generate_keypair", "load_public_key", "verify_signature", "key_id"]

_INSTALL_HINT = "signing needs the 'cryptography' package: pip install 'agentleak[sign]'"


def _ed25519() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - exercised without the extra
        raise RuntimeError(_INSTALL_HINT) from exc
    return ed25519


def _serialization() -> Any:
    from cryptography.hazmat.primitives import serialization

    return serialization


def _raw_public(public_key: Any) -> bytes:
    s = _serialization()
    return bytes(public_key.public_bytes(s.Encoding.Raw, s.PublicFormat.Raw))


def key_id(public_key: Any) -> str:
    """A short, stable name for a public key, recorded next to each signature."""
    return hashlib.sha256(_raw_public(public_key)).hexdigest()[:16]


def generate_keypair(private_path: str | os.PathLike[str]) -> tuple[Path, Path]:
    """Write a new private key (mode 600) and its public key beside it (.pub)."""
    ed25519 = _ed25519()
    s = _serialization()
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_file = Path(private_path)
    public_file = private_file.with_suffix(private_file.suffix + ".pub")
    private_file.parent.mkdir(parents=True, exist_ok=True)
    pem = private_key.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption())
    fd = os.open(private_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    public_file.write_bytes(
        private_key.public_key().public_bytes(s.Encoding.PEM, s.PublicFormat.SubjectPublicKeyInfo)
    )
    return private_file, public_file


def load_public_key(path: str | os.PathLike[str]) -> Any:
    _ed25519()
    return _serialization().load_pem_public_key(Path(path).read_bytes())


class Signer:
    """Signs entry hashes with a private key read once at start-up."""

    def __init__(self, private_path: str | os.PathLike[str]) -> None:
        _ed25519()
        key = _serialization().load_pem_private_key(Path(private_path).read_bytes(), password=None)
        self._key = key
        self.key_id = key_id(key.public_key())

    def sign(self, entry_hash: str) -> str:
        return base64.b64encode(self._key.sign(entry_hash.encode("ascii"))).decode("ascii")


def verify_signature(public_key: Any, entry_hash: str, signature: str) -> bool:
    try:
        public_key.verify(base64.b64decode(signature), entry_hash.encode("ascii"))
    except Exception:  # noqa: BLE001 - InvalidSignature, bad base64: both are "no"
        return False
    return True
