"""Derived inputs of the case (data section of the article) from the processed records:

- the delivery factor eta: median ratio of the discharge at the gauge upstream of the Dustlik node (pg_dustlik_Q)
  to the head discharge of the Kegeyli canal (kegeyli_Q) on steady days of the 2020 dispatcher sheets, a steady day
  being one whose head discharge and that of the previous calendar day are both recorded and positive and differ by
  at most 5% of the previous day's value;
- the monthly share of the Abad-Yarmish regulator in the node inflow, s_1,m = sum(abad_yarmysh_Q) / sum(pg_dustlik_Q)
  over the days with both records, for April-August 2020; the sheets end in August, so the September share is the
  April-August share;
- the balance of the Dustlik node, pg_dustlik_Q - below_dostlik_Q - abad_yarmysh_Q - kokshiel_Q, on the days with all
  four records (complete cases) and, separately, with a missing Kokshiel record counted as zero;
- the decadal demand at the node, D_j = eta * Q_plan,d * s_j,m * Delta_p, written at full precision to
  DATA/processed/demand_decadal.csv for the demand variants A (observed Abad-Yarmish share, the rest by irrigated
  area), B (all outlets by irrigated area) and C (all outlets by capacity), with eta = demand_eta_reference;
- the agreement of the daily head-gauge series with the official annual volumes (annual_volumes_2010_2019.csv);
- the checks of the daily records (vegetation seasons 2010-2019 unless stated otherwise): repeated head levels,
  the longest run of a constant head discharge, terminal digits, identical discharges in two seasons, the head
  balance of the Dustlik canal, level-discharge pairs and the level-discharge relation of the Kegeyli head, the
  2020 head discharges against this relation, and the blank head-discharge entries.

Usage: python scripts/derive_inputs.py [--write-demand]  ->  results/inputs/derived_inputs.json (and the demand file)
"""
import argparse
import calendar
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.passport import value  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402

PROC = ROOT / "DATA/processed"
OUT = ROOT / "results/inputs"
STEADY_CHANGE = 0.05


def days_in_decade(month, decade, year=2021):
    return 10 if decade < 3 else calendar.monthrange(year, month)[1] - 20


def delivery_factor(disp):
    q, q_prev, node = disp.kegeyli_Q, disp.kegeyli_Q.shift(1), disp.pg_dustlik_Q
    consecutive = disp.date.diff().dt.days.eq(1)
    steady = (consecutive & q.gt(0) & q_prev.gt(0) & node.notna()
              & ((q - q_prev).abs() <= STEADY_CHANGE * q_prev + 1e-9))
    ratio = (node / q)[steady]
    every = (node / q)[q.gt(0) & node.notna()]
    return {"rule": "head discharge of the day and of the previous day recorded and positive, change <= 5%",
            "n": int(steady.sum()), "median": float(ratio.median()),
            "quartiles": [float(ratio.quantile(0.25)), float(ratio.quantile(0.75))],
            "all_days": {"n": int(every.size), "median": float(every.median())},
            "steady_dates": disp.date[steady].dt.strftime("%Y-%m-%d").tolist()}


def abad_shares(disp):
    pair = disp.dropna(subset=["abad_yarmysh_Q", "pg_dustlik_Q"])
    month = pair.date.dt.month
    shares = {int(m): float(g.abad_yarmysh_Q.sum() / g.pg_dustlik_Q.sum()) for m, g in pair[month.between(4, 8)]
              .groupby(month[month.between(4, 8)])}
    season = pair[month.between(4, 8)]
    shares[9] = float(season.abad_yarmysh_Q.sum() / season.pg_dustlik_Q.sum())
    days = {int(m): int(n) for m, n in month[month.between(4, 8)].value_counts().sort_index().items()}
    return shares, days


def node_balance(disp):
    cols = ["pg_dustlik_Q", "below_dostlik_Q", "abad_yarmysh_Q"]
    complete = disp.dropna(subset=cols + ["kokshiel_Q"])
    res_c = complete.pg_dustlik_Q - complete.below_dostlik_Q - complete.abad_yarmysh_Q - complete.kokshiel_Q
    zero = disp.dropna(subset=cols)
    res_z = zero.pg_dustlik_Q - zero.below_dostlik_Q - zero.abad_yarmysh_Q - zero.kokshiel_Q.fillna(0.0)
    stats = lambda r: {"n": int(r.size), "mean": float(r.mean()), "max_abs": float(r.abs().max()),
                       "exact_closures": int((r.abs() < 1e-9).sum())}
    return {"complete_cases": stats(res_c), "kokshiel_missing_as_zero": stats(res_z)}


def demand_table(plan, s1, eta):
    area = np.asarray(value("irrigated_area_ha"), float)
    cap = np.asarray(value("outlet_capacity_m3s"), float)
    users = ["Абад-ярмиш", "Р-1", "Халкабад-2", "Қанли-яб", "К-2", "Кегейли-қуйи"]
    rows = []
    for var in "ABC":
        for _, r in plan.iterrows():
            m, d = int(r.month), int(r.decade)
            if var == "A":
                sh = np.r_[s1[m], (1.0 - s1[m]) * area[1:] / area[1:].sum()]
            elif var == "B":
                sh = area / area.sum()
            else:
                sh = cap / cap.sum()
            q = eta * float(r.plan_Q_m3s) * sh
            nd = days_in_decade(m, d)
            for j in range(6):
                rows.append(dict(variant=var, month=m, decade=d, days=nd, j=j + 1, user=users[j], share=sh[j],
                                 D_mln_m3=q[j] * nd * 86400 / 1e6, q_mean_m3s=q[j]))
    return pd.DataFrame(rows)


def annual_agreement(daily, annual):
    d = daily.assign(year=daily.date.dt.year)
    vol = d.groupby("year").kegeyli_Q.apply(lambda s: s.fillna(0.0).sum() * 86400 / 1e6)
    a = annual.set_index("year").kegeyli_mln_m3
    rel = (vol - a) / a
    return {int(y): {"daily_sum_mln_m3": float(vol[y]), "official_mln_m3": float(a[y]), "relative_difference": float(rel[y])}
            for y in a.index}


def _season(df):
    return df[df.date.dt.month.between(4, 9)]


def data_checks(daily, disp):
    """Checks of the daily operating records."""
    d = daily.sort_values("date").copy()
    consec = d.date.diff().dt.days.eq(1)
    for c in ("dostlik_H_cm", "kegeyli_H_cm", "kj_H_cm"):
        d[c + "_prev"] = d[c].shift(1).where(consec)
    s = _season(d)
    out = {}
    # head level of the Kegeyli head equal to that of the previous day (consecutive days with supply)
    m = s.kegeyli_H_cm.notna() & s.kegeyli_H_cm_prev.notna() & s.kegeyli_Q.fillna(0).gt(0)
    dh = (s.kegeyli_H_cm - s.kegeyli_H_cm_prev)[m]
    out["head_level_repeated"] = {"n": int(m.sum()), "share_equal": float((dh == 0).mean()),
                                  "share_1cm": float((dh.abs() == 1).mean())}
    # the three head levels at the Dustlik canal (Dustlik, Kegeyli, Kuanyshjarma) all unchanged on the same day
    cols = ["dostlik_H_cm", "kegeyli_H_cm", "kj_H_cm"]
    m = s[cols + [c + "_prev" for c in cols]].notna().all(axis=1)
    same = np.logical_and.reduce([s[c] == s[c + "_prev"] for c in cols])[m.to_numpy()]
    out["three_levels_repeated"] = {"n": int(m.sum()), "share": float(np.mean(same))}
    # longest run of a constant positive head discharge within a season
    best = {"days": 0}
    for _, g in s.groupby(s.date.dt.year):
        q, dates, run = g.kegeyli_Q.to_numpy(), g.date.to_numpy(), 1
        for i in range(1, len(q)):
            run = run + 1 if (q[i] > 0 and q[i] == q[i - 1]) else 1
            if run > best["days"]:
                best = {"days": run, "discharge_m3s": float(q[i]),
                        "from": str(pd.Timestamp(dates[i - run + 1]).date())}
    out["longest_constant_run"] = best
    # values ending in 0 or 5 (20% expected): discharges rounded to whole m3/s, levels in whole cm
    def ends(x):
        x = x.dropna(); x = x[x > 0]
        return {"n": int(x.size), "share": float((np.round(x).astype(int) % 5 == 0).mean())}
    sd = _season(disp)
    out["terminal_digits"] = {"kegeyli_Q": ends(s.kegeyli_Q), "dostlik_Q": ends(s.dostlik_Q),
                              "dostlik_Q_2020": ends(disp.dostlik_Q), "kegeyli_H_cm": ends(s.kegeyli_H_cm),
                              "kegeyli_H_cm_2020": ends(disp.kegeyli_H_cm), "season_2020_days": int(len(sd))}
    # identical positive daily head discharges on the same calendar day of two seasons
    piv = s.assign(md=s.date.dt.strftime("%m-%d")).pivot_table(index="md", columns=s.date.dt.year, values="kegeyli_Q")
    shares = []
    for a_, b_ in itertools.combinations(piv.columns, 2):
        both = piv[a_].notna() & piv[b_].notna() & piv[a_].gt(0)
        if both.any():
            shares.append(float((piv[a_][both] == piv[b_][both]).mean()))
    out["identical_seasons_max_share"] = max(shares)
    # head balance of the Dustlik canal: head - Kegeyli - Kuanyshjarma - Kokozek (Kokozek blank counted as zero)
    hb = (s.dostlik_Q - s.kegeyli_Q - s.kj_Q - s.kok_ozek_Q.fillna(0.0)).dropna()
    out["head_balance"] = {"n": int(hb.size), "median": float(hb.median()), "exact_zero": int((hb.abs() < 1e-9).sum())}
    # level-discharge relation of the Kegeyli head (all records 2010-2019), Q = a H^b with H in m
    allp = d.dropna(subset=["kegeyli_H_cm", "kegeyli_Q"]); allp = allp[allp.kegeyli_Q.gt(0) & allp.kegeyli_H_cm.gt(0)]
    x, y = np.log(allp.kegeyli_H_cm / 100.0), np.log(allp.kegeyli_Q)
    b_, la = np.polyfit(x, y, 1)
    r2 = 1.0 - float(((y - la - b_ * x) ** 2).sum() / ((y - y.mean()) ** 2).sum())
    out["head_relation"] = {"a": float(np.exp(la)), "b": float(b_), "r2_log": r2, "n": int(allp.size // allp.shape[1])}
    # level-discharge pairs (season days with supply; levels with at least 5 records)
    sp = s.dropna(subset=["kegeyli_H_cm", "kegeyli_Q"]); sp = sp[sp.kegeyli_Q.gt(0)]
    g = sp.groupby("kegeyli_H_cm").kegeyli_Q; n_ = g.size(); keep = n_[n_ >= 5].index
    out["level_discharge_pairs"] = {"levels": int(keep.size), "distinct_per_level_mean": float(g.nunique()[keep].mean()),
                                    "cv_mean": float((g.std() / g.mean())[keep].mean())}
    # 2020 head discharges against the 2010-2019 relation
    dd = disp.dropna(subset=["kegeyli_H_cm", "kegeyli_Q"]); dd = dd[dd.kegeyli_Q.gt(0)]
    ratio = dd.kegeyli_Q / (np.exp(la) * (dd.kegeyli_H_cm / 100.0) ** b_)
    out["head_2020_vs_relation"] = {"n": int(ratio.size), "median": float(ratio.median()),
                                    "quartiles": [float(ratio.quantile(0.25)), float(ratio.quantile(0.75))]}
    # blank head-discharge entries and what the upstream gauges leave for the Kegeyli canal
    bl = s[s.kegeyli_Q.isna()].copy()
    left = bl.dostlik_Q - bl.kj_Q.fillna(0.0) - bl.kok_ozek_Q.fillna(0.0)
    no_up = bl[left.isna()]
    blank_days = set(bl.date)

    def at_edge(t):                                      # blank run that reaches the start or the end of the season
        y0, y1 = pd.Timestamp(f"{t.year}-04-01"), pd.Timestamp(f"{t.year}-09-30")
        k = t
        while k >= y0 and k in blank_days:
            k -= pd.Timedelta(days=1)
        if k < y0:
            return True
        k = t
        while k <= y1 and k in blank_days:
            k += pd.Timedelta(days=1)
        return k > y1
    edge = [t for t in no_up.date if at_edge(t)]
    out["blank_entries"] = {"n": int(len(bl)), "share": float(len(bl) / len(s)),
                            "upstream_leaves_at_most_8": int((left <= 8.0).sum()), "no_upstream_record": int(len(no_up)),
                            "no_upstream_at_season_edge": len(edge),
                            "no_upstream_inside": [str(t.date()) for t in no_up.date if t not in set(edge)]}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-demand", action="store_true", help="write DATA/processed/demand_decadal.csv")
    a = ap.parse_args()
    load_config()
    disp = pd.read_csv(PROC / "dispatcher_2020_kegeyli.csv", parse_dates=["date"]).sort_values("date")
    plan = pd.read_csv(PROC / "plan_2021_kegeyli_decadal.csv")
    daily = pd.read_csv(PROC / "rashod_2010_2019_daily.csv", parse_dates=["date"])
    annual = pd.read_csv(PROC / "annual_volumes_2010_2019.csv")
    eta = delivery_factor(disp)
    s1, s1_days = abad_shares(disp)
    eta_ref = float(value("demand_eta_reference"))
    demand = demand_table(plan, s1, eta_ref)
    out = {"delivery_factor": eta, "eta_configuration": float(value("eta")), "demand_eta_reference": eta_ref,
           "abad_share_by_month": s1, "abad_share_days": s1_days, "dustlik_node_balance": node_balance(disp),
           "plan_volume_mln_m3": float(sum(r.plan_Q_m3s * days_in_decade(int(r.month), int(r.decade)) * 86400
                                           for _, r in plan.iterrows()) / 1e6),
           "node_demand_volume_mln_m3": {v: float(g.D_mln_m3.sum()) for v, g in demand.groupby("variant")},
           "annual_volume_agreement": annual_agreement(daily, annual),
           "data_checks": data_checks(daily, disp)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "derived_inputs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.write_demand:
        demand.to_csv(PROC / "demand_decadal.csv", index=False, float_format="%.17g")
    print(f"eta: median {eta['median']:.4f}, IQR {eta['quartiles'][0]:.3f}-{eta['quartiles'][1]:.3f}, n = {eta['n']}"
          f" (all days: {eta['all_days']['median']:.3f}, n = {eta['all_days']['n']}); configuration {out['eta_configuration']}")
    print("Abad-Yarmish share:", {m: round(v, 5) for m, v in s1.items()})
    print("Dustlik balance:", out["dustlik_node_balance"])
    print("node demand, 10^6 m3:", {v: round(x, 2) for v, x in out["node_demand_volume_mln_m3"].items()})
    print("annual agreement:", {y: f"{v['relative_difference']:+.4f}" for y, v in out["annual_volume_agreement"].items()})
    print("data checks:", json.dumps(out["data_checks"], indent=1))


if __name__ == "__main__":
    main()
