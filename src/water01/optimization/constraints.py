"""Sections 2.4-2.5: planning constraints.

1. Daily water balance Σ_j x_{j,p} ≤ A_p = η·S_p and variable bounds (capacity, r ≤ 1, executed days).
2. Retention of the previous stage optimum: x ≥ (λ* − ε1)·D (and μ* − ε1 for the current day in Stage 1b).
3. Integrator-delay (ID) model (8) and its identification from the Saint-Venant plant.
4. Command constraint (9): chord (secant) interpolant of the concave gate limit, which is conservative.
"""
import math

import numpy as np
from scipy.sparse import lil_matrix

from ..domain.passport import value


# --- 1. balance and bounds
def daily_balance(J, P):
    """Matrix [P × J·P] for Σ_j x_{j,p} ≤ A_p."""
    Ab = lil_matrix((P, J * P))
    for p in range(P):
        for j in range(J):
            Ab[p, j * P + p] = 1.0
    return Ab


def variable_bounds(D, U, fixed):
    """lb, ub [J×P] and the mask of executed pairs. ub = min(U, D) (r ≤ 1, capacity); D = 0 -> 0."""
    J, P = D.shape
    pos = D > 0
    ub = np.where(pos, np.minimum(U, D), 0.0)
    lb = np.zeros((J, P))
    is_fixed = np.zeros((J, P), bool)
    for (j, p), v in (fixed or {}).items():
        lb[j, p] = ub[j, p] = v; is_fixed[j, p] = True
    return lb, ub, is_fixed


def effective_supply(A, lb):
    """A_eff = max(A, Σ_j lb), so that executed days cannot make the problem infeasible."""
    return np.maximum(A, lb.sum(axis=0))


def retained_bounds(lb, ub, D, floor):
    """2. Optimum retention: x ≥ floor·D (no constraint where floor = −∞); never exceeds ub."""
    J, P = D.shape
    xb = [(max(lb[j, p], floor[j, p] * D[j, p]) if np.isfinite(floor[j, p]) else lb[j, p], ub[j, p])
          for j in range(J) for p in range(P)]
    return [(min(a, b), b) for a, b in xb]


# --- 3. ID model (8)
def id_step(level_m, delayed_inlet_m3s, outlets_m3s, barrier_m3s, storage_area_m2, dt_s, eta):
    """(8): A_s (h[k+1] − h[k]) / Δt = η Q(0, k−d) − Σ q_j − Q_C."""
    return level_m + dt_s * (eta * delayed_inlet_m3s - sum(outlets_m3s) - barrier_m3s) / storage_area_m2


def delay_steps(wave_delay_s, dt_s):
    """d = ⌈τ / Δt⌉ (also valid for non-integer ratios)."""
    if wave_delay_s < 0 or dt_s <= 0:
        raise ValueError("τ ≥ 0 and Δt > 0 are required")
    return math.ceil(wave_delay_s / dt_s - 1e-12)


def identify_from_step(time_s, level_m, inflow_step_m3s, fit_fraction=None):
    """Identifies the parameters of (8) from the plant step response (Section 2.4; Schuurmans et al., 1999).

    The inflow is increased by dQ at t = 0 with constant outflows. After the delay, the downstream level rises
    linearly: h_L(t) ≈ h_L(0) + dQ (t − τ) / A_s. A line is fitted to the last `fit_fraction` of the record:
    A_s = dQ / slope, τ = time at which the line crosses the initial level. Returns: (A_s [m²], τ [s])."""
    fit_fraction = value("id_fit_fraction") if fit_fraction is None else fit_fraction
    t = np.asarray(time_s, float); h = np.asarray(level_m, float)
    if t.size != h.size or t.size < 4 or inflow_step_m3s == 0:
        raise ValueError("At least 4 points and dQ ≠ 0 are required")
    k = int(t.size * (1.0 - fit_fraction))
    slope, icpt = np.polyfit(t[k:], h[k:], 1)
    if slope * inflow_step_m3s <= 0:
        raise ValueError("Level does not change in the direction of dQ: no integrator behaviour")
    return float(inflow_step_m3s / slope), float(max((h[0] - icpt) / slope, 0.0))


# --- 4. command constraint (9)
def chord_interpolant(x, xp, fp):
    """Chord interpolation (not tangent): lies below a concave function."""
    return float(np.interp(x, xp, fp))


def feasible_command(level, breakpoints, max_flows, capacity):
    """(9): 0 ≤ q ≤ min(chord(h_L), c̄)."""
    return max(0.0, min(chord_interpolant(level, breakpoints, max_flows), capacity))


def command_is_conservative(breakpoints, max_flows, function):
    xs = np.linspace(min(breakpoints), max(breakpoints), 101)
    return bool(np.all(np.interp(xs, breakpoints, max_flows) <= np.asarray(function(xs)) + 1e-10))


def chords(breakpoints, values):
    """(9): chords (α_m, β_m) with f(h) ≥ α_m + β_m h on each [h_m, h_{m+1}]; for concave f, min_m (α_m + β_m h)
    is the piecewise-linear interpolant and lies below f (conservative)."""
    h = np.asarray(breakpoints, float); f = np.asarray(values, float)
    beta = np.diff(f) / np.diff(h)
    alpha = f[:-1] - beta * h[:-1]
    return alpha, beta


def is_concave(breakpoints, values, tol=1e-9):
    """If the chord slopes are non-increasing, the piecewise-linear interpolant is concave (min_m form is exact)."""
    _, beta = chords(breakpoints, values)
    return bool(np.all(np.diff(beta) <= tol))


def is_convex(breakpoints, values, tol=1e-9):
    _, beta = chords(breakpoints, values)
    return bool(np.all(np.diff(beta) >= -tol))


def command_limit(breakpoints, values, h_ref, f_ref, slope_ref, mixed="error"):
    """LP form of (9), chosen according to the shape of f_j(h) at the breakpoints (q ≤ ... ≤ f):
    - concave f (regulators with constant tailwater level): chords, min_m(α_m + β_m h);
    - convex f (check structure: tailwater rises with discharge): a single tangent at h_ref,
      f(h_ref) + f′(h_ref)(h − h_ref); the tangent of a convex function lies below it.
    If f is neither, an error is raised (mixed="error"), or the tangent is returned (mixed="tangent"); the caller
    must then make it conservative (lower_to_function)."""
    if is_concave(breakpoints, values):
        return chords(breakpoints, values)
    if is_convex(breakpoints, values) or mixed == "tangent":
        return np.array([f_ref - slope_ref * h_ref]), np.array([slope_ref])
    raise ValueError("f_j(h) is neither concave nor convex: a conservative linear constraint is not guaranteed")


def lower_to_function(alpha, beta, grid, true, iterations=20):
    """Lowers the lines (α_m, β_m) of min_m(α_m + β_m h) until the minimum does not exceed the function values `true`
    on `grid`: each line that is the active minimum where the minimum exceeds the function is lowered by its largest
    excess there. Returns the new α."""
    alpha = np.array(alpha, float); beta = np.asarray(beta, float)
    for _ in range(iterations):
        vals = alpha[:, None] + beta[:, None] * grid[None, :]
        excess = vals.min(axis=0) - true
        if excess.max() <= 1e-12:
            break
        active = vals.argmin(axis=0)
        for mm in np.unique(active[excess > 1e-12]):
            alpha[mm] -= excess[(active == mm) & (excess > 1e-12)].max()
    return alpha
