"""Options added for the sensitivity and exploratory cases: they leave the baseline unchanged and act as described."""
import numpy as np
import pytest

from water01.domain.config import load
from water01.iot.communication import LinkState, transmit
from water01.iot.telemetry import measure
from water01.optimization.lexlp import solve_intraday
from water01.simulation.runner import build_controller_model
from water01.simulation.scenarios import iot_scenario, load_config
from water01.hydraulics.node import DustlikNode


def test_link_counters_split_blocked_and_lost():
    s = LinkState(window_steps=4, budget=1)
    assert transmit(s, 0) and not transmit(s, 1)               # second packet of the window is blocked
    assert not transmit(s, 4, delivered=False)                 # new window: sent but lost
    assert (s.sent_total, s.blocked, s.lost, s.dropped) == (2, 1, 1, 2)


def test_sensor_bias_is_a_constant_offset():
    assert measure(3.0, 0.025, unit_noise=0.0, bias_m=0.02) == pytest.approx(3.02)
    assert measure(3.0, 0.025, unit_noise=1.0, bias_m=-0.025) == pytest.approx(3.0)


def test_scenario_additions_and_defaults():
    base = load_config()
    assert iot_scenario(base, ("sensor",)).sensor_bias_m == 0.0
    cfg = load_config(scenario="sensor_bias_pos")
    assert iot_scenario(cfg, ("sensor",)).sensor_bias_m == pytest.approx(0.025)
    assert load(scenario="rating_outlets").params["outlet_rating_factors"].status == "assumed"
    load_config()
    with pytest.raises(KeyError):
        load(scenario="normal").value("sensor_bias_m")


def _lp(share, delivered, target):
    cfg = load_config()
    m = build_controller_model(DustlikNode(), cfg)
    K = 8
    remaining = np.maximum(target - delivered, 0.0)
    return solve_intraday([60.0] * m.d, np.full(K, 60.0), 3.0, remaining, target / 86400, 4, K, m.dt, m.eta, m.A_s,
                          m.d, m.chords, m.capacity, m.h_lo, m.h_hi, m.h_ref, None, m.dq_max, share=share,
                          delivered_today=delivered, target_today=target)


def test_final_share_executor_raises_the_worst_final_share():
    """With unequal past delivery, the final-share LP gives the worst-off user at least the final share reached by
    the remaining-share LP (the example of a user that has received nothing yet)."""
    target = np.array([3e5, 4e3, 8e3, 3e4, 1.5e4, 6e5])
    delivered = target * np.array([0.0, 0.5, 0.5, 0.5, 0.5, 0.5])
    final = lambda sol: ((delivered + (sol["q"][:, :4] * 900.0).sum(axis=1)) / target)[:5].min()
    rem, fin = _lp("remaining", delivered, target), _lp("final", delivered, target)
    assert final(fin) >= final(rem) - 1e-6
    load_config()


def test_exploratory_groups_and_case_runs():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from run_experiment import EXPLORATORY, groups
    assert sum(len(ms) * len(tu) * len(io) for ms, tu, io in groups("dt_450")) == 5
    assert all(groups(c) for c in EXPLORATORY)


def test_gate_change_at_step_start_credits_a_pulse_to_its_step():
    """A one-step pulse of the smallest executable opening: with the gate change at the start of the step, the whole
    pulse volume is credited to the step in which the gate is open, for any number of hydraulic steps; with the
    theta-weighted change of the first code versions, only theta + (1 - theta)(1 - 1/n) of it."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from verification_pulse import run
    for n in (1, 2):
        old, new = run(n, False), run(n, True)
        theta = load_config().preissmann_theta
        assert abs(old["share_in_open_step"] - (1 - (1 - theta) / n)) < 1e-3
        assert new["share_in_open_step"] > 0.999
        assert abs(new["vol_total_m3"] - old["vol_total_m3"]) < 1e-3 * old["vol_total_m3"]
    load_config()


def test_season_signflip_uses_the_day_weighted_estimate():
    from water01.evaluation.statistics import season_signflip
    d = np.r_[np.full(10, 1.0), np.full(30, 3.0), [np.nan] * 5]
    g = np.r_[np.zeros(10), np.ones(30), np.ones(5)]
    est, p = season_signflip(d, g)
    assert abs(est - np.nanmean(d)) < 1e-12 and p == 0.5          # two seasons: 2 of 4 patterns as extreme
