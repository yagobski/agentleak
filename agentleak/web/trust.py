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
from pathlib import Path
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
                "tone": "stale", "stale": True, "reason": "no run recorded yet"}

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
            "tone": "stale",
            "stale": True,
            "reason": f"last checked {int(age)} days ago",
            "score": score,
        }

    if verdict in ("Fail", "High risk") or score < 60:
        tone = "fail"
    elif degraded or verdict == "Conditional pass" or score < 85:
        # A degraded run can never show green. Silence about a tier that did not
        # run is exactly how a weak claim passes for a strong one.
        tone = "warn"
    else:
        tone = "pass"

    # `tone` is the meaning; `colour` is one rendering of it. The badge wants
    # the shields palette so it sits naturally beside other README badges, the
    # page wants the site's. Deriving both from one decision is what stops them
    # ever disagreeing about whether a run passed.
    return {
        "label": "privacy",
        "message": f"{score}/100",
        "colour": COLOURS[tone],
        "tone": tone,
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


_FONT_DIR = Path(__file__).resolve().parent / "static" / "assets"

# The site's own two faces, already shipped with the package for its product UI.
# Resolved by glob because the filenames carry a build hash: a missing file just
# means the page falls back to the system grotesque rather than 404-ing for a
# font, which is the right failure for a page whose job is to load.
_FONT_FILES = (
    ("Hanken Grotesk Variable", "hanken-grotesk-latin-wght-normal-*.woff2", "100 900"),
    ("JetBrains Mono", "jetbrains-mono-latin-400-normal-*.woff2", "400"),
    ("JetBrains Mono", "jetbrains-mono-latin-500-normal-*.woff2", "500"),
)


def _font_faces() -> str:
    rules = []
    for family, pattern, weight in _FONT_FILES:
        try:
            match = next(iter(sorted(_FONT_DIR.glob(pattern))), None)
        except OSError:  # pragma: no cover - unreadable static dir
            match = None
        if match:
            rules.append(
                f'@font-face{{font-family:"{family}";font-style:normal;'
                f"font-weight:{weight};font-display:swap;"
                f'src:url("/assets/{match.name}") format("woff2")}}'
            )
    return "".join(rules)


# The site's tokens, transcribed rather than imported: this page is served by
# the package, and a self-hosted install has no marketing stylesheet to borrow
# from. Dark is the default because that is the site's default; a light OS gets
# the site's own light palette rather than an inverted guess at one.
_PAGE_CSS = """
:root{
 --paper:#080909;--raised:#0c0c0b;--ink:#f1f1ed;--muted:#9e9d96;--dim:#babab4;
 --line:#252520;--soft:#1a1a18;--code:#101010;--accent:#ff8257;
 --ok:hsl(160 62% 50%);--warn:hsl(45 93% 58%);--bad:hsl(0 80% 65%);--none:#77766f;
 --wrap:720px;--gutter:clamp(20px,3vw,32px);
 color-scheme:dark}
@media(prefers-color-scheme:light){:root{
 --paper:#fff;--raised:#fafafa;--ink:#191913;--muted:#77766e;--dim:#56564f;
 --line:#dfdfda;--soft:#e6e6e4;--code:#f1f1ef;
 --ok:hsl(160 50% 38%);--warn:hsl(42 90% 42%);--bad:hsl(0 72% 50%);--none:#77766f;
 color-scheme:light}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
 font-family:"Hanken Grotesk Variable","Helvetica Neue",Helvetica,Arial,sans-serif;
 font-size:15px;line-height:1.5;font-feature-settings:"ss01","cv11";
 -webkit-font-smoothing:antialiased}
a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
a:hover{border-color:var(--muted)}
.wrap{max-width:var(--wrap);margin:0 auto;padding:72px var(--gutter) 96px}
.eyebrow{display:flex;align-items:center;gap:8px;margin:0 0 14px;color:var(--accent);
 font:500 10px/1 "JetBrains Mono",monospace;letter-spacing:.09em;text-transform:uppercase}
.mark{flex:0 0 auto;display:block}
h1{margin:0 0 6px;font-size:34px;line-height:1.1;font-weight:500;letter-spacing:-.03em}
.slug{margin:0 0 44px;color:var(--muted);font:400 12px/1 "JetBrains Mono",monospace}
.score{display:flex;align-items:baseline;gap:14px;margin:0 0 14px}
.score b{font:400 62px/1 "JetBrains Mono",monospace;letter-spacing:-.06em}
.score i{color:var(--muted);font:400 15px/1 "JetBrains Mono",monospace;font-style:normal}
.verdict{display:inline-flex;min-height:25px;align-items:center;padding:0 11px;
 border:1px solid var(--line);border-radius:999px;
 font:500 9.5px/1 "JetBrains Mono",monospace;letter-spacing:.06em;text-transform:uppercase}
.note{margin:26px 0 0;padding:16px 18px;border:1px solid var(--soft);border-radius:8px;
 background:var(--raised);font-size:14px;line-height:1.65;color:var(--dim)}
.note b{color:var(--ink);font-weight:550}
hr{border:0;border-top:1px solid var(--line);margin:44px 0}
dl{display:grid;grid-template-columns:1fr 1fr;gap:26px 32px;margin:0}
dt{margin:0 0 6px;color:var(--muted);
 font:500 10px/1 "JetBrains Mono",monospace;letter-spacing:.08em;text-transform:uppercase}
dd{margin:0;font-size:15px}
dd code,.tier{display:inline-block;margin:0 4px 4px 0;padding:4px 9px;
 border:1px solid var(--soft);border-radius:999px;background:var(--raised);
 font:400 11px/1 "JetBrains Mono",monospace;color:var(--dim)}
.trend-label{margin:0 0 10px;color:var(--muted);
 font:500 10px/1 "JetBrains Mono",monospace;letter-spacing:.08em;text-transform:uppercase}
.foot{color:var(--muted);font-size:14px;line-height:1.7}
.foot h2{margin:0 0 8px;color:var(--ink);font-size:14px;font-weight:550;letter-spacing:-.01em}
.foot p{margin:0 0 26px;max-width:640px}
pre{margin:0 0 26px;padding:16px 18px;overflow-x:auto;
 border:1px solid var(--soft);border-radius:8px;background:var(--code);
 font:400 11.5px/1.7 "JetBrains Mono",monospace;color:var(--dim)}
@media(max-width:560px){
 .wrap{padding-top:52px}dl{grid-template-columns:1fr}
 h1{font-size:27px}.score b{font-size:50px}}
"""

# The AgentLeak mark, drawn in currentColor so one copy serves both of the
# site's themes — the brand ships a black file and a white file, and a page that
# carries both palettes would otherwise need logic to pick between them. Only the
# glyph: the wordmark would just repeat the line of text sitting next to it.
_MARK = (
    '<svg class="mark" viewBox="-6 71 266 292" width="15" height="16" '
    'aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M254.055 120.935C254.055 120.935 221.678 112.525 189.301 99.4902C160.288 87.7168 136.32 73 136.32 73C136.32 73 112.773 88.1373 83.3397 99.4902C51.3832 112.525 19.0062 120.514 18.5857 120.935C16.0629 135.231 14.8014 150.368 14.8014 165.506C14.8014 168.869 14.8014 170.551 15.2219 173.915C16.9038 191.996 48.8603 183.166 60.2133 178.961C61.4747 178.54 63.1566 177.7 64.4181 177.279C68.6229 175.597 72.8277 173.915 77.4529 171.813C86.283 168.028 95.5336 163.403 105.205 158.357C119.08 150.789 133.377 142.379 145.571 132.708C127.49 157.096 88.8059 186.109 45.4965 204.61C34.564 209.236 19.4267 215.122 8.91471 214.702C-3.69969 214.281 0.505106 216.384 1.34607 216.804C14.8014 223.532 22.3701 233.203 26.1544 242.033C28.6773 247.92 37.5073 257.17 85.0216 232.782C111.932 218.907 146.412 199.144 181.312 171.392C182.573 170.551 183.834 169.29 185.096 168.449C192.664 162.142 200.654 155.835 208.222 149.107C190.142 185.689 139.264 228.157 77.8734 259.693C58.5313 269.785 53.4856 271.046 45.076 273.989C33.723 277.774 22.7905 276.092 22.7905 278.194C22.3701 281.138 37.0869 284.081 52.2242 299.218C66.1 313.094 101 297.116 115.717 289.127C132.115 279.876 161.549 261.375 181.312 244.135C185.096 240.772 188.46 237.408 191.824 234.044C177.107 268.944 145.571 294.172 103.943 317.719C93.4312 323.606 75.771 328.652 68.2024 330.754C66.1 331.595 63.1566 331.595 63.1566 332.857C63.1566 335.38 79.9758 337.061 90.9083 342.948C106.046 350.937 116.558 355.142 120.342 356.404C125.388 358.506 130.854 359.767 136.32 361.029C208.643 345.051 257.418 262.216 257.418 165.085C257.839 150.368 256.577 135.231 254.055 120.935Z"/>'
    "</svg>"
)


# tone -> the site's severity ramp. The badge keeps the shields palette; this is
# the same decision wearing the site's clothes.
_TONE_VAR = {"pass": "var(--ok)", "warn": "var(--warn)", "fail": "var(--bad)",
             "stale": "var(--none)"}


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

    # A fixed 0–100 axis, because an auto-scaled one turns a wobble between 97
    # and 99 into a cliff. But a fixed axis only tells the truth if it is tall
    # enough to resolve it: squeezed into a sparkline, a real thirty-point climb
    # flattens into a straight line, and the graph understates instead of
    # exaggerating. So the axis is drawn, labelled, and given room.
    w, h = 600, 150
    left, top, bottom = 34, 12, 126
    span = bottom - top

    def y_for(score: float) -> float:
        return top + (100 - score) / 100 * span

    step = (w - left) / (len(scores) - 1)
    coords = " ".join(f"{left + i * step:.1f},{y_for(s):.1f}" for i, s in enumerate(scores))
    last_x, last_y = coords.split(" ")[-1].split(",")

    grid = "".join(
        f'<line x1="{left}" x2="{w}" y1="{y_for(v):.1f}" y2="{y_for(v):.1f}" '
        f'stroke="currentColor" stroke-opacity="{0.14 if v else 0.22}"/>'
        f'<text x="{left - 9}" y="{y_for(v) + 3.5:.1f}" text-anchor="end" '
        f'fill="currentColor" fill-opacity=".45" '
        f'font-family="JetBrains Mono, monospace" font-size="9.5">{v}</text>'
        for v in (100, 50, 0)
    )
    return (
        f'<svg class="trend" viewBox="0 0 {w} {h}" width="100%" role="img" '
        f'aria-label="Score out of 100 over the last {len(scores)} runs, '
        f'oldest first: {", ".join(str(s) for s in scores)}">'
        f"{grid}"
        f'<polyline fill="none" stroke="#ff8257" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{coords}"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="3.5" fill="#ff8257"/>'
        "</svg>"
    )


def trust_page_html(summary: dict[str, Any], *, site_url: str = "") -> str:
    """Render the public page. Self-contained, and never shows a finding."""
    badge = summary["badge"]
    latest = summary.get("latest")
    name = _esc(str(summary.get("name") or "This agent"))
    slug = _esc(str(summary.get("slug") or ""))
    tone = _TONE_VAR.get(str(badge.get("tone") or "stale"), "var(--none)")

    if latest:
        verdict = _esc(str(latest["verdict"] or "unknown"))
        score = f'<b style="color:{tone}">{latest["score"]}</b><i>/ 100</i>'
        tiers = latest["detection"]["tiers"]
        tier_html = (
            "".join(f'<span class="tier">{_esc(str(t))}</span>' for t in tiers)
            if tiers else "—"
        )
        facts = f"""
    <dl>
      <div><dt>Last checked</dt><dd>{_esc(_age_phrase(_age_days(float(latest["at"]))))}</dd></div>
      <div><dt>Risk index</dt><dd>{latest["risk_index"]:.3f}</dd></div>
      <div><dt>Detection tiers that ran</dt><dd>{tier_html}</dd></div>
      <div><dt>Channels examined</dt><dd>{latest["channels_checked"]}</dd></div>
      <div><dt>Detection mode</dt><dd><code>{_esc(str(latest["detection"]["mode"]))}</code></dd></div>
      <div><dt>Runs recorded</dt><dd>{summary["runs_recorded"]}</dd></div>
    </dl>"""
    else:
        verdict = "not checked"
        score = f'<b style="color:{tone}">—</b>'
        facts = ""

    # The warnings are the page. A reader who skims should still leave knowing
    # what this number does not cover.
    notes = []
    if badge.get("stale"):
        notes.append(
            f"<b>This score is stale.</b> It was measured "
            f"{_esc(str(badge.get('reason', 'some time ago')))}, and describes the code as it was "
            f"then. Anything older than {summary['stale_after_days']} days says nothing about "
            "what is running today."
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
            f'<hr><p class="trend-label">Score over the last '
            f'{len(summary["trend"])} runs</p>{trend_html}'
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
<style>{_font_faces()}{_PAGE_CSS}</style>
</head><body><main class="wrap">
  <p class="eyebrow">{_MARK}<span>Measured by AgentLeak</span></p>
  <h1>{name}</h1>
  <p class="slug">{slug}</p>

  <div class="score">{score}</div>
  <span class="verdict" style="color:{tone};border-color:{tone}">{verdict}</span>

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
    <p><a href="https://www.agentleak.org">How the score is measured</a></p>
  </div>
</main></body></html>"""
