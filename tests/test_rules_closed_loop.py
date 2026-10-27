"""Short closed-loop checks of the execution rules (two days of the 2010 season, quantised actuator only)."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import iot_scenario, load_config  # noqa: E402

import rules  # noqa: E402

DAYS = 2


def run(method):
    cfg = load_config(scenario="normal")
    rules.register(); rules.LOG.clear()
    out = run_closed_loop_period(method, ROOT / "DATA/processed/rashod_2010_2019_daily.csv",
                                 ROOT / "DATA/processed/demand_decadal.csv", cfg, "2010-04-01", DAYS, tuned=True,
                                 iot=iot_scenario(cfg, ("quantisation",)), seed=cfg.seed + 2010)
    return out["result"], {p: {k: (v.copy() if hasattr(v, "copy") else v) for k, v in r.items()}
                           for p, r in rules.LOG.items()}


@pytest.fixture(scope="module")
def results():
    return {m: run(m) for m in ("LXB-DA", "LXB-T050", "LXB-ES", "LXB-CO")}


def test_theta_half_coincides_with_core_deadband_aware_rule(results):
    a, _ = results["LXB-DA"]; b, _ = results["LXB-T050"]
    assert np.allclose(a.delivered, b.delivered, rtol=0, atol=1e-9)


def test_equal_split_error_is_within_half_a_step(results):
    res, log = results["LXB-ES"]
    from water01.hydraulics.node import DustlikNode
    from water01.domain.passport import value
    node = DustlikNode(); amax = np.asarray(node.max_opening, float)[:5]
    g_hi = np.asarray(node.offtakes(value("H_max_m") - 0.2, value("gate_resolution_fraction") * amax)) * value("dt_s")
    checked = 0
    for p in range(DAYS):
        for j, mode in enumerate(log[p]["mode"]):
            if mode == "ES":
                assert abs(res.delivered_est[j, p] - res.targets[j, p]) <= g_hi[j] / 2 + 1e-6
                checked += 1
    assert checked > 0


def test_carry_over_debt_recursion(results):
    res, log = results["LXB-CO"]
    x0, x1 = log[0]["x"][:5], log[1]["x"][:5]
    raw1 = x1 + (x0 - res.delivered_est[:5, 0])
    assert np.allclose(log[1]["xt"][:5], np.maximum(raw1, 0.0), atol=1e-6)
