"""Closed-loop checks of Theorems 1-4 on the stored Saint-Venant runs (results/runs) and the daily price of
indivisibility of the Kegeyli node (Theorem 2). Writes results/analysis/*.csv and *.md.

Parts:
  quanta  step volumes of the regulators at three levels and the conditions of Theorem 1(b).
  t1  Theorem 1(a): predicted exclusion (0 < x < (1 - 1/(2k)) q_min) against regulator-days without water under floor
      rounding (LXB), for the deadband, discharge-coefficient and leakage cases; Theorem 1(b): equal-split error.
  t2  Theorem 2: daily lambda*, lambda_q and Pi_ind of the node from the operating records (quanta at the upper
      operating level and at the daily maximum level of the run).
  t3  Theorem 3: bounds of the theta pulse rule on regulator-days in the pulse regime.
  t4  Theorem 4: debt bounds of the carry-over rule and accounting-period errors for T = 1, 10, 30 days and the season.
  rules  outcome of every rule (daily worst-case satisfaction, outlet-days without water, shortfall, over-delivery).
Usage: python scripts/analyse_theorems.py [--parts quanta,t1,t2,t3,t4,rules]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_common import (OUT, REGULATORS, YEARS, Quanta, available, load, markdown, node_water,
                             regulator_days)
from quantmaxmin.allocation import continuous_level, quantised_level

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
            r[f"g_{tag}_m3"] = float(qa.g(h)[j]); r[f"q_{tag}_m3"] = float(qa.q(h)[j])
            r[f"p_{tag}_m3"] = float(qa.p(h)[j])
        r["C_step_lo_m3"] = float(c_step[j])
        r["C_ge_2q_3g"] = bool(c_step[j] >= 2 * r["q_hi_m3"] + 3 * r["g_hi_m3"])
        r["es_upper_limit_m3"] = float(math.ceil(N / 2) * (c_step[j] - r["g_hi_m3"]))
        rows.append(r)
    df = pd.DataFrame(rows)
    # daily demands of the season (baseline demand file, eta = 0.81)
    _, _, D = node_water(2010)
    df["D_min_m3"] = D[:5].min(axis=1); df["D_max_m3"] = D[:5].max(axis=1)
    df["D_min_over_q_lo"] = df["D_min_m3"] / df["q_lo_m3"]
    save(df, "step_volumes", "Step volumes of the regulators (one resolution step g, quantum q = k g, pulse p = (k + 1) g; "
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
    save(pd.DataFrame(rows), "theorem1a_exclusion", "Theorem 1(a): exclusion under floor rounding (LXB)")
    rows = []
    for case in ("q_main", "iot_main"):
        df = load(case, "LXB-ES")
        if df.empty:
            continue
        qa = Quanta(CASE_SCENARIO[case])
        rd = regulator_days(df, qa)
        es = rd["mode"] == "ES"
        err_hat = (rd["Vhat"] - rd["xt"]).abs()[es]; err = (rd["V"] - rd["xt"]).abs()[es]
        half = rd["g_max"][es] / 2; half_e = rd["g_max_est"][es] / 2
        rows.append({"case": case, "es_regulator_days": int(es.sum()),
                     "within_half_step_est": int((err_hat <= half_e + 1e-6).sum()),
                     "within_half_step_true": int((err <= half + 1e-6).sum()),
                     "max_err_over_half_step_est": float((err_hat / half_e).max()) if es.any() else np.nan,
                     "max_err_over_half_step_true": float((err / half).max()) if es.any() else np.nan,
                     "mean_abs_err_m3": float(err.mean()) if es.any() else np.nan,
                     "mean_abs_err_T050_same_days_m3": mean_err_same_days(case, rd[es])})
    save(pd.DataFrame(rows), "theorem1b_equal_split", "Theorem 1(b): equal split, |V - x| <= g_max / 2")


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
    qa = Quanta("normal")
    h_hi = float(qa.cfg.params["H_max_m"].value) - float(qa.cfg.freeboard_m)
    q_hi = np.r_[qa.q(h_hi), 0.0]                                 # check structure: no quantum
    q_lo = np.r_[qa.q(float(qa.cfg.params["h_min_operating_m"].value)), 0.0]
    rows = []
    ref = {y: load("q_main", "LXB-T050", (y,)) for y in YEARS}
    for y in YEARS:
        dates, A, D = node_water(y)
        hmax = ref[y]["h_max"].to_numpy() if not ref[y].empty else np.full(len(dates), np.nan)
        for p, d in enumerate(dates):
            q_day = np.r_[qa.q(hmax[p]), 0.0] if np.isfinite(hmax[p]) else q_hi
            lam = continuous_level(A[p], D[:, p])
            lq = quantised_level(A[p], D[:, p], q_hi)
            lq_day = quantised_level(A[p], D[:, p], q_day)
            rows.append({"year": y, "date": d.date(), "V_m3": A[p], "sumD_m3": D[:, p].sum(), "lambda_star": lam,
                         "lambda_q": lq, "Pi_ind": lam - lq, "Pi_ind_day_level": lam - quantised_level(
                             A[p], D[:, p], q_day), "bound_sum_q_over_sum_D": q_hi.sum() / D[:, p].sum(),
                         "R1_demand_below_quantum": bool(D[1, p] < q_hi[1]), "lambda_q_day": lq_day,
                         "sum_qmin_exceeds_V": bool(A[p] < q_lo.sum())})
    daily = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT / "theorem2_daily.csv", index=False)
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
         "Theorem 2: price of indivisibility of the Dustlik node (quanta at the upper operating level)")


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
            rd = regulator_days(df, qa)
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
                rows.append({"case": case, "rule": m, "theta": th, "volume": vol, "pulse_regime_days": int(pure.sum()),
                             "lower_bound_holds": int(ok_lo.sum()), "upper_bound_holds": int(ok_up.sum()),
                             "days_x_ge_p": int(big.sum()), "sharp_upper_bound_holds": int(ok_sh.sum()),
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
    steps differ from the commanded pulses by one or two (a command packet lost: (A3) violated), the error of the
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
            half_e = rd["g_max_est"] / 2
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
def part_rules():
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
            rows.append({"case": case, "rule": m, "seasons": int(df["year"].nunique()), "days": int(len(df)),
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parts", default="quanta,t1,t2,t3,t4,rules,device")
    a = ap.parse_args()
    for part in a.parts.split(","):
        {"quanta": part_quanta, "t1": part_t1, "t2": part_t2, "t3": part_t3, "t4": part_t4, "rules": part_rules,
         "device": part_device}[part]()


if __name__ == "__main__":
    main()
