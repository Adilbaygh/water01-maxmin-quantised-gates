"""Gate activity of the execution rules: movements and travel of every gate, per day, with the quantised actuator.

The stored daily tables (results/runs) do not keep the gate openings of the control steps. This script re-runs the
seasons of the case q_main (the quantised actuator alone, Table 2 of the article) for the five execution methods,
counts per day and outlet the control steps at which the gate opening changed (a movement), the movements that open a
closed gate and the travel (sum of the absolute changes of the opening, in units of the full travel), and checks that
the re-run reproduces the stored daily volumes. The closed loop of this case is deterministic.

Output: results/analysis/gate_activity_runs/<method>_<season>.csv (one row per day and outlet) and, after all
seasons, results/analysis/gate_activity.csv and .md (means per regulator-day with a positive plan, x > 1e-6 m3, by
method and regulator).

Usage:
    python scripts/gate_activity.py                 # all jobs, resumable
    python scripts/gate_activity.py --part 0/2      # every second job, for two processes
    python scripts/gate_activity.py --summary       # summary of the stored job files only
About 4 minutes per season and method on one core.
"""
import argparse
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

from water01.domain.passport import USERS  # noqa: E402
from water01.hydraulics.node import DustlikNode  # noqa: E402
from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import iot_scenario, load_config  # noqa: E402

import rules  # noqa: E402
import run_cases as rc  # noqa: E402
from analysis_common import markdown  # noqa: E402

CASE = "q_main"
OUT = ROOT / "results/analysis/gate_activity_runs"
TOL = 1e-6                                   # m3, reproduction of the stored daily volumes
EPS = 1e-6                                   # m3, smallest positive plan, as in scripts/analyse_theorems.py


def job_path(method, year):
    return OUT / f"{method}_{year}.csv"


def run_job(method, year):
    scenario, chain, _ = rc.CASES[CASE]
    cfg = load_config(scenario=scenario)
    rules.register()
    rules.LOG.clear()
    iot = iot_scenario(cfg, rc.CHAINS[chain])
    start = f"{year}-{cfg.season_start}"
    out = run_closed_loop_period(method, ROOT / rc.SUP, ROOT / rc.DEM, cfg, start, cfg.season_days, tuned=True,
                                 iot=iot, seed=cfg.seed + year)
    res = out["result"]; spd = cfg.steps_per_day; P = out["D"].shape[1]
    a = np.asarray(res.trace["openings"], float)                     # [steps x 6], m
    travel = np.asarray(DustlikNode().max_opening, float)              # full travel of each gate, m
    prev = np.vstack([np.zeros((1, a.shape[1])), a[:-1]])             # opening before each step (closed at the start)
    changed = np.abs(a - prev) > 1e-12
    opened = (prev <= 0) & (a > 0)
    stored = pd.read_csv(rc.RUNS / CASE / f"{method}_{year}.csv")
    rows = []
    dates = pd.date_range(start, periods=P, freq="D")
    for p in range(P):
        sl = slice(p * spd, (p + 1) * spd)
        for j, u in enumerate(USERS):
            v = float(res.delivered[j, p])
            rows.append({"method": method, "year": year, "date": dates[p].date(), "user": u,
                         "moves": int(changed[sl, j].sum()), "openings_from_closed": int(opened[sl, j].sum()),
                         "travel": float(np.abs(a[sl, j] - prev[sl, j]).sum() / travel[j]),
                         "open_steps": int((a[sl, j] > 0).sum()), "V": v,
                         "V_stored": float(stored[f"V_{u}"].iloc[p]), "x": float(stored[f"x_{u}"].iloc[p]),
                         "mode": stored[f"mode_{u}"].iloc[p] if f"mode_{u}" in stored else ""})
    df = pd.DataFrame(rows)
    dev = float((df.V - df.V_stored).abs().max())
    if dev > TOL:
        raise RuntimeError(f"{method} {year}: the re-run differs from the stored volumes by {dev:.3g} m3")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = job_path(method, year).with_suffix(".part")
    df.to_csv(tmp, index=False)
    os.replace(tmp, job_path(method, year))
    return dev


def summary():
    files = sorted(OUT.glob("*.csv"))
    if not files:
        return None
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    reg = df[df.user.isin(USERS[:5]) & (df.x > EPS)]          # residues of the programs count as zero plans
    rows = []
    for method, g in reg.groupby("method", sort=False):
        r = {"method": method, "seasons": g.year.nunique(), "regulator_days": len(g),
             "moves_per_day": g.moves.mean(), "openings_per_day": g.openings_from_closed.mean(),
             "travel_per_day": g.travel.mean()}
        for u in USERS[:5]:
            r[f"moves_{u}"] = g.loc[g.user == u, "moves"].mean()
        r["max_dev_m3"] = float((g.V - g.V_stored).abs().max())
        rows.append(r)
    s = pd.DataFrame(rows)
    order = {m: i for i, m in enumerate(["LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO"])}
    s = s.sort_values("method", key=lambda c: c.map(order)).reset_index(drop=True)
    s.to_csv(ROOT / "results/analysis/gate_activity.csv", index=False)
    (ROOT / "results/analysis/gate_activity.md").write_text(
        "Gate activity, quantised actuator (q_main): means per regulator-day with a positive plan "
        "(x > 1e-6 m3).\n\n"
        + markdown(s), encoding="utf-8")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", default="0/1")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if not a.summary:
        i, n = (int(v) for v in a.part.split("/"))
        todo = [(m, y) for m in rc.CASES[CASE][2] for y in rc.YEARS]
        for k, (m, y) in enumerate(todo):
            if k % n != i or job_path(m, y).exists():
                continue
            t0 = time.time()
            dev = run_job(m, y)
            print(f"{m} {y}: {(time.time() - t0) / 60:.1f} min, largest deviation from the stored volumes "
                  f"{dev:.2g} m3", flush=True)
    s = summary()
    if s is not None:
        print(s.to_string())


if __name__ == "__main__":
    main()
