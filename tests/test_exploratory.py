"""Exploratory cases: B3V, LXB-DA, independent seeds, leave-one-year-out forecast, blank supply entries, reverse
untuned mismatch, and bootstrap block lengths."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from water01.control import CONTROLLERS  # noqa: E402
from water01.control.lxb import pulse_adjust  # noqa: E402
from water01.domain.config import CONFIG_DIR, load  # noqa: E402
from water01.simulation.runner import run_closed_loop_period, select_limit  # noqa: E402
from water01.simulation.scenarios import derive_limit, iot_scenario, load_config, load_supply  # noqa: E402
from _inputs import DEM, SUP  # noqa: E402



def test_exploratory_cases_are_complete():
    from run_experiment import EXPLORATORY
    for case, (methods, tuned, iots) in EXPLORATORY.items():
        assert (CONFIG_DIR / "scenarios" / f"{case}.yaml").exists(), case
        assert load(scenario=case).scenario == case
        assert set(methods) <= set(CONTROLLERS), case
        assert set(tuned) <= {"tuned", "untuned"} and set(iots) <= {"phys", "iot"}


def test_independent_seeds_differ():
    seeds = {load(scenario=s).value("seed") for s in ("normal", "seed_1", "seed_2", "seed_3")}
    assert len(seeds) == 4


def test_leave_one_year_out_forecast_excludes_the_year():
    sup = load_supply(SUP)
    load_config(scenario="forecast_loo")
    loo = select_limit(sup, 2011)
    load_config()
    ref = derive_limit(sup[sup.date.dt.year != 2011])
    assert np.allclose(loo.S_lim_m3s.to_numpy(), ref.S_lim_m3s.to_numpy())
    assert not np.allclose(loo.S_lim_m3s.to_numpy(), derive_limit(sup).S_lim_m3s.to_numpy())
    with pytest.raises(ValueError):
        load_config(scenario="forecast_loo"); select_limit(sup, None)
    load_config()


def test_blank_supply_policy():
    zero = load_supply(SUP, blank_policy="zero")
    carry = load_supply(SUP, blank_policy="carry_forward")
    b = zero.supply_blank_assumed_zero
    assert b.any() and (zero.S_m3s[b] == 0).all()
    assert (carry.S_m3s[~b] == zero.S_m3s[~b]).all()            # recorded days are unchanged
    assert (carry.S_m3s[b] > 0).any()
    with pytest.raises(ValueError):
        load_supply(SUP, blank_policy="interpolate")


def test_bootstrap_block_scenarios():
    assert [load(scenario=f"block_{b}").value("bootstrap_block_days") for b in (5, 20)] == [5, 20]


def test_pulse_rule():
    q_db = np.array([1.0, 0.05, 0.05, 0.05, 0.05, 0.0])
    q = np.array([2.0, 0.001, 0.001, 0.0, 0.08, 30.0])
    rem = np.array([0.0, 30.0, 10.0, 30.0, 0.0, 0.0])            # m3; half a pulse = 0.05*900/2 = 22.5 m3
    out, n = pulse_adjust(q, q_db, rem, 900.0)
    assert out[1] == 0.05 and out[2] == 0.0                       # enough remaining volume: pulse; too little: closed
    assert out[0] == 2.0 and out[3] == 0.0 and out[4] == 0.08 and out[5] == 30.0
    assert n == 1
    # daily plan smaller than one pulse (R-1, April): the threshold is half the plan
    out, n = pulse_adjust(q, q_db, rem, 900.0, target=np.array([5.0, 26.0, 18.0, 30.0, 1.0, 1.0]))
    assert out[1] == 0.05 and out[2] == 0.05 and n == 2


def test_b3v_tracks_remaining_volume_ideal():
    cfg = load_config()
    r = run_closed_loop_period("B3V", SUP, DEM, cfg, "2018-07-01", 1)["result"]
    b3 = run_closed_loop_period("B3", SUP, DEM, cfg, "2018-07-01", 1)["result"]
    assert r.mass_error < 1e-9
    # under ideal execution both deliver the same daily plan
    assert np.allclose(r.delivered[:5], b3.targets[:5], rtol=5e-3)


def test_lxb_da_serves_small_outlet_in_early_april():
    """1-10 April 2012, quantisation only: under LXB the R-1 gate does not move on several days (r = 0), whereas
    LXB-DA meets the demand every day with pulses."""
    cfg = load_config()
    iot = iot_scenario(cfg, ("quantisation",))
    r1 = lambda m: (lambda o: o["result"].delivered[1] / o["D"][1])(
        run_closed_loop_period(m, SUP, DEM, cfg, "2012-04-01", 10, iot=iot, seed=cfg.seed + 2012))
    lx, da = r1("LXB"), r1("LXB-DA")
    assert (lx < 0.01).sum() >= 3 and (da >= 0.99).all()


def test_reverse_untuned_case_inverts_the_mismatch():
    v = load(scenario="untuned_reverse").value
    assert v("untuned_controller_gate_factor") > 1 and v("untuned_offtake_factor") < 1
