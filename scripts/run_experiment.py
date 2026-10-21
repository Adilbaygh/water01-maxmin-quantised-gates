"""Simulation experiment (Methods, Section 2.10): seasons 2010–2019 × controllers × tuned/untuned × IoT chain.

Usage:
    python scripts/run_experiment.py --all --jobs 4             # confirmatory sweep: 240 main + 140 Shapley + 10 ablation
    python scripts/run_experiment.py --sensitivity --jobs 4     # descriptive sensitivity cases → results/sensitivity/
    python scripts/run_experiment.py --exploratory --jobs 4     # exploratory cases → results/exploratory/
    python scripts/run_experiment.py --verify --years 2018 --methods LXB --tuned tuned --iot iot
                                                                # rerun one season into results/verification/rerun/
                                                                # and compare it with the stored result
Every parameter comes from configs/kegeyli_reference.yaml and configs/scenarios/<scenario>.yaml. Each job
(method, year, tuned, iot) writes one CSV with a .meta.json (environment, configuration, code and input checksums).
An existing result is kept only if its metadata show the current code and inputs and the table is complete;
otherwise, and always with --force, it is recomputed, so an interrupted sweep can be resumed.
Approximate time per season (183 days): B0, B1, B3 ≈ 2 min; B2, LXB, Oracle ≈ 8 min.

Protocol: results/experiment/PREREGISTRATION.json holds the SHA-256 of requirements/hypotheses.md recorded when the
hypotheses were frozen (--freeze, once). Every run checks that the protocol is unchanged and stops otherwise.
Configuration files are not part of the protocol; their checksums are recorded in each .meta.json.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

# One BLAS/OpenMP thread per worker process, so that --jobs N does not oversubscribe the cores. This must be set
# before NumPy is imported and does not affect the results.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.passport import USERS  # noqa: E402
from water01.optimization.lexlp import FALLBACKS, LEX_CHECK  # noqa: E402
from water01.optimization.objectives import satisfaction  # noqa: E402
from water01.simulation.provenance import code_sha256, config_inputs, relative_posix, sha256, write_metadata  # noqa: E402
from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import AVAILABLE_FACTORS, iot_scenario, load_config  # noqa: E402

EXP = ROOT / "results/experiment"
OUT = EXP / "normal"
SUP = ROOT / "DATA/processed/rashod_2010_2019_daily.csv"
DEM = ROOT / "DATA/processed/demand_decadal.csv"
HYP = ROOT / "requirements/hypotheses.md"
DATA = ("requirements/hypotheses.md", "DATA/processed/rashod_2010_2019_daily.csv", "DATA/processed/demand_decadal.csv")
METHODS = ("B0", "B1", "B2", "B3", "LXB", "Oracle")
CODE = {"S": "sensor", "Q": "quantisation", "C": "communication", "E": "energy"}
# Shapley coalitions other than the empty set (phys) and the full set (iot), which belong to the main sweep
SUBSETS = ("S", "Q", "C", "E", "SQ", "SC", "SE", "QC", "QE", "CE", "SQC", "SQE", "SCE", "QCE")
SENS = ROOT / "results/sensitivity"
VERIFY = ROOT / "results/verification/rerun"
CHECK = ROOT / "results/experiment_check"
SENS_METHODS = ("LXB", "B0", "B3")
# Descriptive sensitivity cases (Section 2.10): one assumption changes, tuned coefficients, no hypothesis test.
# Hydraulic and data assumptions are run with and without the IoT chain; IoT-layer assumptions only with it
# (under ideal execution they coincide with the baseline).
SENSITIVITY = {
    "supply_ramp": ("phys", "iot"), "limit_2021": ("phys", "iot"), "demand_area": ("phys", "iot"),
    "demand_capacity": ("phys", "iot"), "eta_low": ("phys", "iot"), "eta_high": ("phys", "iot"),
    "design_geometry": ("phys", "iot"), "deadband_low": ("iot",), "deadband_high": ("iot",),
    # stress tests of the energy and communication layers (inactive in the baseline)
    "energy_moderate": ("iot",), "energy_severe": ("iot",), "communication_loss": ("iot",),
    "communication_budget_2": ("iot",), "communication_budget_1": ("iot",),
    # plant/controller mismatch and persistent errors (efficiency, outlet rating, tail water, level sensor)
    "eta_true_low": ("phys", "iot"), "eta_fixed_demand_low": ("phys", "iot"), "rating_outlets": ("phys", "iot"),
    "tailwater_high": ("phys", "iot"), "sensor_bias_pos": ("iot",), "sensor_bias_neg": ("iot",),
}

EXPL = ROOT / "results/exploratory"
# Exploratory cases (not pre-specified; descriptive): case → (methods, tuned, iot). Where phys is absent, the phys
# reference is results/experiment/normal (the IoT assumptions do not affect ideal execution).
EXPLORATORY = {
    "b3_feedback": (("B3V",), ("tuned", "untuned"), ("phys", "iot")),       # proportional rationing + volume feedback
    "deadband_aware": (("LXB-DA",), ("tuned", "untuned"), ("iot",)),        # LXB with the pulse rule
    "seed_1": (("LXB", "B0", "B3"), ("tuned",), ("iot",)),                   # independent random seeds
    "seed_2": (("LXB", "B0", "B3"), ("tuned",), ("iot",)),
    "seed_3": (("LXB", "B0", "B3"), ("tuned",), ("iot",)),
    "forecast_loo": (("LXB",), ("tuned",), ("phys", "iot")),                # forecast without the simulated season
    "blank_carry": (("LXB", "B0", "B3"), ("tuned",), ("phys", "iot")),      # blank supply entries: nearest record
    "untuned_reverse": (("LXB", "B0", "B3", "B3V"), ("untuned",), ("phys", "iot")),   # reverse gate mismatch
    "final_share": (("LXB-F",), ("tuned", "untuned"), ("phys", "iot")),     # execution LP on the final daily share
    "b3v_deadband": (("B3V-DA",), ("tuned", "untuned"), ("iot",)),          # B3V with the pulse rule of LXB-DA
    "gate_head_h0": (("LXB", "B0", "B1", "B3"), ("tuned",), ("phys", "iot")),  # gate law closer to Eq. (6) at zero head
    "terminal_weight_low": (("LXB",), ("tuned", "untuned"), ("phys", "iot")),  # weak end-of-day level condition
    "plant_substeps_4": [(("LXB", "B3"), ("tuned",), ("phys", "iot")),        # hydraulic step 225 s, command 15 min
                         (("LXB-DA",), ("tuned",), ("iot",))],
    "dt_450": [(("LXB", "B3"), ("tuned",), ("phys", "iot")),                  # command step 7.5 min
               (("LXB-DA",), ("tuned",), ("iot",))],
}


def groups(case):
    """Groups (methods, tuned, iot) of an exploratory case (one tuple or a list of tuples)."""
    spec = EXPLORATORY[case]
    return spec if isinstance(spec, list) else [spec]


def runtime_inputs(cfg, iot, year):
    """Further input files of a run: the NASA POWER file of the season (energy factor) and the official 2021 limit
    profile (limit_source = limit_2021)."""
    out = []
    if "energy" in factors_of(iot):
        out.append(f"DATA/raw/nasa_power/nasa_power_hourly_{year}.csv")
    if cfg.limit_source == "limit_2021":
        out.append("DATA/processed/limit_2021_kegeyli_decadal.csv")
    return tuple(p for p in out if (ROOT / p).exists())


def factors_of(code):
    """IoT code -> factors: phys is the empty set, iot is {S, Q, C, E}, and letters give a coalition (e.g. SQ)."""
    if code == "phys":
        return ()
    if code == "iot":
        return AVAILABLE_FACTORS
    if not code or set(code) - set(CODE) or len(set(code)) != len(code):
        raise ValueError(f"Unknown IoT code: {code}")
    return tuple(CODE[c] for c in "SQCE" if c in code)


PROGRESS_DAYS = 30                                        # progress line interval (days); no effect on the results


def run_job(method, year, tuned, iot, start=None, days=None, scenario="normal", out_dir=None):
    cfg = load_config(scenario=scenario)                  # each worker process activates its own configuration
    out_dir = Path(out_dir) if out_dir else OUT
    start = start or f"{year}-{cfg.season_start}"; days = days or cfg.season_days
    t0 = time.time()
    FALLBACKS["count"] = 0; LEX_CHECK["violations"] = 0
    tag = f"{method}_{year}_{tuned}_{iot}"
    print(f"  started: {tag}", flush=True)

    def progress(p, P):
        if p % PROGRESS_DAYS == 0 and p < P:
            print(f"    {tag}: day {p}/{P}, {(time.time() - t0) / 60:.1f} min", flush=True)

    out = run_closed_loop_period(method, SUP, DEM, cfg, start, days, tuned=(tuned == "tuned"),
                                 iot=iot_scenario(cfg, factors_of(iot)), seed=cfg.seed + year,
                                 progress=progress)
    res = out["result"]; D = out["D"]; r = satisfaction(res.delivered, D)
    tr = res.trace; spd = cfg.steps_per_day
    dates = pd.date_range(start, periods=days, freq="D")
    rows = []
    for p in range(days):
        sl = slice(p * spd, (p + 1) * spd)
        row = {"method": method, "year": year, "tuned": tuned, "iot": iot, "date": dates[p].date(),
               "lambda": out["lambda_daily"][p], "h_min": tr["h_true"][sl].min(), "h_max": tr["h_true"][sl].max()}
        for j, u in enumerate(USERS):
            row[f"r_{u}"] = r[j, p]
            row[f"V_{u}"] = res.delivered[j, p]
            row[f"lost_{u}"] = int(tr["command_lost"][sl, j].sum())   # steps without head for the planned rate (H6)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["storage_change_share_season"] = out["storage_change_share"]
    df["mass_error"] = res.mass_error
    df["messages"] = res.messages_sent; df["dropped"] = res.messages_dropped
    df["blocked"] = res.messages_blocked; df["lost"] = res.messages_lost   # dropped = blocked + lost
    df["low_head_steps"] = res.low_head_steps; df["low_head_volume_m3"] = res.low_head_volume_m3
    df["lp_fallbacks"] = FALLBACKS["count"]                # solves that needed the HiGHS fallback path
    df["lex_violations"] = LEX_CHECK["violations"]          # solves in which a retained optimum was violated
    df["interlock_steps"] = res.interlock_steps; df["relief_steps"] = res.relief_steps
    df["battery_min_wh"] = res.battery_min_wh; df["radio_off_steps"] = res.radio_off_steps
    df["energy_used_wh"] = res.energy_used_wh; df["extra_substeps"] = res.extra_substeps
    path = out_dir / f"{method}_{year}_{tuned}_{iot}.csv"
    tmp = path.with_name(path.name + ".part")
    df.to_csv(tmp, index=False)
    path.with_suffix(".error.txt").unlink(missing_ok=True)   # error file left by an earlier attempt
    extra = runtime_inputs(cfg, iot, year)
    write_metadata(path, ROOT, config_inputs(cfg, ROOT) + DATA + extra,
                   {"method": method, "year": year, "tuned": tuned, "iot": iot, "start": start, "days": days,
                    "seed": cfg.seed + year}, cfg)
    os.replace(tmp, path)                                   # the table appears only after its metadata
    return path.name, out["lambda"], time.time() - t0


def is_current(path, days, code):
    """True when a stored result can be kept on resumption: its metadata exist, were written by the current code
    with the current checksums of every recorded input, and the table has one row per day."""
    meta = path.with_name(path.name + ".meta.json")
    if not (path.exists() and meta.exists()):
        return False
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
        if m.get("code_sha256") != code:
            return False
        for k, v in m.get("inputs", {}).items():
            q = ROOT / k
            if not q.exists() or sha256(q) != v:
                return False
        if days is not None and m.get("params", {}).get("days") != days:
            return False
        n = len(pd.read_csv(path, usecols=["date"]))
        return n == m.get("params", {}).get("days")
    except (OSError, ValueError, KeyError):
        return False


def _norm(key):
    """Checksum keys as POSIX paths relative to the project root, independent of the platform separator."""
    key = key.replace("\\", "/")
    return "requirements/hypotheses.md" if key == "hypotheses.md" else key


def current_checksums():
    now = {"requirements/hypotheses.md": sha256(HYP)}
    now.update({relative_posix(p, ROOT): sha256(p) for p in sorted((ROOT / "configs").rglob("*.yaml"))})
    return now


def check_preregistration(freeze):
    """The protocol is requirements/hypotheses.md: a changed checksum stops the run. Configuration files are not
    part of the protocol; differences from the frozen state are listed for information."""
    EXP.mkdir(parents=True, exist_ok=True)
    reg = EXP / "PREREGISTRATION.json"
    now = current_checksums()
    if not reg.exists():
        if not freeze:
            sys.exit("The hypotheses are not frozen yet. Run once with --freeze after the protocol is final.")
        reg.write_text(json.dumps({"frozen_utc": pd.Timestamp.now("UTC").isoformat(), "sha256": now}, indent=2))
        print(f"Protocol frozen: {reg.relative_to(ROOT).as_posix()}")
        return
    old = {_norm(k): v for k, v in json.loads(reg.read_text())["sha256"].items()}
    key = "requirements/hypotheses.md"
    if old.get(key) != now[key]:
        sys.exit(f"Stopped: {key} differs from the checksum in {reg.relative_to(ROOT).as_posix()}.")
    changed = sorted(k for k in now if k != key and old.get(k) != now[k])
    if changed:
        print(f"Protocol unchanged. Configuration files added or edited after the freeze (checksums in .meta.json): "
              f"{', '.join(changed)}", flush=True)


def compare_with_stored(new, stored):
    """Largest absolute difference of every numeric column between a rerun and the stored result."""
    a, b = pd.read_csv(new), pd.read_csv(stored)
    added = [c for c in a.columns if c not in b.columns]       # columns added by a later code version
    a = a.drop(columns=added)
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return {"shape": f"{a.shape} vs {b.shape}"}
    num = [c for c in a.select_dtypes("number").columns if c in b.select_dtypes("number").columns]
    nan_mismatch = {c: int((a[c].isna() != b[c].isna()).sum()) for c in num}
    nan_mismatch = {c: n for c, n in nan_mismatch.items() if n}
    diff = (a[num] - b[num]).abs().max()
    if nan_mismatch:                                   # a value that is missing in only one run is a difference
        diff[list(nan_mismatch)] = np.inf
    same_text = all((a[c].astype(str) == b[c].astype(str)).all() for c in a.columns if c not in num)
    return {"max_abs_diff": float(diff.max()), "column": str(diff.idxmax()), "text_columns_equal": same_text,
            "lambda_max_abs_diff": float(diff.get("lambda", np.nan)), "columns_added": ",".join(added),
            "nan_mismatch": ",".join(f"{c}:{n}" for c, n in nan_mismatch.items())}


def parse_years(spec, cfg):
    if spec is None:
        return list(cfg.years)
    if "-" in spec:
        y0, y1 = map(int, spec.split("-"))
        return list(range(y0, y1 + 1))
    return [int(y) for y in spec.split(",")]


def select_cases(spec, table, label):
    cases = spec.split(",") if spec else list(table)
    unknown = set(cases) - set(table)
    if unknown:
        sys.exit(f"Unknown {label} case: {sorted(unknown)}")
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="normal", help="configs/scenarios/<name>.yaml")
    ap.add_argument("--years", default=None, help="e.g. 2010-2019 or 2011,2018; default from the configuration")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--shapley", action="store_true", help="H7: the 14 IoT coalitions for LXB, tuned")
    ap.add_argument("--ablation", action="store_true", help="H3: LXB-noS3 (without stage 3), tuned, phys")
    ap.add_argument("--all", action="store_true", help="main sweep with --shapley and --ablation")
    ap.add_argument("--sensitivity", action="store_true",
                    help="descriptive sensitivity cases x LXB, B0, B3 x tuned -> results/sensitivity/<case>/")
    ap.add_argument("--exploratory", action="store_true",
                    help="exploratory cases -> results/exploratory/<case>/")
    ap.add_argument("--cases", default=None, help="comma-separated cases for --sensitivity or --exploratory")
    ap.add_argument("--verify", action="store_true",
                    help="rerun the selected jobs into results/verification/rerun/ and compare with stored results")
    ap.add_argument("--tuned", default="tuned,untuned")
    ap.add_argument("--iot", default="phys,iot")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="recompute existing result files")
    ap.add_argument("--freeze", action="store_true", help="record the protocol checksum (once)")
    ap.add_argument("--start", help="first day of a short test period (YYYY-MM-DD)")
    ap.add_argument("--days", type=int, help="length of a short test period")
    a = ap.parse_args()
    if a.sensitivity and a.exploratory:
        sys.exit("Use --sensitivity or --exploratory, not both.")
    cfg = load_config(scenario=a.scenario)
    years = parse_years(a.years, cfg)
    short = bool(a.start or a.days)
    if not short:
        check_preregistration(a.freeze)
    if a.exploratory:
        cases = select_cases(a.cases, EXPLORATORY, "exploratory")
        jobs = [(m, y, t, i, c) for c in cases for (ms, tu, io) in groups(c) for y in years for t in tu
                for i in io for m in ms]
        stored = {c: EXPL / c for c in cases}
    elif a.sensitivity:
        cases = select_cases(a.cases, SENSITIVITY, "sensitivity")
        jobs = [(m, y, "tuned", i, c) for c in cases for y in years for i in SENSITIVITY[c] for m in SENS_METHODS]
        stored = {c: SENS / c for c in cases}
    else:
        jobs = [(m, y, t, i, a.scenario) for y in years for t in a.tuned.split(",") for i in a.iot.split(",")
                for m in a.methods.split(",")]
        if a.shapley or a.all:
            jobs += [("LXB", y, "tuned", c, a.scenario) for y in years for c in SUBSETS]
        if a.ablation or a.all:
            jobs += [("LXB-noS3", y, "tuned", "phys", a.scenario) for y in years]
        stored = {a.scenario: EXP / a.scenario}
    group = "exploratory" if a.exploratory else "sensitivity" if a.sensitivity else None
    if a.verify or short:                                  # never write into the stored result folders
        base = VERIFY if a.verify else CHECK
        dirs = {c: (base / group / c if group else base / c) for c in stored}
    else:
        dirs = stored
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    path = lambda m, y, t, i, c: dirs[c] / f"{m}_{y}_{t}_{i}.csv"
    jobs = list(dict.fromkeys(jobs))
    for j in jobs:
        factors_of(j[3])
    if not (a.force or a.verify):
        code = code_sha256(ROOT)
        stale = [j for j in jobs if path(*j).exists() and not is_current(path(*j), a.days, code)]
        jobs = [j for j in jobs if not is_current(path(*j), a.days, code)]
        if stale:
            print(f"{len(stale)} stored result(s) are incomplete or were computed with other code or inputs; "
                  "they are recomputed.", flush=True)
    SLOW = ("LXB", "LXB-noS3", "LXB-DA", "LXB-F", "Oracle", "B2")    # slow methods first, for a more even load
    jobs.sort(key=lambda j: j[0] not in SLOW)
    print(f"Cases: {', '.join(dirs)}; jobs: {len(jobs)} (slow: {sum(j[0] in SLOW for j in jobs)}); "
          f"workers: {a.jobs}", flush=True)
    print(f"A line is printed when a job starts and every {PROGRESS_DAYS} days. Ctrl+C stops the sweep; finished "
          "jobs are kept and skipped when the command is repeated.", flush=True)
    failed, done, t_start, report = [], 0, time.time(), []
    ex = ProcessPoolExecutor(max_workers=a.jobs)
    try:
        futs = {ex.submit(run_job, *j[:4], a.start, a.days, j[4], str(dirs[j[4]])): j for j in jobs}
        pending = set(futs)
        while pending:
            # a wait with a timeout keeps Ctrl+C responsive on Windows
            finished, pending = wait(pending, timeout=2.0, return_when=FIRST_COMPLETED)
            for f in finished:
                j = futs[f]
                try:
                    name, lam, sec = f.result()
                    done += 1
                    label = f"{j[4]}/{name}" if group else name
                    print(f"  [{done}/{len(jobs)}] {label:36s} lambda = {lam:.4f}  ({sec / 60:.1f} min; "
                          f"total {(time.time() - t_start) / 3600:.2f} h)", flush=True)
                    ref = stored[j[4]] / name
                    if a.verify and not short:
                        if ref.exists():
                            report.append({"job": label, **compare_with_stored(path(*j), ref)})
                        else:
                            report.append({"job": label, "max_abs_diff": "no stored result"})
                except BrokenProcessPool:
                    raise
                except Exception as e:                   # one failed job does not stop the others
                    path(*j).with_suffix(".error.txt").write_text(f"{type(e).__name__}: {e}", encoding="utf-8")
                    failed.append(j); print(f"  ERROR {j}: {e}", flush=True)
    except (KeyboardInterrupt, BrokenProcessPool) as e:
        stop_pool(ex)
        if isinstance(e, KeyboardInterrupt):
            sys.exit(f"\nStopped (Ctrl+C). Finished jobs: {done}. Repeat the command to resume.")
        sys.exit(f"\nA worker process ended unexpectedly ({e}). Finished jobs: {done}. Memory may be short; "
                 "repeat with a smaller --jobs.")
    ex.shutdown()
    if report:
        rep = pd.DataFrame(report)
        out = VERIFY / "comparison.csv"
        rep.to_csv(out, index=False)
        print(rep.to_string(index=False))
        print(f"Comparison written to {out.relative_to(ROOT).as_posix()}")
    if failed:
        sys.exit(f"{len(failed)} job(s) failed (see *.error.txt)")


def stop_pool(ex):
    """Cancel queued jobs and terminate running workers so that the program does not hang."""
    procs = list(getattr(ex, "_processes", {}).values())
    ex.shutdown(wait=False, cancel_futures=True)
    for pr in procs:
        if pr.is_alive():
            pr.terminate()
    for pr in procs:
        pr.join(timeout=10)


if __name__ == "__main__":
    main()
