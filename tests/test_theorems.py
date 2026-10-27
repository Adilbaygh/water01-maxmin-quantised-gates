"""Randomised checks of Theorems 1-4 on the abstract quantised actuator (quantmaxmin.execution) and of the exact
quantised level (quantmaxmin.allocation) against a mixed-integer programme."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantmaxmin.allocation import (continuous_level, epsilon_star, price_of_indivisibility,  # noqa: E402
                                    quantised_level, quantised_level_milp, required_volume)
from quantmaxmin.execution import (carry_over, equal_split_day, equal_split_m, exclusion_threshold,  # noqa: E402
                                   floor_rule_day, theta_rule_day)

N = 96
TOL = 1e-9


def day(rng, k, g_lo=1.0, spread=0.4):
    """Step volumes of one resolution step over a day with a varying level: g in [g_lo, g_lo (1 + spread)]."""
    return g_lo * (1.0 + spread * rng.random(N))


# Theorem 2 -----------------------------------------------------------------------------------------------------------
def random_instance(rng):
    n = int(rng.integers(2, 8))
    D = rng.uniform(1.0, 100.0, n)
    q = rng.uniform(0.0, 60.0, n) * (rng.random(n) < 0.9)
    V = rng.uniform(0.0, 1.5) * D.sum()
    return V, D, q


def test_quantised_level_matches_milp():
    rng = np.random.default_rng(1)
    for _ in range(150):
        V, D, q = random_instance(rng)
        assert quantised_level(V, D, q) == pytest.approx(quantised_level_milp(V, D, q), abs=1e-6)


def test_theorem2_formula_bounds_and_conditions():
    rng = np.random.default_rng(2)
    checked = 0
    for _ in range(4000):
        V, D, q = random_instance(rng)
        lam = continuous_level(V, D); lq = quantised_level(V, D, q); pi = lam - lq
        assert -TOL <= pi <= lam + TOL
        if V < q.sum():
            assert lq == 0.0                                            # Theorem 2(c): someone gets no water
            continue
        if lam < 1.0:                                                   # deficit day, Theorem 2(a)
            assert pi == pytest.approx(epsilon_star(V, D, q), abs=1e-8)
            assert pi <= q.sum() / D.sum() + TOL
            assert (pi <= 1e-10) == bool(np.all(lam * D >= q - 1e-9))
            checked += 1
        else:                                                           # Theorem 2(b)
            assert (pi <= 1e-10) == (V >= np.maximum(D, q).sum() - 1e-9)
        if lq > 0:
            assert required_volume(lq, D, q) <= V * (1 + 1e-12) + 1e-9
    assert checked > 1000


def test_theorem2_bound_is_attained_asymptotically():
    # one outlet with a quantum, the others continuous: Pi_ind -> sum q / sum D as the quantum outlet's share vanishes
    D = np.array([1e-6, 100.0]); q = np.array([10.0, 0.0]); V = 50.0
    assert price_of_indivisibility(V, D, q) == pytest.approx(q.sum() / D.sum(), rel=1e-4)


# Theorem 1 -----------------------------------------------------------------------------------------------------------
def test_theorem1a_exclusion_under_floor_rounding():
    rng = np.random.default_rng(3)
    for _ in range(3000):
        k = int(rng.integers(2, 11)); g = day(rng, k)
        q_min = k * g.min()
        x = rng.uniform(1e-6, 1.0) * exclusion_threshold(q_min, k) * (1 - 1e-12)
        frac = rng.uniform(0.2, 1.0)
        V = floor_rule_day(x, g, k, request=lambda i, R: R * frac if rng.random() < 0.5 else R)
        assert V == 0.0


def test_theorem1a_threshold_is_sharp_at_constant_level():
    for k in range(2, 11):
        g = np.ones(N)
        assert floor_rule_day(exclusion_threshold(k, k) * (1 - 1e-9), g, k) == 0.0
        assert floor_rule_day(exclusion_threshold(k, k) * (1 + 1e-9), g, k) > 0.0


def test_theorem1b_equal_split():
    rng = np.random.default_rng(4)
    n_cases = 0
    for _ in range(3000):
        k = int(rng.integers(2, 11)); g = day(rng, k)
        q_max, g_max = k * g.max(), g.max()
        n_max = int(rng.integers(math.ceil((2 * q_max + 3 * g_max) / g.min()), 60 * k))
        c_step = n_max * g.min()                                       # always executable step volume
        x = rng.uniform(q_max, math.ceil(N / 2) * (c_step - g_max))
        m = equal_split_m(x, q_max, g_max, c_step, N)
        assert m is not None and 1 <= m <= math.ceil(N / 2)
        V, ok = equal_split_day(x, g, k, n_max, m)
        assert ok and abs(V - x) <= g_max / 2 + 1e-9
        n_cases += 1
    assert n_cases == 3000


def test_equal_split_with_spread_schedule_of_the_simulation_rule():
    # the rule of scripts/rules.py: m = min(ceil(N/2), max(1, floor(x / (q_max + g_max)))), open steps floor(i N / m)
    rng = np.random.default_rng(5)
    for _ in range(3000):
        k = int(rng.integers(2, 11)); g = day(rng, k)
        q_max, g_max = k * g.max(), g.max()
        n_max = 200 * k
        x = rng.uniform(q_max, 0.9 * N * (k + 1) * g.min())
        m = int(min(math.ceil(N / 2), max(1, math.floor(x / (q_max + g_max)))))
        if x / m + g_max > n_max * g.min():
            continue
        V, ok = equal_split_day(x, g, k, n_max, m, spread=True)
        assert ok and abs(V - x) <= g_max / 2 + 1e-9


# Theorem 3 -----------------------------------------------------------------------------------------------------------
def test_theorem3_theta_rule_bounds():
    rng = np.random.default_rng(6)
    for _ in range(5000):
        k = int(rng.integers(2, 11)); g = day(rng, k)
        p_min, p_max = (k + 1) * g.min(), (k + 1) * g.max()
        theta = float(rng.choice([0.0, 0.25, 0.5, 0.75, 1.0, rng.random()]))
        x = rng.uniform(1e-3, 0.999) * N * p_min                       # F3: the plan fits into the day
        V, pulses = theta_rule_day(x, g, k, theta)
        assert pulses >= 1
        assert V >= x - theta * min(p_max, x) - 1e-9
        assert V < x + p_max
        if theta == 0.0:
            assert V >= x - 1e-9


# Theorem 4 -----------------------------------------------------------------------------------------------------------
def test_theorem4_carry_over():
    rng = np.random.default_rng(7)
    for _ in range(400):
        k = int(rng.integers(2, 11)); T = int(rng.integers(2, 40))
        g_days = [day(rng, k) for _ in range(T)]
        p_max = (k + 1) * max(g.max() for g in g_days)
        theta = float(rng.choice([0.0, 0.25, 0.5, 0.75, 1.0]))
        x = rng.uniform(0.0, 3.0, T) * (k + 1) * min(g.min() for g in g_days)
        V, e, xt = carry_over(x, g_days, k, theta)
        assert np.all(e > -p_max - 1e-9) and np.all(e <= theta * p_max + 1e-9)
        assert V.sum() >= x.sum() - theta * p_max - 1e-9
        assert V.sum() < x.sum() + p_max + 1e-9
        D = x / rng.uniform(0.3, 1.0, T)                                # x = lambda* D with lambda* <= 1
        D[D == 0] = 1.0
        lam_bar = x.sum() / D.sum()
        r = min(1.0, V.sum() / D.sum())
        assert r >= lam_bar - theta * p_max / (T * D.mean()) - 1e-9


def test_daily_satisfaction_below_one_quantum_is_zero_or_one():
    rng = np.random.default_rng(8)
    for _ in range(2000):
        k = int(rng.integers(2, 11)); g = day(rng, k)
        q_min = k * g.min()
        Dj = rng.uniform(0.05, 0.999) * q_min
        x = rng.uniform(0.0, 1.0) * Dj
        V, _ = theta_rule_day(x, g, k, float(rng.random())) if x > 0 else (0.0, 0)
        r = min(1.0, V / Dj)
        assert r in (0.0, 1.0)
