"""Residual cap of direct execution on the simulated trajectories: does every request of LXB stay within the remainder
of the daily plan, and do the requests on the days of predicted exclusion stay inside the deadband?

Theorem 1(a) of the article assumes that direct execution requests in step i a volume u_i with 0 ≤ u_i ≤ R_i^+, where
R_i = x − V_i is the remainder of the daily plan. In LXB the request is the first discharge of the execution LP,
whose bound on the volume of a regulator is soft (an over-delivery variable with a penalty), so the cap is not
enforced by construction. This script re-runs LXB in every case of the article in which Theorem 1(a) is tested (the
closed loop is deterministic; the re-run reproduces the stored daily volumes) and records, for every regulator and
control step, the requested volume u = q Δt, the remainder R^+ = max(x − V̂, 0) used by the controller, and the
request in actuator steps u / v(h) at the level used for the conversion to an opening.

Output: results/analysis/residual_cap_runs/<case>_<season>.csv (one row per day and regulator) and, after all jobs,
results/analysis/residual_cap.csv and .md (one row per case).

Usage:
    python scripts/check_residual_cap.py                 # all jobs, resumable
    python scripts/check_residual_cap.py --part 0/2      # every second job, for two processes
    python scripts/check_residual_cap.py --summary       # summary of the stored job files only
About 4 minutes per season on one core.
"""
import argparse
import math
import os
import sys
import time
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from water01.control import CONTROLLERS  # noqa: E402
from water01.control.lxb import LXBController  # noqa: E402
from water01.domain.passport import USERS, value  # noqa: E402
from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import iot_scenario, load_config  # noqa: E402

import rules  # noqa: E402
import run_cases as rc  # noqa: E402
from analysis_common import Quanta, markdown  # noqa: E402

CASES = ("q_main", "q_deadband_low", "q_deadband_high", "q_cd_low", "q_cd_high", "q_leak_005mm", "iot_main")
OUT = ROOT / "results/analysis/residual_cap_runs"
TOL = 1e-6                                   # m3, reproduction of the stored daily volumes
REGULATORS = USERS[:5]


class LXBRecorder(LXBController):
    """LXB with a record of every request; the commands are those of LXB."""
    log = []

    def step(self, state, demand, supply, constraints, horizon):
        cmd = super().step(state, demand, supply, constraints, horizon)
        x = np.asarray(self.target, float)[:5]
        vhat = np.asarray(state.delivered_today, float)[:5]
        u = np.asarray(cmd.flows, float)[:5] * constraints.dt
        LXBRecorder.log.append((state.day, state.step, float(state.level), x.copy(), vhat.copy(), u.copy()))
        return cmd


def job_path(case, year):
    return OUT / f"{case}_{year}.csv"


def run_job(case, year):
    scenario, chain, methods = rc.CASES[case]
    if "LXB" not in methods:
        raise ValueError(f"case {case} has no LXB run")
    cfg = load_config(scenario=scenario)
    rules.register()
    CONTROLLERS["LXB-REC"] = LXBRecorder
    LXBRecorder.log = []
    quanta = Quanta(scenario)
    k = quanta.k
    iot = iot_scenario(cfg, rc.CHAINS[chain])
    start = f"{year}-{cfg.season_start}"
    out = run_closed_loop_period("LXB-REC", ROOT / rc.SUP, ROOT / rc.DEM, cfg, start, cfg.season_days, tuned=True,
                                 iot=iot, seed=cfg.seed + year)
    res = out["result"]; spd = cfg.steps_per_day; P = out["D"].shape[1]
    a = np.asarray(res.trace["openings"], float)[:, :5]
    h_true = np.asarray(res.trace["h_true"], float)
    stored = pd.read_csv(rc.RUNS / case / f"LXB_{year}.csv")
    log = LXBRecorder.log
    if len(log) != P * spd:
        raise RuntimeError(f"{case} {year}: {len(log)} recorded steps, expected {P * spd}")
    lev = np.array([r[2] for r in log])
    X = np.array([r[3] for r in log]); VH = np.array([r[4] for r in log]); U = np.array([r[5] for r in log])
    R = np.maximum(X - VH, 0.0)
    excess = U - R                                                     # > 0: request above the remainder
    tol = 1e-6 * np.maximum(R, 1.0)
    vstep = np.array([quanta.v(h) for h in lev])                       # one resolution step at the level used
    nreq = np.divide(U, vstep, out=np.zeros_like(U), where=vstep > 0)  # request in actuator steps
    qmin = np.array([quanta.q(h) for h in stored["h_min"]])           # quantum at the lowest level of the day
    rows = []
    dates = pd.date_range(start, periods=P, freq="D")
    for p in range(P):
        sl = slice(p * spd, (p + 1) * spd)
        for j, u in enumerate(REGULATORS):
            x = float(stored[f"x_{u}"].iloc[p])
            rows.append({"case": case, "year": year, "date": dates[p].date(), "user": u, "k": k, "x": x,
                         "q_min": float(qmin[p, j]),
                         "predicted": bool(0.0 < x < (1.0 - 1.0 / (2 * k)) * qmin[p, j] and x > 1e-6),
                         "steps_requested": int((U[sl, j] > 0).sum()),
                         "steps_above_remainder": int((excess[sl, j] > tol[sl, j]).sum()),
                         "max_excess_m3": float(excess[sl, j].max()),
                         "max_request_steps": float(nreq[sl, j].max()),
                         "opened": bool((a[sl, j] > 0).any()),
                         "V": float(res.delivered[j, p]), "V_stored": float(stored[f"V_{u}"].iloc[p]),
                         "h_min": float(h_true[sl].min()), "h_max": float(h_true[sl].max())})
    df = pd.DataFrame(rows)
    dev = float((df.V - df.V_stored).abs().max())
    if dev > TOL:
        raise RuntimeError(f"{case} {year}: the re-run differs from the stored volumes by {dev:.3g} m3")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = job_path(case, year).with_suffix(".part")
    df.to_csv(tmp, index=False)
    os.replace(tmp, job_path(case, year))
    return dev


def summary():
    files = sorted(OUT.glob("*.csv"))
    if not files:
        return None
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    rows = []
    for case in CASES:
        g = df[df.case == case]
        if g.empty:
            continue
        pos = g[g.x > 1e-6]
        pred = pos[pos.predicted]
        rows.append({"case": case, "seasons": g.year.nunique(), "k": int(g.k.iloc[0]),
                     "regulator_days_x_pos": len(pos),
                     "requests": int(g.steps_requested.sum()),
                     "requests_above_remainder": int(g.steps_above_remainder.sum()),
                     "days_with_request_above_remainder": int((g.steps_above_remainder > 0).sum()),
                     "max_excess_m3": float(g.max_excess_m3.max()),
                     "days_above_remainder_zero_plan": int(((g.steps_above_remainder > 0) & (g.x <= 1e-6)).sum()),
                     "predicted_days": len(pred),
                     "predicted_days_above_remainder": int((pred.steps_above_remainder > 0).sum()),
                     "max_request_steps_predicted": float(pred.max_request_steps.max()) if len(pred) else math.nan,
                     "deadband_limit_steps": float(g.k.iloc[0]) - 0.5,
                     "predicted_opened": int(pred.opened.sum()),
                     "max_dev_m3": float((g.V - g.V_stored).abs().max())})
    s = pd.DataFrame(rows)
    s.to_csv(ROOT / "results/analysis/residual_cap.csv", index=False)
    (ROOT / "results/analysis/residual_cap.md").write_text(
        "Residual cap of direct execution (LXB) on the simulated trajectories: requests u = q Δt of the regulators "
        "against the remainder R+ = max(x − V̂, 0) (tolerance 10⁻⁶ max(R+, 1 m³)); requests in actuator steps u / v(h) "
        "on the days of predicted exclusion against the deadband limit k − 1/2.\n\n" + markdown(s), encoding="utf-8")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", default="0/1")
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if not a.summary:
        i, n = (int(v) for v in a.part.split("/"))
        todo = [(c, y) for c in a.cases.split(",") for y in rc.YEARS]
        for kk, (c, y) in enumerate(todo):
            if kk % n != i or job_path(c, y).exists():
                continue
            t0 = time.time()
            dev = run_job(c, y)
            print(f"{c} {y}: {(time.time() - t0) / 60:.1f} min, largest deviation from the stored volumes "
                  f"{dev:.2g} m3", flush=True)
    s = summary()
    if s is not None:
        print(s.to_string())


if __name__ == "__main__":
    main()
