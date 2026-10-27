"""Single-node max-min allocation with indivisible deliveries (Theorem 2).

A node with n outlets receives the daily volume V; outlet j demands D_j > 0. A delivery is either zero or at least one
quantum q_j >= 0 (semi-continuous variable). The continuous max-min level and the quantised level are

    lambda*   = min{1, V / sum_j D_j},
    lambda_q  = max{t in [0, 1] : exists V_j in {0} U [q_j, inf), V_j >= t D_j, sum_j V_j <= V},

and the price of indivisibility is Pi_ind = lambda* - lambda_q. For t > 0 every outlet needs at least
max{t D_j, q_j}, so lambda_q = max{t in [0, 1] : G(t) <= V} with G(t) = sum_j max{t D_j, q_j} whenever V >= sum_j q_j,
and lambda_q = 0 otherwise.
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


def daily_prices(V, D, q):
    """Vectorised over days: V [P], D [n x P], q [n x P] -> (lambda* [P], lambda_q [P], Pi_ind [P])."""
    V = np.asarray(V, float); D = np.asarray(D, float); q = np.asarray(q, float)
    lam = np.array([continuous_level(V[p], D[:, p]) for p in range(V.size)])
    lq = np.array([quantised_level(V[p], D[:, p], q[:, p]) for p in range(V.size)])
    return lam, lq, lam - lq
