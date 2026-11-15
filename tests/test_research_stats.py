# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""agentleak.research.stats against published values and hand computations.

Published reference values: Newcombe RG (1998). Two-sided confidence intervals
for the single proportion: comparison of seven methods. Stat Med 17:857-872,
Table II (Wilson "score" and Clopper-Pearson "exact" columns); and Newcombe RG
(1998). Interval estimation for the difference between independent
proportions. Stat Med 17:873-890, example (a), method 10.
"""

from __future__ import annotations

import itertools
import math
import random

import pytest

from agentleak.research import stats

# (k, n, wilson_low, wilson_high, exact_low, exact_high) -- Newcombe 1998, Table II.
NEWCOMBE_TABLE_II = [
    (81, 263, 0.2553, 0.3662, 0.2527, 0.3676),
    (15, 148, 0.0624, 0.1605, 0.0578, 0.1617),
    (0, 20, 0.0, 0.1611, 0.0, 0.1684),
    (1, 29, 0.0061, 0.1718, 0.0009, 0.1776),
]


@pytest.mark.parametrize("k,n,wl,wh,el,eh", NEWCOMBE_TABLE_II)
def test_wilson_and_exact_match_newcombe_table(k, n, wl, wh, el, eh):
    w = stats.wilson_interval(k, n)
    e = stats.clopper_pearson_interval(k, n)
    assert w.ci_low == pytest.approx(wl, abs=5e-5)
    assert w.ci_high == pytest.approx(wh, abs=5e-5)
    assert e.ci_low == pytest.approx(el, abs=1e-4)
    assert e.ci_high == pytest.approx(eh, abs=1e-4)
    assert w.estimate == pytest.approx(k / n)


def test_clopper_pearson_closed_forms_at_the_boundaries():
    # k = 0: upper = 1 - (alpha/2)^(1/n); k = n: lower = (alpha/2)^(1/n).
    for n in (1, 5, 10, 37):
        zero = stats.clopper_pearson_interval(0, n)
        full = stats.clopper_pearson_interval(n, n)
        assert zero.ci_low == 0.0
        assert zero.ci_high == pytest.approx(1 - 0.025 ** (1 / n), abs=1e-9)
        assert full.ci_high == 1.0
        assert full.ci_low == pytest.approx(0.025 ** (1 / n), abs=1e-9)


def test_wilson_handles_empty_denominator_without_inventing_a_rate():
    p = stats.wilson_interval(0, 0)
    assert p.estimate is None and p.ci_low is None and p.ci_high is None
    assert p.fmt() == "n/a (0/0)"
    with pytest.raises(ValueError):
        stats.wilson_interval(3, 2)


def test_proportion_dispatches_and_rejects_unknown_method():
    assert stats.proportion(3, 10, "clopper-pearson").method == "clopper-pearson"
    assert stats.proportion(3, 10).method == "wilson"
    with pytest.raises(ValueError):
        stats.proportion(3, 10, "wald")


def test_risk_difference_matches_newcombe_method_10():
    # Newcombe 1998 (b), example (a): 56/70 vs 48/80 -> 0.2000 (0.0524, 0.3339).
    d = stats.risk_difference(56, 70, 48, 80)
    assert d.estimate == pytest.approx(0.2)
    assert d.ci_low == pytest.approx(0.0524, abs=1e-4)
    assert d.ci_high == pytest.approx(0.3339, abs=1e-4)


def test_cohens_h_hand_value_and_sign():
    h = stats.cohens_h(0.5, 0.25)
    assert h == pytest.approx(2 * math.asin(math.sqrt(0.5)) - 2 * math.asin(0.5))
    assert h == pytest.approx(0.5236, abs=1e-4)
    assert stats.cohens_h(0.25, 0.5) == pytest.approx(-h)
    with pytest.raises(ValueError):
        stats.cohens_h(1.2, 0.1)


def test_mcnemar_exact_and_chi_square_by_hand():
    # b=1, c=9: n=10, P(X<=1) = 11/1024, two-sided p = 22/1024.
    exact = stats.mcnemar_exact(1, 9)
    assert exact.p_value == pytest.approx(22 / 1024)
    # Continuity-corrected X2 = (|1-9|-1)^2/10 = 4.9.
    cc = stats.mcnemar_chi2(1, 9)
    assert cc.statistic == pytest.approx(4.9)
    assert cc.p_value == pytest.approx(math.erfc(math.sqrt(4.9 / 2)))
    raw = stats.mcnemar_chi2(1, 9, continuity=False)
    assert raw.statistic == pytest.approx(6.4)
    assert stats.mcnemar_exact(0, 0).p_value == 1.0
    assert stats.mcnemar_exact(5, 5).p_value == pytest.approx(1.0)


def test_holm_bonferroni_by_hand():
    adjusted = stats.holm_bonferroni([0.01, 0.04, 0.03, 0.005])
    # sorted: 0.005*4=0.02, 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> monotone 0.06
    assert adjusted == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert stats.holm_bonferroni([0.9, 0.8]) == pytest.approx([1.0, 1.0])
    assert stats.holm_bonferroni([]) == []


def test_cochran_armitage_by_hand():
    # r = 1,3,6 of 10 each, scores 1,2,3: pbar = 1/3, T = 5,
    # Var = (1/3)(2/3)(140 - 3600/30) = 40/9, z = 5 / sqrt(40/9).
    res = stats.cochran_armitage([1, 3, 6], [10, 10, 10], [1, 2, 3])
    z = 5 / math.sqrt(40 / 9)
    assert res.statistic == pytest.approx(z)
    assert res.p_value == pytest.approx(math.erfc(z / math.sqrt(2)))


def _brute_force_trend(successes, totals, scores):
    m = sum(successes)
    t_obs = sum(s * r for s, r in zip(scores, successes, strict=True))
    total = tail = 0
    for alloc in itertools.product(*[range(n + 1) for n in totals]):
        if sum(alloc) != m:
            continue
        w = math.prod(math.comb(n, r) for n, r in zip(totals, alloc, strict=True))
        total += w
        if sum(s * r for s, r in zip(scores, alloc, strict=True)) >= t_obs:
            tail += w
    return tail / total


@pytest.mark.parametrize("successes,totals", [([1, 3, 6], [10, 10, 10]), ([0, 2, 3], [3, 5, 4]),
                                              ([2, 2], [6, 6])])
def test_exact_trend_matches_brute_force_enumeration(successes, totals):
    scores = list(range(1, len(totals) + 1))
    res = stats.exact_trend_test(successes, totals, scores)
    assert res.p_value == pytest.approx(_brute_force_trend(successes, totals, scores))


def test_exact_trend_alternatives_are_consistent():
    greater = stats.exact_trend_test([1, 3, 6], [10, 10, 10]).p_value
    less = stats.exact_trend_test([1, 3, 6], [10, 10, 10], alternative="less").p_value
    two = stats.exact_trend_test([1, 3, 6], [10, 10, 10], alternative="two-sided").p_value
    assert greater < 0.05 < less
    assert greater <= two <= 1.0
    with pytest.raises(ValueError):
        stats.exact_trend_test([1], [2], alternative="sideways")


def test_quantile_type7():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert stats.quantile(xs, 0.0) == 1.0
    assert stats.quantile(xs, 1.0) == 4.0
    assert stats.quantile(xs, 0.5) == pytest.approx(2.5)
    assert stats.quantile(xs, 0.25) == pytest.approx(1.75)


def test_bootstrap_is_seeded_and_sensible():
    rng = random.Random(7)
    xs = [rng.gauss(10, 2) for _ in range(60)]
    a = stats.bootstrap_ci(xs, seed=3)
    b = stats.bootstrap_ci(xs, seed=3)
    c = stats.bootstrap_ci(xs, seed=4)
    assert a == b
    assert a != c
    assert a.ci_low < stats.mean(xs) < a.ci_high
    # For a roughly symmetric mean, BCa and percentile agree closely and both
    # bracket the t-interval half-width within a tolerance.
    pct = stats.bootstrap_ci(xs, seed=3, method="percentile")
    assert abs(a.ci_low - pct.ci_low) < 0.15 and abs(a.ci_high - pct.ci_high) < 0.15
    sd = math.sqrt(sum((x - stats.mean(xs)) ** 2 for x in xs) / (len(xs) - 1))
    half = 2.0 * sd / math.sqrt(len(xs))
    assert (a.ci_high - a.ci_low) / 2 == pytest.approx(half, rel=0.2)


def test_bootstrap_degenerate_and_ratio_statistics():
    flat = stats.bootstrap_ci([0.0] * 20, seed=1)
    assert flat.ci_low == flat.ci_high == 0.0
    pairs = [(1, 4), (2, 4), (0, 3), (3, 5)]
    est = stats.bootstrap_ci(
        pairs, lambda xs: sum(p[0] for p in xs) / sum(p[1] for p in xs), seed=0
    )
    assert est.estimate == pytest.approx(6 / 16)
    assert 0.0 <= est.ci_low <= est.estimate <= est.ci_high <= 1.0
    with pytest.raises(ValueError):
        stats.bootstrap_ci([], seed=0)
    with pytest.raises(ValueError):
        stats.bootstrap_ci([1.0, 2.0], method="studentized")


def test_paired_bootstrap_diff_keeps_pairs_together():
    a = [0.1 * i for i in range(30)]
    b = [x + 0.5 for x in a]  # constant shift: every resample differs by exactly 0.5
    d = stats.paired_bootstrap_diff(a, b, seed=0)
    assert d.estimate == pytest.approx(0.5)
    assert d.ci_low == pytest.approx(0.5) and d.ci_high == pytest.approx(0.5)
    with pytest.raises(ValueError):
        stats.paired_bootstrap_diff([1.0], [1.0, 2.0])


def test_sign_flip_exact_by_hand_and_monte_carlo():
    # diffs 1,1,1: |sum| >= 3 only for all-plus or all-minus -> p = 2/8.
    assert stats.sign_flip_test([1, 1, 1]).p_value == pytest.approx(0.25)
    assert stats.sign_flip_test([]).p_value == 1.0
    big = stats.sign_flip_test([1.0] * 30, n_resamples=2000, seed=1)
    assert big.name == "sign-flip-monte-carlo"
    assert big.p_value < 0.01
    assert stats.sign_flip_test([1.0] * 30, n_resamples=2000, seed=1) == big


def test_kendall_tau_b_known_values():
    assert stats.kendall_tau_b([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert stats.kendall_tau_b([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert stats.kendall_tau_b([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(4 / 6)
    assert math.isnan(stats.kendall_tau_b([1, 1, 1], [1, 2, 3]))


def test_detection_metrics_by_hand():
    m = stats.detection_metrics(tp=8, fp=2, fn=2, tn=8)
    assert m["recall"].estimate == pytest.approx(0.8)
    assert m["specificity"].estimate == pytest.approx(0.8)
    assert m["precision"].estimate == pytest.approx(0.8)
    assert m["f1"] == pytest.approx(0.8)
    assert stats.detection_metrics(0, 0, 0, 5)["f1"] is None


def test_z_value_and_validation():
    assert stats.z_value(0.95) == pytest.approx(1.959964, abs=1e-6)
    with pytest.raises(ValueError):
        stats.z_value(1.0)


def test_tiny_p_values_survive_serialization():
    res = stats.mcnemar_exact(0, 31)
    assert res.p_value == pytest.approx(2 * 0.5**31)
    assert res.to_dict()["p_value"] > 0
    assert stats.fmt_p(res.p_value) == "<0.0001"
    assert stats.fmt_p(0.0321) == "0.0321"
