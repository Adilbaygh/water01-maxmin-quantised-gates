"""Section 2.5, Equations (10)-(13): satisfaction and the objective functions of the three stages (as LP rows).

Variable vector: x_{j,p} -> index j·P + p (n = J·P), followed by auxiliary variables where needed.
"""
import numpy as np
from scipy.sparse import lil_matrix


def satisfaction(x, D):
    """(10): r = min(x/D, 1) for pairs with D > 0; NaN for pairs with D = 0 (outside A+)."""
    x = np.asarray(x, float); D = np.asarray(D, float)
    r = np.full(np.broadcast(x, D).shape, np.nan)
    m = D > 0
    r[m] = np.minimum(x[m] / D[m], 1.0)
    return r


def var_index(P):
    return lambda j, p: j * P + p


def worst_case_rows(pairs, D, n, idx):
    """(11a)/(11b): t ≤ x_{j,p}/D_{j,p} ⇔ −x/D + t ≤ 0. The last column (n) is t (λ or μ).
    Objective: max t ⇔ min (−t); c = [0…0, −1]."""
    G = lil_matrix((len(pairs), n + 1))
    for k, (j, p) in enumerate(pairs):
        G[k, idx(j, p)] = -1.0 / D[j, p]; G[k, n] = 1.0
    c = np.r_[np.zeros(n), -1.0]
    return G, c


def weighted_satisfaction_coeffs(pairs, D, w, n, idx):
    """(12): min −Σ w_j x_{j,p}/D_{j,p}  (−Z2)."""
    c = np.zeros(n)
    for j, p in pairs:
        c[idx(j, p)] = -w[j] / D[j, p]
    return c


def variation_links(pos):
    """Pairs for (13): (j, p−1, p) with both days in A+."""
    J, P = pos.shape
    return [(j, p) for j in range(J) for p in range(1, P) if pos[j, p] and pos[j, p - 1]]


def variation_rows(links, D, n, idx):
    """(13): linearisation of |r_p − r_{p−1}| ≤ t_k: ±(x_p/D_p − x_{p−1}/D_{p−1}) − t_k ≤ 0.
    Returns: (list of rows [of length n + m], objective c = [0…0, 1…1])."""
    m = len(links); nv = n + m
    rows = []
    for k, (j, p) in enumerate(links):
        for s in (1.0, -1.0):
            row = np.zeros(nv)
            row[idx(j, p)] = s / D[j, p]; row[idx(j, p - 1)] = -s / D[j, p - 1]; row[n + k] = -1.0
            rows.append(row)
    return rows, np.r_[np.zeros(n), np.ones(m)]
