"""Consistency checks of the gate law, the command constraint, the IoT options, the energy counters and the input
loading (regression tests)."""
import numpy as np
import pandas as pd
import pytest

from water01.domain.config import load
from water01.hydraulics.node import DustlikNode, gate_discharge, opening_for_flow
from water01.iot.energy import EnergyNode, pv_energy_per_step
from water01.simulation.plant_loop import Actuator, IoTConfig
from water01.simulation.runner import build_controller_model
from water01.simulation.scenarios import load_config, load_supply


@pytest.fixture(autouse=True)
def _config():
    load()


@pytest.mark.parametrize("head", [2e-4, 2e-3, 5e-3, 2e-2, 0.05, 1.0])
def test_inverse_gate_law_recovers_the_requested_discharge(head):
    """Heads inside (below 10 mm) and above the transition of the head term; a discharge below that of the gate
    raised clear of the water is recovered, a larger one is reported as unreachable."""
    node = DustlikNode()
    tw, w, cd = node.tailwater_m[0], node.reg_width[0], node.cd
    hu = tw + head
    q_clear = gate_discharge(10.0 * hu, hu, tw, w, cd)
    for q in (0.05, 0.5 * q_clear, 0.95 * q_clear):
        a = opening_for_flow(q, hu, tw, w, cd)
        if q < q_clear:
            assert gate_discharge(a, hu, tw, w, cd) == pytest.approx(q, rel=1e-9)
        else:
            assert a == float("inf")


def test_inverse_gate_law_reports_unreachable_discharges():
    node = DustlikNode()
    tw, w, cd = node.tailwater_m[0], node.reg_width[0], node.cd
    assert opening_for_flow(0.05, tw + 1e-6, tw, w, cd) == float("inf")            # head too small for 0.05 m3/s
    with pytest.raises(ValueError):
        opening_for_flow(0.05, tw, tw, w, cd)                                      # no head: command lost
    a, lost = node.openings_for(np.r_[0.05, np.zeros(5)], tw)
    assert lost[0] and a[0] == node.reg_max[0]


@pytest.mark.parametrize("scenario", ["normal", "tailwater_high", "design_geometry", "manning_low", "manning_high"])
@pytest.mark.parametrize("cd_factor", [1.0, 0.9])
def test_command_constraint_never_exceeds_the_full_gate_discharge(scenario, cd_factor):
    """Regulators and barrier, tuned and untuned controller relation; the barrier discharge is not convex where the
    gates leave the water (smoother lower reach: manning_low)."""
    cfg = load_config(scenario=scenario)
    node = DustlikNode(cd=cfg.value("gate_cd") * cd_factor)
    m = build_controller_model(node, cfg)
    for h in np.linspace(1.0, 3.8, 113):
        true = node.max_flows(h)
        for j in range(6):
            alpha, beta = m.chords[j]
            assert np.min(alpha + beta * h) <= true[j] + 1e-9
    assert np.allclose(m.max_flows(3.0), node.max_flows(3.0))


def test_deadband_without_quantisation_keeps_small_changes():
    node = DustlikNode()
    act = Actuator(node, IoTConfig(gate_deadband=0.005), np.zeros(6))
    prev = np.full(6, 0.5)
    a = prev.copy(); a[0] += 0.002 * node.max_opening[0]; a[1] += 0.01 * node.max_opening[1]; a[2] = 0.0
    out = act.executable(a, prev)
    assert out[0] == 0.5 and out[1] == a[1] and out[2] == 0.0          # closure is always executed


def test_resolution_alone_is_not_ideal():
    assert not IoTConfig(sensor_resolution_m=0.01).ideal and not IoTConfig(gate_deadband=0.005).ideal
    assert IoTConfig().ideal


def test_pv_energy_requires_a_step_that_divides_an_hour():
    with pytest.raises(ValueError):
        pv_energy_per_step(np.full(24, 500.0), 960.0)
    e = pv_energy_per_step(np.full(24, 1000.0), 900.0, pv_peak_w=400.0, performance_ratio=1.0)
    assert e.size == 96 and e.sum() == pytest.approx(400.0 * 24)


def test_offline_steps_count_the_state_during_the_step():
    en = EnergyNode(pv_wh=np.zeros(10), dt_s=900.0)
    en.state.wh = en.b_min_wh + en.b_reserve_wh + 1e-6                  # drops below the reserve in this step
    assert en.advance(0, 0) is False and en.radio_off_steps == 0
    en.advance(1, 0)
    assert en.radio_off_steps == 1


def test_supply_is_sorted_before_blank_days_are_filled(tmp_path):
    p = tmp_path / "s.csv"
    pd.DataFrame({"date": ["2010-04-03", "2010-04-01", "2010-04-02"], "kegeyli_Q": [30.0, np.nan, 20.0]}).to_csv(
        p, index=False)
    s = load_supply(p, blank_policy="carry_forward")
    assert list(s.S_m3s) == [20.0, 20.0, 30.0]                          # 1 April: first later value (back-fill)
