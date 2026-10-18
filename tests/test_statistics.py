"""Section 2.9, requirements/hypotheses.md §1: block bootstrap, Wilcoxon, Holm, sign consistency, decision rules."""
import numpy as np
import pytest

from water01.evaluation.hypotheses import decide, evaluate_family, holm_families
from water01.evaluation.statistics import holm, moving_block_bootstrap_ci, sign_consistency, wilcoxon_paired

YEARS = np.repeat(np.arange(2010, 2020), 183)


def test_holm_matches_definition():
    adj = holm([0.01, 0.04, 0.03, 0.20])
    assert np.allclose(adj, [0.04, 0.09, 0.09, 0.20])        # 4·0.01; max(3·0.03, 2·0.04); 1·0.2


def test_bootstrap_ci_covers_mean_and_respects_years():
    rng = np.random.default_rng(1)
    d = 0.02 + 0.01 * rng.standard_normal(YEARS.size)
    est, lo, hi = moving_block_bootstrap_ci(d, YEARS, n_boot=2000, seed=3)
    assert lo < est < hi and lo > 0
    assert moving_block_bootstrap_ci(d, YEARS, n_boot=2000, seed=3) == (est, lo, hi)   # determinism


def test_bootstrap_widens_for_autocorrelated_series():
    """Blocks preserve autocorrelation: for an AR(1) series the block CI is wider than the unblocked (block=1) CI."""
    rng = np.random.default_rng(2); e = rng.standard_normal(YEARS.size); d = np.empty_like(e); d[0] = e[0]
    for k in range(1, d.size):
        d[k] = 0.9 * d[k - 1] + e[k]
    _, lo10, hi10 = moving_block_bootstrap_ci(d, YEARS, block=10, n_boot=2000)
    _, lo1, hi1 = moving_block_bootstrap_ci(d, YEARS, block=1, n_boot=2000)
    assert hi10 - lo10 > 1.5 * (hi1 - lo1)


def test_wilcoxon_all_zero_and_sign_consistency():
    assert wilcoxon_paired(np.zeros(20))[1] == 1.0
    d = np.where(YEARS < 2017, 1.0, -1.0)
    assert sign_consistency(d, YEARS, +1) == pytest.approx(0.7)


def test_decision_rules():
    assert decide(0.01, 0.03, "increase", 0.01, 0.001, 0.8) == "superior"
    assert decide(0.01, 0.03, "increase", 0.01, 0.001, 0.6) == "non-inferior"   # sign 6/10 is not superiority
    assert decide(-0.005, 0.02, "increase", 0.01) == "non-inferior"
    assert decide(-0.05, -0.02, "increase", 0.01) == "rejected"
    assert decide(-0.02, 0.02, "increase", 0.01) == "inconclusive"
    assert decide(-0.03, -0.01, "decrease", 0.0, 0.001, 0.9) == "supported"
    assert decide(0.01, 0.03, "decrease") == "rejected"


def test_family_evaluation_applies_holm():
    rng = np.random.default_rng(4)
    diffs = {b: 0.02 + 0.01 * rng.standard_normal(YEARS.size) for b in holm_families()["H1"]}
    diffs["B3"] = np.tile([0.01, -0.01], YEARS.size // 2)          # zero mean, p = 1
    res = {r.baseline: r for r in evaluate_family(diffs, YEARS, "increase", n_boot=500)}
    assert all(res[b].decision == "superior" for b in ("B0", "B1", "B2"))
    assert res["B3"].decision == "non-inferior" and res["B3"].p_raw > 0.5
    assert all(r.p_holm >= r.p_raw for r in res.values())
