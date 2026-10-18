"""Edge cases from full-season runs: zero supply, pool running dry, head ≈ 0 upstream of a gate."""
import numpy as np
import pytest

from water01.control.lxb import blocked_durations, clip_roundoff
from water01.hydraulics.node import DustlikNode, _sqrt_head
from water01.iot.devices import quantize
from water01.optimization.lexlp import solve_intraday
from water01.simulation.plant_loop import Actuator, IoTConfig
from water01.simulation.runner import build_controller_model
from water01.simulation.scenarios import load_config
from _inputs import DEM, SUP  # noqa: E402

CFG = load_config()


def test_full_close_ignores_deadband():
    assert quantize(0.0, 0.001, previous=0.004, deadband=0.005) == 0.0
    assert quantize(0.003, 0.001, previous=0.004, deadband=0.005) == 0.004       # small adjustment is held


def test_rtu_low_level_interlock_closes_all_gates():
    act = Actuator(DustlikNode(), IoTConfig(), np.full(6, 0.3))
    assert not act.interlock(1.35, CFG.rtu_low_level_interlock_m)
    assert act.interlock(1.25, CFG.rtu_low_level_interlock_m) and np.all(act.position == 0) and act.interlock_steps == 1


def test_gate_head_is_smooth_and_matches_sqrt():
    h0 = CFG.gate_head_regularisation_m
    hs = np.linspace(-5 * h0, 5 * h0, 201)
    v = np.array([_sqrt_head(h) for h in hs])
    assert np.all(np.diff(v) > 0) and np.max(np.abs(np.diff(v, 2))) < 1e-2          # monotone, without kinks
    for h in (0.01, 0.1, 1.0):
        assert abs(_sqrt_head(h) / np.sqrt(h) - 1) < 1e-4


def test_execution_lp_feasible_at_very_low_level_without_inflow():
    """h_L = 1.0 m, zero inflow: the chords are negative; the soft constraint keeps the LP feasible, flows ≈ 0."""
    m = build_controller_model(DustlikNode(), CFG)
    tau, n = blocked_durations(96, 8, 4, 4, m.dt)
    D = np.array([1.2e6, 3e4, 6e4, 2.5e5, 1e5, 2.5e6])
    sol = solve_intraday([0.0] * m.d, np.zeros(tau.size), 1.0, D, D / 86400, n, tau.size, m.dt, m.eta, m.A_s, m.d,
                         m.chords, m.capacity, m.h_lo, m.h_hi, m.h_ref, np.full(6, 5.0), m.dq_max, durations=tau)
    assert sol["q"].min() >= -1e-9 and sol["q"][:, 1:].max() < 1e-6


def test_roundoff_remaining_volume_is_well_conditioned():
    """A remaining volume at round-off level (2·10⁻¹³ m³) would give the μ row a coefficient of ~10¹⁵ and a HiGHS
    "Model error"; the row is divided by max(need, 1 m³), so the LP solves."""
    from water01.control.lxb import blocked_durations
    m = build_controller_model(DustlikNode(), CFG)
    tau, n = blocked_durations(96, 8, 4, 4, m.dt)
    D = np.array([1.2e6, 3e4, 6e4, 2.5e5, 1e5, 2.5e6]); D[1] = 2.3e-13
    sol = solve_intraday([60.0] * m.d, np.full(tau.size, 60.0), 3.0, D, D / 86400, n, tau.size, m.dt, m.eta, m.A_s,
                         m.d, m.chords, m.capacity, m.h_lo, m.h_hi, m.h_ref, np.full(6, 5.0), m.dq_max, durations=tau)
    assert np.isfinite(sol["q"]).all()


def test_high_level_relief_opens_barrier_with_hysteresis():
    """Dustlik has no emergency spillway: at H_max the excess water passes through the barrier structure."""
    node = DustlikNode()
    act = Actuator(node, IoTConfig(), np.array([0.5, 0.2, 0.2, 0.3, 0.2, 0.1]))
    hi, lo = CFG.relief_open_level_m if hasattr(CFG, "relief_open_level_m") else 3.43, 3.33
    assert not act.relief(3.40, hi, lo) and act.position[5] == 0.1
    assert act.relief(3.43, hi, lo) and act.position[5] == node.max_opening[5]
    assert act.position[0] == 0.5                                  # the other gates are unchanged
    act.position[5] = 0.1
    assert act.relief(3.36, hi, lo) and act.position[5] == node.max_opening[5]   # hysteresis: still open
    act.position[5] = 0.1
    assert not act.relief(3.33, hi, lo) and act.position[5] == 0.1 and act.relief_steps == 2


def test_energy_node_radio_hysteresis_and_balance():
    """(16): the radio switches off below the reserve and back on at the resume level; the energy balance holds."""
    from water01.iot.energy import EnergyNode
    n = EnergyNode(np.zeros(400), 900.0, capacity_wh=100.0, b_min_wh=10.0, b_reserve_wh=10.0, resume_wh=30.0,
                   eta_ch=1.0, eta_dis=1.0, rtu_w=4.0, gateway_w=4.0, message_wh=0.0)
    on = [n.advance(k, 0) for k in range(41)]                   # 2 Wh/step: 100 → off at 18 Wh (< 20)
    assert on[39] and not on[40] and n.state.wh == pytest.approx(18.0)
    n.pv_wh[:] = 3.0                                           # radio off: +3 − 1 (RTU only) = +2 Wh/step
    on = [n.advance(k, 0) for k in range(41, 50)]
    assert not on[4] and on[5] and n.state.wh == pytest.approx(33.0)    # on at 30 Wh, then +1 Wh/step
    assert n.state.wh == pytest.approx(100.0 + 3.0 * 9 - n.used_wh)      # balance (capacity not reached)
    assert n.radio_off_steps == 6 and n.min_wh == pytest.approx(18.0)


def test_nasa_power_loaded_for_season():
    import pandas as pd
    from water01.iot.energy import load_nasa_power, pv_energy_per_step
    g = load_nasa_power(pd.date_range("2018-04-01", periods=183))
    assert g.shape == (183, 24) and g.min() >= 0 and g[:, 0].max() == 0.0     # zero at night (LST)
    pv = pv_energy_per_step(g, 900.0)
    assert pv.size == 183 * 96 and 300 < pv.sum() / 183 < 700              # 100 W panel, ~0.5 kWh per day


def test_phys_run_reports_zero_messages():
    from water01.simulation.runner import run_closed_loop_period
    from water01.simulation.scenarios import iot_scenario
    out = run_closed_loop_period("B3", SUP, DEM, CFG, "2018-07-01", 1,
                                 iot=iot_scenario(CFG, ()), seed=1)
    r = out["result"]
    assert r.messages_sent == 0 and r.messages_dropped == 0 and r.battery_min_wh is None


def test_execution_roundoff_below_lp_tolerance_is_clipped():
    """LP round-off within tolerance (e.g. −7.3·10⁻¹³ m³/s for the barrier structure) is clipped to zero."""
    q = clip_roundoff(np.array([0.0, 0.5, -7.32e-13]))
    assert np.all(q >= 0) and q[2] == 0.0 and q[1] == 0.5
    with pytest.raises(ValueError):
        clip_roundoff(np.array([1.0, -1e-6]))
