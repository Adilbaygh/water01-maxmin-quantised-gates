"""Last open step of the equal split with a level cap (LXB-ESL): decomposition of the error of the day.

On an equal-split day of LXB-ESL, the last open step aims at the cumulative target T = x of the day. With the volume
V' delivered before it and the request r = T - V', the error of the day is

    V - T = (U^ - r) + eta,

where U^ is the volume of the commanded (quantised) opening at the level used by the controller, so that U^ - r is the
rounding error of the step, at most half a resolution step v/2 at that level when the opening is not limited by the
deadband or the capacity, and eta = U - U^ is the change of the step volume U with the level within the step. Hence
|V - T| <= v/2 + |eta| on every such day (Remark A1 assumes eta = 0).

This script re-runs the ten seasons of q_variants/LXB-ESL with read-only instrumentation of the controller and of the
plant step: the commands and the simulated volumes are those of the stored runs, which the re-run must reproduce
within 1e-6 m3. For the last open step of every equal-split regulator-day it records the target, the volume delivered
before the step (estimated and true), the request, the commanded opening, U^, U, the levels at the start of the step
and at the ends of its hydraulic substeps, the rounding error, eta, the bound of |eta| from these levels, the error of
the day, one resolution step v at the controller's level and v at the highest level of the day (the half-step bound of
Theorem 1(b) checked in Table S8f).

Output: results/analysis/esl_last_step_runs/LXB-ESL_<season>.csv (one row per equal-split regulator-day) and, after all
seasons, results/analysis/esl_last_step.csv and .md.

Usage:
    python scripts/check_esl_last_step.py                 # all seasons, resumable
    python scripts/check_esl_last_step.py --part 0/2      # every second season, for two processes
    python scripts/check_esl_last_step.py --summary       # summary of the stored season files only
About 3 minutes per season on one core.
"""
import argparse
import contextlib
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

import water01.simulation.runner as core_runner  # noqa: E402
from water01.control import CONTROLLERS  # noqa: E402
from water01.domain.config import optional  # noqa: E402
from water01.domain.passport import USERS, value  # noqa: E402
from water01.simulation.plant_loop import CanalPlant  # noqa: E402
from water01.simulation.scenarios import iot_scenario, load_config  # noqa: E402

import rules  # noqa: E402
import rules_variants  # noqa: E402
import run_cases as rc  # noqa: E402
import run_sensitivity as rs  # noqa: E402
from analysis_common import Quanta, markdown  # noqa: E402

CASE, METHOD = "q_variants", "LXB-ESL"
OUT = ROOT / "results/analysis/esl_last_step_runs"
TOL = 1e-6                                   # m3, reproduction of the stored daily volumes
REGULATORS = USERS[:rules.N_REGULATORS]


class ESLRecorder(rules_variants.LevelCappedEqualSplitController):
    """LXB-ESL with a record of the open steps of its equal-split schedules; the commands are those of LXB-ESL."""
    log = {}

    def adjust(self, state, q, m, hz):
        q = super().adjust(state, q, m, hz)
        for j, sch in self.schedule.items():
            T = sch["targets"].get(state.step)
            if T is not None:
                ESLRecorder.log[(state.day, state.step, j)] = {
                    "T": float(T), "V_before_est": float(state.delivered_today[j]), "h_est": float(state.level),
                    "request": float(q[j] * m.dt), "last": state.step == max(sch["targets"]), "m": int(sch["m"])}
        return q


@contextlib.contextmanager
def plant_record(store):
    """Records, for every plant step, the openings, the true volumes before and in the step and the levels at the start
    of the step and at the ends of its hydraulic substeps; the plant itself is not changed."""
    original = CanalPlant.advance

    def advance(self, openings, dt):
        day, step = self.day, self.step_in_day
        h0 = float(self.solver.h[-1]); before = self.delivered.volume[:, day].copy()
        result = original(self, openings, dt)
        store[(day, step)] = {"openings": np.array(openings, float), "V_before": before, "dt": float(dt),
                              "U": self.delivered.volume[:, day] - before,
                              "levels": [h0] + [float(s[1]) for s in self.solver.last_substeps], "node": self.node}
        return result

    CanalPlant.advance = advance
    try:
        yield store
    finally:
        CanalPlant.advance = original


def job_path(year):
    return OUT / f"{METHOD}_{year}.csv"


def run_job(year):
    scenario, chain, _ = rs.CASES[CASE]
    cfg = load_config(scenario=scenario)
    rules_variants.register()
    CONTROLLERS[METHOD] = ESLRecorder
    ESLRecorder.log = {}
    rules.LOG.clear()
    iot = iot_scenario(cfg, rc.CHAINS[chain])
    start = f"{year}-{cfg.season_start}"
    plant = {}
    try:
        with rs.plant_tailwater(optional("plant_tailwater_offset_m", 0.0)), plant_record(plant):
            out = core_runner.run_closed_loop_period(METHOD, ROOT / rc.SUP, ROOT / rs.demand_file(cfg), cfg, start,
                                                     cfg.season_days, tuned=True, iot=iot, seed=cfg.seed + year)
    finally:
        rules_variants.register()                                    # restores the unrecorded LXB-ESL
    res = out["result"]
    stored = pd.read_csv(rs.result_path((CASE, METHOD, year)))
    dev = max(float(np.abs(res.delivered[j, :] - stored[f"V_{u}"].to_numpy()).max()) for j, u in enumerate(REGULATORS))
    if dev > TOL:
        raise RuntimeError(f"{year}: the re-run differs from the stored volumes by {dev:.3g} m3")
    quanta = Quanta(scenario)
    rho = float(value("gate_resolution_fraction"))
    dates = pd.date_range(start, periods=res.delivered.shape[1], freq="D")
    rows = []
    for (day, step, j), r in sorted(ESLRecorder.log.items()):
        if not r["last"]:
            continue
        p = plant[(day, step)]
        node, a, dt = p["node"], p["openings"][:5], p["dt"]
        unit = np.zeros(5); unit[j] = rho * float(node.max_opening[j])
        v_est = float(node.offtakes(r["h_est"], unit)[j] * dt)                 # one resolution step at h_est
        nominal = float(node.offtakes(r["h_est"], a)[j] * dt)                  # U^
        at_levels = [float(node.offtakes(h, a)[j] * dt) for h in p["levels"]]
        U = float(p["U"][j]); V = float(res.delivered[j, day])
        rows.append({"year": year, "date": dates[day].date(), "user": REGULATORS[j], "step": step, "m": r["m"],
                     "T": r["T"], "V_before_est": r["V_before_est"], "V_before": float(p["V_before"][j]),
                     "request": r["request"], "opening_m": float(a[j]), "h_est": r["h_est"],
                     "h_min_step": min(p["levels"]), "h_max_step": max(p["levels"]), "U_nominal": nominal, "U": U,
                     "rounding_error": nominal - r["request"], "eta": U - nominal,
                     "eta_bound": max(abs(z - nominal) for z in at_levels), "error_day": V - r["T"],
                     "v_est": v_est, "v_max_day": float(quanta.v(float(stored["h_max"].iloc[day]))[j]),
                     "V_after_step": float(p["V_before"][j]) + U, "V_day": V})
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = job_path(year).with_suffix(".part")
    df.to_csv(tmp, index=False)
    os.replace(tmp, job_path(year))
    return dev, len(df)


def summary():
    files = sorted(OUT.glob(f"{METHOD}_*.csv"))
    if not files:
        return None
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["over_daily_half_step"] = df.error_day.abs() > df.v_max_day / 2 + 1e-6
    df["within_v_est_half_plus_eta"] = df.error_day.abs() <= df.v_est / 2 + df.eta.abs() + 1e-7
    rows = []
    for key, g in list(df.groupby("year")) + [("all", df)]:
        rows.append({"season": key, "regulator_days": len(g),
                     "days_over_daily_half_step": int(g.over_daily_half_step.sum()),
                     "days_within_half_step_plus_eta": int(g.within_v_est_half_plus_eta.sum()),
                     "max_rounding_minus_half_step_m3": float((g.rounding_error.abs() - g.v_est / 2).max()),
                     "max_abs_eta_m3": float(g.eta.abs().max()),
                     "max_eta_minus_bound_m3": float((g.eta.abs() - g.eta_bound).max()),
                     "max_ledger_error_m3": float((g.V_before - g.V_before_est).abs().max()),
                     "max_identity_residual_m3": float((g.error_day - g.rounding_error - g.eta).abs().max()),
                     "max_after_step_minus_day_m3": float((g.V_after_step - g.V_day).abs().max())})
    s = pd.DataFrame(rows)
    ex = df[df.over_daily_half_step][["date", "user", "T", "error_day", "rounding_error", "eta", "v_est",
                                       "v_max_day", "h_min_step", "h_max_step"]].copy()
    ex["half_v_est"] = ex.v_est / 2; ex["half_v_max_day"] = ex.v_max_day / 2
    ex = ex.drop(columns=["v_est", "v_max_day"])
    s.to_csv(ROOT / "results/analysis/esl_last_step.csv", index=False)
    ex.to_csv(ROOT / "results/analysis/esl_last_step_exceptions.csv", index=False)
    (ROOT / "results/analysis/esl_last_step.md").write_text(
        "# Last open step of LXB-ESL on its equal-split regulator-days (q_variants, ten seasons)\n\n"
        "Error of the day V − T = rounding error at the controller's level (U^ − r) + change of the step volume with "
        "the level within the step (η = U − U^); v_est: one resolution step at the controller's level, v_max_day: at "
        "the highest level of the day (half-step bound of Theorem 1(b) in Table S8f). Re-runs reproduce the stored "
        "daily volumes within 10⁻⁶ m³; the identity residual and the ledger error are in m³.\n\n" + markdown(s) +
        "\n\n## Regulator-days above half the daily largest resolution step\n\n" + markdown(ex), encoding="utf-8")
    return s, ex


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", default="0/1")
    ap.add_argument("--years", default=",".join(str(y) for y in rc.YEARS))
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if not a.summary:
        i, n = (int(v) for v in a.part.split("/"))
        for kk, y in enumerate(int(v) for v in a.years.split(",")):
            if kk % n != i or job_path(y).exists():
                continue
            t0 = time.time()
            dev, rows = run_job(y)
            print(f"{y}: {(time.time() - t0) / 60:.1f} min, {rows} regulator-days, largest deviation from the stored "
                  f"volumes {dev:.2g} m3", flush=True)
    out = summary()
    if out is not None:
        print(out[0].to_string()); print(out[1].to_string())


if __name__ == "__main__":
    main()
