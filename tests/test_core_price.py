"""§2.7, (17)–(18): price and Shapley properties."""
import itertools
import pytest
from water01.evaluation.metrics import FACTORS, prices, shapley


def subsets(v):
    return {frozenset(c): v(frozenset(c)) for r in range(5) for c in itertools.combinations(FACTORS, r)}


def test_shapley_efficiency_and_additive_case():
    w = {"sensor": 0.01, "quantisation": 0.05, "communication": 0.03, "energy": 0.0}
    vals = subsets(lambda F: sum(w[f] for f in F) + (0.02 if {"quantisation", "communication"} <= F else 0.0))
    phi = shapley(vals)
    assert abs(sum(phi.values()) - vals[frozenset(FACTORS)]) < 1e-12
    assert abs(phi["quantisation"] - phi["communication"] - 0.02) < 1e-12  # a symmetric interaction is split equally


def test_shapley_requires_all_subsets():
    with pytest.raises(ValueError):
        shapley({frozenset(): 0.0})


def test_price_with_zero_reference():
    p = prices({"lambda": 0.0, "Z2": 0.0, "Z3": 0.0}, {"lambda": 0.0, "Z2": 0.0, "Z3": 1.0})
    assert not p["Pi1_relative"] and p["Pi3"] == 1.0
