"""Numerical convergence of the plant (Table S2a).

Test case: from the steady state at 86.7 m3/s and H_norm, the head discharge drops to 70 m3/s with fixed gates at the
node. Recorded: the node level h_L and the outflow Q_L after 6 h, and two measures that are sensitive to the
travelling wave: the largest deviation of the node-level trajectory from the reference trajectory (sampled every
15 min) and the arrival time of the wave, when the node level has fallen by 1 cm.
(a) grid: N = 21, 41, 58 (baseline, dx about 200 m), 81 and 161 nodes, dt = 15 min;
(b) time step: dt = 15, 7.5, 3.75, 1.875 and 0.9375 min, N = 58. The reference is the finest variant.
By default the pool has no distributed loss (eta = 1); --eta 0.81 repeats the test with the loss (5) of the baseline,
starting from the steady profile with that loss and the barrier opening that passes the outflow eta * 86.7 m3/s.
Usage: python scripts/verification_convergence.py [--eta 0.81]
       ->  results/verification/convergence.csv and .md (eta = 1) or convergence_eta0.81.csv and .md
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.geometry import Reach  # noqa: E402
from water01.hydraulics.node import DustlikNode  # noqa: E402
from water01.hydraulics.preissmann import PreissmannSolver  # noqa: E402
from water01.hydraulics.saint_venant import inflow_bc, outflow_bc, steady_profile  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402

Q_C, Q_NEW, HOURS = 86.7, 70.0, 6.0
REG = (0.5, 0.2, 0.2, 0.3, 0.2)


def run(N, dt, eta=1.0):
    cfg = load_config()
    r = Reach(N=N); node = DustlikNode()
    h0, Q0 = steady_profile(r, Q_C, cfg.H_norm_m, eta=eta)
    q_reg = node.offtakes(h0[-1], REG).sum()
    a_bar = brentq(lambda a: node.barrier(h0[-1], a) - (float(Q0[-1]) - q_reg), 1e-4, 3.0, xtol=1e-12)
    s = PreissmannSolver(r, dt, h0, Q0, inflow_bc(lambda t: Q_NEW if t > 0 else Q_C),
                         outflow_bc(lambda t, hN: node.outflow(hN, REG, a_bar)), eta=eta)
    every = int(round(900.0 / dt)); traj = [float(s.h[-1])]
    for k in range(1, int(round(HOURS * 3600 / dt)) + 1):
        s.step()
        if k % every == 0:
            traj.append(float(s.h[-1]))
    traj = np.array(traj)
    drop = np.nonzero(traj <= traj[0] - 0.01)[0]
    arrival = float(drop[0] * 15.0) if drop.size else np.nan            # minutes, at 15-min resolution
    return float(s.h[-1]), float(s.Q[-1]), r.L / (N - 1), traj, arrival


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eta", type=float, default=1.0, help="delivery factor of the pool (default 1: no loss)")
    eta = ap.parse_args().eta
    rows = []
    trajs = []
    for test, N, dt in [("grid", N, 900.0) for N in (21, 41, 58, 81, 161)] + \
                       [("time_step", 58, dt) for dt in (900.0, 450.0, 225.0, 112.5, 56.25)]:
        h, q, dx, traj, arr = run(N, dt, eta)
        rows.append(dict(test=test, N=N, dx_m=dx, dt_s=dt, h_L=h, Q_L=q, arrival_min=arr)); trajs.append(traj)
    t = pd.DataFrame(rows)
    ref_traj = {"grid": trajs[4], "time_step": trajs[9]}
    t["max_traj_dev_mm"] = [float(np.abs(tr - ref_traj[x]).max() * 1000) for x, tr in zip(t.test, trajs)]
    for test, ref in (("grid", t[(t.test == "grid") & (t.N == 161)].iloc[0]),
                      ("time_step", t[(t.test == "time_step") & (t.dt_s == 56.25)].iloc[0])):
        m = t.test == test
        t.loc[m, "dh_vs_ref_mm"] = (t.loc[m, "h_L"] - ref.h_L) * 1000
        t.loc[m, "dQ_vs_ref_pct"] = (t.loc[m, "Q_L"] - ref.Q_L) / ref.Q_L * 100
    out = ROOT / "results/verification"; out.mkdir(parents=True, exist_ok=True)
    name = "convergence" if eta == 1.0 else f"convergence_eta{eta:g}"
    t.insert(0, "eta", eta)
    t.to_csv(out / f"{name}.csv", index=False)
    lines = ["| Test | N | Δx, m | Δt, s | h_L, m | Q_L, m³/s | Δh vs ref, mm | ΔQ vs ref, % | max trajectory "
             "deviation, mm | arrival, min |", "|" + "---|" * 10]
    for r in t.itertuples():
        lines.append(f"| {r.test} | {r.N} | {r.dx_m:.0f} | {r.dt_s:.0f} | {r.h_L:.4f} | {r.Q_L:.3f} | "
                     f"{r.dh_vs_ref_mm:+.2f} | {r.dQ_vs_ref_pct:+.3f} | {r.max_traj_dev_mm:.2f} | {r.arrival_min:.0f} |")
    (out / f"{name}.md").write_text(f"Delivery factor eta = {eta:g}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
