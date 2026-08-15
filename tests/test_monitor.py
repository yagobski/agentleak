# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Continuous watch, and the ways a monitor makes itself useless.

Two failure modes, both fatal in practice: alert on every wobble and people mute
it; stay quiet through a real regression and it may as well not be running.
Every test below pins one of those.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentleak.monitor import MIN_SAMPLES, Alert, Monitor


def report(score: int, *, levels: list[int] | None = None) -> dict[str, Any]:
    return {
        "privacy_score": score,
        "findings": [{"level": level} for level in (levels or [])],
    }


def feed(monitor: Monitor, scores: list[int]) -> None:
    for score in scores:
        monitor.record(report(score))


# ------------------------------------------------------- not too talkative
def test_one_bad_sample_does_not_raise_an_alert() -> None:
    """A monitor that pages on a single unlucky run gets muted by lunchtime."""
    monitor = Monitor(drop=10)
    assert monitor.record(report(20)) is None


def test_no_trend_is_claimed_before_there_are_samples() -> None:
    monitor = Monitor()
    feed(monitor, [90] * (MIN_SAMPLES - 1))
    assert monitor.status()["has_trend"] is False
    assert monitor.status()["alerts"] == []


def test_a_steady_low_score_is_not_alerted_every_run() -> None:
    """A service that has always sat at 70 does not need telling hourly."""
    monitor = Monitor(drop=10)
    feed(monitor, [70] * 40)
    drops = [a for a in monitor.alerts if a.kind == "score_drop"]
    assert drops == [], "a flat line raised a regression alert"


def test_small_wobbles_stay_quiet() -> None:
    monitor = Monitor(drop=10)
    feed(monitor, [90, 88, 91, 89, 92, 87, 90, 89, 91, 88])
    assert monitor.alerts == []


# ---------------------------------------------------------- not too quiet
def test_a_real_regression_is_reported() -> None:
    monitor = Monitor(drop=10)
    feed(monitor, [95] * 10)          # establish a baseline
    feed(monitor, [55] * 15)          # the deployment gets worse

    drops = [a for a in monitor.alerts if a.kind == "score_drop"]
    assert drops, "a 40-point fall went unreported"
    assert drops[0].baseline > drops[0].current


def test_a_severity_never_seen_before_is_reported_immediately() -> None:
    """Waiting for a trend before mentioning a first L4 is waiting too long."""
    monitor = Monitor()
    feed(monitor, [95] * 10)
    alert = monitor.record(report(95, levels=[4]))
    assert alert is not None
    assert alert.kind == "new_critical"
    assert "L4" in alert.message


def test_the_same_severity_is_only_announced_once() -> None:
    monitor = Monitor()
    monitor.record(report(90, levels=[4]))
    before = len(monitor.alerts)
    for _ in range(5):
        monitor.record(report(90, levels=[4]))
    assert len(monitor.alerts) == before


def test_a_floor_catches_a_slide_that_never_drops_sharply() -> None:
    """Gradual decay never trips a drop threshold; the floor is what does."""
    monitor = Monitor(drop=50, floor=80)
    feed(monitor, [79] * MIN_SAMPLES)
    assert any(a.kind == "score_drop" for a in monitor.alerts)


def test_the_baseline_never_decays_toward_a_regression() -> None:
    """A baseline that follows a slow slide makes the slide invisible."""
    monitor = Monitor(drop=15)
    feed(monitor, [95] * 10)
    baseline = monitor.status()["baseline"]
    feed(monitor, [85] * 10)          # a drift too small to alert on
    assert monitor.status()["baseline"] >= baseline


# ------------------------------------------------------------- sampling
def test_sampling_counts_every_run_and_scores_a_fraction() -> None:
    monitor = Monitor(sample=0.5)
    taken = sum(monitor.should_sample() for _ in range(2000))
    assert monitor.observed == 2000
    assert 800 < taken < 1200, "sampling was not close to the requested rate"


def test_a_full_sample_rate_takes_everything() -> None:
    monitor = Monitor(sample=1.0)
    assert all(monitor.should_sample() for _ in range(50))


@pytest.mark.parametrize("bad", [0, -0.1, 1.5])
def test_an_impossible_sample_rate_is_refused_at_construction(bad: float) -> None:
    with pytest.raises(ValueError):
        Monitor(sample=bad)


# -------------------------------------------------------------- callback
def test_the_callback_receives_the_alert() -> None:
    seen: list[Alert] = []
    monitor = Monitor(drop=10, on_alert=seen.append)
    feed(monitor, [95] * 10)
    feed(monitor, [50] * 10)
    assert seen and seen[0].kind == "score_drop"


def test_a_throwing_callback_cannot_break_the_agent() -> None:
    """The monitor rides in a production hot path; it must never be the cause."""
    def explode(_: Alert) -> None:
        raise RuntimeError("pager is down")

    monitor = Monitor(drop=10, on_alert=explode)
    feed(monitor, [95] * 10)
    feed(monitor, [40] * 10)          # a real regression, so an alert fires
    assert monitor.alerts, "the fixture never triggered an alert to throw on"


# ---------------------------------------------------------------- status
def test_status_is_serializable_and_says_whether_it_knows_anything() -> None:
    import json

    monitor = Monitor()
    json.loads(json.dumps(monitor.status()))
    assert monitor.status()["current"] is None
    assert monitor.status()["healthy"] is True

    feed(monitor, [90] * MIN_SAMPLES)
    assert monitor.status()["current"] == 90
    assert monitor.status()["has_trend"] is True
