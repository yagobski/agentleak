"""The public trust page, and the ways a badge could quietly lie.

A badge is a claim made to someone who will not read the report behind it. Every
test here is about one specific way that claim could be more flattering than the
run it came from.
"""

from __future__ import annotations

import time
from typing import Any

from agentleak.web.trust import (
    STALE_AFTER_DAYS,
    badge_state,
    badge_svg,
    public_summary,
)


def run(
    *,
    score: int = 95,
    verdict: str = "Pass",
    days_ago: float = 0,
    degraded: bool = False,
    tiers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "created_at": time.time() - days_ago * 86400,
        "privacy_score": score,
        "risk_index": 0.0,
        "verdict": verdict,
        "report": {
            "degraded": degraded,
            "detection": {"mode": "fast", "tiers": tiers or ["regex"], "degraded": degraded},
            "channel_risks": [{"channel": "tool_call"}],
            "findings": [{"redacted_value": "sk-**", "channel": "tool_call"}],
        },
    }


# ------------------------------------------------- a badge must not flatter
def test_a_stale_score_stops_claiming_to_be_current() -> None:
    """A green badge from months ago says nothing about today's code."""
    state = badge_state(run(score=100, days_ago=STALE_AFTER_DAYS + 1))
    assert state["stale"] is True
    assert "stale" in state["message"]
    assert state["colour"] != "#3fb950", "a stale run still showed the passing colour"


def test_a_fresh_perfect_score_is_allowed_to_be_green() -> None:
    state = badge_state(run(score=100, days_ago=1))
    assert state["stale"] is False
    assert state["colour"] == "#3fb950"


def test_a_degraded_run_can_never_show_green() -> None:
    """A pass from a narrower pipeline is a narrower claim, and must look it."""
    state = badge_state(run(score=100, degraded=True))
    assert state["colour"] != "#3fb950"


def test_a_failing_verdict_is_red_whatever_the_score_says() -> None:
    assert badge_state(run(score=99, verdict="Fail"))["colour"] == "#f85149"


def test_no_run_reads_as_not_checked_not_as_passing() -> None:
    state = badge_state(None)
    assert state["message"] == "not checked"
    assert state["colour"] != "#3fb950"


def test_the_badge_reports_the_latest_run_not_the_best_one() -> None:
    """Cherry-picking is the third way a badge lies, so the page picks for you."""
    runs = [run(score=40, verdict="Fail"), run(score=100, days_ago=2)]
    summary = public_summary({"name": "a", "public_slug": "a"}, runs)
    assert summary["latest"]["score"] == 40
    assert summary["badge"]["colour"] == "#f85149"


# -------------------------------------------------------------- the SVG
def test_the_badge_needs_nothing_from_the_network() -> None:
    """GitHub's image proxy runs no scripts and fetches no fonts."""
    svg = badge_svg(badge_state(run()))
    # The xmlns is a namespace identifier, not a fetch; these are fetches.
    for forbidden in ("<script", "<image", "@import", "xlink:href", "<foreignObject", "src="):
        assert forbidden not in svg, f"badge reaches for {forbidden}"
    # url(#id) is an internal reference; url(http…) would not be.
    assert "url(http" not in svg
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_the_badge_is_readable_without_looking_at_it() -> None:
    svg = badge_svg(badge_state(run(score=72)))
    assert 'role="img"' in svg
    assert "72/100" in svg
    assert "<title>" in svg


def test_a_hostile_label_cannot_break_out_of_the_markup() -> None:
    svg = badge_svg({"label": '"><script>x</script>', "message": "1", "colour": "#000"})
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


# ------------------------------------------------ what a stranger may see
def test_the_public_summary_never_exposes_a_finding() -> None:
    """Findings name real values from someone's private data."""
    summary = public_summary({"name": "a", "public_slug": "a"}, [run()])
    rendered = repr(summary)
    assert "sk-**" not in rendered
    assert "findings" not in rendered


def test_the_public_summary_names_the_tiers_that_ran() -> None:
    summary = public_summary({"name": "a", "public_slug": "a"}, [run(tiers=["regex"])])
    assert summary["latest"]["detection"]["tiers"] == ["regex"]


def test_the_trend_shows_a_direction_without_rebuilding_a_run() -> None:
    runs = [run(score=90), run(score=80, days_ago=1), run(score=70, days_ago=2)]
    trend = public_summary({"name": "a", "public_slug": "a"}, runs)["trend"]
    assert [point["score"] for point in trend] == [90, 80, 70]
    assert all(set(point) == {"at", "score"} for point in trend)


def test_a_project_with_no_runs_still_renders() -> None:
    summary = public_summary({"name": "a", "public_slug": "a"}, [])
    assert summary["latest"] is None
    assert summary["badge"]["message"] == "not checked"


# ------------------------------------------------- the page behind the badge
def page(**kw: Any) -> str:
    from agentleak.web.trust import trust_page_html
    runs = kw.pop("runs", None)
    if runs is None:
        runs = [run(**kw)] if kw or not kw.get("empty") else []
    return trust_page_html(
        public_summary({"name": "Support bot", "public_slug": "support-bot"}, runs),
        site_url="https://www.agentleak.org",
    )


def test_the_page_shows_the_verdict_and_never_a_finding() -> None:
    """Following the badge must not hand over the private values it measured."""
    html = page()
    assert "95" in html and "Pass" in html
    assert "sk-**" not in html


def test_the_page_needs_nothing_from_the_network() -> None:
    """A page that renders blank without a CDN cannot be used to check a claim."""
    html = page()
    for forbidden in ("<script", "@import", "src=", "cdn.", "fonts.googleapis"):
        assert forbidden not in html, f"page reaches for {forbidden}"


def test_a_stale_page_says_so_in_words_not_just_colour() -> None:
    html = page(days_ago=STALE_AFTER_DAYS + 12)
    assert "stale" in html.lower()


def test_a_degraded_run_is_called_out_on_the_page() -> None:
    assert "degraded" in page(degraded=True).lower()


def test_the_page_admits_it_shows_the_latest_run() -> None:
    """Someone checking a badge deserves to know it was not cherry-picked."""
    assert "latest run, not the best" in page()


def test_the_page_names_the_tiers_that_ran() -> None:
    assert "entropy" in page(tiers=["regex", "entropy"])


def test_a_hostile_project_name_cannot_inject_markup() -> None:
    from agentleak.web.trust import trust_page_html
    html = trust_page_html(
        public_summary({"name": "<script>x</script>", "public_slug": "a"}, [run()]),
        site_url="",
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_a_project_with_no_runs_still_renders_a_page() -> None:
    from agentleak.web.trust import trust_page_html
    html = trust_page_html(public_summary({"name": "a", "public_slug": "a"}, []), site_url="")
    assert "Not checked" in html


def test_one_run_draws_no_trend_line() -> None:
    """A line through a single point invents a direction that was never measured."""
    assert "<polyline" not in page(runs=[run()])
    assert "<polyline" in page(runs=[run(score=90), run(score=70, days_ago=1)])


def test_the_page_offers_the_badge_snippet_it_describes() -> None:
    html = page()
    assert "/a/support-bot/badge.svg" in html


def test_the_age_reads_like_something_a_person_would_say() -> None:
    from agentleak.web.trust import _age_phrase
    assert _age_phrase(0.4) == "today"
    assert _age_phrase(1.2) == "yesterday"
    assert _age_phrase(9.9) == "9 days ago"


def test_the_page_uses_no_definition_tag_outside_a_list() -> None:
    """A <dt> loose in the body is invalid markup; browsers style it unpredictably."""
    html = page(runs=[run(score=90), run(score=70, days_ago=1)])
    assert html.count("<dt") == html.count("</dt>")
    assert "<dl>" in html and html.index("<dl>") < html.index("<dt")
