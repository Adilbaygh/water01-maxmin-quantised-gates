"""Statistics for paired daily differences (Section 2.9).

- moving-block bootstrap within each season (10-day blocks, 10 000 replicates): confidence interval;
- circular-block, calendar-block and season bootstrap: robustness checks of the interval;
- paired Wilcoxon signed-rank test on daily differences (pre-specified; ignores serial dependence) and an exact
  sign-flip test on seasonal mean differences (seasons as independent units);
- Holm correction within a family of hypotheses;
- sign consistency across seasons.
"""
import numpy as np
from scipy.stats import wilcoxon

from ..domain.passport import value

SCHEMES = ("block", "circular", "season", "calendar")


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
    replacement. scheme = "calendar" resamples moving blocks of consecutive calendar days within each season; diff
    then covers every day of the season, with NaN on the days excluded from the contrast (e.g. λ_phys = 0), so that
    an exclusion does not join the days on both sides of it; statistic must then be np.mean, and each replicate is
    the mean of its eligible days."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown bootstrap scheme: {scheme}")
    block = value("bootstrap_block_days") if block is None else block
    n_boot = value("bootstrap_replicates") if n_boot is None else n_boot
    alpha = value("alpha") if alpha is None else alpha
    d = np.asarray(diff, float)
    calendar = scheme == "calendar"
    if d.ndim != 1 or d.size == 0 or (np.isnan(d).any() and not calendar) or np.isnan(d).all():
        raise ValueError("diff must be a one-dimensional array without NaN (NaN marks excluded days only with "
                         "scheme='calendar')")
    if calendar and statistic is not np.mean:
        raise ValueError("scheme='calendar' supports the mean only")
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
        res = np.concatenate(parts, axis=1)
        if calendar:
            ok = ~np.isnan(res)
            with np.errstate(invalid="ignore"):            # a replicate without an eligible day is left out
                stats = np.where(ok, res, 0.0).sum(axis=1) / np.where(ok.any(axis=1), ok.sum(axis=1), np.nan)
            stats = stats[~np.isnan(stats)]
            if stats.size < 0.5 * n_boot:                  # too few eligible days for a calendar interval
                return float(np.nanmean(d)) if np.isfinite(d).any() else np.nan, np.nan, np.nan
        else:
            stats = statistic(res, axis=1)
    lo, hi = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(np.nanmean(d) if calendar else statistic(d)), float(lo), float(hi)


def season_signflip(diff, groups):
    """Exact two-sided sign-flip (randomisation) test with the seasons as the units of inference. The statistic is
    the mean of the daily differences, written as the mean of the seasonal mean differences weighted by the number
    of eligible days of each season, so that it equals the reported estimate. Under the null hypothesis the seasonal
    mean differences are independent and symmetric about zero, so that every one of the 2^n sign patterns is
    equally likely. NaN entries (excluded days) are ignored. Returns (estimate, p)."""
    d = np.asarray(diff, float); g = np.asarray(groups)
    m, w = [], []
    for k in np.unique(g):
        x = d[g == k]; x = x[~np.isnan(x)]
        if x.size:
            m.append(x.mean()); w.append(x.size)
    m, w = np.array(m), np.array(w, float) / np.sum(w)
    est = float((w * m).sum())
    if np.all(m == 0.0):
        return 0.0, 1.0
    signs = np.array(np.meshgrid(*[[-1.0, 1.0]] * m.size)).reshape(m.size, -1).T
    stats = np.abs((signs * (w * m)).sum(axis=1))
    return est, float(np.mean(stats >= abs(est) - 1e-15))


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
    """Share of seasons whose mean difference has the expected sign (NaN entries are ignored)."""
    d = np.asarray(diff, float); g = np.asarray(groups)
    keys = [k for k in np.unique(g) if not np.isnan(d[g == k]).all()]   # seasons without an eligible day are left out
    ok = sum(1 for k in keys if np.sign(np.nanmean(d[g == k])) == direction)
    return ok / len(keys)
