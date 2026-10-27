"""Abstract quantised actuator and the execution rules of Theorems 1, 3 and 4.

Actuator (simulation core, water01.iot.devices.quantize): the opening is n rho with an integer n; from the position
n_prev a command n is executed when n = 0 (full closure) or |n - n_prev| >= k, otherwise the position is kept. A
commanded opening is rounded to the nearest grid point. With relation (6) the volume of a step at opening n rho and
level h is n g(h), so that the quantum is q(h) = k g(h) and the pulse volume is p(h) = (k + 1) g(h).

The level of every step is known exactly and constant within the step (assumption F2), a closed gate passes no water
(F1) and the gate is closed at the start of the day (F3). A day is described by the sequence g_seq of the step volumes
of one resolution step, g_seq[i] = g(h_i).
"""
import math

import numpy as np


class Actuator:
    """Grid actuator with a deadband of k resolution steps and n_max steps of travel."""

    def __init__(self, k, n_max=10 ** 9, position=0):
        self.k, self.n_max, self.n = int(k), int(n_max), int(position)

    def command(self, n_cmd):
        n_cmd = int(min(max(n_cmd, 0), self.n_max))
        if n_cmd == 0 or abs(n_cmd - self.n) >= self.k:
            self.n = n_cmd
        return self.n


def nearest(v, g):
    """Grid steps nearest to the volume v (ties rounded up)."""
    return int(math.floor(v / g + 0.5))


def exclusion_threshold(q_min, k):
    """Theorem 1(a): floor rounding leaves an outlet dry for 0 < x < (1 - 1 / (2 k)) q_min."""
    return (1.0 - 1.0 / (2.0 * k)) * q_min


def floor_rule_day(x, g_seq, k, request=None, n_max=10 ** 9):
    """Floor rounding: at every step the request u <= R (remaining plan) is rounded to the nearest grid point.
    request(i, R) -> u (default u = R). Returns the delivered volume."""
    act = Actuator(k, n_max); V = 0.0
    for i, g in enumerate(g_seq):
        R = x - V
        u = R if request is None else request(i, R)
        if u > R + 1e-12:
            raise ValueError("floor rounding requests at most the remaining plan")
        V += act.command(nearest(max(u, 0.0), g)) * g
    return V


def equal_split_m(x, q_max, g_max, c_step, N):
    """Number of open steps of Theorem 1(b): m = ceil(x / (C - g_max)); None when the conditions of the theorem fail."""
    if c_step < 2 * q_max + 3 * g_max or not (q_max <= x <= math.ceil(N / 2) * (c_step - g_max)):
        return None
    return int(math.ceil(x / (c_step - g_max)))


def equal_split_day(x, g_seq, k, n_max, m, spread=False):
    """Equal split: m open steps separated by closed steps (steps 0, 2, 4, ... or, with spread, floor(i N / m));
    at the i-th open step the remaining part of the cumulative target i x / m is rounded to the grid.
    Returns (delivered volume, all open-step commands executed as issued and not below k)."""
    N = len(g_seq)
    steps = [int(math.floor(i * N / m)) for i in range(m)] if spread else [2 * i for i in range(m)]
    if len(set(steps)) != m or steps[-1] >= N or any(b - a < 2 for a, b in zip(steps, steps[1:])):
        raise ValueError("the open steps must be separated by closed steps within the day")
    act = Actuator(k, n_max); V = 0.0; ok = True; i = 0
    for s, g in enumerate(g_seq):
        if i < m and s == steps[i]:
            i += 1
            n_cmd = nearest(i * x / m - V, g)
            n = act.command(n_cmd)
            ok &= (n == n_cmd) and n_cmd >= k
            V += n * g
        else:
            act.command(0)
    return V, ok


def theta_rule_day(x, g_seq, k, theta):
    """Theta pulse rule in the pulse regime: a pulse (opening k + 1) when R > 0 and R >= theta min{p, x}, otherwise
    closure. Returns (delivered volume, number of pulses)."""
    act = Actuator(k); V = 0.0; pulses = 0
    for g in g_seq:
        p = (k + 1) * g; R = x - V
        if R > 0 and R >= theta * min(p, x):
            V += act.command(k + 1) * g; pulses += 1
        else:
            act.command(0)
    return V, pulses


def carry_over(x_days, g_days, k, theta):
    """Theorem 4: x~(s) = x(s) + e(s - 1), e(s) = x~(s) - V(s), e(0) = 0; closed for the day when x~(s) <= 0.
    Returns (V [T], e [T], x~ [T])."""
    T = len(x_days); V = np.zeros(T); e = np.zeros(T); xt = np.zeros(T); prev = 0.0
    for s in range(T):
        xt[s] = x_days[s] + prev
        V[s] = theta_rule_day(xt[s], g_days[s], k, theta)[0] if xt[s] > 0 else 0.0
        e[s] = xt[s] - V[s]; prev = e[s]
    return V, e, xt


def period_satisfaction(V, D, T):
    """r^T over consecutive blocks of T days (the last incomplete block is dropped): min{1, sum V / sum D}."""
    V = np.asarray(V, float); D = np.asarray(D, float)
    nb = V.size // T
    if nb == 0:
        return np.array([])
    Vb = V[:nb * T].reshape(nb, T).sum(axis=1); Db = D[:nb * T].reshape(nb, T).sum(axis=1)
    return np.minimum(1.0, Vb / Db)
