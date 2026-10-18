"""§2.10 (5): checks of the reference Saint–Venant plant (Preissmann)."""
import numpy as np
import pytest

from water01.domain.geometry import Reach
from water01.domain.passport import PARAMETERS
from water01.hydraulics.node import DustlikNode, gate_discharge
from water01.hydraulics.preissmann import PreissmannSolver
from water01.hydraulics.saint_venant import (inflow_bc, level_bc, normal_depth_bc, outflow_bc,
                                             steady_profile)
from water01.optimization.constraints import identify_from_step
from water01.simulation.plant_loop import simulate, step_response

Q_C = 86.7      # critical supply at the node
DT = 900.0      # 15 min


def test_uniform_flow_is_preserved():
    r = Reach(); hn = r.normal_depth(Q_C)
    s = PreissmannSolver(r, DT, np.full(r.N, hn), np.full(r.N, Q_C), inflow_bc(lambda t: Q_C), normal_depth_bc(r))
    for _ in range(96):
        s.step()
    assert np.abs(s.h - hn).max() < 1e-8 and np.abs(s.Q - Q_C).max() < 1e-6


def test_steady_gvf_profile_with_seepage_is_preserved():
    """η = 0.82: the steady profile with distributed losses (ODE) is preserved over one day."""
    r = Reach(); eta = PARAMETERS["eta"].value
    h0, Q0 = steady_profile(r, Q_C, PARAMETERS["H_norm_m"].value, eta=eta)
    s = PreissmannSolver(r, DT, h0, Q0, inflow_bc(lambda t: Q_C), level_bc(lambda t: h0[-1]), eta=eta)
    for _ in range(96):
        s.step()
    assert np.abs(s.h - h0).max() < 1e-4                  # ODE vs discrete scheme (Δx ≈ 200 m)
    assert np.abs(s.Q - Q0).max() < 1e-3
    assert abs(s.Q[-1] - eta * Q_C) < 1e-3                # η·S reaches the node


def _step_run(N, hours=6.0, q_new=70.0):
    r = Reach(N=N); node = DustlikNode()
    h0, Q0 = steady_profile(r, Q_C, PARAMETERS["H_norm_m"].value)
    # the node gates are opened so that the initial state is steady
    reg = (0.5, 0.2, 0.2, 0.3, 0.2)
    q_reg = node.offtakes(h0[-1], reg).sum()
    a_bar = _barrier_opening_for(node, h0[-1], Q_C - q_reg)
    down = outflow_bc(lambda t, hN: node.outflow(hN, reg, a_bar))
    s = PreissmannSolver(r, DT, h0, Q0, inflow_bc(lambda t: q_new if t > 0 else Q_C), down)
    for _ in range(int(hours * 3600 / DT)):
        s.step()
    return r, s


def _barrier_opening_for(node, h_up, q):
    from scipy.optimize import brentq
    return brentq(lambda a: node.barrier(h_up, a) - q, 1e-4, 3.0, xtol=1e-12)


def test_discrete_mass_balance():
    """ΔV = Σ Δt [θ(Q_0 − Q_N) + (1−θ)(Q_0 − Q_N)_old + q_l L] to within the Newton tolerance."""
    r = Reach(); eta = 0.82
    h0, Q0 = steady_profile(r, Q_C, 3.0, eta=eta)
    s = PreissmannSolver(r, DT, h0, Q0, inflow_bc(lambda t: 60.0 + 40.0 * np.sin(t / 7200.0)),
                         outflow_bc(lambda t, hN: 50.0), eta=eta)
    V0 = r.volume(s.h); net = 0.0
    for _ in range(96):
        Qo = s.Q.copy(); s.step()
        net += DT * (s.theta * (s.Q[0] - s.Q[-1]) + (1 - s.theta) * (Qo[0] - Qo[-1]) + s.last_ql * r.L)
    err = abs(r.volume(s.h) - V0 - net)
    assert err / V0 < 1e-6


def test_grid_convergence_at_dustlik():
    """N = 21, 41, 81: node level and discharge after 6 h differ by ≤ 0.5 %, and the error decreases."""
    res = {N: _step_run(N)[1] for N in (21, 41, 81)}
    h = {N: s.h[-1] for N, s in res.items()}; q = {N: s.Q[-1] for N, s in res.items()}
    assert abs(h[41] - h[81]) / h[81] < 0.005 and abs(q[41] - q[81]) / q[81] < 0.005
    assert abs(h[21] - h[81]) > abs(h[41] - h[81])


def test_dustlik_node_outflow():
    node = DustlikNode(); reg = (0.5, 0.2, 0.2, 0.3, 0.2)
    q1 = node.outflow(3.0, reg, 0.5); q2 = node.outflow(3.2, reg, 0.5); q3 = node.outflow(3.0, reg, 0.7)
    assert 0 < q1 < q2 and q1 < q3
    # barrier structure: the tailwater level is the normal depth at that discharge (implicit equation)
    qb = node.barrier(3.0, 0.5)
    assert np.isclose(qb, gate_discharge(0.5, 3.0, node.tailwater_barrier(qb), node.bar_width, node.cd), rtol=1e-8)
    # the tailwater table differs from the exact normal depth by less than 1 mm
    assert all(abs(node.tailwater_barrier(q) - node.lower.normal_depth(q)) < 1e-3 for q in (0.7, 5.0, 37.3, 86.7, 160.0))
    assert node.outflow(3.0, (0, 0, 0, 0, 0), 0.0) == 0.0


def test_id_model_identified_from_saint_venant_step():
    """Identification of (8) from the SV step response (Schuurmans, 1997), operating point H_norm, dQ = ±1 m³/s, 6 h.
    A_s is the area of the backwater part: 0.5·T·L < A_s < T·L; the result is insensitive to ±dQ and the grid (≤ 5 %).
    τ is positive and does not exceed the wave travel time along the pool (≈ 32 min)."""
    hold = PARAMETERS["H_norm_m"].value; out = {}
    for N, dt in ((58, DT), (115, DT / 2)):
        for dq in (1.0, -1.0):
            run = step_response(Reach(N=N), Q_C, hold, dq, 6 * 3600, dt)
            out[N, dq] = identify_from_step(run["t"], run["h_L"], dq)
    A_TL = PARAMETERS["A_s_m2"].value
    A = np.array([v[0] for v in out.values()]); tau = np.array([v[1] for v in out.values()])
    assert np.all((0.5 * A_TL < A) & (A < A_TL))
    assert (A.max() - A.min()) / A.mean() < 0.05
    r = Reach(); c = np.sqrt(9.81 * r.area(hold) / r.top(hold)); v = Q_C / r.area(hold)
    assert np.all((0 < tau) & (tau <= r.L / (c + v)))
    assert abs(A.mean() - PARAMETERS["A_s_identified_m2"].value) / A.mean() < 0.02


def test_newton_failure_is_reported():
    r = Reach(N=11)
    s = PreissmannSolver(r, DT, np.full(r.N, 3.0), np.full(r.N, Q_C), inflow_bc(lambda t: Q_C),
                         normal_depth_bc(r), max_iter=1, tol=0.0)
    with pytest.raises(RuntimeError):
        s.step()


def test_simulate_records_trajectory_and_mass_balance():
    """simulation.plant_loop.simulate: trajectory length and mass balance (same criterion as the manual computation)."""
    r = Reach(); eta = 0.82
    h0, Q0 = steady_profile(r, Q_C, 3.0, eta=eta)
    s = PreissmannSolver(r, DT, h0, Q0, inflow_bc(lambda t: 60.0 + 40.0 * np.sin(t / 7200.0)),
                         outflow_bc(lambda t, hN: 50.0), eta=eta)
    out = simulate(s, 6 * 3600)
    assert out["t"].size == 25 and out["h_L"].size == 25
    assert out["mass_error"] < 1e-6
    assert s.state.t == out["t"][-1] and np.isclose(s.state.level_downstream, out["h_L"][-1])
