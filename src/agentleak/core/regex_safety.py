# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Refuse user-supplied regexes that can backtrack catastrophically.

Python's ``re`` has no timeout. A custom detector such as ``(a+)+$`` takes
seconds on 30 characters and hours on 40, and the platform runs custom rules
that any signed-in account submits. The check is structural: a repeat whose
body can itself match a variable number of times (``(a+)+``, ``(\\w*\\s?)*``)
is nested repetition, the shape behind exponential backtracking. Fixed inner
counts (``(\\d{3}-)+``) are allowed.
"""

from __future__ import annotations

from typing import Any

try:  # Python 3.11+
    from re import _parser as _sre_parse  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python 3.10
    import sre_parse as _sre_parse  # type: ignore[no-redef]

_REPEATS = {"MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"}


class UnsafeRegexError(ValueError):
    """The pattern has nested variable repetition."""


def _has_variable_repeat(items: Any) -> bool:
    for op, arg in items:
        name = str(op)
        if name in _REPEATS:
            lo, hi, body = arg
            if hi != lo:
                return True
            if _has_variable_repeat(body):
                return True
        elif name == "SUBPATTERN":
            if _has_variable_repeat(arg[-1]):
                return True
        elif name == "BRANCH":
            if any(_has_variable_repeat(b) for b in arg[1]):
                return True
    return False


def _nested(items: Any) -> bool:
    for op, arg in items:
        name = str(op)
        if name in _REPEATS:
            lo, hi, body = arg
            if hi != lo and name != "POSSESSIVE_REPEAT" and _has_variable_repeat(body):
                return True
            if _nested(body):
                return True
        elif name == "SUBPATTERN":
            if _nested(arg[-1]):
                return True
        elif name == "BRANCH":
            if any(_nested(b) for b in arg[1]):
                return True
        elif name in {"ASSERT", "ASSERT_NOT"}:
            if _nested(arg[1]):
                return True
    return False


def check_regex(pattern: str) -> None:
    """Raise :class:`UnsafeRegexError` (a ``ValueError``) for nested repeats."""
    parsed = _sre_parse.parse(pattern)
    if _nested(list(parsed)):
        raise UnsafeRegexError(
            f"Pattern {pattern!r} nests a repeat inside a repeat (like '(a+)+'), "
            "which can backtrack for hours on a short input. Rewrite it without "
            "the outer repeat or use a fixed inner count."
        )
