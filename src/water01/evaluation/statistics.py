"""Statistics for paired daily differences (Section 2.9).

- moving-block bootstrap within each season (10-day blocks, 10 000 replicates): confidence interval;
- circular-block and season bootstrap: robustness checks of the interval;
- paired Wilcoxon signed-rank test;
- Holm correction within a family of hypotheses;
- sign consistency across seasons.
"""
import numpy as np
from scipy.stats import wilcoxon

from ..domain.passport import value

SCHEMES = ("block", "circular", "season")


def _block_indices(rng, n, b, n_boot, circular):
    """Indices of n_boot resamples of length n built from blocks of b consecutive days. A plain moving block starts
    in [0, n - b], so the first and last days of a season are drawn less often; a circular block wraps around."""
    k = int(np.ceil(n / b))
    starts = rng.integers(0, n if circular else n - b + 1, size=(n_boot, k))
    idx = (starts[:, :, None] + np.arange(b)[None, None, :]).reshape(n_boot, -1)[:, :n]
    return idx % n if circular else idx


def moving_block_bootstrap_ci(diff, groups=None, block=None, n_boot=None, alpha=None, seed=0, statistic=np.mean,
                              scheme="block"):
    """Point estimate and (1 - alpha) percentile interval of statistic(diff).

    groups labels the season of every day. scheme = "block" (pre-specified) and "circular" resample blocks of days
    within each season, so that no block crosses a season boundary; scheme = "season" resamples whole seasons with
    replacement."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown bootstrap scheme: {scheme}")
    block = value("bootstrap_block_days") if block is None else block
    n_boot = value("bootstrap_replicates") if n_boot is None else n_boot
    alpha = value("alpha") if alpha is None else alpha
    d = np.asarray(diff, float)
    if d.ndim != 1 or d.size == 0 or np.isnan(d).any():
        raise ValueError("diff must be a one-dimensional array without NaN")
    g = np.zeros(d.size, int) if groups is None else np.asarray(groups)
    rng = np.random.default_rng(seed)
    keys = np.unique(g)
    if scheme == "season":
        seasons = [d[g == k] for k in keys]
        pick = rng.integers(0, keys.size, size=(n_boot, keys.size))
        stats = np.array([statistic(np.concatenate([seasons[i] for i in row])) for row in pick])
    else:
        parts = []
        for key in keys:
            x = d[g == key]; n = x.size
            parts.append(x[_block_indices(rng, n, min(block, n), n_boot, scheme == "circular")])
        stats = statistic(np.concatenate(parts, axis=1), axis=1)
    lo, hi = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(statistic(d)), float(lo), float(hi)


def wilcoxon_paired(diff):
    """Two-sided paired Wilcoxon signed-rank test; p = 1 when every difference is exactly zero."""
    d = np.asarray(diff, float)
    if np.all(d == 0.0):
        return 0.0, 1.0
    res = wilcoxon(d, zero_method="wilcox", alternative="two-sided")
    return float(res.statistic), float(res.pvalue)


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values (monotone, at most 1), in the input order."""
    p = np.asarray(pvalues, float); m = p.size
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj


def sign_consistency(diff, groups, direction=+1):
    """Share of seasons whose mean difference has the expected sign."""
    d = np.asarray(diff, float); g = np.asarray(groups)
    keys = np.unique(g)
    ok = sum(1 for k in keys if np.sign(d[g == k].mean()) == direction)
    return ok / keys.size
