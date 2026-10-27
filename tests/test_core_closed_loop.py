"""Closed loop: controller → gates → Dustlik node → Saint–Venant plant → measurement → estimate → controller."""
from pathlib import Path

import numpy as np
import pytest

from water01.control.lxb import blocked_durations
from water01.hydraulics.node import DustlikNode
from water01.optimization.constraints import command_limit
from water01.optimization.lexlp import solve_intraday
from water01.simulation.plant_loop import IoTConfig
from water01.simulation.runner import build_controller_model, run_closed_loop_period, run_smoke
from water01.simulation.scenarios import load_config
from _inputs import DEM, SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config()


@pytest.fixture(scope="module")
def ideal_runs():
    return {m: run_closed_loop_period(m, SUP, DEM, CFG, "2018-07-01", 1) for m in ("B3", "LXB")}


def test_closed_loop_mass_balance_and_ledger(ideal_runs):
    for out in ideal_runs.values():
        r = out["result"]
        assert r.mass_error < 1e-9
        # under ideal execution (tuned, IoT disabled) the controller estimate equals the true delivery
        assert np.allclose(r.delivered_est, r.delivered, rtol=1e-9)


def test_lxb_executes_daily_plan_on_plant(ideal_runs):
    r = ideal_runs["LXB"]["result"]
    assert np.allclose(r.delivered, r.targets, rtol=3e-3)
    h = r.trace["h_true"]
    assert CFG.h_min_operating_m - 0.05 < h.min() and h.max() < 3.43 - CFG.freeboard_m + 0.05


def test_static_smoke_is_labelled_as_code_check():
    out = run_smoke(SUP, DEM)
    assert "STATIC" in out["note"] and "NOT a result" in out["note"]


def test_feedback_holds_level_under_untuned_gates():
    """Untuned (C_d × 0.9 in the model, withdrawals × 1.05 in the plant): open-loop B3 drains the pool,
    whereas LXB corrects its plan from the measured level and keeps the level within the operating range."""
    b3 = run_closed_loop_period("B3", SUP, DEM, CFG, "2018-07-01", 1, tuned=False)["result"]
    lxb = run_closed_loop_period("LXB", SUP, DEM, CFG, "2018-07-01", 1, tuned=False)["result"]
    assert lxb.trace["h_true"].min() > CFG.h_min_operating_m - 0.05
    assert b3.trace["h_true"].min() < lxb.trace["h_true"].min() - 0.3


def test_iot_chain_is_applied():
    """Sensor error affects the estimate; the message budget limits the messages per window; if all packets are lost,
    the gates stay at their initial positions (fail-safe)."""
    iot = IoTConfig(sensor_accuracy_m=0.02, gate_resolution=0.001, gate_deadband=0.0,
                    message_window_steps=4, message_budget=1, loss_probability=0.0)
    r = run_closed_loop_period("LXB", SUP, DEM, CFG, "2018-07-01", 1, iot=iot, seed=1)["result"]
    assert np.abs(r.trace["h_est"] - r.trace["h_true"]).max() > 0
    assert r.messages_sent <= 96 // 4
    lost = IoTConfig(message_window_steps=4, message_budget=8, loss_probability=1.0)
    r2 = run_closed_loop_period("B3", SUP, DEM, CFG, "2018-07-02", 1, iot=lost)["result"]
    assert np.allclose(r2.trace["openings"], r2.trace["openings"][0])


def test_blocked_durations_cover_day():
    for k in (0, 50, 93, 95):
        tau, n_today = blocked_durations(96 - k, 8, 4, 4, 900.0)
        assert np.isclose(tau[:n_today].sum(), (96 - k) * 900.0) and np.isclose(tau[n_today:].sum(), 8 * 900.0)
        assert np.all(tau[:2] == 900.0)


def test_intraday_lp_respects_id_model_and_limits():
    m = build_controller_model(DustlikNode(), CFG)
    D = np.array([1.2e6, 3e4, 6e4, 2.5e5, 1e5, 2.5e6])
    tau, n = blocked_durations(96, 8, 4, 4, m.dt)
    sol = solve_intraday([60.0] * m.d, np.full(tau.size, 60.0), 3.0, D * 0.7, D * 0.7 / 86400, n, tau.size, m.dt,
                         m.eta, m.A_s, m.d, m.chords, m.capacity, m.h_lo, m.h_hi, m.h_ref, None, m.dq_max,
                         durations=tau)
    q, h = sol["q"], sol["h"]
    inflow = np.r_[[60.0] * m.d, np.full(tau.size, 60.0)][:tau.size]
    assert np.allclose(m.A_s * np.diff(h), tau * (m.eta * inflow - q.sum(axis=0)), atol=1e-3)   # (8)
    assert np.all(q <= m.capacity[:, None] + 1e-9) and sol["mu"] > 0.99


def test_command_limit_is_conservative_for_both_shapes():
    node = DustlikNode(); bp = np.linspace(1.6, 3.8, 8); hs = np.linspace(1.6, 3.8, 50)
    for j in (1, 5):                                             # regulator (concave) and barrier structure (convex)
        f = np.array([node.max_flows(h)[j] for h in bp])
        fr = node.max_flows(3.0)[j]; sl = (node.max_flows(3.001)[j] - node.max_flows(2.999)[j]) / 0.002
        a, b = command_limit(bp, f, 3.0, fr, sl)
        lim = np.min(a[:, None] + b[:, None] * hs[None, :], axis=0)
        true = np.array([node.max_flows(h)[j] for h in hs])
        assert np.all(lim <= true + 1e-6)


@pytest.fixture(scope="module")
def all_runs():
    return {m: run_closed_loop_period(m, SUP, DEM, CFG, "2018-07-01", 1) for m in ("B0", "B1", "B2", "B3", "LXB", "Oracle")}


def test_all_controllers_run_on_plant(all_runs):
    for name, out in all_runs.items():
        r = out["result"]
        assert r.mass_error < 1e-9, name
        assert np.all(np.isfinite(r.targets[:, 0])), name
        assert r.trace["h_true"].min() > 1.0, name


def test_baselines_behave_as_defined(all_runs):
    D = all_runs["B0"]["D"][:, 0]
    # B0: allocation proportional to area (Abad-Yarmish above its demand, the others an equal share)
    t0 = all_runs["B0"]["result"].targets[:, 0]
    area = np.array([37_161.0, 120.0, 637.0, 3_110.0, 1_027.0, 140_545.0])
    assert np.allclose(t0 / t0.sum(), area / area.sum(), rtol=1e-6)
    # B1: open loop, regulator openings are constant within the day
    op = all_runs["B1"]["result"].trace["openings"]
    assert np.allclose(op[:, :5], op[0, :5])
    # B2: the weighted sum fills the small users first and does not protect the worst-off user
    r2 = all_runs["B2"]["result"].delivered[:, 0] / D
    assert r2[1:5].min() > 0.99 and all_runs["B2"]["lambda"] < all_runs["LXB"]["lambda"]
    # LXB (ideal, tuned) matches B3 and Oracle (B3 is max–min optimal here)
    assert abs(all_runs["LXB"]["lambda"] - all_runs["B3"]["lambda"]) < 2e-3
    assert all_runs["Oracle"]["lambda"] >= all_runs["LXB"]["lambda"] - 2e-3


def test_single_loop_calls_every_controller_identically():
    """All controllers run through one loop: step() once per Δt, with the same keyword arguments."""
    from water01.control import CONTROLLERS
    from water01.simulation import runner
    for name, cls in CONTROLLERS.items():
        calls = []

        class Spy(cls):
            def step(self, **kw):
                calls.append(tuple(sorted(kw)))
                return super().step(**kw)
        Spy.name = name
        orig = runner.CONTROLLERS[name]
        runner.CONTROLLERS[name] = Spy
        try:
            run_closed_loop_period(name, SUP, DEM, CFG, "2018-07-01", 1)
        finally:
            runner.CONTROLLERS[name] = orig
        assert len(calls) == 96, name
        assert set(calls) == {("constraints", "demand", "horizon", "state", "supply")}, name


def test_plant_observe_and_actuator():
    import numpy as np
    from water01.control.interface import Command
    from water01.domain.geometry import Reach
    from water01.simulation.plant_loop import Actuator, CanalPlant
    node = DustlikNode()
    plant = CanalPlant(Reach(N=11), node, [80.0, 80.0], 0.82, 3.0, 900.0, 96, 0.6, np.random.default_rng(0), 0.0)
    a = plant.initialise_gates([0.5, 0.05, 0.05, 0.1, 0.05, 0.0])
    obs = plant.observe()
    assert obs.level == plant.truth()["level"] and np.allclose(obs.openings, a)
    act = Actuator(node, IoTConfig(message_window_steps=4, message_budget=1), a)
    moves = [act.apply(Command(openings=np.r_[a[:5], 0.3 + 0.01 * k]), 3.0, k)[5] for k in range(8)]
    assert sorted(set(np.round(moves, 6))) == [0.3, 0.34]     # 1 message / 4 steps: k = 0 and k = 4
