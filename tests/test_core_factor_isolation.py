"""Isolation of the IoT factors: common random numbers, initial openings, and the ideal branch of LXB-DA."""
from pathlib import Path

import numpy as np

from water01.control.interface import Command
from water01.hydraulics.node import DustlikNode
from water01.simulation.plant_loop import Actuator, IoTConfig
from water01.simulation.runner import run_closed_loop_period
from water01.simulation.scenarios import iot_scenario, load_config
from _inputs import DEM, SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _run(method, factors, start="2014-04-01", days=3):
    cfg = load_config()
    iot = iot_scenario(cfg, factors) if factors else None
    return run_closed_loop_period(method, SUP, DEM, cfg, start, days, iot=iot, seed=cfg.seed + 2014)["result"]


def test_non_binding_lossless_communication_does_not_change_the_run():
    """Adding factor C with zero loss and a non-binding budget leaves the trajectory unchanged: sensor noise and
    packet-loss draws come from separate streams that are drawn once per step."""
    cfg = load_config()
    base = _run("LXB", ("sensor", "quantisation"))
    iot = iot_scenario(cfg, ("sensor", "quantisation", "communication"))
    iot = IoTConfig(**{**iot.__dict__, "loss_probability": 0.0})
    with_c = run_closed_loop_period("LXB", SUP, DEM, cfg, "2014-04-01", 3, iot=iot, seed=cfg.seed + 2014)["result"]
    assert np.array_equal(base.delivered, with_c.delivered)
    assert np.array_equal(base.trace["h_est"], with_c.trace["h_est"])
    assert np.array_equal(base.trace["openings"], with_c.trace["openings"])


def test_sensor_noise_does_not_depend_on_the_controller(monkeypatch):
    """The same seed gives the same sensor innovation at the same step for different controllers."""
    import water01.simulation.plant_loop as pl
    seen, measure = [], pl.measure
    monkeypatch.setattr(pl, "measure", lambda *a, unit_noise=None, **k: (seen.append(unit_noise),
                                                                           measure(*a, unit_noise=unit_noise, **k))[1])
    _run("LXB", ("sensor", "communication"), days=1)
    lxb = list(seen); seen.clear()
    _run("B0", ("sensor", "communication"), days=1)
    assert len(lxb) > 90 and lxb == seen


def test_initial_openings_are_executable_under_quantisation():
    cfg = load_config()
    r = _run("LXB", ("quantisation",), days=1)
    a0 = np.asarray(r.trace["openings"])[0]
    frac = a0 / DustlikNode().max_opening
    steps = frac / cfg.gate_resolution_fraction
    assert np.allclose(steps, np.round(steps), atol=1e-9)
    assert np.all((frac == 0) | (frac >= cfg.gate_deadband_fraction - 1e-12))


def test_lxb_da_coincides_with_lxb_under_ideal_execution():
    a = _run("LXB", (), days=2)
    b = _run("LXB-DA", (), days=2)
    assert np.array_equal(a.delivered, b.delivered)


def test_lost_packet_keeps_the_current_position_after_an_interlock():
    act = Actuator(DustlikNode(), IoTConfig(message_window_steps=4, message_budget=8, loss_probability=0.5),
                   np.full(6, 0.3))
    assert act.interlock(1.0, 1.3) and np.all(act.position == 0)
    act.apply(Command(openings=np.full(6, 0.4)), 3.0, 1, link_draw=0.1)      # lost packet
    assert np.all(act.position == 0)
    act.apply(Command(openings=np.full(6, 0.4)), 3.0, 2, link_draw=0.9)      # received
    assert np.allclose(act.position, 0.4)
