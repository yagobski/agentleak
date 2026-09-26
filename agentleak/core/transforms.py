# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Encoded and obscured copies of sensitive data.

Agents in a multi-agent system pass each other whatever the task seems to need,
and nothing requires that to be readable. A planner that base64-encodes a
customer record into a context blob, a worker that hex-encodes an email into an
identifier, a SIN sent in two halves to the same recipient: each is a disclosure,
and each walks past a detector that only reads plaintext. This module measured
that before it existed. Of ten such copies sent between two agents, the
deterministic tier found one, and only because a reversed SIN still looked like
a SIN.

Two families of transformation, handled differently because they fail
differently:

**Self-announcing encodings** — base64, hex, percent-encoding, letter spacing.
The encoded form has a shape of its own and decodes to readable text or it does
not, so :func:`decoded_views` can decode it with no context and the ordinary
detectors read the result. A SHA-256, a git commit or a PNG in base64 decodes to
binary and is dropped. These views also feed the sanitizer, so ``redact`` and the
runtime gateway remove the encoded token whole.

**Encodings that look like text** — reversal, ROT13, splitting a value across
messages. Nothing about ``682 454 640`` says it was ever anything else, so
running detectors over every reversed or rotated event would report noise. These
are matched only against values the trace itself has already shown to be
sensitive (:func:`find_obscured_copies`). That anchoring is what keeps the false
positive rate at zero on the benign controls, and it is also the limit: an
obscured value that never appears in plaintext anywhere in the trace is not
found.

An encoded copy is attributed to the *original* value. AgentRisk keys a secret
on its value, so the copy adds exposure on the channel where it appeared without
inventing a second secret.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import re
import urllib.parse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .coalesce import _contains_at_boundaries, canonical_form

__all__ = ["CREDENTIAL_TYPES", "DecodedView", "ObscuredCopy", "decoded_views", "describe", "find_obscured_copies"]


# Types whose match is an exact, self-delimiting credential. An encoded span
# inside one (a URL-encoded password in a DSN) is part of that credential, not a
# second finding: the decoded password plus the host after it is shaped like an
# email address, and reporting it as one would be both a duplicate and wrong.
CREDENTIAL_TYPES = frozenset({
    "private_key", "connection_string", "jwt", "bearer_token", "aws_access_key",
    "github_token", "slack_token", "stripe_key", "llm_api_key", "google_api_key",
})


@dataclass(frozen=True)
class DecodedView:
    """Readable text recovered from an encoded span of a larger text."""

    start: int
    end: int
    text: str
    transform: str


# A base64 / base64url token. The look-arounds keep it from starting or ending
# inside a longer run of the same alphabet.
# ``=`` may precede a token (``ctx=<base64>``), so it is not in the look-behind.
_B64_RE = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{8,}={0,2}(?![A-Za-z0-9+/=_-])")
_HEX_RE = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}){8,}(?![0-9A-Fa-f])")
# One URL component (a path segment or a query value), not the whole URL:
# the gateway removes only what is sensitive, and the rest of the call works.
_PERCENT_RUN_RE = re.compile(r"[^\s\"'<>&?=/#]*%[0-9A-Fa-f]{2}[^\s\"'<>&?=/#]*")
# Single characters separated by single spaces: ``j e a n @ e x a m p l e``.
_SPACED_RE = re.compile(r"(?<!\S)(?:\S ){7,}\S(?!\S)")

_MIN_DECODED = 6
_MAX_DEPTH = 2


def _readable(raw: bytes) -> str | None:
    """The bytes as text, or None when they are not text a person wrote."""
    if len(raw) < _MIN_DECODED:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text)
    if printable < len(text) * 0.95:
        return None
    # Text with no letters or digits at all is punctuation noise.
    if not any(ch.isalnum() for ch in text):
        return None
    return text


def _b64(token: str) -> str | None:
    body = token.rstrip("=")
    # Base64 of real text uses both cases or digits; an ordinary long word does
    # not, and would otherwise be decoded on the off chance.
    if body.isalpha() and (body.islower() or body.isupper()):
        return None
    padded = body.replace("-", "+").replace("_", "/")
    padded += "=" * (-len(padded) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    return _readable(raw)


def _hex(token: str) -> str | None:
    try:
        return _readable(bytes.fromhex(token))
    except ValueError:
        return None


def _views_once(text: str) -> list[DecodedView]:
    views: list[DecodedView] = []
    hex_spans: list[tuple[int, int]] = []

    for m in _HEX_RE.finditer(text):
        decoded = _hex(m.group(0))
        if decoded is not None:
            views.append(DecodedView(m.start(), m.end(), decoded, "hex"))
            hex_spans.append((m.start(), m.end()))

    for m in _B64_RE.finditer(text):
        # A hex string is also valid base64; it was read as hex above.
        if any(s <= m.start() and m.end() <= e for s, e in hex_spans):
            continue
        decoded = _b64(m.group(0))
        if decoded is not None:
            views.append(DecodedView(m.start(), m.end(), decoded, "base64"))

    for m in _PERCENT_RUN_RE.finditer(text):
        decoded = urllib.parse.unquote(m.group(0))
        if decoded != m.group(0):
            views.append(DecodedView(m.start(), m.end(), decoded, "percent"))

    for m in _SPACED_RE.finditer(text):
        views.append(DecodedView(m.start(), m.end(), m.group(0).replace(" ", ""), "spaced"))

    return views


def decoded_views(text: str, *, depth: int = _MAX_DEPTH) -> list[DecodedView]:
    """Every self-announcing encoded span in *text*, decoded.

    Nested encodings (base64 of a JSON document holding a hex field) are
    followed up to ``depth`` levels. A nested view keeps the span of the
    outermost token, because that is what has to be removed from the original.
    """
    if not text or depth <= 0:
        return []
    out: list[DecodedView] = []
    for view in _views_once(text):
        out.append(view)
        for inner in decoded_views(view.text, depth=depth - 1):
            out.append(DecodedView(view.start, view.end, inner.text,
                                   f"{view.transform}>{inner.transform}"))
    return out


# ---------------------------------------------------------------------------
# Anchored matching: reversal, ROT13, and values split across messages.
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_MIN_ANCHOR = 6          # canonical length of a value worth anchoring on
_MIN_SPLIT = 8           # alphanumeric length of a value worth reassembling
_MIN_SPLIT_DIGITS = 4
_MIN_FRAGMENT = 3
_MAX_FRAGMENTS = 4


def _alnum(value: str) -> str:
    return "".join(_TOKEN_RE.findall(value)).casefold()


def _fragment_in(tokens: Sequence[str], target: str, pos: int) -> int:
    """Length of the longest run of whole tokens equal to ``target[pos:…]``.

    Whole tokens only: a stray ``2026`` elsewhere in a message must not be able
    to contribute ``026`` to somebody's SIN.
    """
    best = 0
    for i in range(len(tokens)):
        acc = ""
        for j in range(i, len(tokens)):
            acc += tokens[j]
            if not target.startswith(acc, pos):
                break
            best = max(best, len(acc))
    return best


def _is_identifier(target: str) -> bool:
    return len(target) >= _MIN_SPLIT and sum(ch.isdigit() for ch in target) >= _MIN_SPLIT_DIGITS


def _has_token_run(text: str, target: str) -> bool:
    tokens = [t.casefold() for t in _TOKEN_RE.findall(text)]
    return any(_fragment_in(tokens[i:], target, 0) == len(target) for i in range(len(tokens)))


def _reassembled(value: str, texts: Sequence[tuple[int, str]]) -> list[int] | None:
    """Indices of the events whose fragments spell *value*, in order, or None."""
    target = _alnum(value)
    # Identifiers only. Split a phrase and you get its words, and words turn up
    # in every message: "{hotel_address" reassembles from a message saying
    # "Hotel" and another saying "address". SINs, cards, keys and account
    # numbers carry digits; that is what makes a fragment of one mean anything.
    if not _is_identifier(target):
        return None
    for start in range(len(texts)):
        pos, used = 0, list[int]()
        for index, text in texts[start:start + _MAX_FRAGMENTS * 2]:
            tokens = [t.casefold() for t in _TOKEN_RE.findall(text)]
            k = _fragment_in(tokens, target, pos)
            if k >= _MIN_FRAGMENT or (k and pos + k == len(target) and used):
                pos += k
                used.append(index)
                if pos == len(target):
                    return used if len(used) >= 2 else None
                if len(used) >= _MAX_FRAGMENTS:
                    break
            elif used:
                break
    return None


@dataclass(frozen=True)
class ObscuredCopy:
    """A known sensitive value found in an event in obscured form."""

    event_index: int
    value: str
    transform: str
    fragments: tuple[int, ...] = ()


def find_obscured_copies(
    events: Sequence[tuple[str, str, str]],
    known_values: Iterable[str],
) -> list[ObscuredCopy]:
    """Reversed, ROT13 and split copies of values the trace already exposed.

    ``events`` is ``(text, target, channel)`` per event, in trace order.

    A copy counts only *after* the value first appeared in plain text: data
    flows forward, and without that rule matching is symmetric — a SIN and its
    reversal each look like an obscured copy of the other, and the original
    gets relabelled as the copy.

    A copy is *obscured* only where the value is not also present in plain
    text. ROT13 leaves digits alone, so without that rule every plaintext
    number would come back as a "ROT13 copy" of itself — which is a plaintext
    occurrence the detectors did not flag, not an obscured one, and labelling
    it otherwise would be wrong.
    """
    values = {canonical_form(v): v for v in known_values if len(canonical_form(v)) >= _MIN_ANCHOR}
    if not values:
        return []

    copies: list[ObscuredCopy] = []
    seen: set[tuple[int, str]] = set()
    plain = [canonical_form(text) if text else "" for text, _t, _c in events]

    # Longest first, so "type 2 diabetes" claims an event before "diabetes"
    # inside it can be reported again as a second copy.
    ordered = sorted(values.items(), key=lambda kv: -len(kv[0]))

    first_seen: dict[str, int] = {}
    for canon in values:
        first = next((i for i, text in enumerate(plain) if _contains_at_boundaries(text, canon)), None)
        if first is not None:
            first_seen[canon] = first
    ordered = [(c, o) for c, o in ordered if c in first_seen]

    for index, (text, _target, _channel) in enumerate(events):
        if not text:
            continue
        claimed: list[str] = []
        views = (
            ("reversed", canonical_form(text[::-1])),
            ("rot13", canonical_form(codecs.encode(text, "rot13"))),
        )
        for canon, original in ordered:
            if index <= first_seen[canon] or (index, canon) in seen:
                continue
            if _contains_at_boundaries(plain[index], canon):
                continue
            if any(_contains_at_boundaries(longer, canon) for longer in claimed):
                continue
            hit = next((t for t, view in views if _contains_at_boundaries(view, canon)), None)
            if hit is None and _is_identifier(_alnum(original)):
                # A decoded identifier loses its formatting: "0 4 6 4 5 4 2 8 6"
                # reads back as 046454286, which no SIN pattern accepts and
                # which, as a string, is not the SIN the trace already holds.
                hit = next(
                    (v.transform for v in decoded_views(text) if _has_token_run(v.text, _alnum(original))),
                    None,
                )
            if hit is not None:
                copies.append(ObscuredCopy(index, original, hit))
                seen.add((index, canon))
                claimed.append(canon)

    by_target: dict[str, list[tuple[int, str]]] = {}
    for index, (text, target, _channel) in enumerate(events):
        if text:
            by_target.setdefault(target or "", []).append((index, text))

    for texts in by_target.values():
        if len(texts) < 2:
            continue
        for canon, original in ordered:
            later = [(i, t) for i, t in texts if i > first_seen[canon]]
            used = _reassembled(original, later)
            if not used:
                continue
            last = used[-1]
            if any((i, canon) in seen or _contains_at_boundaries(plain[i], canon) for i in used):
                continue
            copies.append(ObscuredCopy(last, original, "split", tuple(used)))
            seen.add((last, canon))

    return copies


def describe(transform: str) -> str:
    """Human wording for a transform chain, for recommendations."""
    names = {
        "base64": "base64-encoded", "hex": "hex-encoded", "percent": "URL-encoded",
        "spaced": "letter-spaced", "reversed": "reversed", "rot13": "ROT13-rotated",
        "split": "split across messages",
    }
    return " then ".join(names.get(part, part) for part in transform.split(">"))
