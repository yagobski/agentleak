# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Continuous watch: sample production runs and notice when they get worse.

A one-shot audit tells you about the code you had on the day you ran it.
Agents drift — a prompt changes, a tool is added, a model is swapped — and the
next leak arrives without a release to blame. This is the piece that turns a
one-off verdict into something that keeps watching.

Three decisions shape it, and each one is about not being annoying enough to get
switched off:

**Sampling, because scoring every run costs latency in a hot path.** The default
is 5%, chosen so a service doing a thousand runs an hour still gets fifty
measurements — plenty for a trend, cheap enough that nobody reaches for the off
switch.

**A trend, not a single reading.** Any one run can score badly for an innocent
reason. A monitor that pages on one bad sample teaches people to ignore it, so
the alert compares a rolling window against a baseline.

**Alerting on the change, not the level.** A service that has always sat at 78
does not need telling every hour. What matters is a *drop*, or a severity that
was not there before.

Everything is local and in-process. No thread, no timer, no network unless the
surrounding `watch()` was already configured to submit.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Enough runs that one unlucky sample cannot move the mean much, few enough
# that a real regression shows up within minutes rather than hours.
WINDOW = 20

# Below this many samples, there is no trend yet and saying otherwise is noise.
MIN_SAMPLES = 5

# A drop this size is worth interrupting someone for; smaller is drift.
DEFAULT_DROP = 10


@dataclass
class Alert:
    """Something changed for the worse, with enough context to act."""

    kind: str                      # "score_drop" | "new_critical"
    message: str
    current: float
    baseline: float
    samples: int
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "current": round(self.current, 1),
            "baseline": round(self.baseline, 1),
            "samples": self.samples,
            "at": self.at,
        }


class Monitor:
    """Watches sampled runs and reports regressions.

    Thread-safe because production agents are usually concurrent, and a torn
    read of the window would produce an alert nobody can reproduce.
    """

    def __init__(
        self,
        *,
        sample: float = 0.05,
        drop: float = DEFAULT_DROP,
        floor: float | None = None,
        on_alert: Callable[[Alert], None] | None = None,
        window: int = WINDOW,
    ) -> None:
        if not 0 < sample <= 1:
            raise ValueError("sample must be a fraction between 0 (exclusive) and 1")
        self.sample = sample
        self.drop = drop
        self.floor = floor
        self.on_alert = on_alert
        self._scores: deque[float] = deque(maxlen=window)
        self._baseline: float | None = None
        self._seen_levels: set[int] = set()
        self._lock = threading.Lock()
        self.alerts: list[Alert] = []
        self.observed = 0
        self.sampled = 0

    # -- sampling --------------------------------------------------------
    def should_sample(self) -> bool:
        """Whether to score this run. Counts every run, samples a fraction."""
        with self._lock:
            self.observed += 1
            take = random.random() < self.sample
            if take:
                self.sampled += 1
        return take

    # -- observing -------------------------------------------------------
    def record(self, report: dict[str, Any]) -> Alert | None:
        """Feed one scored run in. Returns an alert if this run raised one."""
        score = float(report.get("privacy_score", 100))
        levels = {
            int(f.get("level", 0))
            for f in (report.get("findings") or [])
            if int(f.get("level", 0)) >= 3
        }

        with self._lock:
            self._scores.append(score)
            samples = len(self._scores)
            current = sum(self._scores) / samples
            baseline = self._baseline
            # A severity this deployment had never produced before.
            unseen = levels - self._seen_levels
            self._seen_levels |= levels

            alert: Alert | None = None
            if unseen and samples >= 1:
                worst = max(unseen)
                alert = Alert(
                    kind="new_critical",
                    message=(
                        f"First L{worst} finding seen on this deployment. "
                        "Something the monitor had not observed before is leaking."
                    ),
                    current=score,
                    baseline=baseline if baseline is not None else score,
                    samples=samples,
                )
            elif samples >= MIN_SAMPLES and baseline is not None and baseline - current >= self.drop:
                alert = Alert(
                    kind="score_drop",
                    message=(
                        f"Privacy score fell {baseline - current:.0f} points "
                        f"({baseline:.0f} → {current:.0f}) over the last {samples} sampled runs."
                    ),
                    current=current,
                    baseline=baseline,
                    samples=samples,
                )
            elif samples >= MIN_SAMPLES and self.floor is not None and current < self.floor:
                alert = Alert(
                    kind="score_drop",
                    message=f"Privacy score {current:.0f} is below the floor of {self.floor:.0f}.",
                    current=current,
                    baseline=self.floor,
                    samples=samples,
                )

            # The baseline only ever follows the window once there is a window
            # to follow. Setting it from the first sample would make that run
            # the standard everything else is judged against.
            if samples >= MIN_SAMPLES:
                if self._baseline is None:
                    self._baseline = current
                elif alert is None:
                    # Track improvement, never decay toward a regression: a
                    # baseline that drifts down turns a slow leak invisible.
                    self._baseline = max(self._baseline, current)

            if alert:
                self.alerts.append(alert)

        if alert and self.on_alert:
            # Outside the lock: a slow or throwing callback must not block or
            # poison the agent that is only trying to answer a user.
            try:
                self.on_alert(alert)
            except Exception:  # noqa: BLE001
                pass
        return alert

    # -- reading ---------------------------------------------------------
    def status(self) -> dict[str, Any]:
        """Where things stand, for a dashboard, a log line, or an exit code."""
        with self._lock:
            samples = len(self._scores)
            current = sum(self._scores) / samples if samples else None
            return {
                "observed": self.observed,
                "sampled": self.sampled,
                "sample_rate": self.sample,
                "window": samples,
                "current": None if current is None else round(current, 1),
                "baseline": None if self._baseline is None else round(self._baseline, 1),
                "has_trend": samples >= MIN_SAMPLES,
                "alerts": [a.to_dict() for a in self.alerts[-10:]],
                "healthy": not self.alerts,
            }
