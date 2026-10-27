"""Randomised checks of Theorems 1-4 on the abstract quantised actuator (quantmaxmin.execution) and of the exact
minimum-delivery and whole-step levels (quantmaxmin.allocation) against a mixed-integer programme and an enumeration."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantmaxmin.allocation import (continuous_level, epsilon_star, price_of_indivisibility,  # noqa: E402
                                    quantised_level, quantised_level_milp, required_volume, whole_step_level,
                                    whole_step_level_enumerated, whole_step_lower_bound)
from quantmaxmin.execution import (Actuator, carry_over, direct_execution_day, equal_split_day,  # noqa: E402
                                   equal_split_m, exclusion_threshold, theta_rule_day)

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
            assert lq == 0.0                                            # Theorem 2(d): someone gets no water
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


def whole_step_instance(rng, n_grid):
    """n_grid outlets with a quantum and a step grid, and one or two outlets without a quantum (q = v = 0)."""
    n_free = int(rng.integers(1, 3))
    v = np.r_[rng.uniform(0.5, 4.0, n_grid), np.zeros(n_free)]
    k = rng.integers(2, 11, n_grid)
    q = np.r_[k * v[:n_grid], np.zeros(n_free)]
    D = np.r_[rng.uniform(0.2, 3.0, n_grid) * q[:n_grid], rng.uniform(5.0, 200.0, n_free)]
    V = rng.uniform(0.3, 1.3) * D.sum()
    return V, D, q, v


def test_whole_step_level_matches_enumeration():
    rng = np.random.default_rng(11)
    for _ in range(300):
        V, D, q, v = whole_step_instance(rng, int(rng.integers(1, 4)))
        assert whole_step_level(V, D, q, v) == pytest.approx(whole_step_level_enumerated(V, D, q, v), abs=1e-9)


def test_theorem2c_whole_step_bracket():
    # counterexample of a minimum-delivery level that whole steps cannot reach: D = (6, 6), W = 11, q = (5, 0), v = (1, 0)
    assert quantised_level(11.0, [6.0, 6.0], [5.0, 0.0]) == pytest.approx(11 / 12)
    assert whole_step_level(11.0, [6.0, 6.0], [5.0, 0.0], [1.0, 0.0]) == pytest.approx(5 / 6, abs=1e-9)
    rng = np.random.default_rng(12)
    for _ in range(3000):
        V, D, q, v = whole_step_instance(rng, int(rng.integers(1, 7)))
        lq = quantised_level(V, D, q); lv = whole_step_level(V, D, q, v)
        D0 = D[v == 0].sum()
        assert lv <= lq + 1e-9
        assert lv >= lq - v.sum() / D0 - 1e-9


def test_theorem2c_all_outlets_quantised():
    # the bound of part (c) needs no outlet without a quantum; in the counterexample it is attained: tau = 5/6
    assert whole_step_lower_bound(11.0, [6.0, 6.0], [5.0, 0.0], [1.0, 0.0]) == pytest.approx(5 / 6)
    rng = np.random.default_rng(14)
    n_pos = 0
    for i in range(3000):
        n = int(rng.integers(1, 5))
        v = rng.uniform(0.5, 4.0, n); k = rng.integers(2, 11, n); q = k * v
        D = rng.uniform(0.5, 6.0, n) * q
        V = rng.uniform(0.3, 1.3) * D.sum()
        lq = quantised_level(V, D, q); lv = whole_step_level(V, D, q, v); tau = whole_step_lower_bound(V, D, q, v)
        assert tau - 1e-9 <= lv <= lq + 1e-9
        if n <= 3 and i < 600:
            assert lv == pytest.approx(whole_step_level_enumerated(V, D, q, v), abs=1e-9)
        n_pos += tau > 0
    assert n_pos > 1000


def test_theorem2c_condition_for_a_gate_with_a_nonlinear_discharge():
    """Appendix A: at a constant level, a gate whose one-step volume P(n) increases with the opening, with quantum
    q = P(k), largest one-step increment v and full-opening volume C >= 2q, delivers a volume in [y, y + v] for every
    q <= y <= (N - 3) C, from the closed or an open position: m fully open steps, a closure and up to two openings
    from the closed position, all executed by the actuator (3)."""
    rng = np.random.default_rng(15)
    checked = 0
    for _ in range(2000):
        k = int(rng.integers(2, 11)); n_max = int(rng.integers(50, 1001))
        a, b = rng.uniform(0.5, 5.0), rng.uniform(0.0, 0.02)
        P = lambda n: a * n / (1.0 + b * n)                                       # noqa: E731
        q, C = P(k), P(n_max)
        v = max(P(n + 1) - P(n) for n in range(k, n_max))
        if C < 2 * q:
            continue
        y = rng.uniform(q, (N - 3) * C)
        start = 0 if rng.random() < 0.5 else int(rng.integers(1, n_max + 1))
        m = max(0, math.ceil((y - 2 * C) / C)); r = y - m * C
        grid = np.array([P(n) for n in range(k, n_max + 1)])
        up = lambda z: k + int(np.searchsorted(grid, z - 1e-12))                  # noqa: E731  smallest n, P(n) >= z
        trims = [up(r)] if r <= C else ([n_max, up(r - C)] if r - C >= q else [up(r - q), k])
        plan = [0] + [n_max] * m + [0]                                           # close, full steps, close
        for i, n in enumerate(trims):
            plan += [0, n] if i else [n]                                         # openings from the closed position
        assert len(plan) <= N
        plan += [0] * (N - len(plan))                                            # closed for the rest of the day
        act = Actuator(k, n_max, position=start); total = 0.0
        for n in plan:
            pos = act.command(n)
            assert pos == n                                                      # every command is executed
            total += P(pos) if pos > 0 else 0.0
        assert y - 1e-9 <= total <= y + v + 1e-9
        checked += 1
    assert checked > 1500


def test_corollary1_node_level_with_a_free_outlet():
    # theta = 0 at every quantised outlet: each receives at least its plan and less than one pulse more, so the outlet
    # without a quantum, which receives the rest, loses less than the sum of the pulses
    rng = np.random.default_rng(13)
    for _ in range(500):
        n = int(rng.integers(1, 6)); k = int(rng.integers(2, 11))
        g_days = [day(rng, k) for _ in range(n)]
        p_max = np.array([(k + 1) * g.max() for g in g_days])
        x = np.array([rng.uniform(1e-3, 0.9) * N * (k + 1) * g.min() for g in g_days])
        D0 = rng.uniform(10.0, 1e4); lam = rng.uniform(0.05, 1.0); x0 = lam * D0
        W = x.sum() + x0
        V = np.array([theta_rule_day(x[j], g_days[j], k, 0.0)[0] for j in range(n)])
        V0 = W - V.sum()
        assert np.all(V >= x - 1e-9)
        assert V0 / D0 > lam - p_max.sum() / D0 - 1e-12


# Theorem 1 -----------------------------------------------------------------------------------------------------------
def test_theorem1a_exclusion_under_direct_execution():
    rng = np.random.default_rng(3)
    for _ in range(3000):
        k = int(rng.integers(2, 11)); g = day(rng, k)
        q_min = k * g.min()
        x = rng.uniform(1e-6, 1.0) * exclusion_threshold(q_min, k) * (1 - 1e-12)
        frac = rng.uniform(0.2, 1.0)
        V = direct_execution_day(x, g, k, request=lambda i, R: R * frac if rng.random() < 0.5 else R)
        assert V == 0.0


def test_theorem1a_threshold_is_sharp_at_constant_level():
    for k in range(2, 11):
        g = np.ones(N)
        assert direct_execution_day(exclusion_threshold(k, k) * (1 - 1e-9), g, k) == 0.0
        assert direct_execution_day(exclusion_threshold(k, k) * (1 + 1e-9), g, k) > 0.0


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
