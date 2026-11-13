"""Closed-loop sensitivity cases: control step, demand of R-1 in early April, gate parameters, demand of the users,
closure at the start of the day and equal splits with few openings (seasons 2010-2019).

Each job (case, method, season) runs in closed loop with the Saint-Venant plant exactly as in scripts/run_cases.py
(water01.simulation.runner.run_closed_loop_period, tuned gate coefficients, quantised actuator only) and writes
results/runs/<case>/<method>_<season>.csv with the daily table of scripts/run_cases.py plus, for each regulator, the
gate movements of the day (moves_*), the openings of a closed gate (opened_*), the travel in units of the full travel
(travel_*), the opening at the day break in resolution steps (break_steps_*) and, for the rules with closure at the
start of the day, the closures (start_closed_*). The .meta.json file has the fields of scripts/run_cases.py and the
checksums of scripts/rules_variants.py and of this script. The simulation core, scripts/rules.py and
scripts/run_cases.py are not modified.

Scenario options read by this script (additions of configs/scenarios/*.yaml):
  demand_scale             - demand of every outlet and decade multiplied by this factor;
  demand_r1_april_factor   - demand of R-1 in the first decade of April multiplied by this factor;
  plant_tailwater_offset_m - tail-water levels of the regulators in the plant shifted by this amount (the
                             controller's model keeps the configured levels).
The modified demand is written to results/inputs/sensitivity/demand_<scenario>.csv and its checksum is kept in the
.meta.json file.

Usage:
    python scripts/run_sensitivity.py --groups R1,DT          # run the jobs of these groups (resumable)
    python scripts/run_sensitivity.py --groups all --list     # list the jobs and their state
    python scripts/run_sensitivity.py --groups all --max-minutes 110   # start no job after 110 minutes
    python scripts/run_sensitivity.py --cases q_dt30 --years 2010      # the jobs of these cases and seasons
    python scripts/run_sensitivity.py --cases q_dt30 --years 2010 --check DIR
                    # re-run the stored jobs into DIR and compare their daily tables with the stored ones
"""
import argparse
import contextlib
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

import water01.simulation.runner as core_runner  # noqa: E402
from water01.domain.config import optional  # noqa: E402
from water01.domain.passport import USERS, value  # noqa: E402
from water01.simulation.provenance import config_inputs, sha256, write_metadata  # noqa: E402
from water01.simulation.scenarios import iot_scenario, load_config  # noqa: E402

import rules  # noqa: E402
import rules_variants  # noqa: E402
import run_cases as rc  # noqa: E402

RUNS = ROOT / "results/runs"
DEMAND_DIR = Path("results/inputs/sensitivity")
YEARS = rc.YEARS
R1_INDEX = 2                                 # j of R-1 in the demand file (1-based)
T = ("LXB", "LXB-T050", "LXB-CO")
PAIR = ("LXB-T050", "LXB-CO")

# case -> (scenario, chain, methods)
CASES = {
    "q_r1apr_050": ("r1_april_050", "Q", T),
    "q_r1apr_100": ("r1_april_100", "Q", T),
    "q_r1apr_150": ("r1_april_150", "Q", T),
    "q_r1apr_180": ("r1_april_180", "Q", ("LXB",)),
    "q_r1apr_200": ("r1_april_200", "Q", T),
    "q_dt30": ("dt_30min", "Q", T),
    "q_dt5": ("dt_5min", "Q", T),
    "q_main_ext": ("normal", "Q", PAIR),
    "q_variants": ("normal", "Q", ("LXB-T050S", "LXB-COS", "LXB-ESM", "LXB-ESL")),
    "q_tw_high": ("tailwater_high", "Q", ("LXB",)),
    "q_bias_cd_low": ("bias_cd_low", "Q", PAIR),
    "q_bias_cd_high": ("bias_cd_high", "Q", PAIR),
    "q_bias_tw_high": ("bias_tailwater_high", "Q", PAIR),
    "q_bias_tw_low": ("bias_tailwater_low", "Q", PAIR),
    "q_bias_cd_low_apr": ("bias_cd_low_april", "Q", ("LXB",)),
    "q_bias_cd_high_apr": ("bias_cd_high_april", "Q", ("LXB",)),
    "q_bias_tw_high_apr": ("bias_tailwater_high_april", "Q", ("LXB",)),
    "q_bias_tw_low_apr": ("bias_tailwater_low_april", "Q", ("LXB",)),
    "q_dem_B": ("demand_area", "Q", T),
    "q_dem_C": ("demand_capacity", "Q", T),
    "q_dem_080": ("demand_scale_080", "Q", PAIR),
    "q_dem_120": ("demand_scale_120", "Q", PAIR),
}
GROUPS = {"R1": ("q_r1apr_100", "q_r1apr_050", "q_r1apr_150", "q_r1apr_180", "q_r1apr_200"),
          "DT": ("q_dt30", "q_dt5"),
          "RULES": ("q_main_ext", "q_variants"),
          "GATE": ("q_tw_high", "q_bias_cd_low_apr", "q_bias_cd_high_apr", "q_bias_tw_high_apr", "q_bias_tw_low_apr",
                   "q_bias_cd_low", "q_bias_cd_high", "q_bias_tw_high", "q_bias_tw_low"),
          "DEMAND": ("q_dem_B", "q_dem_C", "q_dem_080", "q_dem_120")}
ORDER = ("R1", "RULES", "DT", "GATE", "DEMAND")


def jobs(groups):
    out = []
    for g in groups:
        for case in GROUPS[g]:
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


def claim_path(job):
    return result_path(job).with_suffix(".claim")


def boot_id():
    """Identifier of the running system (Linux), so that a claim made before a restart is not taken for a live one."""
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def claim(job):
    p = claim_path(job)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, f"{os.getpid()} {time.time():.0f} {boot_id()}".encode()); os.close(fd)
    return True


def release_stale_claims(todo):
    """Removes the claim of an incomplete job whose process no longer runs (a worker stopped by a time limit or a
    restart of the system)."""
    n = 0
    for j in todo:
        p = claim_path(j)
        if not p.exists() or complete(j):
            continue
        try:
            fields = p.read_text().split()
            pid = int(fields[0])
            if len(fields) > 2 and fields[2] != boot_id():
                raise OSError("claim made before a restart")
            os.kill(pid, 0)
            continue                                     # the claiming process still runs
        except (ValueError, IndexError, OSError):
            pass
        p.unlink(missing_ok=True); n += 1
    return n


# --- inputs ---------------------------------------------------------------------------------------------------------
def demand_file(cfg):
    """Demand file of the active scenario (relative to ROOT): the processed file, or a modified copy."""
    scale = optional("demand_scale", None)
    r1 = optional("demand_r1_april_factor", None)
    if scale is None and r1 is None:
        return Path(rc.DEM)
    df = pd.read_csv(ROOT / rc.DEM)
    f = np.ones(len(df))
    if scale is not None:
        f *= float(scale)
    if r1 is not None:
        f = np.where((df["j"] == R1_INDEX) & (df["month"] == 4) & (df["decade"] == 1), f * float(r1), f)
    df["D_mln_m3"] = df["D_mln_m3"] * f
    df["q_mean_m3s"] = df["q_mean_m3s"] * f
    rel = DEMAND_DIR / f"demand_{cfg.scenario}.csv"
    text = df.to_csv(index=False, float_format="%.17g", lineterminator="\n")
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        tmp = path.with_name(f"{path.name}.{os.getpid()}.part")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    return rel


@contextlib.contextmanager
def plant_tailwater(offset):
    """Builds the plant node of run_closed_loop_period (the node created with an offtake factor) with the tail-water
    levels shifted by offset; the controller's model keeps the configured levels."""
    if not offset:
        yield None
        return
    base = core_runner.DustlikNode
    made = {"plant": 0, "model": 0}

    def factory(*args, **kw):
        if "offtake_factor" in kw:
            kw["tailwater_m"] = tuple(float(h) + float(offset) for h in value("regulator_tailwater_m"))
            made["plant"] += 1
        else:
            made["model"] += 1
        return base(*args, **kw)

    core_runner.DustlikNode = factory
    try:
        yield made
    finally:
        core_runner.DustlikNode = base
    if made["plant"] != 1:
        raise RuntimeError(f"expected one plant node, built {made['plant']}")


# --- results ---------------------------------------------------------------------------------------------------------
def gate_columns(df, out, cfg):
    """Gate movements and day-break openings of the five regulators (definitions of scripts/gate_activity.py)."""
    res = out["result"]; spd = cfg.steps_per_day; P = len(df)
    a = np.asarray(res.trace["openings"], float)                 # [steps x 6], m
    amax = np.asarray(core_runner.DustlikNode().max_opening, float)
    prev = np.vstack([np.zeros((1, a.shape[1])), a[:-1]])       # opening before each step (closed at the start)
    changed = np.abs(a - prev) > 1e-12
    opened = (prev <= 0) & (a > 0)
    rho = float(value("gate_resolution_fraction"))
    extra = {}
    for j, u in enumerate(USERS[:rules.N_REGULATORS]):
        mv = np.zeros(P, int); op = np.zeros(P, int); tr = np.zeros(P); br = np.zeros(P, int); sc = np.zeros(P, int)
        for p in range(P):
            sl = slice(p * spd, (p + 1) * spd)
            mv[p] = int(changed[sl, j].sum()); op[p] = int(opened[sl, j].sum())
            tr[p] = float(np.abs(a[sl, j] - prev[sl, j]).sum() / amax[j])
            br[p] = int(round(prev[p * spd, j] / (rho * amax[j])))
            rec = rules.LOG.get(p)
            if rec is not None and "start_closed" in rec:
                sc[p] = int(rec["start_closed"][j])
        extra.update({f"moves_{u}": mv, f"opened_{u}": op, f"travel_{u}": tr, f"break_steps_{u}": br,
                      f"start_closed_{u}": sc})
    return pd.concat([df, pd.DataFrame(extra, index=df.index)], axis=1)


def run(job, path=None):
    """Runs one job and writes its daily table and .meta.json file to path (default: the stored result)."""
    case, method, year = job
    scenario, chain, _ = CASES[case]
    cfg = load_config(scenario=scenario)
    rules_variants.register()
    rules.LOG.clear()
    iot = iot_scenario(cfg, rc.CHAINS[chain])
    start = f"{year}-{cfg.season_start}"; days = cfg.season_days
    dem = demand_file(cfg)
    t0 = time.time()
    with plant_tailwater(optional("plant_tailwater_offset_m", 0.0)):
        out = core_runner.run_closed_loop_period(method, ROOT / rc.SUP, ROOT / dem, cfg, start, days, tuned=True,
                                                 iot=iot, seed=cfg.seed + year)
    df = gate_columns(rc.daily_table(job, out, cfg), out, cfg)
    path = result_path(job) if path is None else Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    df.to_csv(tmp, index=False)
    inputs = list(config_inputs(cfg, ROOT)) + [rc.SUP, dem.as_posix()]
    meta = write_metadata(path, ROOT, inputs, {"case": case, "method": method, "year": year, "chain": chain,
                                                "scenario": scenario, "tuned": "tuned", "start": start,
                                                "days": days, "seed": cfg.seed + year}, cfg)
    m = json.loads(meta.read_text(encoding="utf-8"))
    m["core_sha256"] = rc.tree_sha256(list((ROOT / "src/water01").rglob("*.py")))
    m["rules_sha256"] = sha256(ROOT / "scripts/rules.py")
    m["runner_sha256"] = sha256(ROOT / "scripts/run_cases.py")
    m["rules_variants_sha256"] = sha256(ROOT / "scripts/rules_variants.py")
    m["sensitivity_runner_sha256"] = sha256(Path(__file__).resolve())
    m["minutes"] = round((time.time() - t0) / 60, 2)
    meta.write_text(json.dumps(m, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return (time.time() - t0) / 60


def check(todo, out_dir):
    """Re-runs stored jobs into out_dir and compares their daily tables with the stored ones: the same columns and days,
    equal text columns, missing values at the same places and numeric columns within 1e-6 (m3 for the volumes).
    Returns the number of jobs that differ."""
    bad = 0
    for j in todo:
        if not complete(j):
            print(*j, "not stored", flush=True)
            continue
        p = Path(out_dir) / j[0] / f"{j[1]}_{j[2]}.csv"
        run(j, p)
        a, b = pd.read_csv(result_path(j)), pd.read_csv(p)
        same = list(a.columns) == list(b.columns) and len(a) == len(b)
        d = float("nan")
        if same:
            num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c])]
            txt = [c for c in a.columns if c not in num]
            A, B = a[num].to_numpy(float), b[num].to_numpy(float)
            diff = np.abs(A - B)
            d = float(np.nanmax(diff)) if np.isfinite(diff).any() else 0.0
            same = (np.array_equal(np.isnan(A), np.isnan(B)) and a[txt].astype(str).equals(b[txt].astype(str))
                    and d <= 1e-6)
        bad += not same
        print(*j, f"largest difference {d:.3g}:", "reproduced" if same else "DIFFERS", flush=True)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--groups", default="R1", help="comma-separated groups or 'all'")
    ap.add_argument("--cases", default=None, help="comma-separated cases (instead of --groups)")
    ap.add_argument("--years", default=None, help="comma-separated seasons (default: all)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=None, help="start no new job after this many minutes")
    ap.add_argument("--check", default=None, metavar="DIR",
                    help="re-run the selected stored jobs into DIR and compare their daily tables with the stored ones")
    a = ap.parse_args()
    groups = ORDER if a.groups == "all" else tuple(a.groups.split(","))
    todo = [(c, m, y) for c in a.cases.split(",") for m in CASES[c][2] for y in YEARS] if a.cases else jobs(groups)
    if a.years:
        seasons = {int(y) for y in a.years.split(",")}
        todo = [j for j in todo if j[2] in seasons]
    if a.check:
        sys.exit(1 if check(todo, a.check) else 0)
    if a.list:
        for j in todo:
            state = "done" if complete(j) else ("claimed" if claim_path(j).exists() else "todo")
            print(*j, state)
        return
    freed = release_stale_claims(todo)
    print(f"jobs: {len(todo)}, complete: {sum(complete(j) for j in todo)}, stale claims released: {freed}", flush=True)
    t0 = time.time(); k = 0
    for j in todo:
        if a.max_minutes is not None and (time.time() - t0) / 60 > a.max_minutes:
            print("time limit reached", flush=True)
            break
        if complete(j) or not claim(j):
            continue
        try:
            mins = run(j); msg = "ok"
        except Exception as e:                    # noqa: BLE001 (record and continue)
            result_path(j).with_suffix(".error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            mins = 0.0; msg = f"FAILED {e}"
        k += 1
        print(f"{j[0]} {j[1]} {j[2]}: {mins:.2f} min {msg} (elapsed {(time.time() - t0) / 60:.1f} min)", flush=True)
    print(f"done: {k} jobs in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
