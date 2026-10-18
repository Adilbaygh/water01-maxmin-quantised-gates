"""§2.10 (3), (7): edge cases and preservation of the lexicographic optima."""
import numpy as np
from water01.evaluation.metrics import compute
from water01.optimization.lexlp import solve_lexicographic

D = np.array([[5.0, 5.0, 5.0], [2.0, 2.0, 2.0], [1.0, 0.0, 1.0]])


def test_full_supply_gives_lambda_one():
    assert abs(solve_lexicographic(D, D.sum(axis=0) * 2)["lambda_star"] - 1.0) < 1e-8


def test_zero_supply_gives_lambda_zero():
    assert abs(solve_lexicographic(D, np.zeros(3))["lambda_star"]) < 1e-9


def test_supply_couples_users():
    out = solve_lexicographic([[5.0], [5.0]], [1.0])
    assert abs(out["lambda_star"] - 0.1) < 1e-8
    assert out["x"].sum() <= 1.0 + 1e-8


def test_single_user():
    assert abs(solve_lexicographic([[4.0, 4.0]], [2.0, 4.0])["lambda_star"] - 0.5) < 1e-8


def test_zero_demand_pairs_are_excluded():
    out = solve_lexicographic(D, D.sum(axis=0))
    assert abs(out["lambda_star"] - 1.0) < 1e-8
    m = compute(out["x"], D)
    assert m["lambda"] >= 1.0 - 1e-4 - 1e-9 and np.isnan(m["r"][2, 1])  # within the ε1 tolerance


def test_stage_optima_are_preserved():
    A = np.array([3.0, 6.0, 4.0]); e1 = e2 = 1e-4
    out = solve_lexicographic(D, A, epsilon_1=e1, epsilon_2=e2)
    m = compute(out["x"], D)
    assert m["lambda"] >= out["lambda_star"] - e1 - 1e-7
    assert m["Z2"] >= out["Z2_star"] - e2 - 1e-7


def test_stage3_does_not_increase_variation():
    A = np.array([3.0, 6.0, 4.0])
    out = solve_lexicographic(D, A)
    z3_stage2 = compute(out["stage2_x"], D)["Z3"]
    assert out["Z3_star"] <= z3_stage2 + 1e-7


def test_supply_never_exceeded():
    A = np.array([3.0, 6.0, 4.0])
    x = solve_lexicographic(D, A)["x"]
    assert np.all(x.sum(axis=0) <= A + 1e-7)



def test_delay_is_counted_in_time_when_intervals_are_blocked():
    """With 1-h blocks after the fine steps, an inflow change reaches the node d steps later, not d blocks later."""
    import numpy as np
    from water01.optimization.lexlp import delayed_inflow
    tau = np.r_[[900.0] * 2, [3600.0] * 2]                 # two 15-min steps, then two 1-h blocks
    q = delayed_inflow([1.0, 1.0], [2.0, 2.0, 4.0, 4.0], tau, 900.0, 2)
    assert np.allclose(q, [1.0, 1.0, 3.0, 4.0])            # block 3 covers steps 2-5: inflows 2, 2, 4, 4
    assert np.allclose(delayed_inflow([1.0, 1.0], [2.0] * 4, np.full(4, 900.0), 900.0, 2), [1.0, 1.0, 2.0, 2.0])
