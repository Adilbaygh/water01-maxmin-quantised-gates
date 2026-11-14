"""Sensitivity analyses of the quantised max-min execution: the control step, the demand of R-1 in early April, the gate
parameters, the demand of the users, the timing of deliveries shifted between days, the period-average max-min level,
the gate state at the day break (H3), the pool level on deficit days and the rule variants of scripts/rules_variants.py.
Reads the stored runs of scripts/run_cases.py and scripts/run_sensitivity.py and writes
results/analysis/sensitivity_*.csv and *.md.

Parts:
  shift   longest run of days without water although the plan is positive, delay of the cumulative delivery behind the
          cumulative plan (days), largest cumulative delivery ahead of the plan and largest backlog (m3 and pulses).
  fair    period-average satisfaction sum V / sum D over calendar dekads, months and the season; the period-average
          max-min level (minimum over the outlets) of the deliveries against that of the plans.
  h3      regulator-days that start with an open gate (H3 fails): the days after a day of continuous opening (stored
          runs) and the opening at the day break (runs with gate columns); the bounds of Theorem 3 on these days and
          the bound with an open start, V < x~ + max{p, n0 v} (n0 resolution steps open at the day break).
  level   range of the pool level on the days of deficit and on the other days; level change of one pulse.
  dt      control step: step volumes of R-1, daily pulse capacity, predicted exclusion and the bounds of Theorems 2-4
          against the step (static), and the closed-loop runs with steps of 5 and 30 min.
  r1      demand of R-1 in the first decade of April: predicted exclusion against a multiplier of the demand (static)
          and the closed-loop windows 1 April - 10 May with multipliers 0.5-2.0.
  gate    gate parameters: step volumes of R-1 against the discharge coefficient and the tail-water level (static);
          a consistent rise of the tail-water level and plant/controller bias of both parameters (closed loop).
  demand  demand of the users: regulator-days below one quantum and the bound of Theorem 2 by demand variant and level
          (static); closed-loop runs with the demand variants B and C and the demand scaled by 0.8 and 1.2.
  rules   closure at the start of the day (LXB-T050S, LXB-COS), the equal split with the fewest openings (LXB-ESM)
          and the equal split with a level cap and a trimming step (LXB-ESL) against LXB-T050, LXB-CO and LXB-ES.
  coupling  pulses per day of the four small regulators against the N steps of a day (one shared pulse per step).
  schedule  the recorded daily pulse counts of the four small regulators scheduled on one shared pulse per step by
            the earliest-deadline rule (quantmaxmin.execution.shared_pulse_schedule): days within the N steps, largest
            deviation of the cumulative pulses from the uniform share of the day.
  benchmark period-average max-min level of the plans and deliveries over calendar dekads, months and seasons against
            the period level with perfect foresight under the same daily node volumes, demands and outlet limits
            (quantmaxmin.allocation.period_level, checked by its cut bound).
Usage: python scripts/analyse_sensitivity.py [--parts coupling,schedule,benchmark,shift,fair,h3,level,dt,r1,gate,demand,
       rules]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_common import (OUT, REGULATORS, ROOT, YEARS, Quanta, load, markdown, node_water,  # noqa: E402
                             regulator_days)
from analyse_theorems import dekad_errors  # noqa: E402
from quantmaxmin.allocation import continuous_level, period_level, period_level_cut, quantised_level  # noqa: E402
from quantmaxmin.execution import shared_pulse_schedule  # noqa: E402

from water01.domain.passport import USERS, value  # noqa: E402
from water01.hydraulics.node import DustlikNode  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402

EPS = 1e-6                                   # m3: smallest positive plan, as in scripts/analyse_theorems.py
VEPS = 1e-6                                  # m3: a day without water
TOL = 1e-3                                   # m3: tolerance of the cumulative catch-up
THETA = {"LXB-T000": 0.0, "LXB-T025": 0.25, "LXB-T050": 0.5, "LXB-T075": 0.75, "LXB-ES": 0.5, "LXB-CO": 0.5,
         "LXB-T050S": 0.5, "LXB-COS": 0.5, "LXB-ESM": 0.5, "LXB-ESL": 0.5}
SCENARIO = {"phys": "normal", "q_main": "normal", "q_theta": "normal", "q_main_ext": "normal",
            "q_variants": "normal", "q_dt5": "dt_5min", "q_dt30": "dt_30min", "q_tw_high": "tailwater_high",
            "q_bias_cd_low": "bias_cd_low", "q_bias_cd_high": "bias_cd_high",
            "q_bias_tw_high": "bias_tailwater_high", "q_bias_tw_low": "bias_tailwater_low",
            "q_dem_B": "demand_area", "q_dem_C": "demand_capacity", "q_dem_080": "demand_scale_080",
            "q_dem_120": "demand_scale_120", "q_cd_low": "gate_cd_low", "q_cd_high": "gate_cd_high",
            "q_rating": "rating_outlets"}
for _f in ("050", "100", "150", "180", "200"):
    SCENARIO[f"q_r1apr_{_f}"] = f"r1_april_{_f}"
SCENARIO.update({"q_bias_cd_low_apr": "bias_cd_low_april", "q_bias_cd_high_apr": "bias_cd_high_april",
                 "q_bias_tw_high_apr": "bias_tailwater_high_april", "q_bias_tw_low_apr": "bias_tailwater_low_april"})
MAIN = (("q_main", "LXB"), ("q_main", "LXB-T000"), ("q_main", "LXB-T050"), ("q_main", "LXB-ES"), ("q_main", "LXB-CO"),
        ("q_theta", "LXB-T025"), ("q_theta", "LXB-T075"))


def save(df, name, title):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"{name}.csv", index=False)
    (OUT / f"{name}.md").write_text(f"# {title}\n\n" + markdown(df), encoding="utf-8")
    print(f"{name}: {len(df)} rows")


_QUANTA = {}


def quanta(case):
    sc = SCENARIO.get(case, "normal")
    if sc not in _QUANTA:
        _QUANTA[sc] = Quanta(sc)
    load_config(scenario=sc)
    return _QUANTA[sc]


def table(case, method, years=YEARS):
    """Long regulator-day table of a stored case with the pulse-only flag, the day-break flags and the gate columns."""
    df = load(case, method, years)
    if df.empty:
        return None, None
    qa = quanta(case)
    rd = regulator_days(df, qa)
    n_steps = round(86400 / qa.dt)
    for col in ("moves", "opened", "travel", "break_steps", "start_closed"):
        rd[col] = np.concatenate([df[f"{col}_{u}"].to_numpy() if f"{col}_{u}" in df else np.full(len(df), np.nan)
                                  for u in REGULATORS])
    rd = rd.sort_values(["user", "date"]).reset_index(drop=True)
    rd["pure"] = (rd["pulses"] > 0) & (rd["open"] == rd["pulses"]) & (rd["esopen"] == 0) & (rd["xt"] > EPS)
    rd["prev_open_all_day"] = rd.groupby(["user", "year"])["open"].shift(1) == n_steps
    rd["n_steps"] = n_steps
    return rd, df


# --- shift -------------------------------------------------------------------------------------------------------------
def runs_of(flags):
    """Lengths of the runs of consecutive True values."""
    out = []; n = 0
    for f in flags:
        if f:
            n += 1
        elif n:
            out.append(n); n = 0
    if n:
        out.append(n)
    return out


def delays(X, W):
    """For every day s with W(s) < X(s) - TOL: the smallest L >= 0 with W(s + L) >= X(s) - TOL (np.inf if the season
    ends first). Cumulative (first-in, first-out) delay of the planned volume."""
    L = np.zeros(len(X)); n = len(X)
    j = 0
    for s in range(n):
        if W[s] >= X[s] - TOL:
            continue
        j = max(j, s)
        while j < n and W[j] < X[s] - TOL:
            j += 1
        L[s] = (j - s) if j < n else np.inf
    return L


def shift_metrics(rd, label, user_filter=None):
    """Metrics of the delivery timing for each regulator (and for all regulators) of a regulator-day table."""
    rows = []
    groups = [(u, rd[rd["user"] == u]) for u in REGULATORS] + [("all regulators", rd)]
    for u, g in groups:
        if user_filter is not None and u not in user_filter:
            continue
        dry_runs = []; dry_days = 0; Lmax = 0.0; Lsum = 0.0; Lcnt = 0; cens = 0; ahead = 0.0; back = 0.0
        end_back_p = 0.0
        ahead_p = 0.0; back_p = 0.0; pos_days = 0
        for (y, uu), h in g.groupby(["year", "user"]):
            h = h.sort_values("date")
            x = h["x"].to_numpy(); V = h["V"].to_numpy()
            pm = float(h["p_max"].max())
            dry = (x > EPS) & (V <= VEPS)
            dry_days += int(dry.sum()); dry_runs += runs_of(dry)
            X = np.cumsum(np.maximum(x, 0.0)); W = np.cumsum(V)
            e = W - X
            ahead = max(ahead, float(e.max(initial=0.0))); back = max(back, float((-e).max(initial=0.0)))
            ahead_p = max(ahead_p, float(e.max(initial=0.0)) / pm); back_p = max(back_p, float((-e).max(initial=0.0)) / pm)
            L = delays(X, W)
            pos = x > EPS
            pos_days += int(pos.sum())
            fin = np.isfinite(L)
            last = np.zeros(len(L), bool); last[-1] = True            # the debt left at the end of the season
            cens += int((~fin & pos & ~last).sum())
            end_back_p = max(end_back_p, max(float(X[-1] - W[-1]), 0.0) / pm)
            if (fin & pos).any():
                Lmax = max(Lmax, float(L[fin & pos].max())); Lsum += float(L[fin & pos].sum()); Lcnt += int((fin & pos).sum())
        rows.append({"case_rule": label, "outlet": u, "days_plan_pos": pos_days, "days_without_water": dry_days,
                     "longest_run_days": max(dry_runs) if dry_runs else 0,
                     "runs_ge_2_days": int(sum(r >= 2 for r in dry_runs)),
                     "max_delay_days": Lmax, "mean_delay_days": Lsum / Lcnt if Lcnt else 0.0,
                     "days_not_caught_up_before_season_end": cens, "season_end_backlog_pulses_max": end_back_p,
                     "max_ahead_m3": ahead, "max_ahead_pulses": ahead_p,
                     "max_backlog_m3": back, "max_backlog_pulses": back_p})
    return rows


def part_shift():
    rows = []
    for case, m in MAIN:
        rd, _ = table(case, m)
        if rd is None:
            continue
        rows += shift_metrics(rd, f"{case} {m}")
    save(pd.DataFrame(rows), "sensitivity_shift", "Timing of the deliveries (true volumes, seasons 2010-2019): days "
         "without water although x > 0, longest run of such days, delay of the cumulative delivery behind the cumulative "
         "plan (first in, first out), largest cumulative delivery ahead of the plan and largest backlog (m3 and pulses "
         "p_max of the outlet)")


# --- fair --------------------------------------------------------------------------------------------------------------
def part_fair():
    rows = []
    for case, m in (("phys", "LXB"),) + MAIN:
        df = load(case, m)
        if df.empty:
            continue
        d = pd.DatetimeIndex(df["date"])
        keys = {"dekad": d.year * 1000 + d.month * 10 + np.where(d.day <= 10, 0, np.where(d.day <= 20, 1, 2)),
                "month": d.year * 100 + d.month, "season": d.year}
        for period, key in keys.items():
            for scope, users in (("six outlets", USERS), ("five regulators", REGULATORS)):
                g = df.assign(k=key).groupby("k")
                sV = pd.DataFrame({u: g[f"V_{u}"].sum() for u in users})
                sx = pd.DataFrame({u: g[f"x_{u}"].sum() for u in users})
                sD = pd.DataFrame({u: g[f"D_{u}"].sum() for u in users})
                ok = sD > 0
                rV = (sV / sD).where(ok); rx = (sx / sD).where(ok)
                LV = rV.min(axis=1); Lx = rx.min(axis=1)
                dif = LV - Lx
                rows.append({"case": case, "rule": m, "period": period, "outlets": scope, "blocks": int(len(dif)),
                             "mean_maxmin_V": float(LV.mean()), "mean_maxmin_x": float(Lx.mean()),
                             "mean_diff": float(dif.mean()), "min_diff": float(dif.min()),
                             "blocks_below_plan_by_0.01": int((dif < -0.01).sum()),
                             "max_abs_sat_diff_R1": float((rV["R-1"] - rx["R-1"]).abs().max()),
                             "mean_abs_sat_diff_R1": float((rV["R-1"] - rx["R-1"]).abs().mean()),
                             "max_abs_sat_diff_any": float((rV - rx).abs().max().max())})
    save(pd.DataFrame(rows), "sensitivity_fairness", "Period-average satisfaction sum V / sum D by calendar dekad, month "
         "and season: max-min level of the deliveries (minimum over the outlets) against that of the plans, and the "
         "largest difference of the period-average satisfaction of R-1 and of any outlet")


# --- h3 ----------------------------------------------------------------------------------------------------------------
def h3_rows(rd, case, m):
    th = THETA.get(m, 0.5)
    r = rd[rd["pure"]].copy()
    have_break = r["break_steps"].notna().all() and len(r) > 0
    k = quanta(case).k
    lower = r["xt"] - th * np.minimum(r["p_max"], r["xt"])
    upper = r["xt"] + r["p_max"]
    big = r["xt"] >= r["p_max"]
    sharp = np.where(big, r["xt"] + (1 - th) * r["p_max"], upper)
    out = {"case": case, "rule": m, "pulse_only_days": int(len(r)),
           "after_day_open_throughout": int(r["prev_open_all_day"].sum()),
           "share_after_open_throughout": float(r["prev_open_all_day"].mean()) if len(r) else np.nan,
           "lower_bound_holds": int((r["V"] >= lower - 1e-6).sum()), "upper_bound_holds": int((r["V"] < upper + 1e-6).sum()),
           "sharp_bound_holds": int((r["V"] <= sharp + 1e-6).sum())}
    if have_break:
        opn = r["break_steps"] > 0
        n0 = r["break_steps"].clip(lower=0)
        upper_open = r["xt"] + np.maximum(r["p_max"], n0 * r["v_max"])
        out.update({"open_at_day_break": int(opn.sum()), "share_open_at_day_break": float(opn.mean()),
                    "open_at_break_and_after_open_throughout": int((opn & r["prev_open_all_day"]).sum()),
                    "max_break_steps": int(n0.max()),
                    "sharp_violations_open_start": int((opn & (r["V"] > sharp + 1e-6)).sum()),
                    "sharp_violations_closed_start": int((~opn & (r["V"] > sharp + 1e-6)).sum()),
                    "max_excess_over_sharp_open_start_p": float(((r["V"] - sharp) / r["p_max"])[opn].clip(lower=0).max())
                    if opn.any() else 0.0,
                    "open_start_bound_holds": int((r["V"] < upper_open + 1e-6).sum()),
                    "excess_limit_over_p": (k - 1) / (k + 1)})
        allpos = rd[rd["xt"] > EPS]
        out.update({"regulator_days_x_pos": int(len(allpos)),
                    "open_at_day_break_x_pos": int((allpos["break_steps"] > 0).sum()),
                    "start_closures": int(np.nansum(rd["start_closed"])) if rd["start_closed"].notna().any() else 0})
    return out


def part_h3():
    rows = []
    for case, m in (("q_main", "LXB-T000"), ("q_main", "LXB-T050"), ("q_main", "LXB-CO"), ("q_theta", "LXB-T025"),
                    ("q_theta", "LXB-T075"), ("q_main_ext", "LXB-T050"), ("q_main_ext", "LXB-CO"),
                    ("q_variants", "LXB-T050S"), ("q_variants", "LXB-COS")):
        rd, _ = table(case, m)
        if rd is None:
            continue
        rows.append(h3_rows(rd, case, m))
    save(pd.DataFrame(rows), "sensitivity_h3", "Gate open at the day break (H3 fails) on the regulator-days operated by "
         "pulses only: days after a day of continuous opening, opening at the day break (runs with gate columns), the "
         "bounds of Theorem 3 (true volumes) and the bound with an open start x~ + max{p, n0 v}")


# --- level -------------------------------------------------------------------------------------------------------------
def part_level():
    W = pd.concat([pd.DataFrame({"date": node_water(y)[0], "W": node_water(y)[1],
                                 "sumD": node_water(y)[2].sum(axis=0)}) for y in YEARS], ignore_index=True)
    A_s = float(value("A_s_identified_m2"))
    qa = quanta("q_main")
    h_norm = float(value("H_norm_m"))
    rows = []
    for case, m in (("phys", "LXB"),) + MAIN[:5]:
        df = load(case, m)
        if df.empty:
            continue
        d = df.merge(W, on="date", how="left")
        sup = d["W"] > 0
        defi = sup & (d["W"] < d["sumD"])
        rng = d["h_max"] - d["h_min"]
        pulses = sum(d[f"pulses_{u}"] for u in REGULATORS)
        for scope, sel in (("deficit days", defi), ("other days with supply", sup & ~defi)):
            rows.append({"case": case, "rule": m, "days": scope, "n": int(sel.sum()),
                         "mean_range_m": float(rng[sel].mean()), "max_range_m": float(rng[sel].max()),
                         "min_level_m": float(d["h_min"][sel].min()), "max_level_m": float(d["h_max"][sel].max()),
                         "mean_pulses_per_day": float(pulses[sel].mean())})
    lv = pd.DataFrame(rows)
    p_norm = qa.p(h_norm)
    extra = pd.DataFrame([{"case": "pulse", "rule": u, "days": "level change of one pulse at H_norm",
                           "n": 0, "mean_range_m": float(p_norm[j] / A_s), "max_range_m": np.nan,
                           "min_level_m": np.nan, "max_level_m": np.nan, "mean_pulses_per_day": np.nan}
                          for j, u in enumerate(REGULATORS)])
    b = qa.barrier(h_norm)
    extra2 = pd.DataFrame([{"case": "barrier", "rule": name, "days": "level change at H_norm", "n": 0,
                            "mean_range_m": float(b[key] / A_s), "max_range_m": float(b[key]),
                            "min_level_m": np.nan, "max_level_m": np.nan, "mean_pulses_per_day": np.nan}
                           for name, key in (("quantum q", "q"), ("largest step v", "v"))])
    save(pd.concat([lv, extra, extra2], ignore_index=True), "sensitivity_level",
         "Pool level on the deficit days and on the other days with supply (daily range h_max - h_min, extreme levels, "
         "pulses of the regulators per day); level change of one pulse of each regulator and of one barrier step at "
         "H_norm over the identified storage area (max_range_m: the barrier volume, m3)")


# --- shared closed-loop summary ------------------------------------------------------------------------------------------
def outcome(case, m, months=None):
    """Closed-loop outcome of a (case, rule): exclusion (x > 0 and the gate never opened), dekad errors of R-1, waterless
    runs of R-1, worst season satisfaction, mean daily lambda; months restricts the days (e.g. (4,) for April)."""
    rd, df = table(case, m)
    if rd is None:
        return None
    if months is not None:
        df = df[pd.DatetimeIndex(df["date"]).month.isin(months)]
        rd = rd[pd.DatetimeIndex(rd["date"]).month.isin(months)]
    qa = quanta(case)
    pos = rd["x"] > EPS
    thr = (1 - 1 / (2 * qa.k)) * rd["q_min"]
    dk = dekad_errors(df, "V"); dk_hat = dekad_errors(df, "Vhat")
    r1 = rd[rd["user"] == "R-1"]
    sh = shift_metrics(r1, f"{case} {m}", user_filter=("R-1",))[0]
    seas = df.groupby("year")[[f"V_{u}" for u in REGULATORS] + [f"D_{u}" for u in REGULATORS]].sum()
    sat = pd.DataFrame({u: seas[f"V_{u}"] / seas[f"D_{u}"] for u in REGULATORS})
    pure = rd["pure"]
    th = THETA.get(m, 0.5)
    lo = rd["xt"] - th * np.minimum(rd["p_max"], rd["xt"]); up = rd["xt"] + rd["p_max"]
    lo_e = rd["xt"] - th * np.minimum(rd["p_max_est"], rd["xt"]); up_e = rd["xt"] + rd["p_max_est"]
    return {"case": case, "rule": m, "seasons": int(df["year"].nunique()), "days": int(len(df)),
            "N_steps": int(round(86400 / qa.dt)), "k": qa.k,
            "regulator_days_x_pos": int(pos.sum()), "predicted_exclusion": int((pos & (rd["x"] < thr)).sum()),
            "never_opened_x_pos": int((pos & (rd["open"] == 0)).sum()),
            "R1_never_opened": int((pos & (rd["open"] == 0) & (rd["user"] == "R-1")).sum()),
            "R1_dekads": int(dk.size), "R1_dekad_err_mean": float(dk.mean()), "R1_dekad_err_max": float(dk.max()),
            "R1_dekad_err_mean_est": float(dk_hat.mean()),
            "R1_days_without_water": sh["days_without_water"], "R1_longest_dry_run": sh["longest_run_days"],
            "R1_max_delay_days": sh["max_delay_days"], "R1_max_ahead_pulses": sh["max_ahead_pulses"],
            "R1_max_backlog_pulses": sh["max_backlog_pulses"],
            "pulse_only_days": int(pure.sum()),
            "T3_bounds_hold_true": int((pure & (rd["V"] >= lo - 1e-6) & (rd["V"] < up + 1e-6)).sum()),
            "T3_bounds_hold_est": int((pure & (rd["Vhat"] >= lo_e - 1e-6) & (rd["Vhat"] < up_e + 1e-6)).sum()),
            "season_satisfaction_min": float(sat.to_numpy().min()),
            "season_satisfaction_R1_mean": float(sat["R-1"].mean()),
            "R1_season_V_over_x": float(df["V_R-1"].sum() / df["x_R-1"].clip(lower=0).sum()),
            "mean_daily_lambda": float(df["lambda"].mean()),
            "R1_p_norm_m3": float(qa.p(float(value("H_norm_m")))[1]),
            "R1_q_norm_m3": float(qa.q(float(value("H_norm_m")))[1])}


# --- dt ----------------------------------------------------------------------------------------------------------------
def early_plan():
    """Median plan of R-1 on the days 1-10 April with a positive plan (q_main, LXB), m3."""
    df = load("q_main", "LXB")
    d = pd.DatetimeIndex(df["date"])
    x = df.loc[(d.month == 4) & (d.day <= 10) & (df["x_R-1"] > EPS), "x_R-1"]
    return float(x.median())


def part_dt():
    qa = quanta("q_main")
    h_norm = float(value("H_norm_m")); h_hi = float(value("H_max_m")) - float(value("freeboard_m"))
    base = load("q_main", "LXB")
    rd = regulator_days(base, qa)
    pos = rd["x"] > EPS
    x_e = early_plan()
    days = {y: node_water(y) for y in YEARS}
    rows = []
    for dt in (300.0, 450.0, 600.0, 900.0, 1200.0, 1800.0, 3600.0):
        f = dt / qa.dt
        N = int(round(86400 / dt))
        q_n = qa.q(h_norm) * f; p_n = qa.p(h_norm) * f; v_n = qa.v(h_norm) * f
        thr = (1 - 1 / (2 * qa.k)) * rd["q_min"] * f
        pi = []; bnd = []
        for y in YEARS:
            dates, A, D = days[y]
            q6 = np.r_[qa.q(h_hi), qa.barrier(h_hi)["q"]] * f
            for p in range(len(dates)):
                if A[p] > 0:
                    pi.append(continuous_level(A[p], D[:, p]) - quantised_level(A[p], D[:, p], q6))
                    bnd.append(q6.sum() / D[:, p].sum())
        rows.append({"dt_s": dt, "N": N, "R1_v_norm_m3": float(v_n[1]), "R1_q_norm_m3": float(q_n[1]),
                     "R1_p_norm_m3": float(p_n[1]), "R1_daily_pulse_capacity_m3": float(N * p_n[1]),
                     "R1_early_april_plan_m3": x_e, "plan_over_q": x_e / float(q_n[1]),
                     "predicted_exclusion_all": int((pos & (rd["x"] < thr)).sum()),
                     "predicted_exclusion_R1": int((pos & (rd["x"] < thr) & (rd["user"] == "R-1")).sum()),
                     "T2_Pi_max": float(max(pi)), "T2_Pi_mean": float(np.mean(pi)), "T2_bound_mean": float(np.mean(bnd)),
                     "T3_band_over_plan_R1": float((p_n[1] + 0.5 * min(p_n[1], x_e)) / x_e),
                     "T4_cum_bound_over_dekad_plan_R1": float(1.5 * p_n[1] / (10 * x_e))})
    save(pd.DataFrame(rows), "sensitivity_dt_static", "Control step: step volumes of R-1 at H_norm, daily pulse capacity "
         "N p, early-April plan of R-1 over the quantum, regulator-days predicted excluded (0 < x < (1 - 1/(2k)) q_min, "
         "levels and plans of q_main LXB), daily price of indivisibility (quanta at the upper operating level, barrier "
         "at H_norm) and the width of the bands of Theorems 3 and 4 relative to the early-April plan of R-1")
    rows = [r for r in (outcome(c, m) for c in ("q_dt5", "q_main", "q_dt30") for m in ("LXB", "LXB-T050", "LXB-CO"))
            if r is not None]
    if rows:
        save(pd.DataFrame(rows), "sensitivity_dt_runs", "Control step in closed loop (steps of 5, 15 and 30 min; "
             "seasons 2010-2019): exclusion, dekad errors of R-1, days without water, bounds of Theorem 3")


# --- r1 ----------------------------------------------------------------------------------------------------------------
def part_r1():
    qa = quanta("q_main")
    base = load("q_main", "LXB")
    rd = regulator_days(base, qa)
    d = pd.DatetimeIndex(rd["date"])
    early = (rd["user"] == "R-1") & (d.month == 4) & (d.day <= 10) & (rd["x"] > EPS)
    e = rd[early]
    rows = []
    for f in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.6, 1.7, 1.75, 1.8, 1.85, 1.9, 2.0, 2.25, 2.5, 3.0):
        x = f * e["x"]
        thr = (1 - 1 / (2 * qa.k)) * e["q_min"]
        rows.append({"multiplier": f, "plan_m3_median": float(x.median()), "days_x_pos": int(len(e)),
                     "predicted_exclusion": int((x < thr).sum()), "below_q_min": int((x < e["q_min"]).sum()),
                     "plan_over_q_min_min": float((x / e["q_min"]).min()), "plan_over_q_min_max": float((x / e["q_min"]).max()),
                     "T050_overdelivery_bound_m3": float((e["p_max"] - 0.5 * np.minimum(e["p_max"], x)).max()),
                     "dekad_bound_CO": float((1.5 * e["p_max"] / (10 * f * e["D"])).max())})
    st = pd.DataFrame(rows)
    ratio = (e["q_min"] * (1 - 1 / (2 * qa.k)) / e["x"])
    st.attrs["threshold"] = (float(ratio.min()), float(ratio.max()))
    save(st, "sensitivity_r1_static", "Demand of R-1 in 1-10 April multiplied by a factor (plans and levels of q_main "
         "LXB): regulator-days predicted excluded (x < (1 - 1/(2k)) q_min) of the "
         f"{len(e)} early-April days with a positive plan; the exclusion holds on every day below the multiplier "
         f"{ratio.min():.3f} and on none above {ratio.max():.3f}")
    rows = []
    for fac in ("050", "100", "150", "180", "200"):
        for m in ("LXB", "LXB-T050", "LXB-CO"):
            r = outcome(f"q_r1apr_{fac}", m, months=(4,))
            if r is not None:
                r["multiplier"] = int(fac) / 100
                df = load(f"q_r1apr_{fac}", m)
                d = pd.DatetimeIndex(df["date"])
                e1 = df[(d.month == 4) & (d.day <= 10)].groupby("year")[["V_R-1", "x_R-1", "D_R-1"]].sum()
                e1 = e1[e1["D_R-1"] > 0]
                err = (e1["V_R-1"] - e1["x_R-1"]).abs() / e1["D_R-1"]
                r.update({"R1_dekad_1_10_april_err_mean": float(err.mean()), "R1_dekad_1_10_april_err_max": float(err.max()),
                          "R1_dekad_1_10_april_V_over_x": float(e1["V_R-1"].sum() / e1["x_R-1"].sum())})
                rows.append(r)
    if rows:
        save(pd.DataFrame(rows), "sensitivity_r1_runs", "Demand of R-1 in 1-10 April in closed loop (windows 1 April - "
             "10 May, April evaluated; seasons 2010-2019): exclusion, April dekad errors of R-1, days without water, "
             "delay and cumulative errors in pulses")


# --- gate --------------------------------------------------------------------------------------------------------------
def part_gate():
    load_config(scenario="normal")
    h_norm = float(value("H_norm_m")); h_lo = float(value("h_min_operating_m"))
    h_hi = float(value("H_max_m")) - float(value("freeboard_m"))
    rho = float(value("gate_resolution_fraction")); k = int(math.ceil(value("gate_deadband_fraction") / rho - 1e-9))
    dt = float(value("dt_s")); tw = np.asarray(value("regulator_tailwater_m"), float); cd = float(value("gate_cd"))
    x_e = early_plan()
    rows = []
    for cd_f in (0.8, 1.0, 1.2):
        for dh in (-0.3, 0.0, 0.3):
            node = DustlikNode(cd=cd * cd_f, tailwater_m=tuple(tw + dh))
            amax = np.asarray(node.max_opening, float)[:5]
            q = np.asarray(node.offtakes(h_norm, k * rho * amax), float) * dt
            p = np.asarray(node.offtakes(h_norm, (k + 1) * rho * amax), float) * dt
            base = DustlikNode()
            fac = [float(node.offtakes(h, 0.1 * amax)[1] / base.offtakes(h, 0.1 * amax)[1]) for h in (h_lo, h_norm, h_hi)]
            rows.append({"cd": cd * cd_f, "tailwater_shift_m": dh, "R1_q_norm_m3": float(q[1]), "R1_p_norm_m3": float(p[1]),
                         "early_april_plan_over_q": x_e / float(q[1]),
                         "exclusion_predicted": bool(x_e < (1 - 1 / (2 * k)) * float(q[1])),
                         "plan_multiplier_to_serve": (1 - 1 / (2 * k)) * float(q[1]) / x_e,
                         "plant_over_model_R1_lo": fac[0], "plant_over_model_R1_norm": fac[1],
                         "plant_over_model_R1_hi": fac[2]})
    save(pd.DataFrame(rows), "sensitivity_gate_static", "Gate parameters: quantum and pulse of R-1 at H_norm for the "
         "discharge coefficient 0.62 +- 20% and the tail-water level +- 0.3 m; early-April plan of R-1 over the quantum; "
         "ratio of the discharge with the changed parameters to that of the baseline (a plant/controller bias) at the "
         "lower, normal and upper operating levels")
    from water01.hydraulics.node import em_discharge, gate_discharge
    width = float(value("regulator_width_m")[1]); amax1 = float(DustlikNode().max_opening[1])
    rows = []
    for dh in (-0.3, 0.0, 0.3):
        for h in (h_lo, h_norm, h_hi):
            for n in (k, k + 1):
                a_n = n * rho * amax1
                q6 = gate_discharge(a_n, h, tw[1] + dh, width, cd)
                qe = em_discharge(a_n, h, tw[1] + dh, width, cd)
                rows.append({"tailwater_m": tw[1] + dh, "level_m": h, "steps": n, "opening_mm": a_n * 1000,
                             "relation_2_m3": q6 * dt, "energy_momentum_m3": qe * dt, "ratio": qe / q6})
    save(pd.DataFrame(rows), "sensitivity_gate_relation", "Step volume of R-1 at the quantum (k steps) and pulse "
         "(k + 1 steps) openings from relation (2) and from an energy-momentum relation of a sluice gate (contracted "
         "jet, free or drowned; contraction coefficient equal to C_d) at the lower, normal and upper operating levels")
    rows = [r for r in (outcome(c, m, months=(4,)) for c, m in
                        (("q_r1apr_100", "LXB"), ("q_bias_cd_low_apr", "LXB"), ("q_bias_cd_high_apr", "LXB"),
                         ("q_bias_tw_high_apr", "LXB"), ("q_bias_tw_low_apr", "LXB"))) if r is not None]
    if rows:
        save(pd.DataFrame(rows), "sensitivity_gate_april", "Plant/controller bias of the gate parameters under direct "
             "execution in April (windows 1 April - 10 May): exclusion of R-1 against the window of the baseline")
    rows = [r for r in (outcome(c, m) for c, m in
                        (("q_main", "LXB"), ("q_tw_high", "LXB"), ("q_cd_low", "LXB"),
                         ("q_cd_high", "LXB"), ("q_main", "LXB-T050"), ("q_main", "LXB-CO"),
                         ("q_bias_cd_low", "LXB-T050"), ("q_bias_cd_low", "LXB-CO"), ("q_bias_cd_high", "LXB-T050"),
                         ("q_bias_cd_high", "LXB-CO"), ("q_bias_tw_high", "LXB-T050"), ("q_bias_tw_high", "LXB-CO"),
                         ("q_bias_tw_low", "LXB-T050"), ("q_bias_tw_low", "LXB-CO"), ("q_rating", "LXB-T050"),
                         ("q_rating", "LXB-CO"))) if r is not None]
    if rows:
        save(pd.DataFrame(rows), "sensitivity_gate_runs", "Gate parameters in closed loop: consistent changes of the "
             "discharge coefficient and of the tail-water level (direct execution) and plant/controller bias of both "
             "parameters (pulse rule and carry-over; the controller keeps the nominal relation)")


# --- demand ------------------------------------------------------------------------------------------------------------
def part_demand():
    qa = quanta("q_main")
    h_norm = float(value("H_norm_m"))
    q5 = qa.q(h_norm)
    rows = []
    for name, variant, scale in (("A (baseline)", "A", 1.0), ("B (area)", "B", 1.0), ("C (capacity)", "C", 1.0),
                                 ("A x 0.8", "A", 0.8), ("A x 1.2", "A", 1.2)):
        sc = {"A": "normal", "B": "demand_area", "C": "demand_capacity"}[variant]
        below = 0; total = 0; bnd = []
        per_user = np.zeros(5, int)
        for y in YEARS:
            _, A, D = node_water(y, sc)
            D = D * scale
            ok = A > 0
            b = (D[:5] > 0) & (D[:5] < q5[:, None]) & ok
            per_user += b.sum(axis=1); below += int(b.sum()); total += int(((D[:5] > 0) & ok).sum())
            q6 = np.r_[qa.q(float(value("H_max_m")) - float(value("freeboard_m"))), qa.barrier(h_norm)["q"]]
            bnd += list(q6.sum() / D[:, ok].sum(axis=0))
        r = {"demand": name, "regulator_days_D_pos": total, "regulator_days_D_below_q": below,
             "T2_bound_mean": float(np.mean(bnd)), "T2_bound_max": float(np.max(bnd))}
        r.update({f"below_q_{u}": int(per_user[j]) for j, u in enumerate(REGULATORS)})
        rows.append(r)
    load_config(scenario="normal")
    save(pd.DataFrame(rows), "sensitivity_demand_static", "Demand of the users: regulator-days with supply and a "
         "demand below one quantum at H_norm (where direct execution can exclude), by demand variant and level; bound of "
         "Theorem 2 (sum of the quanta over the total demand)")
    rows = [r for r in (outcome(c, m) for c, m in
                        (("q_main", "LXB"), ("q_dem_B", "LXB"), ("q_dem_C", "LXB"), ("q_main", "LXB-T050"),
                         ("q_dem_B", "LXB-T050"), ("q_dem_C", "LXB-T050"), ("q_dem_080", "LXB-T050"),
                         ("q_dem_120", "LXB-T050"), ("q_main", "LXB-CO"), ("q_dem_B", "LXB-CO"), ("q_dem_C", "LXB-CO"),
                         ("q_dem_080", "LXB-CO"), ("q_dem_120", "LXB-CO"))) if r is not None]
    if rows:
        save(pd.DataFrame(rows), "sensitivity_demand_runs", "Demand of the users in closed loop: demand variants B "
             "(area) and C (capacity), demand of variant A scaled by 0.8 and 1.2")


# --- rules -------------------------------------------------------------------------------------------------------------
def activity(case, m):
    """Gate activity per regulator-day with a positive plan: stored gate columns, or scripts/gate_activity.py."""
    rd, _ = table(case, m)
    if rd is None:
        return None
    if rd["moves"].isna().all():
        f = ROOT / "results/analysis/gate_activity_runs"
        ga = pd.concat([pd.read_csv(p) for p in sorted(f.glob(f"{m}_*.csv"))], ignore_index=True) if case == "q_main" \
            else pd.DataFrame()
        if ga.empty:
            return None
        ga = ga[ga["user"].isin(REGULATORS) & (ga["x"] > EPS)]
        return {"moves": ga["moves"].mean(), "moves_R1": ga.loc[ga["user"] == "R-1", "moves"].mean(),
                "openings": ga["openings_from_closed"].mean(), "travel": ga["travel"].mean()}
    g = rd[rd["x"] > EPS]
    return {"moves": g["moves"].mean(), "moves_R1": g.loc[g["user"] == "R-1", "moves"].mean(),
            "openings": g["opened"].mean(), "travel": g["travel"].mean()}


def part_rules():
    rows = []
    for case, m in (("q_main", "LXB-T050"), ("q_variants", "LXB-T050S"), ("q_main", "LXB-CO"), ("q_variants", "LXB-COS"),
                    ("q_main", "LXB-ES"), ("q_variants", "LXB-ESM"), ("q_variants", "LXB-ESL")):
        r = outcome(case, m)
        if r is None:
            continue
        a = activity(case, m)
        if a is not None:
            r.update({f"gate_{k}_per_regulator_day": v for k, v in a.items()})
        rd, _ = table(case, m)
        es = rd["mode"] == "ES"
        if es.any():
            err = (rd["V"] - rd["xt"]).abs()[es]; half = rd["v_max"][es] / 2
            out = (err > half + 1e-6)
            r.update({"es_days": int(es.sum()), "es_within_half_step": int((~out).sum()),
                      "es_max_err_over_half_step": float((err / half).max()), "es_mean_open_steps": float(rd["m"][es].mean()),
                      "es_max_open_steps": int(rd["m"][es].max()),
                      "es_outside_users": " and ".join(u for u in REGULATORS if u in set(rd["user"][es][out]))})
            r.update(es_step_volumes(case, m, rd[es]))
        rows.append(r)
    if rows:
        save(pd.DataFrame(rows), "sensitivity_rules", "Rule variants: closure at the start of the day (LXB-T050S, "
             "LXB-COS), equal split with the fewest openings (LXB-ESM) and equal split with a level cap and a trimming "
             "step (LXB-ESL) against LXB-T050, LXB-CO and LXB-ES (q_main); gate activity per regulator-day with a positive "
             "plan; largest planned volume of one open step on the equal-split days and the change of the pool level that "
             "it causes over the identified storage area")


def es_step_volumes(case, m, e):
    """Largest planned volume of one open step on the equal-split days of a rule: x / m for LXB-ES and LXB-ESM; for
    LXB-ESL, x if m = 1 and otherwise max((x - y) / (m - 1), y), y = q^hi + g^hi (scripts/rules_variants.py)."""
    qa = quanta(case)
    h_hi = float(value("H_max_m")) - float(value("freeboard_m"))
    y = qa.q(h_hi) * (1 + 1 / qa.k)
    a_s = float(value("A_s_identified_m2"))
    j = e["user"].map({u: i for i, u in enumerate(REGULATORS)}).to_numpy()
    x = e["xt"].to_numpy(float); mm = e["m"].to_numpy(float)
    if m == "LXB-ESL":
        inc = np.where(mm <= 1, x, np.maximum((x - y[j]) / np.maximum(mm - 1, 1), y[j]))
    else:
        inc = x / mm
    i = int(np.argmax(inc))
    cap = a_s * 0.002
    return {"es_max_step_m3": float(inc[i]), "es_max_step_user": str(e["user"].iloc[i]),
            "es_max_step_level_mm": float(inc[i] / a_s * 1000),
            "es_days_step_above_2mm": int((inc > cap + 1e-6).sum()),
            "es_single_step_days": int((mm <= 1).sum())}


def part_coupling():
    """Pulses of the four small regulators (outlets 2-5) per day: whether one shared pulse per step would suffice."""
    small = REGULATORS[1:]
    rows = []
    for case, m in (("q_main", "LXB-T000"), ("q_main", "LXB-T050"), ("q_main", "LXB-CO"), ("q_theta", "LXB-T075")):
        df = load(case, m)
        if df.empty:
            continue
        N = 96
        tot = sum(df[f"pulses_{u}"] for u in small)
        allr = sum(df[f"pulses_{u}"] for u in REGULATORS)
        npulsing = sum((df[f"pulses_{u}"] > 0).astype(int) for u in small)
        rows.append({"case": case, "rule": m, "days": int(len(df)), "N": N,
                     "max_pulses_small_per_day": int(tot.max()), "mean_pulses_small_per_day": float(tot.mean()),
                     "days_small_pulses_above_N": int((tot > N).sum()),
                     "max_pulses_all_regulators_per_day": int(allr.max()),
                     "max_small_regulators_pulsing_same_day": int(npulsing.max()),
                     "days_two_or_more_small_pulsing": int((npulsing >= 2).sum())})
    save(pd.DataFrame(rows), "sensitivity_coupling", "Pulses per day of the four small regulators (R-1, Khalkabad-2, "
         "Kanly-Yab, K-2): if they had to share one pulse per step, a day needs at most N = 96 pulses")


def part_schedule():
    """The recorded daily pulse counts of the four small regulators on one pulse per step shared by all of them: the
    earliest-deadline rule with the counts of the day known at its start, each spread uniformly over the N steps."""
    small = REGULATORS[1:]
    k = len(small) + 1                                       # the four regulators and the idle state
    rows = []
    for case, m in (("q_main", "LXB-T000"), ("q_main", "LXB-T050"), ("q_main", "LXB-CO"), ("q_theta", "LXB-T075")):
        df = load(case, m)
        if df.empty:
            continue
        N = 96
        c = df[[f"pulses_{u}" for u in small]].to_numpy(int)
        dev, seen = [], {}
        for row in c:
            if row.sum() > N:
                continue
            key = tuple(row)
            if key not in seen:
                u, d = shared_pulse_schedule(np.tile(row[:, None] / N, (1, N)))
                if not np.array_equal(u.sum(axis=1), row) or u.sum(axis=0).max() > 1:
                    raise RuntimeError(f"{case} {m}: schedule does not deliver the counts {row}")
                seen[key] = d
            dev.append(seen[key])
        rows.append({"case": case, "rule": m, "days": int(len(df)), "N": N,
                     "days_within_N": int((c.sum(axis=1) <= N).sum()), "days_above_N": int((c.sum(axis=1) > N).sum()),
                     "max_pulses_per_day": int(c.sum(axis=1).max()), "distinct_count_vectors": len(seen),
                     "max_deviation_pulses": float(max(dev)), "bound_pulses": 1.0 - 1.0 / (2 * k - 2)})
    save(pd.DataFrame(rows), "sensitivity_schedule", "Recorded daily pulse counts of the four small regulators on one "
         "shared pulse per step: earliest-deadline schedule of the days with at most N = 96 pulses (counts of the day "
         "known at its start and spread uniformly over the day); largest deviation of the cumulative pulses of a "
         "regulator from its uniform share, against the bound 1 − 1/(2k − 2) with k = 5 (four regulators and the idle "
         "state)")


BENCH = ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")


def part_benchmark():
    """Period-average max-min level of the plans and deliveries of q_main against the period level with perfect
    foresight under the same daily node volumes A, demands D and daily outlet limits (no water moved between days)."""
    load_config(scenario="normal")
    C = np.asarray(value("outlet_capacity_m3s"), float) * 86400
    blocks = []
    for y in YEARS:
        dates, A, D = node_water(y)
        frames = {m: load("q_main", m, [y]) for m in BENCH}
        for m, f in frames.items():
            if np.abs(f[[f"D_{u}" for u in USERS]].to_numpy().T - D).max() > 1e-6:
                raise RuntimeError(f"q_main {m} {y}: stored demands differ from node_water")
        d = pd.DatetimeIndex(dates)
        keys = {"dekad": d.month * 10 + np.where(d.day <= 10, 0, np.where(d.day <= 20, 1, 2)),
                "month": d.month, "season": np.zeros(len(d), int)}
        for period, key in keys.items():
            for kk in np.unique(key):
                ix = np.flatnonzero(key == kk); B = D[:, ix].sum(axis=1); pos = B > 0
                lam, _ = period_level(D[:, ix], A[ix], C)
                cut, S = period_level_cut(D[:, ix], A[ix], C)
                if abs(lam - cut) > 1e-8:
                    raise RuntimeError(f"{y} {period} {kk}: LP {lam} differs from the cut bound {cut}")
                rec = {"year": y, "period": period, "start": d[ix[0]].date(), "end": d[ix[-1]].date(), "days": len(ix),
                       "lambda_opt": lam, "lambda_cut": cut, "limiting_outlets": ", ".join(USERS[j] for j in S)}
                for m, f in frames.items():
                    x = f[[f"x_{u}" for u in USERS]].to_numpy()[ix].T; V = f[[f"V_{u}" for u in USERS]].to_numpy()[ix].T
                    sx = x.sum(axis=1)[pos] / B[pos]; sV = V.sum(axis=1)[pos] / B[pos]
                    rec[f"plan_{m}"] = float(sx.min()); rec[f"delivered_{m}"] = float(sV.min())
                    if m == "LXB-CO":
                        users = [u for u, ok in zip(USERS, pos) if ok]
                        rec["plan_lowest_outlet"] = users[int(np.argmin(sx))]
                        rec["plan_highest_satisfaction"] = float(sx.max())
                blocks.append(rec)
    bl = pd.DataFrame(blocks)
    save(bl, "sensitivity_benchmark_blocks", "Period level with perfect foresight (lambda_opt, LP; lambda_cut, its cut "
         "bound) and period-average max-min level of the plans and deliveries of q_main for every calendar dekad, month "
         "and season")
    rows = []
    for period in ("dekad", "month", "season"):
        g = bl[bl.period == period]
        for m in BENCH:
            plan_gap = g.lambda_opt - g[f"plan_{m}"]; exe = g[f"plan_{m}"] - g[f"delivered_{m}"]
            tot = g.lambda_opt - g[f"delivered_{m}"]
            rows.append({"period": period, "rule": m, "blocks": int(len(g)), "max_planning_gap": float(plan_gap.max()),
                         "mean_planning_gap": float(plan_gap.mean()), "max_execution_shortfall": float(exe.max()),
                         "max_total_gap": float(tot.max()), "mean_total_gap": float(tot.mean())})
    save(pd.DataFrame(rows), "sensitivity_benchmark", "Period-average max-min level of the plans and deliveries of "
         "q_main below the period level with perfect foresight: planning gap (lambda_opt − plan), execution shortfall "
         "(plan − delivery) and total gap, largest and mean over the calendar dekads, months and seasons")
    s = bl[bl.period == "season"][["year", "lambda_opt", "plan_LXB-CO", "delivered_LXB-CO", "plan_lowest_outlet",
                                   "plan_highest_satisfaction", "limiting_outlets"]].copy()
    s["planning_gap"] = s.lambda_opt - s["plan_LXB-CO"]
    save(s, "sensitivity_benchmark_seasons", "Seasons: period level with perfect foresight, period-average max-min level "
         "of the plan and of the deliveries of LXB-CO, the outlet with the lowest seasonal satisfaction of the plan and "
         "the highest seasonal satisfaction of an outlet under the plan")


PARTS = {"coupling": part_coupling, "schedule": part_schedule, "benchmark": part_benchmark, "shift": part_shift, "fair": part_fair, "h3": part_h3, "level": part_level, "dt": part_dt, "r1": part_r1,
         "gate": part_gate, "demand": part_demand, "rules": part_rules}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parts", default=",".join(PARTS))
    a = ap.parse_args()
    for p in a.parts.split(","):
        PARTS[p]()


if __name__ == "__main__":
    main()
