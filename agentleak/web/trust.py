"""The public trust page: a score someone else can check.

A badge an agent awards itself is worth nothing. The only thing that makes this
worth putting in a README is that AgentLeak measured the number, and that anyone
can follow the link and see what it was measured on.

Which puts the whole design weight on one thing: **the badge must never flatter
the run behind it.** Three ways it could, and what stops each:

- *A stale score reads as current.* A green badge from six months ago tells a
  reader nothing about the code they are looking at today. Age is part of the
  badge, and past a threshold the colour goes grey and the label says so.
- *A weak check reads as a strong one.* A pass from the pattern tier alone is a
  narrower claim than a pass from the full pipeline. The tier is on the page, and
  a degraded run cannot show a passing colour.
- *A cherry-picked run reads as the state of things.* The badge always shows the
  **latest** run, never the best one.

Everything here is public by deliberate act of the project owner. Nothing is
published as a side effect of recording a run.
"""

from __future__ import annotations

import time
from typing import Any

# Past this, "verified" is no longer an honest word for it.
STALE_AFTER_DAYS = 30

# Shields-style palette, so a badge sits naturally beside the others in a README.
COLOURS = {
    "pass": "#3fb950",
    "warn": "#d29922",
    "fail": "#f85149",
    "stale": "#8b949e",
}


def _age_days(when: float) -> float:
    return max(0.0, (time.time() - when) / 86400.0)


def badge_state(run: dict[str, Any] | None) -> dict[str, Any]:
    """Decide what the badge says, erring toward the less flattering reading.

    Returned as data rather than markup so the page and the SVG cannot disagree
    about what a run means.
    """
    if not run:
        return {"label": "privacy", "message": "not checked", "colour": COLOURS["stale"],
                "stale": True, "reason": "no run recorded yet"}

    age = _age_days(float(run.get("created_at") or 0))
    report = run.get("report") or {}
    detection = report.get("detection") or {}
    degraded = bool(report.get("degraded") or detection.get("degraded"))
    score = int(run.get("privacy_score") or 0)
    verdict = str(run.get("verdict") or "")

    if age > STALE_AFTER_DAYS:
        # Say the age rather than the score: the score is about code that may
        # not exist any more.
        return {
            "label": "privacy",
            "message": f"stale ({int(age)}d)",
            "colour": COLOURS["stale"],
            "stale": True,
            "reason": f"last checked {int(age)} days ago",
            "score": score,
        }

    if verdict in ("Fail", "High risk") or score < 60:
        colour = COLOURS["fail"]
    elif degraded or verdict == "Conditional pass" or score < 85:
        # A degraded run can never show green. Silence about a tier that did not
        # run is exactly how a weak claim passes for a strong one.
        colour = COLOURS["warn"]
    else:
        colour = COLOURS["pass"]

    return {
        "label": "privacy",
        "message": f"{score}/100",
        "colour": colour,
        "stale": False,
        "degraded": degraded,
        "verdict": verdict,
        "score": score,
        "tiers": list(detection.get("tiers") or []),
        "checked_days_ago": int(age),
    }


def _text_width(text: str) -> int:
    """Rough advance width at 11px DejaVu Sans, which is what shields assumes."""
    return int(len(text) * 6.6) + 20


def badge_svg(state: dict[str, Any]) -> str:
    """Render the badge. Self-contained SVG: no fonts, no external references.

    A README badge is fetched by GitHub's image proxy, which will not run
    scripts, follow links or load a font. Anything that needs those silently
    renders as a broken image.
    """
    label, message, colour = state["label"], state["message"], state["colour"]
    lw, mw = _text_width(label), _text_width(message)
    total = lw + mw

    def esc(value: str) -> str:
        return (
            value.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;")
        )

    label, message = esc(label), esc(message)
    alt = f"{label}: {message}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" '
        f'role="img" aria-label="{alt}">'
        f"<title>{alt}</title>"
        '<linearGradient id="s" x2="0" y2="100%">'
        '<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        '<stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>'
        '<g clip-path="url(#r)">'
        f'<rect width="{lw}" height="20" fill="#555"/>'
        f'<rect x="{lw}" width="{mw}" height="20" fill="{colour}"/>'
        f'<rect width="{total}" height="20" fill="url(#s)"/></g>'
        '<g fill="#fff" text-anchor="middle" '
        'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{lw / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>'
        f'<text x="{lw / 2}" y="14">{label}</text>'
        f'<text x="{lw + mw / 2}" y="15" fill="#010101" fill-opacity=".3">{message}</text>'
        f'<text x="{lw + mw / 2}" y="14">{message}</text>'
        "</g></svg>"
    )


def public_summary(project: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    """What a stranger is allowed to see: the verdict, never the evidence.

    Findings name real values from someone's private data. The point of the page
    is that a score was measured and by what, not what it found.
    """
    latest = runs[0] if runs else None
    state = badge_state(latest)
    report = (latest or {}).get("report") or {}
    detection = report.get("detection") or {}

    # Enough history to show a direction, not enough to reconstruct a run.
    trend = [
        {"at": r["created_at"], "score": int(r.get("privacy_score") or 0)}
        for r in runs[:20]
    ]

    return {
        "slug": project.get("public_slug", ""),
        "name": project["name"],
        "agent_type": project.get("agent_type", "generic"),
        "badge": state,
        "latest": None if not latest else {
            "at": latest["created_at"],
            "score": int(latest.get("privacy_score") or 0),
            "risk_index": float(latest.get("risk_index") or 0),
            "verdict": latest.get("verdict", ""),
            "channels_checked": len(report.get("channel_risks") or []),
            "detection": {
                "mode": detection.get("mode", "fast"),
                "tiers": list(detection.get("tiers") or []),
                "degraded": bool(report.get("degraded") or detection.get("degraded")),
            },
        },
        "runs_recorded": len(runs),
        "trend": trend,
        "stale_after_days": STALE_AFTER_DAYS,
    }
