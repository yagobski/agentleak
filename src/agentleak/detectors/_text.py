# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Small text helpers shared by the detectors."""

from __future__ import annotations

import re

_BLOB_RE = re.compile(r"[A-Za-z0-9+/=_-]{24,}")
_SPACE = " \t\r\n\"'`,;()[]{}<>|"

# Month names and abbreviations in EN/FR/ES/DE/PT/IT, shared by the date of
# birth rules in :mod:`.pii` and :mod:`.context`.
MONTHS = (
    r"jan(?:uary|vier|eiro)?|feb(?:ruary|ruar)?|f[ée]v(?:rier)?|fevereiro|mar(?:ch|s|zo|ço)?|"
    r"m[äa]rz|apr(?:il)?|avr(?:il)?|abr(?:il)?|aprile|may|mai|mayo|maio|maggio|"
    r"jun[ei]?|juin|junio|junho|giugno|jul[iy]?|juillet|julio|julho|luglio|"
    r"aug(?:ust)?|ao[uû]t|agosto|sep(?:t(?:ember)?)?|septembre|septiembre|setembro|settembre|"
    r"oct(?:ober)?|octobre|octubre|okt(?:ober)?|outubro|ottobre|"
    r"nov(?:ember)?|novembre|noviembre|novembro|dec(?:ember)?|d[ée]cembre|dez(?:ember)?|"
    r"diciembre|dezembro|dicembre|ene(?:ro)?|gen(?:naio)?|janeiro"
)


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


def trie_pattern(terms: list[str]) -> str:
    """One regex alternation for many literal terms, factored as a trie.

    Python's ``re`` tries every alternative of ``a|b|c…`` at each position, so
    a 200-word dictionary costs 200 attempts per word boundary. Sharing
    prefixes (``diab(?:ète|ete|etes)``) makes it one walk down the trie. A
    terminal node's children are optional and greedy, so the longest term
    still wins, as it did with the longest-first alternation.
    """
    root: dict[str, dict] = {}
    for term in terms:
        node = root
        for ch in term:
            node = node.setdefault(ch, {})
        node[""] = {}

    def build(node: dict[str, dict]) -> str:
        terminal = "" in node
        branches = [re.escape(ch) + build(child) for ch, child in sorted(node.items()) if ch]
        if not branches:
            return ""
        body = branches[0] if len(branches) == 1 else "(?:" + "|".join(branches) + ")"
        if terminal:
            return "(?:" + body + ")?"
        return body

    return build(root)


class SubstringIndex:
    """Which values already taken contain, or are contained in, a new one.

    The de-duplication of the context and address rules asks, for each new
    value, ``any(value in v or v in value for v in taken)``. Asked that way it
    compares every new value with every earlier one, and a long event of
    distinct values cost time quadratic in their number. This answers the
    same question exactly from two indexes:

    * ``value in v``: for each length a query has had, the set of every slice
      of that length of every value taken. A query is one set lookup.
    * ``v in value`` (``both_ways``): the values taken, grouped by length; a
      query looks up each slice of the new value whose length is one of them.

    Work grows with the total length of the values times the number of
    distinct lengths among them (a few dozen for detector values), not with
    the square of their count.
    """

    def __init__(self, values: list[str] | None = None, *, both_ways: bool = True) -> None:
        self._both = both_ways
        self._values: list[str] = []
        self._slices: dict[int, set[str]] = {}  # query length -> slices of taken values
        self._by_len: dict[int, set[str]] = {}  # taken values by length
        for value in values or []:
            self.add(value)

    def add(self, value: str) -> None:
        self._values.append(value)
        n = len(value)
        for size, bucket in self._slices.items():
            if size <= n:
                bucket.update(value[i:i + size] for i in range(n - size + 1))
        if self._both:
            self._by_len.setdefault(n, set()).add(value)

    def related(self, value: str) -> bool:
        """``any(value in v or v in value for v in taken)`` (only the first
        test when not ``both_ways``)."""
        n = len(value)
        bucket = self._slices.get(n)
        if bucket is None:
            bucket = self._slices[n] = {
                v[i:i + n] for v in self._values if len(v) >= n for i in range(len(v) - n + 1)
            }
        if value in bucket:
            return True
        if self._both:
            for size, taken in self._by_len.items():
                if size <= n and any(value[i:i + size] in taken for i in range(n - size + 1)):
                    return True
        return False
