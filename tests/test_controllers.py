"""§2.8: controllers share one interface; static Oracle ≥ LXB (λ); stage 1b."""
import numpy as np
import pytest
import inspect

from water01.control import CONTROLLERS, Command, b3_proportional, lxb_receding, oracle
from water01.evaluation.metrics import compute

rng = np.random.default_rng(0)
D = rng.uniform(1, 5, size=(3, 8))
A = rng.uniform(2, 10, size=8)
A_fc = np.full(8, A.mean())


def test_b3_never_exceeds_demand_or_supply():
    x = b3_proportional(D, A)
    assert np.all(x <= D + 1e-9) and np.all(x.sum(axis=0) <= A + 1e-9)


def test_oracle_lambda_not_below_lxb():
    lam_lxb = compute(lxb_receding(D, A, A_fc), D)["lambda"]
    lam_or = compute(oracle(D, A), D)["lambda"]
    assert lam_or >= lam_lxb - 1e-6


@pytest.mark.parametrize("name", ["B0", "B1", "B2", "B3", "LXB", "Oracle"])
def test_controllers_share_one_interface(name):
    """command = controller.step(state=…, demand=…, supply=…, constraints=…, horizon=…)."""
    ctrl = CONTROLLERS[name]()
    params = list(inspect.signature(ctrl.step).parameters)
    assert params == ["state", "demand", "supply", "constraints", "horizon"]
    assert ctrl.name == name and hasattr(ctrl, "reset")


def test_command_validation():
    c = Command(); c.flows[0] = 1.0; c.openings[0] = 0.5
    with pytest.raises(ValueError):
        c.validate()


def test_pessimistic_forecast_does_not_sacrifice_today():
    """Case 2012-05-II: ample water today, pessimistic forecast. LXB must not sacrifice today's worst-off user."""
    Dd = np.array([[1.0] * 3, [1.0] * 3, [10.0] * 3])
    A_act = np.array([11.4, 13.5, 13.5]); A_fc = np.array([11.2, 11.2, 11.2])
    lam_b3 = compute(b3_proportional(Dd, A_act), Dd)["lambda"]
    lam_lxb = compute(lxb_receding(Dd, A_act, A_fc, epsilon_1=1e-6), Dd)["lambda"]
    lam_no_stage1b = compute(lxb_receding(Dd, A_act, A_fc, epsilon_1=1e-6, protect_today=False), Dd)["lambda"]
    assert lam_lxb >= lam_b3 - 1e-5
    assert lam_no_stage1b < lam_b3 - 1e-3  # without stage 1b (protect_today=False) the case fails
