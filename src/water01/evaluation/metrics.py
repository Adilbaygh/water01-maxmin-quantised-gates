"""Sections 2.5, 2.7, 2.10: metrics and the IoT price of executability.

- λ, Z2, Z3 are computed only over pairs in A+ = {(j,p): D_{j,p} > 0};
- (17) IoT price Π1, Π2, Π3 and (18) Shapley decomposition (16 subsets).
"""
import itertools
import math

import numpy as np

from ..optimization.objectives import satisfaction

FACTORS = ("sensor", "quantisation", "communication", "energy")


def daily_lambda(r):
    """Daily worst-case satisfaction λ[p] = min_j r_{j,p} (the paired unit for the statistical tests)."""
    r = np.asarray(r, float)
    out = np.full(r.shape[1], np.nan)
    for p in range(r.shape[1]):
        col = r[:, p][~np.isnan(r[:, p])]
        if col.size:
            out[p] = col.min()
    return out


def variation(r):
    """Z3 = Σ_j Σ_{p≥2} |r_{j,p} − r_{j,p−1}| (only where both days are in A+)."""
    r = np.atleast_2d(np.asarray(r, float))
    d = np.abs(np.diff(r, axis=1))
    return float(np.nansum(d))


def compute(x, D, weights=None):
    r = satisfaction(np.atleast_2d(x), np.atleast_2d(D))
    w = np.ones(r.shape[0]) if weights is None else np.asarray(weights, float)
    valid = ~np.isnan(r)
    lam = float(np.nanmin(r)) if valid.any() else float("nan")
    z2 = float(np.nansum(r * w[:, None]))
    return {"lambda": lam, "lambda_daily": daily_lambda(r), "Z2": z2, "Z3": variation(r), "r": r}


# --- (17)-(18): IoT price of executability
def prices(phys, iot):
    """(17). If λ^phys = 0 or Z2^phys = 0, the signed absolute difference is returned instead of the relative one."""
    rel1 = phys["lambda"] > 0
    rel2 = phys["Z2"] > 0
    return {
        "Pi1": (phys["lambda"] - iot["lambda"]) / phys["lambda"] if rel1 else phys["lambda"] - iot["lambda"],
        "Pi1_relative": rel1,
        "Pi2": (phys["Z2"] - iot["Z2"]) / phys["Z2"] if rel2 else phys["Z2"] - iot["Z2"],
        "Pi2_relative": rel2,
        "Pi3": iot["Z3"] - phys["Z3"],
    }


def shapley(values, factors=FACTORS, tol=1e-9):
    """(18). values: {frozenset(F): v(F)} for all 2^4 = 16 subsets, with v(∅) = 0 (phys run)."""
    n = len(factors)
    need = {frozenset(c) for r in range(n + 1) for c in itertools.combinations(factors, r)}
    missing = need - set(values)
    if missing:
        raise ValueError(f"{len(missing)} subsets are missing")
    if abs(values[frozenset()]) > tol:
        raise ValueError("v(∅) must be 0 (phys run)")
    phi = {}
    for i in factors:
        others = [f for f in factors if f != i]
        s = 0.0
        for r in range(n):
            for sub in itertools.combinations(others, r):
                F = frozenset(sub)
                s += math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n) * (values[F | {i}] - values[F])
        phi[i] = s
    return phi
