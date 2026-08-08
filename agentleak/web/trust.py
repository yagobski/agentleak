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


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


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

    label, message = _esc(label), _esc(message)
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


# ---------------------------------------------------------------------------
# The page behind the badge
#
# The badge is a claim; this is where someone goes to check it. That makes the
# page worth more than the badge, and it is rendered here rather than in the
# marketing site for three reasons: the data lives here, the honesty rules live
# here, and anyone self-hosting the package gets a working link rather than a
# dead one. Server-rendered, so a crawler or a link preview sees the real
# verdict instead of an empty shell.
# ---------------------------------------------------------------------------

_PAGE_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0d1117;color:#e6edf3;
 font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:680px;margin:0 auto;padding:64px 24px 96px}
a{color:#58a6ff}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#8b949e;margin:0 0 10px}
h1{font-size:30px;line-height:1.2;margin:0 0 6px;font-weight:640;letter-spacing:-.01em}
.slug{color:#8b949e;font-size:14px;margin:0 0 40px;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.score{display:flex;align-items:baseline;gap:16px;margin:0 0 6px}
.score b{font-size:64px;line-height:1;font-weight:680;letter-spacing:-.03em;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.score span{font-size:18px;color:#8b949e}
.verdict{display:inline-block;padding:3px 10px;border-radius:999px;font-size:13px;
 font-weight:560;border:1px solid}
.note{margin:24px 0 0;padding:14px 16px;border-radius:8px;font-size:14px;
 border:1px solid #30363d;background:#161b22;color:#c9d1d9}
.note b{color:#e6edf3}
hr{border:0;border-top:1px solid #21262d;margin:40px 0}
dl{display:grid;grid-template-columns:1fr 1fr;gap:24px 32px;margin:0}
dt{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8b949e;margin:0 0 4px}
dd{margin:0;font-size:15px}
dd code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;
 background:#161b22;border:1px solid #21262d;border-radius:5px;padding:1px 6px}
.trend{margin:8px 0 0}
.trend-label{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8b949e;margin:0}
.foot{color:#8b949e;font-size:14px}
.foot h2{font-size:14px;color:#e6edf3;margin:0 0 8px;font-weight:600}
pre{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 14px;
 overflow-x:auto;font-size:12.5px;color:#c9d1d9;margin:12px 0 0}
@media(max-width:560px){dl{grid-template-columns:1fr}h1{font-size:25px}.score b{font-size:52px}}
"""


def _age_phrase(days: float) -> str:
    """Say the age the way a person would. "0 days ago" is not a thing anyone says."""
    whole = int(days)
    if whole == 0:
        return "today"
    if whole == 1:
        return "yesterday"
    return f"{whole} days ago"


def _trend_svg(trend: list[dict[str, Any]]) -> str:
    """A direction, drawn from the same numbers the page already shows.

    Oldest to newest, left to right. Fewer than two points is not a trend, and
    drawing a line through one would invent one.
    """
    points = list(reversed(trend))
    if len(points) < 2:
        return ""
    scores = [max(0, min(100, int(p["score"]))) for p in points]
    w, h, pad = 600, 56, 4
    step = w / (len(scores) - 1)
    # A fixed 0–100 axis: an auto-scaled one turns a wobble between 97 and 99
    # into a cliff, which is the graph lying about the numbers beside it.
    coords = " ".join(
        f"{i * step:.1f},{pad + (100 - s) / 100 * (h - 2 * pad):.1f}"
        for i, s in enumerate(scores)
    )
    return (
        f'<svg class="trend" viewBox="0 0 {w} {h}" width="100%" height="{h}" '
        f'role="img" aria-label="Score over the last {len(scores)} runs, oldest first: '
        f'{", ".join(str(s) for s in scores)}">'
        f'<polyline fill="none" stroke="#30363d" stroke-width="1" '
        f'points="0,{h / 2} {w},{h / 2}"/>'
        f'<polyline fill="none" stroke="#58a6ff" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{coords}"/>'
        "</svg>"
    )


def trust_page_html(summary: dict[str, Any], *, site_url: str = "") -> str:
    """Render the public page. Self-contained, and never shows a finding."""
    badge = summary["badge"]
    latest = summary.get("latest")
    name = _esc(str(summary.get("name") or "This agent"))
    slug = _esc(str(summary.get("slug") or ""))
    colour = badge["colour"]

    if latest:
        verdict = _esc(str(latest["verdict"] or "—"))
        score = f'<b style="color:{colour}">{latest["score"]}</b><span>/ 100</span>'
        checked = _age_phrase(_age_days(float(latest["at"])))
        tiers = latest["detection"]["tiers"]
        tier_html = (
            " ".join(f"<code>{_esc(str(t))}</code>" for t in tiers) if tiers else "—"
        )
        facts = f"""
    <dl>
      <div><dt>Last checked</dt><dd>{_esc(checked)}</dd></div>
      <div><dt>Risk index</dt><dd>{latest["risk_index"]:.3f}</dd></div>
      <div><dt>Detection tiers that ran</dt><dd>{tier_html}</dd></div>
      <div><dt>Channels examined</dt><dd>{latest["channels_checked"]}</dd></div>
      <div><dt>Detection mode</dt><dd><code>{_esc(str(latest["detection"]["mode"]))}</code></dd></div>
      <div><dt>Runs recorded</dt><dd>{summary["runs_recorded"]}</dd></div>
    </dl>"""
    else:
        verdict = "Not checked"
        score = '<b style="color:#8b949e">—</b>'
        facts = ""

    # The warnings are the page. A reader who skims should still leave knowing
    # what this number does not cover.
    notes = []
    if badge.get("stale"):
        notes.append(
            f"<b>This score is stale.</b> It was measured "
            f"{_esc(str(badge.get('reason', 'some time ago')))}, and describes the code as it was "
            f"then. Anything after {summary['stale_after_days']} days says nothing about what is "
            "running today."
        )
    if latest and latest["detection"]["degraded"]:
        notes.append(
            "<b>This run was degraded.</b> Part of the detection pipeline did not run, so this "
            "is a narrower check than a full one — a pass here is a smaller claim."
        )
    if latest and not badge.get("stale"):
        notes.append(
            "<b>This is the latest run, not the best one.</b> The page has no way to show a "
            "flattering result: it always reports whatever was measured most recently."
        )

    notes_html = "".join(f'<p class="note">{n}</p>' for n in notes)
    trend_html = _trend_svg(summary.get("trend") or [])
    if trend_html:
        trend_html = (
            f'<hr><p class="trend-label">Score over the last {len(summary["trend"])} runs</p>'
            f"{trend_html}"
        )

    badge_url = f"{site_url}/a/{slug}/badge.svg"
    page_url = f"{site_url}/a/{slug}"
    snippet = _esc(f"[![privacy]({badge_url})]({page_url})")
    title = f"{name} — privacy score | AgentLeak"

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="An independently measured privacy score for {name}, \
covering what its agent trace exposed and which detection tiers looked.">
<meta property="og:title" content="{_esc(title)}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<meta name="robots" content="index,follow">
<style>{_PAGE_CSS}</style>
</head><body><main class="wrap">
  <p class="eyebrow">Measured by AgentLeak</p>
  <h1>{name}</h1>
  <p class="slug">{slug}</p>

  <div class="score">{score}</div>
  <span class="verdict" style="color:{colour};border-color:{colour}33;background:{colour}14">\
{verdict}</span>

  {notes_html}
  <hr>
  {facts}
  {trend_html}
  <hr>
  <div class="foot">
    <h2>What this page does not show</h2>
    <p>Never the findings themselves. A finding names a real value taken from real data, so
    publishing one here would leak exactly what the score exists to measure. What you get is
    the verdict, the date, and which detectors looked — enough to judge the claim, not enough
    to reconstruct the run.</p>
    <h2>Embed this badge</h2>
    <pre>{snippet}</pre>
    <p><a href="https://github.com/yagobski/agentleak">How the score is measured</a></p>
  </div>
</main></body></html>"""
