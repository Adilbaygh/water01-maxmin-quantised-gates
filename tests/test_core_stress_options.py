"""Stress options of the IoT layer and of the gate model (scenario additions, inactive by default): telemetry loss,
bursty channel, command delay, backhaul and mains outages, gate leakage and the energy-momentum gate relation."""
import numpy as np
import pytest

from water01.hydraulics.node import DustlikNode, em_discharge, gate_discharge
from water01.simulation.plant_loop import (Actuator, IoTConfig, burst_sequence, outage_sequence,
                                           two_state_chain)
from water01.simulation.runner import run_closed_loop_period
from water01.simulation.scenarios import iot_scenario, load_config
from _inputs import DEM, SUP  # noqa: E402

CFG = load_config()


def test_defaults_are_inactive():
    iot = IoTConfig()
    assert iot.ideal and not iot.stress
    base = iot_scenario(CFG)                               # full chain of the reference configuration
    assert not base.stress
    assert IoTConfig(uplink_loss_probability=0.1).stress and not IoTConfig(uplink_loss_probability=0.1).ideal
    assert IoTConfig(grid_outage_rate_per_day=0.2, grid_outage_mean_hours=2.0).stress


def test_two_state_chain_statistics():
    rng = np.random.default_rng(7)
    x = burst_sequence(rng, 400_000, 0.10, 8.0)
    assert abs(x.mean() - 0.10) < 0.01
    starts = np.flatnonzero(x[1:] & ~x[:-1]) + 1
    ends = np.flatnonzero(~x[1:] & x[:-1]) + 1
    n = min(len(starts), len(ends[ends > starts[0]]))
    lengths = ends[ends > starts[0]][:n] - starts[:n]
    assert abs(lengths.mean() - 8.0) < 0.4
    out = outage_sequence(np.random.default_rng(3), 96 * 20_000, 0.5, 3.0, 900.0)
    onsets = np.count_nonzero(out[1:] & ~out[:-1])
    up_days = np.count_nonzero(~out) / 96
    assert abs(onsets / up_days - 0.5) < 0.03
    assert not two_state_chain(np.random.default_rng(1), 100, 0.0, 1.0).any()
    with pytest.raises(ValueError):
        outage_sequence(np.random.default_rng(1), 10, 1.0, 0.0, 900.0)


def test_energy_momentum_relation():
    """The energy-momentum discharge is continuous across the free-drowned transition, is close to relation (6) for
    a drowned jet of a small opening, equals the free-jet energy relation below the conjugate depth, and its inverse
    in the node reproduces the commanded discharge."""
    b, cd = 1.0, 0.62
    hu = 3.0
    assert abs(em_discharge(0.02, hu, 2.6, b, cd) / gate_discharge(0.02, hu, 2.6, b, cd) - 1.0) < 0.01
    y1 = cd * 0.05
    q_free = b * y1 * np.sqrt(2 * 9.81 * (hu - y1)) / np.sqrt(1 - (y1 / hu) ** 2)
    assert np.isclose(em_discharge(0.05, hu, 0.3, b, cd), q_free, rtol=1e-12)
    a = 0.3
    hd = np.linspace(0.0, 2.9, 2901)
    q = np.array([em_discharge(a, hu, x, b, cd) for x in hd])
    assert np.all(np.diff(q) <= 1e-9)                      # tail water rising: discharge does not increase
    assert np.max(np.abs(np.diff(q))) < 0.01 * q[0]         # no jump at the transition
    node = DustlikNode(relation="energy_momentum")
    for h in (2.6, 3.0):
        for j in (1, 2, 3, 4):
            target = np.zeros(6); target[j] = 0.5 * node.max_flows(h)[j]
            openings, lost = node.openings_for(target, h)
            assert not lost[j]
            assert abs(node.offtakes(h, openings[:5])[j] - target[j]) < 1e-9
    with pytest.raises(ValueError):
        DustlikNode(relation="unknown")


def test_leakage_of_closed_regulators():
    sealed, leaky = DustlikNode(), DustlikNode(leak_opening_m=2e-4)
    h = 3.0
    closed = np.zeros(5)
    assert np.all(sealed.offtakes(h, closed) == 0.0)
    q = leaky.offtakes(h, closed)
    assert np.all(q > 0.0)
    expected = [gate_discharge(2e-4, h, hd, w, sealed.cd) for hd, w in zip(sealed.tailwater_m, sealed.reg_width)]
    assert np.allclose(q, expected)
    a = np.full(5, 0.1)                                     # larger openings are unaffected
    assert np.allclose(leaky.offtakes(h, a), sealed.offtakes(h, a))


class _Command:
    def __init__(self, openings):
        self.openings = np.asarray(openings, float); self.flows = np.full(6, np.nan)
        self.conversion_level = np.full(6, np.nan)


def test_command_delay_and_hold():
    node = DustlikNode()
    act = Actuator(node, IoTConfig(), np.zeros(6))
    target = np.r_[0.1, 0.1, 0.1, 0.1, 0.1, 0.5]
    assert np.all(act.apply(_Command(target), 3.0, 0, delay=True) == 0.0)   # delivered, executed next step
    assert act.delayed == 1
    assert np.allclose(act.apply(_Command(target), 3.0, 1), target)       # the delayed command, no new packet
    act2 = Actuator(node, IoTConfig(), np.zeros(6))
    act2.apply(_Command(target), 3.0, 0, delay=True)
    assert np.all(act2.hold() == 0.0) and act2.delayed_dropped == 1         # next step without link or mains
    act3 = Actuator(node, IoTConfig(message_window_steps=4, message_budget=8, channel_burst_fraction=0.5,
                                    channel_burst_mean_steps=2.0), np.zeros(6))
    assert np.all(act3.apply(_Command(target), 3.0, 0, channel_bad=True) == 0.0)
    assert act3.link.lost == 1


def test_zero_valued_options_reproduce_the_default_run():
    base = IoTConfig(sensor_accuracy_m=0.005, gate_resolution=0.001, gate_deadband=0.005, message_window_steps=4,
                     message_budget=8, loss_probability=0.02)
    zero = IoTConfig(**{**base.__dict__, "uplink_loss_probability": 0.0, "command_delay_probability": 0.0})
    r0 = run_closed_loop_period("LXB", SUP, DEM, CFG, "2018-07-01", 1, iot=base, seed=5)["result"]
    r1 = run_closed_loop_period("LXB", SUP, DEM, CFG, "2018-07-01", 1, iot=zero, seed=5)["result"]
    assert np.array_equal(r0.delivered, r1.delivered)
    assert np.array_equal(r0.trace["openings"], r1.trace["openings"])


def test_stress_options_act_in_closed_loop():
    base = dict(sensor_accuracy_m=0.005, gate_resolution=0.001, gate_deadband=0.005, message_window_steps=4,
                message_budget=8, loss_probability=0.02)
    r = run_closed_loop_period("LXB", SUP, DEM, CFG, "2018-07-01", 2, seed=5, iot=IoTConfig(
        **base, uplink_loss_probability=0.2, channel_burst_fraction=0.1, channel_burst_mean_steps=4.0,
        command_delay_probability=0.2, backhaul_outage_rate_per_day=1.0, backhaul_outage_mean_hours=2.0,
        grid_outage_rate_per_day=1.0, grid_outage_mean_hours=2.0))["result"]
    assert r.telemetry_lost_steps > 0 and r.burst_steps > 0 and r.commands_delayed > 0
    assert r.backhaul_off_steps > 0 and r.grid_off_steps > 0
    assert r.mass_error < 1e-9
    # gates do not move during a mains outage
    grid = run_closed_loop_period("B3", SUP, DEM, CFG, "2018-07-01", 1, seed=5, iot=IoTConfig(
        grid_outage_rate_per_day=50.0, grid_outage_mean_hours=24.0))["result"]
    assert grid.grid_off_steps > 90
    a = grid.trace["openings"]
    assert np.allclose(a, a[0])


def test_sensor_drift_raises_the_estimate_over_time():
    r = run_closed_loop_period("LXB", SUP, DEM, CFG, "2018-07-01", 2, seed=5,
                               iot=IoTConfig(sensor_drift_m_per_day=0.02))["result"]
    err = r.trace["h_est"] - r.trace["h_true"]
    assert not IoTConfig(sensor_drift_m_per_day=0.02).ideal
    assert err[96:].mean() > err[:96].mean() + 0.005


def test_rotation_serves_small_outlets_in_turn():
    """ROT under ideal execution: at most one small regulator is open at a time, the daily targets of the small
    outlets are delivered, and the node level stays near H_norm."""
    out = run_closed_loop_period("ROT", SUP, DEM, CFG, "2018-07-01", 1)
    r = out["result"]
    q = r.trace["q_cmd"]
    assert np.all((q[:, 1:5] > 0).sum(axis=1) <= 1)
    small = slice(1, 5)
    assert np.allclose(r.delivered[small, 0], r.targets[small, 0], rtol=0.02)
    assert abs(r.trace["h_true"].mean() - CFG.value("H_norm_m")) < 0.1
    # quantised actuator: the commands are executable (no small regulator below the deadband discharge)
    iot = IoTConfig(gate_resolution=0.001, gate_deadband=0.005)
    r2 = run_closed_loop_period("ROT", SUP, DEM, CFG, "2016-04-02", 1, iot=iot)["result"]
    assert r2.targets[1, 0] > 0
    assert r2.delivered[1, 0] > 0.5 * r2.targets[1, 0]
