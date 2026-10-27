"""Single-node max-min allocation with indivisible deliveries (Theorem 2).

A node with n outlets receives the daily volume V; outlet j demands D_j > 0. A delivery is either zero or at least one
quantum q_j >= 0 (semi-continuous variable). The continuous max-min level and the quantised level are

    lambda*   = min{1, V / sum_j D_j},
    lambda_q  = max{t in [0, 1] : exists V_j in {0} U [q_j, inf), V_j >= t D_j, sum_j V_j <= V},

and the price of indivisibility is Pi_ind = lambda* - lambda_q. For t > 0 every outlet needs at least
max{t D_j, q_j}, so lambda_q = max{t in [0, 1] : G(t) <= V} with G(t) = sum_j max{t D_j, q_j} whenever V >= sum_j q_j,
and lambda_q = 0 otherwise. lambda_q is the minimum-delivery level: it keeps the smallest positive delivery q_j but not
the grid of whole steps above it.

Whole steps (Theorem 2(c)). The whole-step level lambda_v is the max-min level when outlet j delivers a volume of
the set S_j of volumes that it can deliver in a day. If every S_j contains 0 and, for every q_j <= y <= max{D_j, q_j},
a volume of [y, y + v_j], then lambda_v >= tau for every tau in (0, lambda_q] with
sum_j v_j <= (lambda_q - tau) * D_q(tau), where D_q(tau) is the demand of the outlets with q_j <= tau D_j
(whole_step_lower_bound); if no S_j has a positive volume below q_j, also lambda_v <= lambda_q. At a constant level,
a gate whose discharge is proportional to the opening and that starts the day closed has the grid
S_j = {0} U {q_j + m v_j, m = 0, 1, ...}, v_j being the volume of one resolution step; whole_step_level computes
lambda_v for such grids, an outlet with v_j = 0 taking every volume of at least q_j.
"""
import numpy as np


def _arrays(D, q):
    D = np.asarray(D, float); q = np.asarray(q, float)
    if D.ndim != 1 or D.shape != q.shape:
        raise ValueError("D and q must be one-dimensional arrays of equal length")
    if np.any(D <= 0) or np.any(q < 0):
        raise ValueError("D must be positive and q non-negative")
    return D, q


def continuous_level(V, D):
    """lambda* = min{1, V / sum D}."""
    D = np.asarray(D, float)
    return float(min(1.0, max(V, 0.0) / D.sum()))


def required_volume(t, D, q):
    """G(t) = sum_j max{t D_j, q_j}: the least volume that gives every outlet the level t > 0."""
    D, q = _arrays(D, q)
    return float(np.maximum(t * D, q).sum())


def quantised_level(V, D, q):
    """lambda_q computed exactly: G is continuous, non-decreasing and piecewise linear with breakpoints q_j / D_j."""
    D, q = _arrays(D, q)
    if V < q.sum():
        return 0.0
    if required_volume(1.0, D, q) <= V:
        return 1.0
    bps = np.unique(np.clip(np.r_[0.0, q / D, 1.0], 0.0, 1.0))
    G = np.array([required_volume(t, D, q) for t in bps])
    i = int(np.searchsorted(G, V, side="right")) - 1          # last breakpoint with G <= V (G[0] <= V < G[-1])
    t0, t1 = bps[i], bps[i + 1]
    slope = D[(t0 + t1) / 2 * D > q].sum()                     # on (t0, t1): outlets with t D_j > q_j
    return float(min(t1, t0 + (V - G[i]) / slope))             # slope > 0 because G[i + 1] > V >= G[i]


def price_of_indivisibility(V, D, q):
    """Pi_ind = lambda* - lambda_q."""
    return continuous_level(V, D) - quantised_level(V, D, q)


def epsilon_star(V, D, q, tol=1e-12):
    """Theorem 2(a) on a deficit day: the least eps >= 0 with sum_j max{0, q_j - (lambda* - eps) D_j} <= eps sum_j D_j,
    computed by bisection (independent of quantised_level)."""
    D, q = _arrays(D, q)
    lam = continuous_level(V, D)

    def ok(eps):
        return np.maximum(0.0, q - (lam - eps) * D).sum() <= eps * D.sum() + 1e-12 * max(1.0, D.sum())

    if ok(0.0):
        return 0.0
    lo, hi = 0.0, max(lam, 0.0)
    if not ok(hi):
        raise ValueError("the condition fails at eps = lambda*; V < sum q?")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi


def quantised_level_milp(V, D, q):
    """lambda_q by mixed-integer programming (SciPy/HiGHS), for checking quantised_level:
    max t s.t. V_j >= t D_j, q_j y_j <= V_j <= M y_j, sum V_j <= V, y_j binary, 0 <= t <= 1."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    D, q = _arrays(D, q)
    n = D.size; M = max(V, 1.0) * 2.0
    # variables: t, V_1..V_n, y_1..y_n
    c = np.zeros(1 + 2 * n); c[0] = -1.0
    A = []; lb = []; ub = []
    for j in range(n):
        row = np.zeros(1 + 2 * n); row[0] = D[j]; row[1 + j] = -1.0; A.append(row); lb.append(-np.inf); ub.append(0.0)
        row = np.zeros(1 + 2 * n); row[1 + j] = -1.0; row[1 + n + j] = q[j]; A.append(row); lb.append(-np.inf); ub.append(0.0)
        row = np.zeros(1 + 2 * n); row[1 + j] = 1.0; row[1 + n + j] = -M; A.append(row); lb.append(-np.inf); ub.append(0.0)
    row = np.zeros(1 + 2 * n); row[1:1 + n] = 1.0; A.append(row); lb.append(-np.inf); ub.append(V)
    integrality = np.r_[0, np.zeros(n), np.ones(n)]
    bounds = Bounds(np.r_[0.0, np.zeros(n), np.zeros(n)], np.r_[1.0, np.full(n, M), np.ones(n)])
    res = milp(c, constraints=LinearConstraint(np.array(A), lb, ub), integrality=integrality, bounds=bounds,
               options={"mip_rel_gap": 0.0})
    if not res.success:
        raise RuntimeError(res.message)
    return float(res.x[0])


def _grid_need(t, D, q, v):
    """Least delivery of every outlet for the level t > 0: max{t D_j, q_j}, raised to the grid q_j + m v_j where
    v_j > 0."""
    need = np.maximum(t * D, q)
    grid = v > 0
    if grid.any():
        m = np.ceil((need[grid] - q[grid]) / v[grid] * (1 - 1e-15) - 1e-12)
        need[grid] = q[grid] + v[grid] * np.maximum(m, 0.0)
    return need


def whole_step_level(V, D, q, v, tol=1e-13):
    """lambda_v: the max-min level when the positive deliveries of outlet j lie on the grid q_j + m v_j (v_j > 0)
    or in [q_j, inf) (v_j = 0). The required volume G_v(t) = sum_j need_j(t) is non-decreasing, so lambda_v is found by
    bisection to tol; G_v is left-continuous, so the feasible levels form a closed interval [0, lambda_v]."""
    D, q = _arrays(D, q)
    v = np.asarray(v, float)
    if v.shape != D.shape or np.any(v < 0):
        raise ValueError("v must be a non-negative array of the length of D")
    if V < q.sum():
        return 0.0
    G = lambda t: float(_grid_need(t, D, q, v).sum())          # noqa: E731
    if G(1.0) <= V:
        return 1.0
    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if G(mid) <= V else (lo, mid)
    return lo


def whole_step_lower_bound(V, D, q, v):
    """Lower bound of Theorem 2(c): the largest tau in (0, lambda_q] with sum_j v_j <= (lambda_q - tau) D_q(tau),
    D_q(tau) = sum of D_j over the outlets with q_j <= tau D_j, or 0 if there is none. For such tau, every outlet of
    D_q(tau) needs t D_j on [tau, lambda_q], so G(tau) <= G(lambda_q) - (lambda_q - tau) D_q(tau), and raising every
    delivery to a deliverable volume costs at most sum_j v_j. The candidates are tau = lambda_q - sum v / D_q(s) for
    the sets of outlets with q_j / D_j <= s, s a breakpoint; a candidate is valid if it is not below s."""
    D, q = _arrays(D, q)
    v = np.asarray(v, float)
    if v.shape != D.shape or np.any(v < 0):
        raise ValueError("v must be a non-negative array of the length of D")
    lq = quantised_level(V, D, q)
    sv = float(v.sum())
    if lq <= 0.0 or sv == 0.0:
        return lq
    b = q / D
    best = 0.0
    for s in np.unique(b[b <= lq]):
        tau = lq - sv / D[b <= s].sum()
        if tau >= s and tau > best:
            best = tau
    return float(best)


def whole_step_level_enumerated(V, D, q, v):
    """lambda_v by enumeration of the grid deliveries of the outlets with v_j > 0 (at most three), for checking
    whole_step_level. The outlets with v_j = 0 must have no quantum (q_j = 0); they share the rest in proportion to
    their demands. Deliveries above max{D_j, q_j} + v_j are not needed and are not enumerated."""
    D, q = _arrays(D, q)
    v = np.asarray(v, float)
    grid = np.flatnonzero(v > 0); free = np.flatnonzero(v <= 0)
    if grid.size > 3 or np.any(q[free] > 0):
        raise ValueError("at most three grid outlets; the other outlets must have no quantum")
    axes = [np.r_[0.0, q[j] + v[j] * np.arange(int(np.ceil(max(D[j] - q[j], 0.0) / v[j])) + 2)] for j in grid]
    mesh = np.meshgrid(*axes, indexing="ij")
    Vg = np.stack([m.ravel() for m in mesh], axis=1)            # [combinations x grid outlets]
    t = np.minimum(1.0, (Vg / D[grid]).min(axis=1))
    rest = V - Vg.sum(axis=1)
    if free.size:
        t = np.minimum(t, np.maximum(rest, 0.0) / D[free].sum())
    t[rest < -1e-12] = 0.0
    return float(t.max())


def daily_prices(V, D, q):
    """Vectorised over days: V [P], D [n x P], q [n x P] -> (lambda* [P], lambda_q [P], Pi_ind [P])."""
    V = np.asarray(V, float); D = np.asarray(D, float); q = np.asarray(q, float)
    lam = np.array([continuous_level(V[p], D[:, p]) for p in range(V.size)])
    lq = np.array([quantised_level(V[p], D[:, p], q[:, p]) for p in range(V.size)])
    return lam, lq, lam - lq
