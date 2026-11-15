# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Statistics for privacy-leakage experiments, in pure standard-library Python.

Every function here is deterministic: resampling methods take an explicit
``seed`` and use their own :class:`random.Random` instance, so the same inputs
always give the same interval. Nothing requires numpy, scipy or pandas.

Conventions
-----------
* ``confidence`` is the two-sided coverage, e.g. ``0.95``; ``alpha = 1 - confidence``.
* ``z`` is the standard normal quantile ``Phi^-1(1 - alpha/2)`` (1.959964 for 95%),
  computed with :class:`statistics.NormalDist`.
* A proportion with a zero denominator has no estimate: :class:`Proportion`
  stores ``None`` rather than inventing 0 or 1.

References are given per function. Where a function is checked against a
published value, the test that does so names the source.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any

_STD_NORMAL = NormalDist()


def z_value(confidence: float = 0.95) -> float:
    """Two-sided standard normal critical value, ``Phi^-1(1 - alpha/2)``."""
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return _STD_NORMAL.inv_cdf(1.0 - (1.0 - confidence) / 2.0)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Interval:
    """A confidence interval with the method that produced it."""

    low: float
    high: float
    method: str
    confidence: float = 0.95

    def to_dict(self) -> dict[str, Any]:
        return {
            "ci_low": _r(self.low),
            "ci_high": _r(self.high),
            "ci_method": self.method,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class Proportion:
    """``numerator / denominator`` with a confidence interval.

    ``estimate`` and the interval bounds are ``None`` when the denominator is 0.
    """

    numerator: int
    denominator: int
    estimate: float | None
    ci_low: float | None
    ci_high: float | None
    method: str
    confidence: float = 0.95

    def to_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": _r(self.estimate),
            "ci_low": _r(self.ci_low),
            "ci_high": _r(self.ci_high),
            "ci_method": self.method,
            "confidence": self.confidence,
        }

    def fmt(self, digits: int = 3) -> str:
        """``0.930 (93/100; 95% CI 0.863-0.966, wilson)``, or ``n/a (0/0)``."""
        if self.estimate is None or self.ci_low is None or self.ci_high is None:
            return f"n/a ({self.numerator}/{self.denominator})"
        pct = round(self.confidence * 100)
        return (
            f"{self.estimate:.{digits}f} ({self.numerator}/{self.denominator}; "
            f"{pct}% CI {self.ci_low:.{digits}f}-{self.ci_high:.{digits}f}, {self.method})"
        )


@dataclass(frozen=True)
class TestResult:
    """A hypothesis test: statistic, p-value and what was tested."""

    name: str
    statistic: float
    p_value: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "test": self.name,
            "statistic": _r(self.statistic),
            "p_value": _r(self.p_value),
            **self.details,
        }


@dataclass(frozen=True)
class Estimate:
    """A point estimate with an interval (bootstrap or analytic)."""

    estimate: float
    ci_low: float
    ci_high: float
    method: str
    confidence: float = 0.95
    n: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate": _r(self.estimate),
            "ci_low": _r(self.ci_low),
            "ci_high": _r(self.ci_high),
            "ci_method": self.method,
            "confidence": self.confidence,
            "n": self.n,
            **self.details,
        }


def _r(x: float | None, digits: int = 6) -> float | None:
    """Round for serialization so JSON output is stable across platforms."""
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return x
    return round(float(x), digits)


# ---------------------------------------------------------------------------
# Binomial proportions
# ---------------------------------------------------------------------------
def _check_counts(k: int, n: int) -> None:
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"need 0 <= k <= n, got k={k}, n={n}")


def wilson_interval(k: int, n: int, confidence: float = 0.95) -> Proportion:
    """Wilson score interval for a binomial proportion (Wilson, 1927).

    With ``p = k/n`` and ``z = Phi^-1(1 - alpha/2)``::

        centre = (p + z^2/(2n)) / (1 + z^2/n)
        half   = z * sqrt(p(1-p)/n + z^2/(4n^2)) / (1 + z^2/n)
        CI     = [centre - half, centre + half]

    Recommended over the Wald interval for small ``n`` and for ``p`` near 0
    or 1 (Newcombe, 1998, Stat. Med. 17:857-872). Returns ``None`` bounds for
    ``n = 0``.
    """
    _check_counts(k, n)
    method = "wilson"
    if n == 0:
        return Proportion(k, n, None, None, None, method, confidence)
    z = z_value(confidence)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low = 0.0 if k == 0 else max(0.0, centre - half)
    high = 1.0 if k == n else min(1.0, centre + half)
    return Proportion(k, n, p, low, high, method, confidence)


def _binom_logpmf(i: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if i == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if i == n else -math.inf
    return (
        math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        + i * math.log(p) + (n - i) * math.log1p(-p)
    )


def binom_cdf(k: int, n: int, p: float) -> float:
    """``P(X <= k)`` for ``X ~ Binomial(n, p)``, summed in log space."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return min(1.0, sum(math.exp(_binom_logpmf(i, n, p)) for i in range(k + 1)))


def binom_sf(k: int, n: int, p: float) -> float:
    """``P(X >= k)`` for ``X ~ Binomial(n, p)``."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return min(1.0, sum(math.exp(_binom_logpmf(i, n, p)) for i in range(k, n + 1)))


def _bisect(f: Callable[[float], float], lo: float, hi: float, iters: int = 200) -> float:
    """Root of a monotone ``f`` on ``[lo, hi]`` by bisection."""
    f_lo = f(lo)
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        f_mid = f(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
        if hi - lo < 1e-15:
            break
    return (lo + hi) / 2.0


def clopper_pearson_interval(k: int, n: int, confidence: float = 0.95) -> Proportion:
    """Clopper-Pearson "exact" interval (Clopper & Pearson, 1934).

    The bounds invert two one-sided binomial tests::

        p_low  solves  P(X >= k | n, p_low)  = alpha/2   (p_low = 0 if k = 0)
        p_high solves  P(X <= k | n, p_high) = alpha/2   (p_high = 1 if k = n)

    equivalently the ``alpha/2`` and ``1 - alpha/2`` quantiles of
    ``Beta(k, n-k+1)`` and ``Beta(k+1, n-k)``. Solved here by bisection on
    the binomial tail, which is exact up to floating point. Conservative:
    coverage is at least ``confidence`` for every ``p``.
    """
    _check_counts(k, n)
    method = "clopper-pearson"
    if n == 0:
        return Proportion(k, n, None, None, None, method, confidence)
    alpha = 1.0 - confidence
    if k == 0:
        low = 0.0
    else:
        low = _bisect(lambda p: binom_sf(k, n, p) - alpha / 2, 0.0, 1.0)
    if k == n:
        high = 1.0
    else:
        high = _bisect(lambda p: binom_cdf(k, n, p) - alpha / 2, 0.0, 1.0)
    return Proportion(k, n, k / n, low, high, method, confidence)


def proportion(k: int, n: int, method: str = "wilson", confidence: float = 0.95) -> Proportion:
    """A proportion with the named interval: ``wilson`` or ``clopper-pearson``."""
    if method == "wilson":
        return wilson_interval(k, n, confidence)
    if method in ("clopper-pearson", "exact"):
        return clopper_pearson_interval(k, n, confidence)
    raise ValueError(f"unknown interval method {method!r}; use 'wilson' or 'clopper-pearson'")


# ---------------------------------------------------------------------------
# Two proportions
# ---------------------------------------------------------------------------
def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for two proportions (Cohen, 1988)::

        h = 2 asin(sqrt(p1)) - 2 asin(sqrt(p2))

    Rules of thumb (Cohen): 0.2 small, 0.5 medium, 0.8 large. Sign follows
    ``p1 - p2``.
    """
    for p in (p1, p2):
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"proportions must be in [0, 1], got {p}")
    return 2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2))


def risk_difference(k1: int, n1: int, k2: int, n2: int, confidence: float = 0.95) -> Estimate:
    """Difference ``p1 - p2`` of two *independent* proportions with Newcombe's
    hybrid score interval (Newcombe, 1998, Stat. Med. 17:873-890, method 10)::

        (l1, u1), (l2, u2) = Wilson intervals of p1 and p2
        delta = p1 - p2
        low   = delta - sqrt((p1 - l1)^2 + (u2 - p2)^2)
        high  = delta + sqrt((u1 - p1)^2 + (p2 - l2)^2)

    For two configurations scored on the *same* scenarios, use
    :func:`paired_bootstrap_diff` and :func:`mcnemar_exact` instead: the
    samples are not independent.
    """
    if n1 == 0 or n2 == 0:
        raise ValueError("both denominators must be positive")
    a = wilson_interval(k1, n1, confidence)
    b = wilson_interval(k2, n2, confidence)
    assert a.estimate is not None and a.ci_low is not None and a.ci_high is not None
    assert b.estimate is not None and b.ci_low is not None and b.ci_high is not None
    delta = a.estimate - b.estimate
    low = delta - math.sqrt((a.estimate - a.ci_low) ** 2 + (b.ci_high - b.estimate) ** 2)
    high = delta + math.sqrt((a.ci_high - a.estimate) ** 2 + (b.estimate - b.ci_low) ** 2)
    return Estimate(
        delta, max(-1.0, low), min(1.0, high), "newcombe-hybrid-score", confidence, n1 + n2,
        {"cohens_h": _r(cohens_h(a.estimate, b.estimate))},
    )


# ---------------------------------------------------------------------------
# Paired binary outcomes
# ---------------------------------------------------------------------------
def mcnemar_exact(b: int, c: int) -> TestResult:
    """Exact (binomial) McNemar test on the two discordant counts.

    ``b`` = pairs positive under A only, ``c`` = positive under B only. Under
    H0 the discordant pairs split 50/50, so::

        p = min(1, 2 * P(X <= min(b, c))),  X ~ Binomial(b + c, 1/2)

    With no discordant pairs the p-value is 1. Preferred over the chi-square
    form when ``b + c`` is small (< 25 is the usual rule).
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2.0 * binom_cdf(min(b, c), n, 0.5))
    return TestResult("mcnemar-exact", float(min(b, c)), p, {"b": b, "c": c, "discordant": n})


def mcnemar_chi2(b: int, c: int, continuity: bool = True) -> TestResult:
    """McNemar chi-square test, with Edwards' continuity correction by default::

        X2 = (|b - c| - 1)^2 / (b + c)      (continuity-corrected)
        X2 = (b - c)^2 / (b + c)            (uncorrected)
        p  = P(chi2_1 >= X2) = erfc(sqrt(X2 / 2))
    """
    n = b + c
    if n == 0:
        return TestResult("mcnemar-chi2", 0.0, 1.0, {"b": b, "c": c, "continuity": continuity})
    diff = abs(b - c)
    if continuity:
        diff = max(0, diff - 1)
    x2 = diff * diff / n
    p = math.erfc(math.sqrt(x2 / 2.0))
    name = "mcnemar-chi2-cc" if continuity else "mcnemar-chi2"
    return TestResult(name, x2, p, {"b": b, "c": c, "continuity": continuity})


# ---------------------------------------------------------------------------
# Multiple comparisons
# ---------------------------------------------------------------------------
def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values (Holm, 1979).

    Sort ascending ``p_(1) <= ... <= p_(m)``; the adjusted value is::

        p~_(i) = min(1, max_{j <= i} (m - j + 1) * p_(j))

    returned in the *original* order. Reject H_i at level alpha when
    ``p~_i <= alpha``. Controls the family-wise error rate under any
    dependence.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: (p_values[i], i))
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p_values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


# ---------------------------------------------------------------------------
# Trend across ordered groups
# ---------------------------------------------------------------------------
def cochran_armitage(
    successes: Sequence[int], totals: Sequence[int], scores: Sequence[float] | None = None
) -> TestResult:
    """Cochran-Armitage test for a linear trend in proportions (asymptotic).

    Groups ``i`` with ``r_i`` successes out of ``n_i`` and scores ``s_i``
    (default ``0, 1, 2, ...``); ``N = sum n_i``, ``pbar = sum r_i / N``::

        T      = sum s_i (r_i - n_i pbar)
        Var(T) = pbar (1 - pbar) [sum n_i s_i^2 - (sum n_i s_i)^2 / N]
        z      = T / sqrt(Var(T)),   two-sided p = erfc(|z| / sqrt 2)

    (Agresti, *Categorical Data Analysis*, 3rd ed., section 5.3.5.) With small
    counts prefer :func:`exact_trend_test`.
    """
    if len(successes) != len(totals) or not successes:
        raise ValueError("successes and totals must be non-empty and the same length")
    s = list(scores) if scores is not None else [float(i) for i in range(len(totals))]
    if len(s) != len(totals):
        raise ValueError("scores must match the number of groups")
    n_total = sum(totals)
    r_total = sum(successes)
    if n_total == 0:
        raise ValueError("no observations")
    pbar = r_total / n_total
    t = sum(si * (ri - ni * pbar) for si, ri, ni in zip(s, successes, totals, strict=True))
    sxx = sum(ni * si * si for si, ni in zip(s, totals, strict=True))
    sx = sum(ni * si for si, ni in zip(s, totals, strict=True))
    var = pbar * (1 - pbar) * (sxx - sx * sx / n_total)
    if var <= 0:
        return TestResult("cochran-armitage", 0.0, 1.0, {"T": _r(t), "note": "zero variance"})
    z = t / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return TestResult("cochran-armitage", z, p, {"T": _r(t), "alternative": "two-sided"})


def exact_trend_test(
    successes: Sequence[int],
    totals: Sequence[int],
    scores: Sequence[float] | None = None,
    alternative: str = "greater",
) -> TestResult:
    """Exact conditional (permutation) version of the Cochran-Armitage test.

    Conditions on the group sizes ``n_i`` and the total successes ``m``; each
    allocation ``(r_1..r_k)`` with ``sum r_i = m`` has null weight
    ``prod_i C(n_i, r_i)`` (multivariate hypergeometric). The statistic is
    ``T = sum s_i r_i``::

        greater:   p = P(T >= T_obs)
        less:      p = P(T <= T_obs)
        two-sided: p = P(|T - E T| >= |T_obs - E T|)

    The distribution is built by dynamic programming over groups, so it is
    exact and fast for the group sizes seen in scenario corpora.
    """
    if alternative not in ("greater", "less", "two-sided"):
        raise ValueError("alternative must be 'greater', 'less' or 'two-sided'")
    if len(successes) != len(totals) or not successes:
        raise ValueError("successes and totals must be non-empty and the same length")
    s = list(scores) if scores is not None else [float(i) for i in range(len(totals))]
    for ri, ni in zip(successes, totals, strict=True):
        _check_counts(ri, ni)
    m = sum(successes)
    t_obs = sum(si * ri for si, ri in zip(s, successes, strict=True))
    # dist: (successes allocated so far, T so far) -> combinatorial weight
    dist: dict[tuple[int, float], int] = {(0, 0.0): 1}
    for si, ni in zip(s, totals, strict=True):
        nxt: dict[tuple[int, float], int] = {}
        for (used, tval), w in dist.items():
            for r in range(0, min(ni, m - used) + 1):
                key = (used + r, round(tval + si * r, 9))
                nxt[key] = nxt.get(key, 0) + w * math.comb(ni, r)
        dist = nxt
    final = {t: w for (used, t), w in dist.items() if used == m}
    total_w = sum(final.values())
    mean = sum(t * w for t, w in final.items()) / total_w
    eps = 1e-9
    if alternative == "greater":
        tail = sum(w for t, w in final.items() if t >= t_obs - eps)
    elif alternative == "less":
        tail = sum(w for t, w in final.items() if t <= t_obs + eps)
    else:
        dev = abs(t_obs - mean)
        tail = sum(w for t, w in final.items() if abs(t - mean) >= dev - eps)
    return TestResult(
        "exact-trend", t_obs, tail / total_w,
        {"alternative": alternative, "expected_T": _r(mean), "successes_total": m},
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def mean(values: Sequence[float]) -> float:
    """Arithmetic mean (``nan`` for an empty sequence)."""
    return sum(values) / len(values) if values else math.nan


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (Hyndman & Fan type 7, numpy's default)."""
    if not sorted_values:
        raise ValueError("empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def _replicates(
    data: Sequence[Any], statistic: Callable[[Sequence[Any]], float], n_boot: int, seed: int
) -> list[float]:
    rng = random.Random(seed)
    n = len(data)
    reps = []
    for _ in range(n_boot):
        sample = [data[rng.randrange(n)] for _ in range(n)]
        reps.append(statistic(sample))
    reps.sort()
    return reps


def bootstrap_ci(
    data: Sequence[Any],
    statistic: Callable[[Sequence[Any]], float] = mean,
    *,
    n_boot: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
    method: str = "bca",
) -> Estimate:
    """Nonparametric bootstrap interval for ``statistic(data)`` (Efron, 1987).

    Resamples ``data`` with replacement ``n_boot`` times using
    ``random.Random(seed)``; ``theta*_b`` are the sorted replicates.

    * ``percentile``: ``[Q(alpha/2), Q(1 - alpha/2)]`` of the replicates.
    * ``bca`` (bias-corrected and accelerated, Efron & Tibshirani 1993, ch. 14)::

          z0 = Phi^-1( (#{theta*_b < theta_hat} + 0.5 #{theta*_b = theta_hat}) / B )
          a  = sum (tbar - theta_(i))^3 / (6 [sum (tbar - theta_(i))^2]^(3/2))
               with theta_(i) the jackknife leave-one-out estimates
          a1 = Phi(z0 + (z0 + z_{alpha/2})   / (1 - a (z0 + z_{alpha/2})))
          a2 = Phi(z0 + (z0 + z_{1-alpha/2}) / (1 - a (z0 + z_{1-alpha/2})))
          CI = [Q(a1), Q(a2)]

      Falls back to the percentile interval (and says so in ``method``) when
      every replicate is on one side of ``theta_hat``, where ``z0`` is infinite.

    ``data`` may hold any items (numbers, tuples, dicts); ``statistic`` maps a
    resample to a float, so ratio estimators such as ``sum(WSL)/sum(rho)``
    work by passing pairs.
    """
    if method not in ("bca", "percentile"):
        raise ValueError("method must be 'bca' or 'percentile'")
    if not data:
        raise ValueError("cannot bootstrap an empty sample")
    if n_boot < 100:
        raise ValueError("n_boot must be at least 100")
    alpha = 1.0 - confidence
    theta = statistic(data)
    reps = _replicates(data, statistic, n_boot, seed)
    details: dict[str, Any] = {"n_boot": n_boot, "seed": seed}
    if reps[0] == reps[-1]:
        return Estimate(theta, reps[0], reps[-1], f"bootstrap-{method}", confidence, len(data),
                        details)
    if method == "percentile":
        return Estimate(
            theta, quantile(reps, alpha / 2), quantile(reps, 1 - alpha / 2),
            "bootstrap-percentile", confidence, len(data), details,
        )
    below = sum(1 for r in reps if r < theta)
    ties = sum(1 for r in reps if r == theta)
    frac = (below + 0.5 * ties) / n_boot
    if frac <= 0.0 or frac >= 1.0:
        return Estimate(
            theta, quantile(reps, alpha / 2), quantile(reps, 1 - alpha / 2),
            "bootstrap-percentile (bca fallback: z0 infinite)", confidence, len(data), details,
        )
    z0 = _STD_NORMAL.inv_cdf(frac)
    n = len(data)
    jack = [statistic([data[j] for j in range(n) if j != i]) for i in range(n)] if n > 1 else [theta]
    jbar = mean(jack)
    num = sum((jbar - t) ** 3 for t in jack)
    den = 6.0 * (sum((jbar - t) ** 2 for t in jack) ** 1.5)
    accel = num / den if den > 0 else 0.0
    z_lo = _STD_NORMAL.inv_cdf(alpha / 2)
    z_hi = _STD_NORMAL.inv_cdf(1 - alpha / 2)

    def adj(zq: float) -> float:
        return _STD_NORMAL.cdf(z0 + (z0 + zq) / (1 - accel * (z0 + zq)))

    a1, a2 = adj(z_lo), adj(z_hi)
    details = {**details, "z0": _r(z0), "acceleration": _r(accel)}
    return Estimate(theta, quantile(reps, a1), quantile(reps, a2), "bootstrap-bca",
                    confidence, len(data), details)


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = mean,
    *,
    n_boot: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> Estimate:
    """Paired bootstrap percentile interval for ``statistic(b) - statistic(a)``.

    ``a[i]`` and ``b[i]`` are the same unit (scenario) under two
    configurations. Each replicate draws unit indices with replacement and
    keeps the pairs together, so the between-unit correlation is preserved::

        d*_b = statistic(b[I_b]) - statistic(a[I_b]),   I_b ~ U{0..n-1}^n
        CI   = [Q(alpha/2), Q(1 - alpha/2)] of d*

    For a 0/1 outcome and the mean statistic this is the paired difference in
    rates; report it with :func:`mcnemar_exact`.
    """
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    if not a:
        raise ValueError("cannot bootstrap an empty sample")
    alpha = 1.0 - confidence
    rng = random.Random(seed)
    n = len(a)
    reps = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        reps.append(statistic([b[i] for i in idx]) - statistic([a[i] for i in idx]))
    reps.sort()
    est = statistic(b) - statistic(a)
    return Estimate(
        est, quantile(reps, alpha / 2), quantile(reps, 1 - alpha / 2),
        "paired-bootstrap-percentile", confidence, n, {"n_boot": n_boot, "seed": seed},
    )


def sign_flip_test(diffs: Sequence[float], *, n_resamples: int = 20000, seed: int = 0,
                   exact_limit: int = 16) -> TestResult:
    """Two-sided paired permutation (sign-flip) test of ``mean(diffs) = 0``.

    Under H0 each paired difference is equally likely to have either sign::

        p = #{ s in {-1,1}^n : |sum s_i d_i| >= |sum d_i| } / 2^n

    Enumerated exactly when ``n <= exact_limit`` (2^16 = 65,536 assignments);
    otherwise estimated from ``n_resamples`` seeded random sign vectors as
    ``(hits + 1) / (n_resamples + 1)``. Zero differences are kept: they do not
    change the statistic.
    """
    d = [float(x) for x in diffs]
    n = len(d)
    if n == 0:
        return TestResult("sign-flip", 0.0, 1.0, {"n": 0})
    obs = abs(sum(d))
    eps = 1e-12 * max(1.0, obs)
    if n <= exact_limit:
        hits = 0
        for signs in itertools.product((1.0, -1.0), repeat=n):
            if abs(sum(s * x for s, x in zip(signs, d, strict=True))) >= obs - eps:
                hits += 1
        return TestResult("sign-flip-exact", sum(d), hits / 2**n, {"n": n, "assignments": 2**n})
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_resamples):
        total = sum(x if rng.random() < 0.5 else -x for x in d)
        if abs(total) >= obs - eps:
            hits += 1
    return TestResult(
        "sign-flip-monte-carlo", sum(d), (hits + 1) / (n_resamples + 1),
        {"n": n, "resamples": n_resamples, "seed": seed},
    )


# ---------------------------------------------------------------------------
# Rank agreement
# ---------------------------------------------------------------------------
def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float:
    """Kendall's tau-b rank correlation (handles ties), O(n^2)::

        tau_b = (C - D) / sqrt((n0 - n1)(n0 - n2))

    with ``C``/``D`` concordant/discordant pairs, ``n0 = n(n-1)/2`` and
    ``n1``/``n2`` the pairs tied in ``x``/``y``. Returns ``nan`` when either
    ranking is constant.
    """
    if len(x) != len(y):
        raise ValueError("x and y must have the same length")
    n = len(x)
    conc = disc = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 and dy == 0:
                tx += 1
                ty += 1
            elif dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif (dx > 0) == (dy > 0):
                conc += 1
            else:
                disc += 1
    n0 = n * (n - 1) / 2
    denom = math.sqrt((n0 - tx) * (n0 - ty))
    return (conc - disc) / denom if denom else math.nan


# ---------------------------------------------------------------------------
# Detection metrics
# ---------------------------------------------------------------------------
def detection_metrics(
    tp: int, fp: int, fn: int, tn: int, *, method: str = "wilson", confidence: float = 0.95
) -> dict[str, Any]:
    """Precision, recall, specificity (each with an interval) and F1.

    ::

        recall      = TP / (TP + FN)        (sensitivity)
        specificity = TN / (TN + FP)
        precision   = TP / (TP + FP)
        F1          = 2 TP / (2 TP + FP + FN)

    Precision and F1 depend on the ratio of positives to negatives in the
    corpus, which is set by construction in a benchmark; report them next to
    the negative set they were computed against. F1 has no closed-form
    interval here; bootstrap the units if you need one.
    """
    f1_den = 2 * tp + fp + fn
    return {
        "recall": proportion(tp, tp + fn, method, confidence),
        "specificity": proportion(tn, tn + fp, method, confidence),
        "precision": proportion(tp, tp + fp, method, confidence),
        "f1": (2 * tp / f1_den) if f1_den else None,
        "counts": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


__all__ = [
    "Estimate",
    "Interval",
    "Proportion",
    "TestResult",
    "binom_cdf",
    "binom_sf",
    "bootstrap_ci",
    "clopper_pearson_interval",
    "cochran_armitage",
    "cohens_h",
    "detection_metrics",
    "exact_trend_test",
    "holm_bonferroni",
    "kendall_tau_b",
    "mcnemar_chi2",
    "mcnemar_exact",
    "mean",
    "paired_bootstrap_diff",
    "proportion",
    "quantile",
    "risk_difference",
    "sign_flip_test",
    "wilson_interval",
    "z_value",
]
