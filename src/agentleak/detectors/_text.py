# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Small text helpers shared by the detectors."""

from __future__ import annotations

import re

_BLOB_RE = re.compile(r"[A-Za-z0-9+/=_-]{24,}")
_SPACE = " \t\r\n\"'`,;()[]{}<>|"


def inside_blob(text: str, start: int, end: int) -> bool:
    """Whether ``text[start:end]`` sits inside an opaque encoded token.

    A base64 image, a hash or a key is not prose: "VIH", "k3V1B1" or "c/Mayor2"
    found inside one is a coincidence of the alphabet. The token is the run of
    non-space characters around the match; it is a blob when it is long, uses
    only the base64/base64url alphabet, and mixes upper case, lower case and
    digits as random data does.
    """
    left = start
    while left > 0 and text[left - 1] not in _SPACE:
        left -= 1
    right = end
    while right < len(text) and text[right] not in _SPACE:
        right += 1
    token = text[left:right]
    if not _BLOB_RE.fullmatch(token):
        return False
    return (
        any(c.isdigit() for c in token)
        and any(c.isupper() for c in token)
        and any(c.islower() for c in token)
    )
