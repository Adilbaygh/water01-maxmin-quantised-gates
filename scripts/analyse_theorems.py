"""Closed-loop checks of Theorems 1-4 on the stored Saint-Venant runs (results/runs) and the daily price of
indivisibility of the Kegeyli node (Theorem 2). Writes results/analysis/*.csv and *.md.

Parts:
  quanta  step volumes of the regulators at three levels and the conditions of Theorem 1(b).
  t1  Theorem 1(a): predicted exclusion (0 < x < (1 - 1/(2k)) q_min) against regulator-days without water under direct
      execution (LXB), for the deadband, discharge-coefficient and leakage cases; Theorem 1(b): equal-split error.
  t2  Theorem 2: daily lambda*, minimum-delivery level lambda_q and Pi_ind of the node from the operating records
      (quanta at the upper operating level and at the daily maximum level of the run), and the whole-step level
      lambda_v at the levels of the operating range in steps of 1 cm with the bound of Theorem 2(c).
  node  balance of the six outlets by rule: surplus of the regulators, satisfaction of the barrier against lambda*,
      change of storage of the pool.
  t3  Theorem 3: bounds of the theta pulse rule on regulator-days in the pulse regime.
  t4  Theorem 4: debt bounds of the carry-over rule and accounting-period errors for T = 1, 10, 30 days and the season.
  rules  outcome of every rule (daily worst-case satisfaction, outlet-days without water, shortfall, over-delivery,
      error of R-1 over calendar dekads, days by execution mode, gate activity from scripts/gate_activity.py).
Usage: python scripts/analyse_theorems.py [--parts quanta,t1,t2,node,t3,t4,rules,device]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_common import (OUT, REGULATORS, ROOT, YEARS, Quanta, available, load, markdown, node_water,
                             regulator_days)
from quantmaxmin.allocation import continuous_level, quantised_level, whole_step_level, whole_step_lower_bound

THETA = {"LXB-T000": 0.0, "LXB-T025": 0.25, "LXB-T050": 0.5, "LXB-T075": 0.75, "LXB-ES": 0.5, "LXB-CO": 0.5}
CASE_SCENARIO = {"phys": "normal", "q_main": "normal", "q_theta": "normal", "iot_main": "normal",
                 "q_deadband_low": "deadband_low", "q_deadband_high": "deadband_high", "q_cd_low": "gate_cd_low",
                 "q_cd_high": "gate_cd_high", "q_leak_005mm": "gate_leak_005mm", "q_rating": "rating_outlets"}
EPS = 1e-6


def save(df, name, title):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"{name}.csv", index=False)
    (OUT / f"{name}.md").write_text(f"# {title}\n\n" + markdown(df), encoding="utf-8")
    print(f"{name}: {len(df)} rows")


# Step volumes --------------------------------------------------------------------------------------------------------
def part_quanta():
    """Step volumes of the regulators at the lower operating level, the normal level and the upper operating level,
    and the conditions of Theorem 1(b) (baseline scenario)."""
    qa = Quanta("normal")
    P = qa.cfg.params
    h_lo = float(P["h_min_operating_m"].value); h_no = float(P["H_norm_m"].value)
    h_hi = float(P["H_max_m"].value) - float(qa.cfg.freeboard_m)
    width = np.asarray(P["regulator_width_m"].value, float); tail = np.asarray(P["regulator_tailwater_m"].value, float)
    cap = np.asarray(P["outlet_capacity_m3s"].value, float)[:5]
    N = int(round(86400 / qa.dt))
    c_step = np.minimum(cap, np.asarray(qa.node.max_flows(h_lo), float)[:5]) * qa.dt
    rows = []
    for j, u in enumerate(REGULATORS):
        r = {"user": u, "width_m": width[j], "travel_m": qa.amax[j], "tailwater_m": tail[j],
             "resolution_step_mm": 1e3 * qa.res * qa.amax[j], "k": qa.k,
             "smallest_opening_mm": 1e3 * qa.k * qa.res * qa.amax[j]}
        for tag, h in (("lo", h_lo), ("norm", h_no), ("hi", h_hi)):
            r[f"v_{tag}_m3"] = float(qa.v(h)[j]); r[f"q_{tag}_m3"] = float(qa.q(h)[j])
            r[f"p_{tag}_m3"] = float(qa.p(h)[j])
        r["C_step_lo_m3"] = float(c_step[j])
        r["C_ge_2q_3v"] = bool(c_step[j] >= 2 * r["q_hi_m3"] + 3 * r["v_hi_m3"])
        r["es_upper_limit_m3"] = float(math.ceil(N / 2) * (c_step[j] - r["v_hi_m3"]))
        rows.append(r)
    df = pd.DataFrame(rows)
    # daily demands of the season (baseline demand file, eta = 0.81)
    _, _, D = node_water(2010)
    df["D_min_m3"] = D[:5].min(axis=1); df["D_max_m3"] = D[:5].max(axis=1)
    df["D_min_over_q_lo"] = df["D_min_m3"] / df["q_lo_m3"]
    # varying level within a day (Appendix A, proof of Theorem 2(c)): the largest volume y = max{D, q_hi} that the
    # lower bound asks of a regulator is requested with half a step added, y + v_hi / 2, which must fit the equal split
    df["largest_shifted_target_m3"] = np.maximum(df["D_max_m3"], df["q_hi_m3"]) + 0.5 * df["v_hi_m3"]
    df["varying_level_ok"] = df["C_ge_2q_3v"] & (df["largest_shifted_target_m3"] <= df["es_upper_limit_m3"])
    save(df, "step_volumes", "Step volumes of the regulators (one resolution step v, quantum q = k v, pulse p = (k + 1) v; "
         "levels: lo = lower operating level, norm = normal level, hi = upper operating level)")


# Theorem 1 -----------------------------------------------------------------------------------------------------------
def part_t1():
    rows = []
    for case in ("q_main", "q_deadband_low", "q_deadband_high", "q_cd_low", "q_cd_high", "q_leak_005mm", "iot_main"):
        df = load(case, "LXB")
        if df.empty:
            continue
        qa = Quanta(CASE_SCENARIO[case])
        rd = regulator_days(df, qa)
        thr = (1 - 1 / (2 * qa.k)) * rd["q_min"]
        pos = rd["x"] > EPS
        predicted = pos & (rd["x"] < thr)
        dry = pos & (rd["open"] == 0)                         # the gate never opened during the day
        nowater = pos & (rd["V"] <= EPS)
        rows.append({"case": case, "k": qa.k, "seasons": int(df["year"].nunique()),
                     "regulator_days_x_pos": int(pos.sum()), "predicted_exclusion": int(predicted.sum()),
                     "gate_never_opened": int(dry.sum()), "no_water": int(nowater.sum()),
                     "predicted_and_never_opened": int((predicted & dry).sum()),
                     "never_opened_not_predicted": int((dry & ~predicted).sum()),
                     "R1_never_opened": int((dry & (rd["user"] == "R-1")).sum()),
                     "min_V_over_x_predicted": float((rd["V"][predicted] / rd["x"][predicted]).min())
                     if predicted.any() else np.nan,
                     "threshold": 1 - 1 / (2 * qa.k),
                     "days_x_below_qmin": int((pos & (rd["x"] < rd["q_min"])).sum()),
                     "max_x_over_qmin_never_opened_not_predicted":
                         float((rd["x"] / rd["q_min"])[dry & ~predicted].max()) if (dry & ~predicted).any() else np.nan,
                     "min_x_over_qmin_opened": float((rd["x"] / rd["q_min"])[pos & ~dry].min()) if (pos & ~dry).any()
                     else np.nan,
                     "min_x_over_qmin_predicted": float((rd["x"] / rd["q_min"])[predicted].min()) if predicted.any()
                     else np.nan,
                     "min_V_predicted_m3": float(rd["V"][predicted].min()) if predicted.any() else np.nan,
                     "max_V_predicted_m3": float(rd["V"][predicted].max()) if predicted.any() else np.nan,
                     "max_x_over_qmin_predicted": float((rd["x"] / rd["q_min"])[predicted].max()) if predicted.any()
                     else np.nan})
    save(pd.DataFrame(rows), "theorem1a_exclusion", "Theorem 1(a): exclusion under direct execution (LXB)")
    rows = []
    for case in ("q_main", "iot_main"):
        df = load(case, "LXB-ES")
        if df.empty:
            continue
        qa = Quanta(CASE_SCENARIO[case])
        rd = regulator_days(df, qa)
        es = rd["mode"] == "ES"
        err_hat = (rd["Vhat"] - rd["xt"]).abs()[es]; err = (rd["V"] - rd["xt"]).abs()[es]
        half = rd["v_max"][es] / 2; half_e = rd["v_max_est"][es] / 2
        rows.append({"case": case, "es_regulator_days": int(es.sum()),
                     "within_half_step_est": int((err_hat <= half_e + 1e-6).sum()),
                     "within_half_step_true": int((err <= half + 1e-6).sum()),
                     "max_err_over_half_step_est": float((err_hat / half_e).max()) if es.any() else np.nan,
                     "max_err_over_half_step_true": float((err / half).max()) if es.any() else np.nan,
                     "mean_abs_err_m3": float(err.mean()) if es.any() else np.nan,
                     "mean_abs_err_T050_same_days_m3": mean_err_same_days(case, rd[es])})
    save(pd.DataFrame(rows), "theorem1b_equal_split", "Theorem 1(b): equal split, |V - x| <= v_max / 2")


def mean_err_same_days(case, es_days):
    """Mean |V - x~| of the pulse rule with theta = 0.5 on the regulator-days served by the equal split."""
    t5 = load(case, "LXB-T050")
    if t5.empty or es_days.empty:
        return np.nan
    t5 = regulator_days(t5, Quanta(CASE_SCENARIO[case]))[["date", "user", "V", "xt"]]
    m = es_days[["date", "user"]].merge(t5, on=["date", "user"])
    return float((m["V"] - m["xt"]).abs().mean())


# Theorem 2 -----------------------------------------------------------------------------------------------------------
def part_t2():
    """Theorem 2 at the node. Daily lambda*, the minimum-delivery level lambda_q and Pi_ind with the quanta of the upper
    operating level, for the six outlets with the barrier from the closed position (its quantum) and without it; at
    every level of the operating range in steps of 1 cm, the lower bound of Theorem 2(c), which holds for every gate
    that delivers a volume in each interval of one step above its quantum (the barrier with its largest one-step
    volume, Appendix A), and the whole-step level lambda_v with all six outlets on grids; for comparison lambda_v with
    a barrier that takes any volume. On the days without deficit, the margin of the supply over max{D_j, q_j} plus one
    step of every outlet; the condition of Theorem 2(c) for the barrier at a constant level."""
    qa = Quanta("normal")
    h_hi = float(qa.cfg.params["H_max_m"].value) - float(qa.cfg.freeboard_m)
    h_lo = float(qa.cfg.params["h_min_operating_m"].value)

    def six(h):                                               # quanta and step volumes of the six outlets at level h
        b = qa.barrier(h)
        return np.r_[qa.q(h), b["q"]], np.r_[qa.v(h), b["v"]]

    q_hi, v_hi = six(h_hi); q_lo, v_lo = six(h_lo)
    q_hi0 = np.r_[qa.q(h_hi), 0.0]                            # barrier without a quantum
    grid_levels = np.round(np.arange(h_lo, h_hi + 1e-9, 0.01), 2)  # operating range in steps of 1 cm
    grid_qv = [six(h) for h in grid_levels]
    rows = []; margins = []; d6_max = 0.0
    ref = {y: load("q_main", "LXB-T050", (y,)) for y in YEARS}
    for y in YEARS:
        dates, A, D = node_water(y)
        hmax = ref[y]["h_max"].to_numpy() if not ref[y].empty else np.full(len(dates), np.nan)
        for p, d in enumerate(dates):
            Dp = D[:, p]
            d6_max = max(d6_max, float(Dp[5]))
            if A[p] > 0 and A[p] >= Dp.sum():                    # no deficit: room for one more step at every outlet
                margins.append(A[p] - np.maximum(Dp, q_hi).sum() - v_hi.sum())
            q_day = six(hmax[p])[0] if np.isfinite(hmax[p]) else q_hi
            lam = continuous_level(A[p], Dp)
            lq = quantised_level(A[p], Dp, q_hi)
            r = {"year": y, "date": d.date(), "V_m3": A[p], "sumD_m3": Dp.sum(), "lambda_star": lam,
                 "lambda_q": lq, "Pi_ind": lam - lq, "Pi_ind_barrier_without_quantum": lam - quantised_level(A[p], Dp, q_hi0),
                 "Pi_ind_day_level": lam - quantised_level(A[p], Dp, q_day),
                 "bound_sum_q_over_sum_D": q_hi.sum() / Dp.sum(),
                 "R1_demand_below_quantum": bool(Dp[1] < q_hi[1]),
                 "sum_qmin_exceeds_V": bool(A[p] < q_lo.sum()), "lambda_q_lo": quantised_level(A[p], Dp, q_lo)}
            if A[p] > 0:
                lv, lb, lqs, lv_reg = [], [], [], []
                for q, v in grid_qv:
                    lqs.append(quantised_level(A[p], Dp, q))
                    lv.append(whole_step_level(A[p], Dp, q, v))
                    lb.append(whole_step_lower_bound(A[p], Dp, q, v))
                    lv_reg.append(whole_step_level(A[p], Dp, np.r_[q[:5], 0.0], np.r_[v[:5], 0.0]))
                lv, lb, lqs = np.array(lv), np.array(lb), np.array(lqs)
                r.update({"lambda_v_min_range": float(lv.min()), "lambda_v_regulators_min_range": float(min(lv_reg)),
                          "loss_bound_max_range": float((lqs - lb).max()),
                          "bracket_ok_range": bool(np.all((lb - 1e-12 <= lv) & (lv <= lqs + 1e-12)))})
            else:
                r.update({"lambda_v_min_range": 0.0, "lambda_v_regulators_min_range": 0.0, "loss_bound_max_range": 0.0,
                          "bracket_ok_range": True})
            rows.append(r)
    daily = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT / "theorem2_daily.csv", index=False)
    sup = daily[daily["V_m3"] > 0]; defi = sup[sup["lambda_star"] < 1]
    gap = sup["lambda_star"] - sup["lambda_v_min_range"]
    gap_reg = sup["lambda_star"] - sup["lambda_v_regulators_min_range"]
    b_lo, b_hi = qa.barrier(h_lo), qa.barrier(h_hi)
    n_steps = round(86400 / qa.dt)
    # condition of Theorem 2(c) for the barrier at a constant level (Appendix A): one fully open step C >= 2 q, and
    # the daily volumes meet [y, y + v] for every q <= y <= (N - 3) C; the extreme values over the operating range
    cover = (n_steps - 3) * b_lo["C"]
    ws = pd.DataFrame([{"supply_days": int(len(sup)), "deficit_days_with_supply": int(len(defi)),
                        "barrier_C_lo_m3": b_lo["C"], "barrier_cover_m3": cover, "max_D6_m3": d6_max,
                        "barrier_condition_ok": bool(b_lo["C"] >= 2 * b_hi["q"] and d6_max <= cover),
                        "no_deficit_min_margin_m3": float(min(margins)),
                        "levels": int(len(grid_levels)), "level_step_m": 0.01,
                        "max_gap_range": float(gap.max()), "mean_gap_range_all_days": float(gap.sum() / len(daily)),
                        "max_gap_range_regulators": float(gap_reg.max()),
                        "max_loss_bound_range": float(sup["loss_bound_max_range"].max()),
                        "max_loss_bound_deficit": float(defi["loss_bound_max_range"].max()),
                        # guaranteed loss lambda* - lambda_v: the bound on the deficit days, zero on the other days
                        "mean_loss_bound_all_days": float(defi["loss_bound_max_range"].sum() / len(daily)),
                        "no_deficit_days_lambda_v_below_1_range": int(((sup["lambda_star"] >= 1)
                                                                       & (sup["lambda_v_min_range"] < 1)).sum()),
                        "bracket_holds_days_range": int(sup["bracket_ok_range"].sum()),
                        "max_Pi": float(sup["Pi_ind"].max()),
                        "max_Pi_barrier_without_quantum": float(sup["Pi_ind_barrier_without_quantum"].max()),
                        "max_Pi_lo": float((sup["lambda_star"] - sup["lambda_q_lo"]).max()),
                        "barrier_q_lo_m3": b_lo["q"], "barrier_q_hi_m3": b_hi["q"],
                        "barrier_v_lo_m3": b_lo["v"], "barrier_v_hi_m3": b_hi["v"],
                        "sum_v_hi_m3": float(v_hi.sum()), "sum_v_hi_regulators_m3": float(v_hi[:5].sum()),
                        "min_sumD_deficit_m3": float(defi["sumD_m3"].min())}])
    save(ws, "theorem2_whole_steps", "Theorem 2(c) at the node: lower bound of the whole-step level of the six outlets "
         "(the barrier with its quantum and largest one-step volume) and lambda_v with all outlets on grids, against "
         "lambda* and lambda_q at the levels of the operating range in steps of 1 cm (days with supply); lambda_v with a "
         "barrier that takes any volume for comparison; the condition of Theorem 2(c) for the barrier")
    summ = daily.groupby("year").agg(days=("date", "size"), deficit_days=("lambda_star", lambda s: int((s < 1).sum())),
                                     Pi_pos_days=("Pi_ind", lambda s: int((s > 1e-12).sum())),
                                     Pi_max=("Pi_ind", "max"), Pi_mean=("Pi_ind", "mean"),
                                     bound_mean=("bound_sum_q_over_sum_D", "mean"),
                                     R1_below_quantum_days=("R1_demand_below_quantum", "sum"),
                                     sum_qmin_exceeds_V_days=("sum_qmin_exceeds_V", "sum")).reset_index()
    tot = pd.DataFrame([{"year": "all", "days": int(summ["days"].sum()), "deficit_days": int(summ["deficit_days"].sum()),
                         "Pi_pos_days": int(summ["Pi_pos_days"].sum()), "Pi_max": float(daily["Pi_ind"].max()),
                         "Pi_mean": float(daily["Pi_ind"].mean()),
                         "bound_mean": float(daily["bound_sum_q_over_sum_D"].mean()),
                         "R1_below_quantum_days": int(summ["R1_below_quantum_days"].sum()),
                         "sum_qmin_exceeds_V_days": int(summ["sum_qmin_exceeds_V_days"].sum())}])
    save(pd.concat([summ, tot], ignore_index=True), "theorem2_summary",
         "Theorem 2: price of indivisibility of the Dustlik node (quanta at the upper operating level, the barrier from "
         "the closed position)")


# Node balance --------------------------------------------------------------------------------------------------------
def part_node():
    """Balance of the six outlets of the node by rule: daily surplus of the five regulators over their plans, which the
    barrier (no quantum, the rest of the inflow) gives up; satisfaction of the barrier against lambda* on the deficit days;
    storage change of the pool, W - sum of the six deliveries; seasonal delivery over the plan for every outlet."""
    from water01.domain.passport import USERS
    W = pd.concat([pd.DataFrame({"date": node_water(y)[0], "W": node_water(y)[1]}) for y in YEARS], ignore_index=True)
    rows = []
    for case, methods in (("phys", ("LXB",)), ("q_main", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
                          ("q_theta", ("LXB-T025", "LXB-T075")),
                          ("iot_main", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO"))):
        for m in methods:
            df = load(case, m)
            if df.empty:
                continue
            d = df.merge(W, on="date", how="left")
            sup = d["W"] > 0
            bar = USERS[5]
            sumD = sum(d[f"D_{u}"] for u in USERS)
            defi = sup & (d["W"] < sumD)                         # deficit day of the recorded supply, lambda* < 1
            plan_ratio = d[f"x_{bar}"] / d[f"D_{bar}"]           # planned satisfaction of the barrier (= lambda*)
            surplus = sum(d[f"V_{u}"] - d[f"x_{u}"] for u in USERS[:5])
            ds = d["W"] - sum(d[f"V_{u}"] for u in USERS)
            dev = d[f"r_{bar}"] - plan_ratio
            r = {"case": case, "rule": m, "supply_days": int(sup.sum()), "deficit_days": int(defi.sum()),
                 "regulator_surplus_mean_m3": float(surplus[sup].mean()), "regulator_surplus_max_m3": float(surplus[sup].max()),
                 "regulator_surplus_max_over_D6_deficit": float((surplus / d[f"D_{bar}"])[defi].max()),
                 "barrier_r_minus_lambda_mean_deficit": float(dev[defi].mean()),
                 "barrier_r_minus_lambda_min_deficit": float(dev[defi].min()),
                 "barrier_r_minus_lambda_max_deficit": float(dev[defi].max()),
                 "barrier_below_lambda_by_1e3_days": int((dev[defi] < -1e-3).sum()),
                 "storage_change_over_W_mean": float((ds / d["W"])[sup].mean()),
                 "storage_change_over_W_min": float((ds / d["W"])[sup].min()),
                 "storage_change_over_W_max": float((ds / d["W"])[sup].max()),
                 "lambda_mean_deficit": float(d["lambda"][defi].mean()),
                 "lambda_star_mean_deficit": float((d["W"] / sumD)[defi].mean()),
                 "plan_ratio_minus_lambda_star_max_abs_deficit": float((plan_ratio - d["W"] / sumD)[defi].abs().max())}
            for u in USERS:
                r[f"V_over_x_{u}"] = float(d[f"V_{u}"].sum() / d[f"x_{u}"].sum())
            rows.append(r)
    save(pd.DataFrame(rows), "node_balance", "Balance of the six outlets by rule (sums over the stored seasons; the "
         "barrier on the deficit days of the recorded supply, its satisfaction against its planned satisfaction)")


# Theorem 3 -----------------------------------------------------------------------------------------------------------
def part_t3():
    rows = []; viol = []
    for case, methods in (("q_main", ("LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
                          ("q_theta", ("LXB-T025", "LXB-T075")),
                          ("iot_main", ("LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
                          ("q_rating", ("LXB-T050", "LXB-CO"))):
        qa = Quanta(CASE_SCENARIO[case])
        for m in methods:
            df = load(case, m)
            if df.empty:
                continue
            th = THETA[m]
            rd = regulator_days(df, qa).sort_values(["user", "date"])
            rd["prev_open_all_day"] = (rd.groupby(["user", "year"])["open"].shift(1) == round(86400 / qa.dt))
            pure = (rd["pulses"] > 0) & (rd["open"] == rd["pulses"]) & (rd["esopen"] == 0) & (rd["xt"] > EPS)
            r = rd[pure]
            for vol in ("Vhat", "V"):
                pcol = "p_max_est" if vol == "Vhat" else "p_max"   # step volumes known to the controller / plant
                lower = r["xt"] - th * np.minimum(r[pcol], r["xt"])
                upper = r["xt"] + r[pcol]
                # sharper upper bound for plans of at least one pulse: V <= x~ + (1 - theta) p_max
                big = r["xt"] >= r[pcol]
                upper_sharp = np.where(big, r["xt"] + (1 - th) * r[pcol], upper)
                ok_lo = r[vol] >= lower - 1e-6; ok_up = r[vol] < upper + 1e-6
                ok_sh = r[vol] <= upper_sharp + 1e-6
                bad = r[~(ok_lo & ok_up)][["year", "date", "user", "xt", "V", "Vhat", "p_max", "open", "pulses"]].copy()
                if len(bad):
                    bad["case"] = case; bad["rule"] = m; bad["volume"] = vol
                    bad["lower_bound_m3"] = lower[~(ok_lo & ok_up)]; bad["upper_bound_m3"] = upper[~(ok_lo & ok_up)]
                    viol.append(bad)
                n_pmin = round(86400 / qa.dt) * r["q_min"] * (qa.k + 1) / qa.k      # N p_min of the day
                rows.append({"case": case, "rule": m, "theta": th, "volume": vol, "pulse_regime_days": int(pure.sum()),
                             "days_x_ge_N_pmin": int((r["xt"] >= n_pmin).sum()),
                             "days_after_day_open_throughout": int(r["prev_open_all_day"].sum()),
                             "max_x_over_N_pmin": float((r["xt"] / n_pmin).max()) if len(r) else 0.0,
                             "lower_bound_holds": int(ok_lo.sum()), "upper_bound_holds": int(ok_up.sum()),
                             "days_x_ge_p": int(big.sum()), "sharp_upper_bound_holds": int(ok_sh.sum()),
                             "sharp_violations_after_day_open_throughout": int((~ok_sh & r["prev_open_all_day"]).sum()),
                             "sharp_max_excess_over_p": float(((r[vol] - upper_sharp) / r[pcol]).clip(lower=0).max())
                             if len(r) else 0.0,
                             "sharp_max_excess_not_after_open_over_p":
                                 float(((r[vol] - upper_sharp) / r[pcol]).clip(lower=0)[~r["prev_open_all_day"]].max())
                                 if len(r) else 0.0,
                             "max_lower_violation_m3": float((lower - r[vol]).clip(lower=0).max()) if len(r) else 0.0,
                             "max_upper_violation_m3": float((r[vol] - upper).clip(lower=0).max()) if len(r) else 0.0,
                             "max_lower_violation_over_p": float(((lower - r[vol]).clip(lower=0) / r[pcol]).max())
                             if len(r) else 0.0,
                             "max_upper_violation_over_p": float(((r[vol] - upper).clip(lower=0) / r[pcol]).max())
                             if len(r) else 0.0,
                             "mean_abs_V_minus_Vhat_over_p": float(((r["V"] - r["Vhat"]).abs() / r["p_max"]).mean())
                             if len(r) else 0.0,
                             "max_abs_V_minus_Vhat_over_p": float(((r["V"] - r["Vhat"]).abs() / r["p_max"]).max())
                             if len(r) else 0.0,
                             "mean_shortfall_m3": float((r["xt"] - r[vol]).clip(lower=0).mean()) if len(r) else 0.0,
                             "mean_overdelivery_m3": float((r[vol] - r["xt"]).clip(lower=0).mean()) if len(r) else 0.0,
                             "days_without_pulse_x_pos": int(((rd["xt"] > EPS) & (rd["open"] == 0)
                                                              & (rd["mode"] == "PULSE")).sum())})
    save(pd.DataFrame(rows), "theorem3_theta_rule", "Theorem 3: bounds of the theta pulse rule (pulse-regime days)")
    if viol:
        pd.concat(viol, ignore_index=True).to_csv(OUT / "theorem3_violations.csv", index=False)


# Theorem 4 -----------------------------------------------------------------------------------------------------------
def period_errors(rd, vol, T_values=(1, 10, 30, 183)):
    pcol = "p_max_est" if vol == "Vhat" else "p_max"
    """Accounting-period error of every block of T consecutive days of a season and outlet, with the share of the
    block's days on which the outlet was operated by pulses only (the setting of Theorems 3 and 4)."""
    out = []
    for (y, u), g in rd.groupby(["year", "user"]):
        g = g.sort_values("date")
        for T in T_values:
            n = len(g) // T
            if n == 0:
                continue
            V = g[vol].to_numpy()[:n * T].reshape(n, T).sum(1)
            x = g["x"].to_numpy()[:n * T].reshape(n, T).sum(1)
            D = g["D"].to_numpy()[:n * T].reshape(n, T).sum(1)
            pure = g["pure"].to_numpy()[:n * T].reshape(n, T).mean(1)
            pm = g[pcol].max()
            for b in range(n):
                out.append({"year": y, "user": u, "T": T, "block": b, "sumV": V[b], "sumx": x[b], "sumD": D[b],
                            "p_max": pm, "pulse_share": pure[b], "err_sat": (V[b] - x[b]) / D[b],
                            # any block: e(start) - e(end) lies in (-(1 + theta) p, (1 + theta) p), theta = 0.5
                            "bound_block": 1.5 * pm / D[b]})
    return pd.DataFrame(out)


def prefix_errors(rd, vol, T_values=(1, 10, 30, 183)):
    """Error of the periods that start with the season (e(0) = 0), the setting of (16): the shortfall of the period is
    at most theta p_max and the over-delivery less than p_max (theta = 0.5)."""
    pcol = "p_max_est" if vol == "Vhat" else "p_max"
    out = []
    for (y, u), g in rd.groupby(["year", "user"]):
        g = g.sort_values("date")
        for T in T_values:
            if len(g) < T:
                continue
            h = g.iloc[:T]
            V, x, D = h[vol].sum(), h["x"].sum(), h["D"].sum()
            pm = g[pcol].max()
            out.append({"year": y, "user": u, "T": T, "all_pulse": bool(h["pure"].all()), "err": V - x,
                        "shortfall_ok": bool(x - V <= 0.5 * pm + 1e-6), "overdelivery_ok": bool(V - x < pm + 1e-6),
                        "err_sat": (V - x) / D, "bound_shortfall_sat": 0.5 * pm / D})
    return pd.DataFrame(out)


def part_t4():
    rows = []; per = []; pre = []; viol = []
    for case in ("q_main", "iot_main", "q_rating"):
        qa = Quanta(CASE_SCENARIO[case])
        for m in ("LXB-CO", "LXB-T050"):
            df = load(case, m)
            if df.empty:
                continue
            rd = regulator_days(df, qa).sort_values(["user", "date"])
            rd["pure"] = (rd["pulses"] > 0) & (rd["open"] == rd["pulses"]) & (rd["esopen"] == 0)
            if m == "LXB-CO":
                # debt recursion of the rule, reconstructed from the plan and the estimated volumes
                e_all = []
                for (y, u), g in rd.groupby(["year", "user"]):
                    prev = 0.0; es = []
                    for x, vh in zip(g["x"], g["Vhat"]):
                        xt = x + prev; e = xt - vh; es.append(e); prev = e
                    e_all.append(pd.Series(es, index=g.index))
                rd["debt"] = pd.concat(e_all)
                pm = rd.groupby(["year", "user"])["p_max_est"].transform("max")   # the debt is the controller's
                ok = (rd["debt"] > -pm - 1e-6) & (rd["debt"] <= 0.5 * pm + 1e-6)
                pure = rd["pure"]
                v = rd[pure & ~ok][["year", "date", "user", "x", "xt", "Vhat", "debt", "p_max", "open", "pulses"]].copy()
                v["case"] = case; viol.append(v)
                for scope, sel in (("all regulators", slice(None)), ("R-1", rd["user"] == "R-1")):
                    r = rd[sel]; ok_r = ok[sel]; pu = pure[sel]; pm_r = pm[sel]
                    rows.append({"case": case, "rule": m, "outlets": scope, "regulator_days": int(len(r)),
                                 "pulse_days": int(pu.sum()), "pulse_days_debt_within_bounds": int((ok_r & pu).sum()),
                                 "pulse_debt_min_over_pmax": float((r["debt"] / pm_r)[pu].min()) if pu.any() else np.nan,
                                 "pulse_debt_max_over_pmax": float((r["debt"] / pm_r)[pu].max()) if pu.any() else np.nan,
                                 "other_days": int((~pu).sum()),
                                 "other_days_debt_within_bounds": int((ok_r & ~pu).sum()),
                                 "other_days_max_abs_debt_over_plan": float((r["debt"].abs() / r["x"].where(r["x"] >= 1.0))[~pu].max())
                                 if (~pu).any() else np.nan})
            for vol in ("Vhat", "V"):                       # estimated volumes (the debt of the rule) and the plant
                pe = period_errors(rd, vol)
                pe["case"] = case; pe["rule"] = m; pe["volume"] = vol
                per.append(pe)
                pf = prefix_errors(rd, vol); pf["case"] = case; pf["rule"] = m; pf["volume"] = vol
                pre.append(pf)
    if viol:
        pd.concat(viol, ignore_index=True).to_csv(OUT / "theorem4_pulse_day_violations.csv", index=False)
    save(pd.DataFrame(rows), "theorem4_debt", "Theorem 4: debt of the carry-over rule (estimated volumes) on the days "
         "operated by pulses only and on the other days")
    if per:
        pe = pd.concat(per, ignore_index=True)
        pe.to_csv(OUT / "theorem4_period_blocks.csv", index=False)
        pe = pe.assign(abs_err=pe["err_sat"].abs(), ratio=pe["err_sat"].abs() / pe["bound_block"],
                       all_pulse=pe["pulse_share"] >= 1 - 1e-12)
        s = pe.groupby(["case", "rule", "volume", "user", "T"]).apply(lambda g: pd.Series({
            "blocks": len(g), "pulse_blocks": int(g["all_pulse"].sum()), "mean_abs_err": g["abs_err"].mean(),
            "max_abs_err": g["abs_err"].max(), "max_err_over_bound": g["ratio"].max(),
            "blocks_within_bound": int((g["ratio"] <= 1 + 1e-9).sum()),
            "blocks_above_theta_p": int((g["abs_err"] > g["bound_block"] / 3 + 1e-12).sum()),   # theta p / sum D
            "max_err_over_bound_pulse_blocks": g.loc[g["all_pulse"], "ratio"].max() if g["all_pulse"].any() else np.nan,
            "mean_err": g["err_sat"].mean()}), include_groups=False).reset_index()
        save(s, "theorem4_periods", "Theorem 4: accounting-period error |sum V - sum x| / sum D by rule and period "
             "(blocks of T consecutive days; bound of any block (1 + theta) p_max / sum D)")
    if pre:
        pf = pd.concat(pre, ignore_index=True)
        pf.to_csv(OUT / "theorem4_prefix.csv", index=False)
        q = pf.groupby(["case", "rule", "volume", "user", "T"]).apply(lambda g: pd.Series({
            "periods": len(g), "all_pulse_periods": int(g["all_pulse"].sum()),
            "bounds_hold_all_pulse": int((g["all_pulse"] & g["shortfall_ok"] & g["overdelivery_ok"]).sum()),
            "bounds_hold_all": int((g["shortfall_ok"] & g["overdelivery_ok"]).sum()),
            "mean_abs_err_sat": g["err_sat"].abs().mean(), "max_abs_err_sat": g["err_sat"].abs().max()}),
            include_groups=False).reset_index()
        save(q, "theorem4_prefix_summary", "Theorem 4: periods that start with the season, shortfall at most "
             "theta p_max and over-delivery below p_max (theta = 0.5)")


# Device chain -----------------------------------------------------------------------------------------------------------
def part_device():
    """Execution under the device chain against the quantised actuator alone: pulse days on which the executed open
    steps differ from the commanded pulses by one or two (a command packet lost: assumption (H4) of the article violated), the error of the
    estimated volume against the plant, and equal-split days outside half a resolution step."""
    rows = []
    for case in ("q_main", "iot_main"):
        qa = Quanta(CASE_SCENARIO[case])
        for m in ("LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO"):
            df = load(case, m)
            if df.empty:
                continue
            rd = regulator_days(df, qa)
            cand = (rd["pulses"] > 0) & (rd["esopen"] == 0) & (rd["xt"] > EPS)
            pure = cand & (rd["open"] == rd["pulses"])
            diff = rd["open"] - rd["pulses"]
            lost = cand & diff.abs().between(1, 2)
            e_lost = ((rd["V"] - rd["xt"]) / rd["p_max"])[lost]
            es = rd["mode"] == "ES"
            half_e = rd["v_max_est"] / 2
            es_out = es & ((rd["Vhat"] - rd["xt"]).abs() > half_e + 1e-6)
            step = rd["xt"] / rd["m"].where(rd["m"] > 0)
            e_es = ((rd["Vhat"] - rd["xt"]).abs() / step)[es_out]
            rows.append({"case": case, "rule": m, "seasons": int(df["year"].nunique()),
                         "pulse_regime_days": int(pure.sum()), "days_with_pulses": int(cand.sum()),
                         "pulse_days_one_or_two_steps_differ": int(lost.sum()),
                         "of_which_step_missing": int((lost & (diff < 0)).sum()),
                         "of_which_step_added": int((lost & (diff > 0)).sum()),
                         "lost_days_err_min_over_p": float(e_lost.min()) if lost.any() else np.nan,
                         "lost_days_err_max_over_p": float(e_lost.max()) if lost.any() else np.nan,
                         "pure_days_mean_abs_V_minus_Vhat_over_p":
                             float(((rd["V"] - rd["Vhat"]).abs() / rd["p_max"])[pure].mean()) if pure.any() else np.nan,
                         "pure_days_max_abs_V_minus_Vhat_over_p":
                             float(((rd["V"] - rd["Vhat"]).abs() / rd["p_max"])[pure].max()) if pure.any() else np.nan,
                         "es_days": int(es.sum()), "es_days_outside_half_step_est": int(es_out.sum()),
                         "es_outside_median_err_over_open_step": float(e_es.median()) if es_out.any() else np.nan,
                         "es_outside_max_err_over_open_step": float(e_es.max()) if es_out.any() else np.nan})
    save(pd.DataFrame(rows), "device_chain", "Device chain against the quantised actuator alone: lost commands on "
         "pulse days, estimated against plant volumes, equal-split days outside half a resolution step")

# Rules ---------------------------------------------------------------------------------------------------------------
def dekad_errors(df, vol, exclude=None):
    """|sum V - sum x| / sum D of R-1 over the calendar dekads (days 1-10, 11-20 and 21 to the end of the month; the
    season of 183 days has 18 of them); with exclude, the dekads that contain one of these days are left out."""
    d = pd.DatetimeIndex(df["date"])
    key = d.year * 1000 + d.month * 10 + np.where(d.day <= 10, 0, np.where(d.day <= 20, 1, 2))
    bad = df["date"].isin(exclude).to_numpy() if exclude is not None else np.zeros(len(df), bool)
    g = pd.DataFrame({"k": key, "V": df[f"{vol}_R-1"].to_numpy(), "x": df["x_R-1"].to_numpy(),
                      "D": df["D_R-1"].to_numpy(), "bad": bad.astype(int)}).groupby("k").sum()
    g = g[g["bad"] == 0]
    return ((g["V"] - g["x"]).abs() / g["D"]).to_numpy()


def part_rules():
    act = OUT / "gate_activity.csv"
    activity = pd.read_csv(act).set_index("method") if act.exists() else None
    rows = []
    for case, methods in (("phys", ("LXB",)), ("q_main", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
                          ("q_theta", ("LXB-T025", "LXB-T075")),
                          ("iot_main", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
                          ("q_deadband_low", ("LXB",)), ("q_deadband_high", ("LXB",)), ("q_cd_low", ("LXB",)),
                          ("q_cd_high", ("LXB",)), ("q_leak_005mm", ("LXB",)), ("q_rating", ("LXB-T050", "LXB-CO"))):
        for m in methods:
            df = load(case, m)
            if df.empty:
                continue
            rcols = [f"r_{u}" for u in REGULATORS]
            r = df[rcols]
            lam = df["lambda"]
            short = sum((df[f"x_{u}"] - df[f"V_{u}"]).clip(lower=0).sum() for u in REGULATORS)
            over = sum((df[f"V_{u}"] - df[f"x_{u}"]).clip(lower=0).sum() for u in REGULATORS)
            plan = sum(df[f"x_{u}"].clip(lower=0).sum() for u in REGULATORS)
            seas = df.groupby("year")[[f"V_{u}" for u in REGULATORS] + [f"D_{u}" for u in REGULATORS]].sum()
            # accounting-period error of R-1 over blocks of 10 consecutive days of each season
            e10 = []; e10_est = []
            for _, g in df.sort_values("date").groupby("year"):
                n = len(g) // 10
                V = g["V_R-1"].to_numpy()[:10 * n].reshape(n, 10).sum(1)
                Vh = g["Vhat_R-1"].to_numpy()[:10 * n].reshape(n, 10).sum(1)
                x = g["x_R-1"].to_numpy()[:10 * n].reshape(n, 10).sum(1)
                D = g["D_R-1"].to_numpy()[:10 * n].reshape(n, 10).sum(1)
                e10.extend(np.abs(V - x) / D); e10_est.extend(np.abs(Vh - x) / D)
            seas_est = df.groupby("year")[[f"Vhat_{u}" for u in REGULATORS]].sum()
            sat = pd.DataFrame({u: seas[f"V_{u}"] / seas[f"D_{u}"] for u in REGULATORS})
            dk = dekad_errors(df, "V"); dk_est = dekad_errors(df, "Vhat")
            pos = df["x_R-1"] > EPS
            extra = {"R1_dekads": int(dk.size), "R1_dekad_err_mean": float(dk.mean()),
                     "R1_dekad_err_median": float(np.median(dk)), "R1_dekad_err_p95": float(np.quantile(dk, 0.95)),
                     "R1_dekad_err_max": float(dk.max()), "R1_dekad_err_mean_est": float(dk_est.mean()),
                     "R1_days_plan_pos": int(pos.sum()),
                     "R1_days_mode_ES": int((pos & (df["mode_R-1"] == "ES")).sum()),
                     "R1_days_mode_PULSE": int((pos & (df["mode_R-1"] == "PULSE")).sum()),
                     "R1_days_mode_LP": int((pos & (df["mode_R-1"] == "LP")).sum())}
            if activity is not None and case == "q_main" and m in activity.index:
                a = activity.loc[m]
                extra.update({"gate_moves_per_regulator_day": float(a["moves_per_day"]),
                              "gate_moves_per_day_R1": float(a["moves_R-1"]),
                              "gate_travel_per_regulator_day": float(a["travel_per_day"])})
            rows.append({**extra, "case": case, "rule": m, "seasons": int(df["year"].nunique()), "days": int(len(df)),
                         "mean_daily_lambda": float(lam.mean()), "min_daily_lambda": float(lam.min()),
                         "days_lambda_zero": int((lam <= EPS).sum()),
                         "regulator_days_r_zero": int((r <= EPS).sum().sum()),
                         "R1_days_r_zero": int((df["r_R-1"] <= EPS).sum()),
                         "regulator_plan_m3": float(plan),
                         "regulator_shortfall_m3": float(short), "regulator_overdelivery_m3": float(over),
                         "shortfall_share": float(short / plan), "overdelivery_share": float(over / plan),
                         "mean_r_R1": float(df["r_R-1"].mean()),
                         "season_satisfaction_min": float(sat.to_numpy().min()),
                         "season_satisfaction_R1_mean": float(sat["R-1"].mean()),
                         "season_satisfaction_R1_mean_est": float((seas_est["Vhat_R-1"] / seas["D_R-1"]).mean()),
                         "R1_mean_abs_err_T10": float(np.mean(e10)), "R1_mean_abs_err_T10_est": float(np.mean(e10_est)),
                         "R1_season_volume_over_plan": float(df["V_R-1"].sum() / df["x_R-1"].clip(lower=0).sum())})
    save(pd.DataFrame(rows), "rules_outcome", "Outcome of the execution rules (regulators, all stored seasons)")


# Records --------------------------------------------------------------------------------------------------------------
def part_data():
    """Operating records. (1) Blank Kegeyli head entries of the seasons, classified by the balance of the Dustlik
    head: on the days with all records, (Kegeyli + Kuanyshjarma + Kokozek) / Dustlik has the median ratio r, so on a
    blank day with the Dustlik and Kuanyshjarma records the Kegeyli discharge is about r Dustlik - Kuanyshjarma -
    Kokozek. (2) The 2011 annual volume against the daily records, month by month (annual summary of the record book).
    (3) The outcome of the rules with the blank days treated as missing instead of zero supply: the blank days and the
    day after each run of blank days are left out (complete-case)."""
    from analysis_common import SUP
    rec = pd.read_csv(SUP, parse_dates=["date"])
    s = rec[rec.date.dt.month.between(4, 9)].copy()
    full = s.dropna(subset=["dostlik_Q", "kegeyli_Q", "kj_Q"])
    full = full[full.dostlik_Q > 0]
    ratio = (full.kegeyli_Q + full.kj_Q + full.kok_ozek_Q.fillna(0.0)) / full.dostlik_Q
    r = float(ratio.median())
    b = s[s.kegeyli_Q.isna()].copy()
    implied = b.dostlik_Q * r - b.kj_Q - b.kok_ozek_Q.fillna(0.0)
    both = b.dostlik_Q.notna() & b.kj_Q.notna()
    rows = [{"blank_days": int(len(b)), "balance_ratio_median": r,
             "balance_ratio_q25": float(ratio.quantile(0.25)), "balance_ratio_q75": float(ratio.quantile(0.75)),
             "days_all_records": int(len(full)),
             "head_and_kj_recorded": int(both.sum()),
             "implied_le_2_m3s": int((both & (implied <= 2.0)).sum()),
             "implied_gt_2_m3s": int((both & (implied > 2.0)).sum()),
             "implied_max_m3s": float(implied[both].max()),
             "head_blank": int(b.dostlik_Q.isna().sum()),
             "other": int((b.dostlik_Q.notna() & b.kj_Q.isna()).sum())}]
    # 2011: annual summary of the record book against the daily records, by month
    summ = pd.read_csv(ROOT / "DATA/processed/annual_summary_2011_monthly.csv").set_index("month")
    d11 = rec[rec.date.dt.year == 2011]
    daily = d11.groupby(d11.date.dt.month)["kegeyli_Q"].sum() * 86400 / 1e6
    diff = (daily.reindex(summ.index) - summ["kegeyli_mln_m3"]).abs()
    may = d11[d11.date.dt.month == 5]
    share = {c: float(summ.loc[5, f"{n}_mln_m3"] / (may[c].sum() * 86400 / 1e6))      # summary / May sheet, by canal
             for c, n in (("dostlik_Q", "dostlik"), ("kegeyli_Q", "kegeyli"), ("kj_Q", "kuanyshjarma"))}
    mfull = may.dropna(subset=["dostlik_Q", "kegeyli_Q", "kj_Q"])
    rows[0].update({"y2011_daily_mln_m3": float(daily.sum()), "y2011_summary_mln_m3": float(summ["kegeyli_mln_m3"].sum()),
                    "y2011_months_differing": ",".join(str(m) for m in diff.index[diff > 1e-6]),
                    "y2011_may_summary_mln_m3": float(summ.loc[5, "kegeyli_mln_m3"]),
                    "y2011_may_daily_mln_m3": float(daily.loc[5]),
                    "y2011_may_summary_share_min": min(share.values()), "y2011_may_summary_share_max": max(share.values()),
                    "y2011_may_balance_ratio_median": float(((mfull.kegeyli_Q + mfull.kj_Q + mfull.kok_ozek_Q.fillna(0.0))
                                                             / mfull.dostlik_Q).median()),
                    "y2011_may_days_balance": int(len(mfull)),
                    "y2011_may_kegeyli_blank_days": int(may.kegeyli_Q.isna().sum())})
    save(pd.DataFrame(rows), "record_checks", "Blank Kegeyli entries of the seasons classified by the balance of the "
         "Dustlik head, and the 2011 annual volume against the daily records")
    # complete-case outcome of the rules
    blank = set(b.date.dt.normalize())
    after = {d + pd.Timedelta(days=1) for d in blank} - blank
    drop = blank | after
    out = []
    for case, methods in (("phys", ("LXB",)), ("q_main", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO")),
                          ("q_theta", ("LXB-T025", "LXB-T075")),
                          ("iot_main", ("LXB", "LXB-T000", "LXB-T050", "LXB-ES", "LXB-CO"))):
        for m in methods:
            df = load(case, m)
            if df.empty:
                continue
            keep = ~df["date"].isin(drop)
            cc = df[keep]
            seas = cc.groupby("year")[["V_R-1", "D_R-1"]].sum()
            dk_all = dekad_errors(df, "V")
            dk_cc = dekad_errors(df, "V", exclude=drop)
            out.append({"case": case, "rule": m, "days": int(len(df)), "days_complete": int(len(cc)),
                        "mean_daily_lambda": float(df["lambda"].mean()),
                        "mean_daily_lambda_complete": float(cc["lambda"].mean()),
                        "days_lambda_zero": int((df["lambda"] <= EPS).sum()),
                        "days_lambda_zero_complete": int((cc["lambda"] <= EPS).sum()),
                        "season_satisfaction_R1_mean_complete": float((seas["V_R-1"] / seas["D_R-1"]).mean()),
                        "R1_dekad_err_mean": float(dk_all.mean()), "R1_dekad_err_mean_complete": float(dk_cc.mean()),
                        "R1_dekads_complete": int(dk_cc.size)})
    out = pd.DataFrame(out)
    ref = out[(out.case == "phys") & (out.rule == "LXB")].iloc[0]
    out["lambda_below_ideal"] = ref.mean_daily_lambda - out.mean_daily_lambda
    out["lambda_below_ideal_complete"] = ref.mean_daily_lambda_complete - out.mean_daily_lambda_complete
    out["change_of_difference"] = out.lambda_below_ideal_complete - out.lambda_below_ideal
    out["lambda_rise"] = out.mean_daily_lambda_complete - out.mean_daily_lambda
    out["dekad_err_change"] = out.R1_dekad_err_mean_complete - out.R1_dekad_err_mean
    save(out, "complete_case", "Outcome of the rules with the blank days of the record treated as missing: "
         "the blank days and the day after each run of blank days left out (complete-case), against all days")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parts", default="quanta,t1,t2,node,t3,t4,rules,device,data")
    a = ap.parse_args()
    for part in a.parts.split(","):
        {"quanta": part_quanta, "t1": part_t1, "t2": part_t2, "node": part_node, "t3": part_t3, "t4": part_t4,
         "rules": part_rules, "device": part_device, "data": part_data}[part]()


if __name__ == "__main__":
    main()
