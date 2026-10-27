"""Closed-loop simulation cases for the quantised max-min study (seasons 2010-2019, 1 April - 30 September).

Each job (case, method, season) runs one method of water01.control.CONTROLLERS or of scripts/rules.py in closed loop
with the Saint-Venant plant (water01.simulation.runner.run_closed_loop_period, tuned gate coefficients) and writes
results/runs/<case>/<method>_<season>.csv with one row per day and a .meta.json file (environment, code and input
checksums, configuration). Several instances may run at once: every job is claimed by an exclusive file first, and a
complete result is never recomputed.

Execution chains: phys - ideal execution (no IoT constraint); Q - quantised actuator only (exact level, no message or
energy constraint; the setting of Theorems 1-4); iot - quantised actuator, level sensor, communication and energy.

Usage:
    python scripts/run_cases.py --phases A            # run the jobs of phase A (resumable)
    python scripts/run_cases.py --phases A,B,C --list # list the jobs and their state
"""
import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from water01.domain.passport import USERS  # noqa: E402
from water01.simulation.provenance import config_inputs, sha256, write_metadata  # noqa: E402
from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import AVAILABLE_FACTORS, iot_scenario, load_config  # noqa: E402

import rules  # noqa: E402

SUP = "DATA/processed/rashod_2010_2019_daily.csv"
DEM = "DATA/processed/demand_decadal.csv"
YEARS = tuple(range(2010, 2020))
RUNS = ROOT / "results/runs"
CHAINS = {"phys": (), "Q": ("quantisation",), "iot": AVAILABLE_FACTORS}
THETA_RULES = ("LXB-T000", "LXB-T025", "LXB-T050", "LXB-T075")

# case -> (scenario, chain, methods)
CASES = {
    "phys": ("normal", "phys", ("LXB",)),
    "q_main": ("normal", "Q", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
    "q_theta": ("normal", "Q", ("LXB-T025", "LXB-T075")),
    "iot_main": ("normal", "iot", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
    "q_deadband_low": ("deadband_low", "Q", ("LXB",)),
    "q_deadband_high": ("deadband_high", "Q", ("LXB",)),
    "q_cd_low": ("gate_cd_low", "Q", ("LXB",)),
    "q_cd_high": ("gate_cd_high", "Q", ("LXB",)),
    "q_leak_005mm": ("gate_leak_005mm", "Q", ("LXB",)),
    "q_rating": ("rating_outlets", "Q", ("LXB-T050", "LXB-CO")),
}
PHASES = {"A": ("phys", "q_main"), "B": ("q_theta", "iot_main"),
          "C": ("q_deadband_low", "q_deadband_high", "q_cd_low", "q_cd_high", "q_leak_005mm", "q_rating")}


def jobs(phases):
    out = []
    for ph in phases:
        for case in PHASES[ph]:
            for method in CASES[case][2]:
                out += [(case, method, y) for y in YEARS]
    return out


def result_path(job):
    case, method, year = job
    return RUNS / case / f"{method}_{year}.csv"


def complete(job):
    p = result_path(job); meta = p.with_name(p.name + ".meta.json")
    if not (p.exists() and meta.exists()):
        return False
    try:
        return len(pd.read_csv(p, usecols=["date"])) == json.loads(meta.read_text(encoding="utf-8"))["params"]["days"]
    except (OSError, ValueError, KeyError):
        return False


def claim(job):
    p = result_path(job).with_suffix(".claim")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.close(os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def tree_sha256(paths):
    import hashlib
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda q: q.relative_to(ROOT).as_posix()):
        h.update(p.relative_to(ROOT).as_posix().encode() + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def daily_table(job, out, cfg):
    case, method, year = job
    res = out["result"]; D = out["D"]; spd = cfg.steps_per_day; P = D.shape[1]
    tr = res.trace
    start = pd.Timestamp(f"{year}-{cfg.season_start}")
    dates = pd.date_range(start, periods=P, freq="D")
    openings = np.asarray(tr["openings"], float)                # [steps x 6]
    rows = []
    for p in range(P):
        sl = slice(p * spd, (p + 1) * spd)
        rec = rules.LOG.get(p)
        row = {"case": case, "method": method, "year": year, "date": dates[p].date(),
               "lambda": out["lambda_daily"][p],
               "h_min": float(np.min(tr["h_true"][sl])), "h_max": float(np.max(tr["h_true"][sl])),
               "h_est_min": float(np.min(tr["h_est"][sl])), "h_est_max": float(np.max(tr["h_est"][sl]))}
        for j, u in enumerate(USERS):
            Dj = float(D[j, p]); Vj = float(res.delivered[j, p])
            row[f"D_{u}"] = Dj
            row[f"x_{u}"] = float(rec["x"][j]) if rec is not None else float(res.targets[j, p])
            row[f"xt_{u}"] = float(res.targets[j, p])
            row[f"V_{u}"] = Vj
            row[f"Vhat_{u}"] = float(res.delivered_est[j, p])
            row[f"r_{u}"] = min(Vj / Dj, 1.0) if Dj > 0 else np.nan
            row[f"open_{u}"] = int(np.sum(openings[sl, j] > 0))
            if j < rules.N_REGULATORS:
                row[f"pulses_{u}"] = int(rec["pulses"][j]) if rec is not None else 0
                row[f"esopen_{u}"] = int(rec["es_open"][j]) if rec is not None else 0
                row[f"m_{u}"] = int(rec["m"][j]) if rec is not None else 0
                row[f"mode_{u}"] = rec["mode"][j] if rec is not None else "LP"
        rows.append(row)
    df = pd.DataFrame(rows)
    df["mass_error"] = res.mass_error
    df["storage_change_share_season"] = out["storage_change_share"]
    df["messages_dropped"] = res.messages_dropped
    df["low_head_steps"] = res.low_head_steps
    df["interlock_steps"] = res.interlock_steps
    df["relief_steps"] = res.relief_steps
    return df


def run(job):
    case, method, year = job
    scenario, chain, _ = CASES[case]
    cfg = load_config(scenario=scenario)
    rules.register()
    rules.LOG.clear()
    iot = iot_scenario(cfg, CHAINS[chain])
    start = f"{year}-{cfg.season_start}"; days = cfg.season_days
    t0 = time.time()
    out = run_closed_loop_period(method, ROOT / SUP, ROOT / DEM, cfg, start, days, tuned=True, iot=iot,
                                 seed=cfg.seed + year)
    df = daily_table(job, out, cfg)
    path = result_path(job); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    df.to_csv(tmp, index=False)
    inputs = list(config_inputs(cfg, ROOT)) + [SUP, DEM]
    if "energy" in CHAINS[chain]:
        inputs.append(f"DATA/raw/nasa_power/nasa_power_hourly_{year}.csv")
    meta = write_metadata(path, ROOT, inputs, {"case": case, "method": method, "year": year, "chain": chain,
                                                "scenario": scenario, "tuned": "tuned", "start": start,
                                                "days": days, "seed": cfg.seed + year}, cfg)
    m = json.loads(meta.read_text(encoding="utf-8"))
    m["core_sha256"] = tree_sha256(list((ROOT / "src/water01").rglob("*.py")))
    m["rules_sha256"] = sha256(ROOT / "scripts/rules.py")
    m["runner_sha256"] = sha256(ROOT / "scripts/run_cases.py")
    m["minutes"] = round((time.time() - t0) / 60, 2)
    meta.write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return (time.time() - t0) / 60


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phases", default="A")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    todo = jobs(a.phases.split(","))
    if a.list:
        for j in todo:
            state = "done" if complete(j) else ("claimed" if result_path(j).with_suffix(".claim").exists() else "todo")
            print(*j, state)
        return
    print(f"jobs: {len(todo)}, complete: {sum(complete(j) for j in todo)}", flush=True)
    t0 = time.time(); k = 0
    for j in todo:
        if complete(j) or not claim(j):
            continue
        try:
            mins = run(j); msg = "ok"
        except Exception as e:                    # noqa: BLE001 (record and continue)
            result_path(j).with_suffix(".error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            mins = (time.time() - t0) / 60; msg = f"FAILED {e}"
        k += 1
        print(f"[{k}] {j[0]}/{j[1]}/{j[2]} {msg} ({mins:.1f} min; total {(time.time() - t0) / 3600:.2f} h)",
              flush=True)


if __name__ == "__main__":
    main()
