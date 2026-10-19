"""Directional decision rules for the hypotheses (Section 2.9).

Differences are written as "LXB - baseline".
- kind="increase" (e.g. H1, lambda): superior if the lower CI bound > 0, the Holm-adjusted p < alpha and the sign is
  correct in at least 7 of 10 seasons; non-inferior if the lower bound > -epsilon; rejected if the upper bound
  < -epsilon; otherwise inconclusive.
- kind="decrease" (e.g. H2, H6): supported if the upper CI bound < 0, the Holm-adjusted p < alpha and the sign is
  correct in at least 7 of 10 seasons; rejected if the lower bound > 0; otherwise inconclusive.
An interval that excludes zero in the expected direction without the p-value or sign condition is inconclusive
(for H1, with a positive margin, such an interval is non-inferior).
"""
from dataclasses import dataclass

from ..domain.passport import value
import numpy as np

from .statistics import holm, moving_block_bootstrap_ci, season_signflip, sign_consistency, wilcoxon_paired


def holm_families():
    """Holm families from the configuration (hypotheses.holm_families)."""
    return {k: tuple(v) for k, v in value("holm_families").items()}


@dataclass
class PairResult:
    baseline: str
    estimate: float
    ci_low: float
    ci_high: float
    p_raw: float
    p_holm: float
    sign_share: float
    decision: str


def decide(ci_low, ci_high, kind, eps=0.0, p_adj=0.0, sign_share=1.0, alpha=None, min_sign_share=None):
    alpha = value("alpha") if alpha is None else alpha
    min_share = value("min_sign_share") if min_sign_share is None else min_sign_share
    if kind == "increase":
        if ci_low > 0 and p_adj < alpha and sign_share >= min_share:
            return "superior"
        if ci_high < -eps:
            return "rejected"
        if eps > 0 and ci_low > -eps:
            return "non-inferior"
        return "inconclusive"
    if kind == "decrease":
        if ci_high < 0 and p_adj < alpha and sign_share >= min_share:
            return "supported"
        if ci_low > 0:
            return "rejected"
        return "inconclusive"
    raise ValueError("kind must be 'increase' or 'decrease'")


def evaluate_family(diffs, years, kind, eps=None, alpha=None, n_boot=None, seed=0, block=None, scheme="block",
                    test="wilcoxon"):
    """diffs: {baseline: daily differences}; years: season of every day. Holm is applied within the family.
    eps, alpha, n_boot and block default to the configuration (section hypotheses).
    test = "wilcoxon" (pre-specified: daily Wilcoxon signed-rank test) or "season" (exact sign-flip test of the
    seasonal mean differences, seasons as independent units). NaN entries mark excluded days (scheme "calendar")."""
    eps = value("epsilon_lambda") if eps is None else eps
    alpha = value("alpha") if alpha is None else alpha
    n_boot = value("bootstrap_replicates") if n_boot is None else n_boot
    block = value("bootstrap_block_days") if block is None else block
    names = list(diffs)
    if test not in ("wilcoxon", "season"):
        raise ValueError("test must be 'wilcoxon' or 'season'")
    def clean(x):                               # days excluded under the calendar scheme are NaN
        m = np.isnan(np.asarray(x, float))
        return np.asarray(x, float)[~m] if m.any() else x
    raw = [wilcoxon_paired(clean(diffs[b]))[1] if test == "wilcoxon" else season_signflip(diffs[b], years)[1]
           for b in names]
    adj = holm(raw)
    direction = +1 if kind == "increase" else -1
    out = []
    for b, pr, pa in zip(names, raw, adj):
        est, lo, hi = moving_block_bootstrap_ci(diffs[b], years, block=block, n_boot=n_boot, alpha=alpha, seed=seed,
                                                scheme=scheme)
        share = sign_consistency(diffs[b], years, direction)
        out.append(PairResult(b, est, lo, hi, float(pr), float(pa), share,
                              decide(lo, hi, kind, eps, pa, share, alpha)))
    return out
