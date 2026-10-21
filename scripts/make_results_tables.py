"""Tables and in-text numbers of the Results section, computed from the result files (never typed by hand).

Reads:  results/experiment/normal/*.csv, results/hypotheses_summary_normal.csv, results/shapley_by_year_normal.csv,
        results/sensitivity_summary.csv, results/exploratory/*, results/exploratory_tests.csv,
        results/exploratory_summary.csv, and, when present, DATA/processed/demand_decadal.csv (closed operating
        records; without it, the demand-floor check and the demand of R-1 are not computed).
Writes: results/tables/results_tables.json (Table 7 of lambda by method, Table 6 of hypothesis decisions, Table S6 of
        all tests, Table 8 of exploratory tests, Tables S7a/S7b, and "numbers", every number quoted in the text),
        results/tables/supplementary_s7.md and results/tables/supplementary_s8.md.
Usage: python scripts/make_results_tables.py [ROOT]
"""
import glob
import itertools
import math
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
TABLES = os.path.join(ROOT, "results", "tables")
OUT = os.path.join(TABLES, "results_tables.json")
DEMAND = os.path.join(ROOT, "DATA/processed/demand_decadal.csv")      # closed operating records (optional)
METHODS = ["Oracle", "LXB", "B2", "B3", "B0", "B1"]
USERS = ["Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli"]
DROUGHT = [2011, 2018]


def load():
    fr = []
    for f in glob.glob(os.path.join(ROOT, "results/experiment/normal/*_20??_*_*.csv")):
        m, y, t, v = os.path.basename(f)[:-4].split("_")
        if m in METHODS + ["LXB-noS3"] and v in ("phys", "iot"):
            fr.append(pd.read_csv(f))
    d = pd.concat(fr, ignore_index=True)
    n = d.groupby(["method", "tuned", "iot"]).size()
    assert n.drop(("LXB-noS3", "tuned", "phys")).eq(1830).all() and len(n) == 25, n
    return d


def f3(x):
    return f"{x:.3f}"


def pct(x, nd=1):
    return f"{100 * x:.{nd}f}"


def minus(s):
    return s.replace("-", "−")


def sci(x):
    m, e = f"{x:.1e}".split("e")
    return f"{m} × 10{{^{int(e)}^}}".replace("{^-", "{^−")


def daily_price(d, m, tuned, early_excluded=False):
    t = d[(d.method == m) & (d.tuned == tuned)]
    x = pd.DataFrame({"p": t[t.iot == "phys"].set_index(["year", "date"])["lambda"],
                      "i": t[t.iot == "iot"].set_index(["year", "date"])["lambda"]})
    if early_excluded:
        md = pd.Series(x.index.get_level_values(1).str[5:], index=x.index)
        x = x[~md.between("04-01", "04-10")]
    ok = x.p > 0
    pi = ((x.p - x.i) / x.p)[ok]
    return x, pi


EXPL_TABLE_HEAD = ["Comparison", "Chain", "Estimate [95% CI]", "p (Holm)", "Sign", "Decision",
                   "Seasons as units: 95% CI; p (Holm)"]
EPS_LAMBDA = 0.01                                     # practical margin of the lambda comparisons (Section 2.9)
DEC = {"superior": "Superior", "non-inferior": "Non-inferior", "supported": "Supported", "rejected": "Rejected",
       "inconclusive": "Inconclusive", "not testable": "Not testable", "no data": "No data",
       "not available": "Not available"}


def exploratory(d, N):
    """Exploratory results: rows of B3V and LXB-DA for Table 7, Table 8 (exploratory tests), Tables S7a and S7b.
    Sources: results/exploratory/{b3_feedback,deadband_aware}/*.csv, results/exploratory_tests.csv
    (scripts/compare_exploratory.py), results/exploratory_summary.csv (scripts/summarize_exploratory.py).
    Returns None if the files are missing."""
    rd = os.path.join(ROOT, "results/exploratory")
    files = glob.glob(os.path.join(rd, "b3_feedback", "B3V_20??_*_*.csv")) + \
        glob.glob(os.path.join(rd, "deadband_aware", "LXB-DA_20??_*_*.csv"))
    tests_p = os.path.join(ROOT, "results/exploratory_tests.csv")
    summ_p = os.path.join(ROOT, "results/exploratory_summary.csv")
    if not files or not (os.path.exists(tests_p) and os.path.exists(summ_p)):
        return None
    r = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    n = r.groupby(["method", "tuned", "iot"]).size()
    assert n.eq(1830).all() and len(n) == 6, n
    g = r.groupby(["method", "tuned", "iot"])["lambda"].mean()
    gd = r[r.year.isin(DROUGHT)].groupby(["method", "tuned", "iot"])["lambda"].mean()
    base = d.groupby(["method", "tuned", "iot"])["lambda"].mean()
    rows = []
    p, q = g[("B3V", "tuned", "phys")], g[("B3V", "tuned", "iot")]
    rows.append(["B3V {^a^}", f3(p), f3(q), pct((p - q) / p), f3(g[("B3V", "untuned", "phys")]),
                 f3(g[("B3V", "untuned", "iot")]), f3(gd[("B3V", "tuned", "phys")]), f3(gd[("B3V", "tuned", "iot")])])
    lp = base[("LXB", "tuned", "phys")]; q = g[("LXB-DA", "tuned", "iot")]
    rows.append(["LXB-DA {^a,b^}", "—", f3(q), pct((lp - q) / lp), "—", f3(g[("LXB-DA", "untuned", "iot")]),
                 "—", f3(gd[("LXB-DA", "tuned", "iot")])])
    for m in ("B3V", "LXB-DA"):
        for t in ("tuned", "untuned"):
            for v in ("phys", "iot"):
                if (m, t, v) in g:
                    N[f"lam_{m}_{t}_{v}"] = g[(m, t, v)]
    N["price_ratio_B3V_tuned"] = (g[("B3V", "tuned", "phys")] - g[("B3V", "tuned", "iot")]) / g[("B3V", "tuned", "phys")]
    N["price_ratio_LXB-DA_tuned"] = (lp - g[("LXB-DA", "tuned", "iot")]) / lp
    lpu = base[("LXB", "untuned", "phys")]
    N["price_ratio_LXB-DA_untuned"] = (lpu - g[("LXB-DA", "untuned", "iot")]) / lpu
    for (m, t, v), x in r.groupby(["method", "tuned", "iot"])[["r_R-1", "h_min"]].mean().iterrows():
        N[f"r_R1_{m}_{t}_{v}"] = x["r_R-1"]; N[f"hmin_mean_{m}_{t}_{v}"] = x.h_min
    # Table 8: exploratory tests
    t = pd.read_csv(tests_p)
    circ_p = os.path.join(ROOT, "results/exploratory_tests_season_seasontest.csv")    # seasons as units
    circ = ({(c.hypothesis, c.comparison, c.variant): c for c in pd.read_csv(circ_p).itertuples()}
            if os.path.exists(circ_p) else {})
    dec = DEC
    t8 = [EXPL_TABLE_HEAD]
    for x in t.itertuples():
        if x.hypothesis == "E5":                       # strict tolerance check of H3, reported in Section S7
            N[f"h3strict_{x.comparison.split(':')[0].replace(' ', '_')}"] = [x.estimate, x.ci_low, x.ci_high, x.decision]
            continue
        if x.hypothesis == "E1" and x.comparison == "LXB − B3":    # identical to H1 (Table S6)
            continue
        comp = x.comparison.replace("Π1", "Π{~1~}").replace("LXB)", "LXB)")
        chain = x.variant.replace("/iot", "/IoT").replace(" (reverse)", ", reverse")
        p = "< 0.001" if x.p_holm < 0.001 else f"{x.p_holm:.3f}"
        tiny = max(abs(x.estimate), abs(x.ci_low), abs(x.ci_high)) < 5e-4
        nm = (lambda v: (("+" if v > 0 else "−") + sci(abs(v))) if 0 < abs(v) < 5e-5 else
              minus(f"{v:+.4f}") if abs(v) < 5e-4 else minus(f"{v:+.3f}")) if not tiny else \
            (lambda v: "0" if v == 0 else ("+" if v > 0 else "−") + sci(abs(v)))
        c = circ.get((x.hypothesis, x.comparison, x.variant))
        lab = dec.get(x.decision, x.decision)
        if x.decision == "superior" and not x.comparison.startswith("Π1") and abs(x.estimate) < EPS_LAMBDA:
            lab += " (below *ε*{~λ~})"
        if c is not None:
            ps = "< 0.001" if c.p_holm < 0.001 else f"{c.p_holm:.3f}"
            ci_c = f"[{nm(c.ci_low)}, {nm(c.ci_high)}]; {ps}"
            if c.decision != x.decision:
                ci_c += f" ({dec.get(c.decision, c.decision).lower()})"
        else:
            ci_c = "—"
        t8.append([comp, chain, f"{nm(x.estimate)} [{nm(x.ci_low)}, {nm(x.ci_high)}]", p,
                   f"{x.sign_share * 10:.0f}/10", lab, ci_c])
        if c is not None:
            N[f"expl_season_{x.hypothesis}_{x.variant.replace(' (reverse)', '').replace('/', '_')}_"
              f"{x.comparison.split(' − ')[-1].strip('()')}"] = [c.ci_low, c.ci_high, c.p_holm, c.decision]
            N[f"expl_circ_{x.hypothesis}_{x.variant.replace(' (reverse)', '').replace('/', '_')}_"
              f"{x.comparison.split(' − ')[-1].strip('()')}"] = [c.ci_low, c.ci_high]
        key = (f"expl_{x.hypothesis}_{x.comparison.split(' − ')[-1].strip('()')}_"
               f"{x.variant.replace(' (reverse)', '').replace('/', '_')}")
        N[key + "_est"] = x.estimate; N[key + "_lo"] = x.ci_low; N[key + "_hi"] = x.ci_high
    rev_i = [i for i, r in enumerate(t8) if r[0].startswith("B3V − LXB")]
    if rev_i:                                         # the reverse comparison follows LXB − B3V (tuned/IoT)
        row = t8.pop(rev_i[0])
        at = next(i for i, r in enumerate(t8) if r[0] == "LXB − B3V" and r[1] == "tuned/IoT") + 1
        t8.insert(at, row)
    # Table S7a: robustness
    sm = pd.read_csv(summ_p)
    v = lambda item, case, metric, method=None: float(sm[(sm.item == item) & (sm.case == case) & (sm.metric == metric)
                                                       & ((sm.method == method) if method else True)].value.iloc[0])
    tS7 = [["Case", "Runs", "*λ*{~LXB~} IoT", "Π{~1~} LXB, %", "LXB − B0 (IoT)", "LXB − B3 (IoT)"]]
    tS7.append(["Baseline seed", "LXB, B0, B3; IoT", f3(v("seeds", "base", "LXB")), pct(v("seeds", "base", "price")),
                minus(f"{v('seeds', 'base', 'dB0'):+.3f}"), minus(f"{v('seeds', 'base', 'dB3'):+.3f}")])
    for k in (1, 2, 3):
        c = f"seed_{k}"
        tS7.append([f"Independent seed {k}", "LXB, B0, B3; IoT", f3(v("seeds", c, "LXB")), pct(v("seeds", c, "price")),
                    minus(f"{v('seeds', c, 'dB0'):+.3f}"), minus(f"{v('seeds', c, 'dB3'):+.3f}")])
        N[f"seed{k}_price"] = v("seeds", c, "price")
    tS7.append(["Leave-one-year-out limit forecast", "LXB; phys, IoT", f3(v("forecast_loo", "forecast_loo", "lam_iot")),
                pct(v("forecast_loo", "forecast_loo", "price_ratio")), "—", "—"])
    bl = {m: (v("blank_carry", "blank_carry", "lam_phys", m), v("blank_carry", "blank_carry", "lam_iot", m)) for m in ("LXB", "B0", "B3")}
    tS7.append(["Blank supply days filled with the last recorded value", "LXB, B0, B3; phys, IoT", f3(bl["LXB"][1]),
                pct(v("blank_carry", "blank_carry", "price_ratio", "LXB")), minus(f"{bl['LXB'][1] - bl['B0'][1]:+.3f}"),
                minus(f"{bl['LXB'][1] - bl['B3'][1]:+.3f}")])
    N["loo_price"] = v("forecast_loo", "forecast_loo", "price_ratio"); N["blank_price"] = v("blank_carry", "blank_carry", "price_ratio", "LXB")
    N["blank_dB0"] = bl["LXB"][1] - bl["B0"][1]; N["blank_dB3"] = bl["LXB"][1] - bl["B3"][1]
    N["blank_price_B0"] = v("blank_carry", "blank_carry", "price_ratio", "B0"); N["blank_price_B3"] = v("blank_carry", "blank_carry", "price_ratio", "B3")
    for name in ("block 5", "block 20", "circular bootstrap", "season bootstrap", "calendar bootstrap",
                 "season sign-flip test"):
        sel = sm[(sm.item == "bootstrap") & (sm.case == name)]
        if len(sel):
            N[name.replace(" ", "_").replace("-", "_") + "_changed"] = int(sel.value.iloc[0])
    for item, case in (("final_share", "final_share"), ("b3v_deadband", "b3v_deadband"), ("dt_450", "dt_450")):
        for r_ in sm[sm.item == item].itertuples():
            N[f"x_{case}_{r_.method}_{r_.tuned}_{r_.chain.replace('→', 'to')}_{r_.metric}"] = float(r_.value)
    rv = {(r.method, r.chain): r.value for r in sm[(sm.item == "untuned_reverse")].itertuples()}
    for (m, c), x in rv.items():
        N[f"reverse_lam_{m}_{c}"] = float(x)
    tR = [["Method", "*R*{~vol~} phys", "*R*{~vol~} IoT", "Loss, %", "*λ* phys", "*λ* IoT", "Π{~1~}, %"]]
    for m in ("Oracle", "LXB", "B2", "B3", "B0", "B1", "B3V", "LXB-DA"):
        a, b = v("volume", "normal", "R_vol_phys", m), v("volume", "normal", "R_vol_iot", m)
        N[f"Rvol_{m}_phys"] = a; N[f"Rvol_{m}_iot"] = b; N[f"Rvol_{m}_loss"] = (a - b) / a
        lp_ = N["lam_LXB_tuned_phys"] if m == "LXB-DA" else N[f"lam_{m}_tuned_phys"]
        tR.append([m, f"{a:.3f}", f"{b:.3f}", minus(f"{(a - b) / a * 100:.2f}"), f3(lp_),
                   f3(N[f'lam_{m}_tuned_iot']), pct(N[f'price_ratio_{m}_tuned'])])
    return rows, t8, tS7, tR


def demand_floor(d, N):
    """Worst-user satisfaction without the user-days whose daily demand is below the volume that the smallest
    executable opening (the deadband, in whole actuator steps) passes in one control step at the mean daily node level.
    Such demands cannot be met exactly by a gate that moves only in executable steps."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from water01.domain.passport import value
    from water01.hydraulics.node import DustlikNode
    from water01.simulation.scenarios import load_config
    load_config()
    node = DustlikNode()
    res, db = value("gate_resolution_fraction"), value("gate_deadband_fraction")
    a_min = np.ceil(db / res - 1e-9) * res * np.asarray(node.max_opening, float)   # smallest opening executed from closed
    dt = 86400.0 / value("steps_per_day")
    if not os.path.exists(DEMAND):
        print("demand_decadal.csv not found: the demand-floor check is skipped")
        lx = d[(d.method == "LXB") & (d.tuned == "tuned") & (d.iot == "phys")]
        N["shortage_days_LXB_phys"] = int((lx["lambda"] < 0.999).sum())
        N["shortage_share_LXB_phys"] = float((lx["lambda"] < 0.999).mean())
        return
    dem = pd.read_csv(DEMAND)
    dem = dem[dem.variant == "A"].set_index(["j", "month", "decade"]).q_mean_m3s
    t = d[(d.tuned == "tuned") & d.method.isin(["LXB", "B0", "B3", "B2", "Oracle", "B1"])].copy()
    dt_ = pd.to_datetime(t.date)
    dec = np.where(dt_.dt.day <= 10, 1, np.where(dt_.dt.day <= 20, 2, 3))
    level = ((t.h_min + t.h_max) / 2).round(2).to_numpy()
    floors = {h: node.offtakes(h, a_min[:5]) * dt for h in np.unique(level)}
    ok = np.ones((len(t), len(USERS)), bool)
    for j, u in enumerate(USERS[:5]):
        D = np.array([dem.loc[(j + 1, mo, de)] for mo, de in zip(dt_.dt.month, dec)]) * 86400.0
        ok[:, j] = D >= np.array([floors[h][j] for h in level])
    r = t[[f"r_{u}" for u in USERS]].to_numpy()
    t["lam_floor"] = np.where(ok, r, np.inf).min(axis=1)
    t.loc[np.isinf(t.lam_floor), "lam_floor"] = np.nan
    N["floor_excluded_pairs_share"] = float(1 - ok[:, :5].mean())
    g = t.groupby(["method", "iot"]).lam_floor.mean()
    for m in ("LXB", "B0", "B3", "B2", "Oracle", "B1"):
        N[f"floor_lam_{m}_phys"] = float(g[(m, "phys")]); N[f"floor_lam_{m}_iot"] = float(g[(m, "iot")])
        N[f"floor_price_{m}"] = float((g[(m, "phys")] - g[(m, "iot")]) / g[(m, "phys")])
    lx = t[(t.method == "LXB") & (t.iot == "phys")]
    N["shortage_days_LXB_phys"] = int((lx["lambda"] < 0.999).sum())
    N["shortage_share_LXB_phys"] = float((lx["lambda"] < 0.999).mean())


TINY = 0.01                                            # lambda_phys below which a day is a residual of a blank entry


def robust(N):
    """Price and Shapley values of LXB (tuned) without the days with 0 < lambda_phys < TINY, on which the pool delivers
    only a residual after a blank supply entry and any IoT deviation gives a daily price of 100%."""
    codes = ["".join(c) for r in range(1, 5) for c in itertools.combinations("SQCE", r)]
    rd = os.path.join(ROOT, "results/experiment/normal")
    rows, tiny, pis = [], 0, []
    for y in range(2010, 2020):
        ph = pd.read_csv(os.path.join(rd, f"LXB_{y}_tuned_phys.csv"))["lambda"].to_numpy()
        ok = ph >= TINY
        tiny += int(((ph > 0) & ~ok).sum())
        v = {frozenset(): 0.0}
        for c in codes:
            it = pd.read_csv(os.path.join(rd, f"LXB_{y}_tuned_{'iot' if c == 'SQCE' else c}.csv"))["lambda"].to_numpy()
            pr = (ph[ok] - it[ok]) / ph[ok]
            v[frozenset(c)] = float(pr.mean())
            if c == "SQCE":
                pis.append(pr)
        phi = {}
        for k in "SQCE":
            rest = [q for q in "SQCE" if q != k]
            phi[k] = sum(math.factorial(r) * math.factorial(3 - r) / 24 * (v[frozenset(c + (k,))] - v[frozenset(c)])
                         for r in range(4) for c in itertools.combinations(rest, r))
        rows.append(phi)
    t = pd.DataFrame(rows)
    N["tiny_days"] = tiny
    N["pi_mean_excl_tiny"] = float(np.concatenate(pis).mean())
    for k, name in zip("SQCE", ("sensor", "quantisation", "communication", "energy")):
        N[f"phi_{name}_excl_tiny"] = float(t[k].mean())
        N[f"phi_{name}_excl_tiny_absmax_year"] = float(t[k].abs().max())


CODES = ["".join(c) for r in range(1, 5) for c in itertools.combinations("SQCE", r)]
FACTORS = dict(zip("SQCE", ("sensor", "quantisation", "communication", "energy")))


def shapley(v):
    """Shapley values of the four factors from the values v[frozenset(code)] of the 16 coalitions."""
    phi = {}
    for k in "SQCE":
        rest = [q for q in "SQCE" if q != k]
        phi[k] = sum(math.factorial(r) * math.factorial(3 - r) / 24 * (v[frozenset(c + (k,))] - v[frozenset(c)])
                     for r in range(4) for c in itertools.combinations(rest, r))
    return phi


def attribution(N, day=None):
    """Shapley attribution of the ratio-of-means price of LXB (tuned) over all seasons and per season, and the
    coalition prices of one day: by default the day whose daily price of the sensor-only coalition has the largest
    magnitude, with its share of the summed magnitudes of that season (concentration of the mean-daily value)."""
    rd = os.path.join(ROOT, "results/experiment/normal")
    lam = {c: [] for c in ["phys"] + CODES}
    for y in range(2010, 2020):
        for c in lam:
            f = pd.read_csv(os.path.join(rd, f"LXB_{y}_tuned_{'iot' if c == 'SQCE' else c}.csv"))
            lam[c].append(f.set_index("date")["lambda"])
    rows = []
    for label, sel in [("all", slice(None))] + [(str(y), slice(i, i + 1)) for i, y in enumerate(range(2010, 2020))]:
        ph = pd.concat(lam["phys"][sel])
        v = {frozenset(): 0.0}
        for c in CODES:
            v[frozenset(c)] = float((ph.mean() - pd.concat(lam[c][sel]).mean()) / ph.mean())
        phi = shapley(v)
        rows.append(dict(season=label, price=v[frozenset("SQCE")], **{f"phi_{FACTORS[k]}": phi[k] for k in "SQCE"}))
    t = pd.DataFrame(rows)
    allr = t.iloc[0]
    for k in FACTORS.values():
        N[f"phi_ratio_{k}"] = float(allr[f"phi_{k}"])
    N["phi_ratio_price"] = float(allr.price)
    N["phi_ratio_seasonal_sum_mean"] = float(t.iloc[1:].price.mean())
    if day is None:
        best = (0.0, None, 0.0)
        for i_, ph_ in enumerate(lam["phys"]):
            ok = ph_ > 0
            pr = ((ph_[ok] - lam["S"][i_].reindex(ph_.index)[ok]) / ph_[ok]).abs()
            if len(pr) and pr.max() > best[0]:
                best = (float(pr.max()), str(pr.idxmax()), float(pr.max() / pr.sum()) if pr.sum() > 0 else 0.0)
        day = best[1] or str(lam["phys"][0].index[0])
        N["day_coalitions_share"] = best[2]
    y = int(day[:4]); i = y - 2010
    ph = float(lam["phys"][i].loc[day])
    coal = [dict(coalition="phys", lam=ph, price=0.0)]
    for c in CODES:
        li = float(lam[c][i].loc[day])
        coal.append(dict(coalition="IoT (SQCE)" if c == "SQCE" else c, lam=li, price=(ph - li) / ph if ph > 0 else np.nan))
    tc = pd.DataFrame(coal)
    N["day_coalitions_date"] = day
    N["day_coalitions_lam_phys"] = ph
    for r in tc.itertuples():
        N[f"day_coalition_{r.coalition.split()[0] if r.coalition != 'IoT (SQCE)' else 'SQCE'}_price"] = float(r.price)
    t.to_csv(os.path.join(TABLES, "shapley_ratio_of_means.csv"), index=False)
    tc.to_csv(os.path.join(TABLES, f"coalitions_{day}.csv"), index=False)
    return t, tc


def link_counters(N):
    """Command packets attempted, refused by the window budget, transmitted and lost (LXB, tuned, IoT chain).
    Needs the counters "blocked" and "lost" of the result files."""
    rd = os.path.join(ROOT, "results/experiment/normal")
    fr = [pd.read_csv(os.path.join(rd, f"LXB_{y}_tuned_iot.csv")).iloc[0] for y in range(2010, 2020)]
    t = pd.DataFrame(fr)
    if "blocked" not in t.columns or "lost" not in t.columns:
        return
    sent, blocked, lost = (float(t[c].sum()) for c in ("messages", "blocked", "lost"))
    N["link_attempted_LXB"] = sent + blocked; N["link_transmitted_LXB"] = sent
    N["link_blocked_share_LXB"] = blocked / (sent + blocked) if sent + blocked > 0 else np.nan
    N["link_lost_share_LXB"] = lost / sent if sent > 0 else np.nan
    N["link_failed_share_LXB"] = (blocked + lost) / (sent + blocked) if sent + blocked > 0 else np.nan


def overdelivery(N):
    """Delivered volume relative to the demand without the cap of r at 1 (tuned, IoT chain): LXB, B3V and LXB-DA.
    Needs the demand file of the closed operating records."""
    if not os.path.exists(DEMAND):
        print("demand_decadal.csv not found: the overdelivery check is skipped")
        return None
    dem = pd.read_csv(DEMAND)
    dem = dem[dem.variant == "A"].set_index(["j", "month", "decade"]).q_mean_m3s
    src = {"LXB": "results/experiment/normal", "B3V": "results/exploratory/b3_feedback",
           "LXB-DA": "results/exploratory/deadband_aware"}
    rows = []
    for m, folder in src.items():
        fs = [os.path.join(ROOT, folder, f"{m}_{y}_tuned_iot.csv") for y in range(2010, 2020)]
        if not all(os.path.exists(f) for f in fs):
            continue
        t = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
        dt_ = pd.to_datetime(t.date)
        dec = np.where(dt_.dt.day <= 10, 1, np.where(dt_.dt.day <= 20, 2, 3))
        for j, u in enumerate(USERS[:5]):
            D = np.array([dem.loc[(j + 1, mo, de)] for mo, de in zip(dt_.dt.month, dec)]) * 86400.0
            V = t[f"V_{u}"].to_numpy()
            ok = D > 0
            ratio = V[ok] / D[ok]
            early = ((dt_.dt.month == 4) & (dec == 1)).to_numpy()[ok]
            rows.append(dict(method=m, user=u, days=int(ok.sum()), demand_m3_day_early=float(D[ok][early].mean()),
                             delivered_m3_day_early=float(V[ok][early].mean()),
                             ratio_mean_early=float(ratio[early].mean()), ratio_max_early=float(ratio[early].max()),
                             ratio_min_early=float(ratio[early].min()), ratio_mean=float(ratio.mean()),
                             early_days_delivered=int((V[ok][early] > 0).sum()),
                             delivered_m3_day_early_pos=float(V[ok][early][V[ok][early] > 0].mean())
                             if (V[ok][early] > 0).any() else np.nan,
                             delivered_m3_day_early_pos_min=float(V[ok][early][V[ok][early] > 0].min())
                             if (V[ok][early] > 0).any() else np.nan,
                             delivered_m3_day_early_max=float(V[ok][early].max()),
                             days_above_1p05=int((ratio > 1.05).sum()),
                             excess_share=float(np.maximum(V[ok] - D[ok], 0).sum() / D[ok].sum())))
    t = pd.DataFrame(rows)
    if t.empty:
        return None
    for r in t.itertuples():
        if r.user == "R-1":
            for k in ("demand_m3_day_early", "delivered_m3_day_early", "ratio_mean_early", "ratio_max_early",
                      "ratio_min_early", "excess_share", "days_above_1p05", "early_days_delivered",
                      "delivered_m3_day_early_pos", "delivered_m3_day_early_pos_min", "delivered_m3_day_early_max"):
                N[f"over_{r.method}_R1_{k}"] = float(getattr(r, k))
    t[t.user == "R-1"].to_csv(os.path.join(TABLES, "overdelivery_R1.csv"), index=False)   # R-1 only (Section 3)
    return t


def demand_floor_common(d, N):
    """Demand-floor check with one mask for all methods and chains: the floor of each user-day is computed at the
    normal node level H_norm, so that every method is evaluated on the same user-days."""
    if not os.path.exists(DEMAND):
        return
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from water01.domain.passport import value
    from water01.hydraulics.node import DustlikNode
    from water01.simulation.scenarios import load_config
    load_config()
    node = DustlikNode()
    res, db = value("gate_resolution_fraction"), value("gate_deadband_fraction")
    a_min = np.ceil(db / res - 1e-9) * res * np.asarray(node.max_opening, float)
    floor = node.offtakes(value("h_init_m"), a_min[:5]) * 86400.0 / value("steps_per_day")
    dem = pd.read_csv(DEMAND)
    dem = dem[dem.variant == "A"].set_index(["j", "month", "decade"]).q_mean_m3s
    t = d[(d.tuned == "tuned") & d.method.isin(["LXB", "B0", "B3", "B2", "Oracle", "B1"])].copy()
    dt_ = pd.to_datetime(t.date)
    dec = np.where(dt_.dt.day <= 10, 1, np.where(dt_.dt.day <= 20, 2, 3))
    ok = np.ones((len(t), len(USERS)), bool)
    for j in range(5):
        D = np.array([dem.loc[(j + 1, mo, de)] for mo, de in zip(dt_.dt.month, dec)]) * 86400.0
        ok[:, j] = D >= floor[j]
    r = t[[f"r_{u}" for u in USERS]].to_numpy()
    t["lam_floor"] = np.where(ok, r, np.inf).min(axis=1)
    lx = (t.method == "LXB") & (t.iot == "phys")
    N["floorc_excluded_user_days"] = int((~ok[lx.to_numpy(), :5]).sum())
    N["floorc_excluded_pairs_share"] = float(1 - ok[lx.to_numpy(), :5].mean())
    g = t.groupby(["method", "iot"]).lam_floor.mean()
    for m in ("LXB", "B0", "B3", "B2", "Oracle", "B1"):
        N[f"floorc_lam_{m}_phys"] = float(g[(m, "phys")]); N[f"floorc_lam_{m}_iot"] = float(g[(m, "iot")])
        N[f"floorc_price_{m}"] = float((g[(m, "phys")] - g[(m, "iot")]) / g[(m, "phys")])


def changed_text(N):
    """Names the decisions that differ from the pre-specified 10-day moving block in any bootstrap variant."""
    base = pd.read_csv(os.path.join(ROOT, "results/hypotheses_summary_normal.csv"))
    key = ["hypothesis", "comparison", "variant", "role"]
    out = []
    for label, f in (("5-day blocks", "hypotheses_summary_block_5.csv"), ("20-day blocks", "hypotheses_summary_block_20.csv"),
                     ("circular blocks", "hypotheses_summary_normal_circular.csv"),
                     ("the season bootstrap", "hypotheses_summary_normal_season.csv"),
                     ("the calendar bootstrap", "hypotheses_summary_normal_calendar.csv")):
        path = os.path.join(ROOT, "results", f)
        if not os.path.exists(path):
            continue
        m = pd.read_csv(path).merge(base, on=key, suffixes=("", "_0"))
        for r in m[m.decision != m.decision_0].itertuples():
            out.append(f"with {label}, {r.hypothesis} ({r.variant.replace(': phys → iot', '').replace('/iot', '/IoT')}) "
                       f"became {r.decision} instead of {r.decision_0}")
    return "" if not out else " (" + "; ".join(out) + ")"


def write_s8(tS7, tR, N):
    """Supplementary S8 (Tables S7a-S7e), appended after S7 by build_appendix_supp.py."""
    md = lambda c: c.replace("{^", "^").replace("^}", "^").replace("{~", "~").replace("~}", "~")
    tab = lambda t: ["| " + " | ".join(md(c) for c in t[0]) + " |", "|" + "---|" * len(t[0])] + \
        ["| " + " | ".join(md(c) for c in r) + " |" for r in t[1:]]
    pr = [N[f"seed{k}_price"] for k in (1, 2, 3)] + [N["price_ratio_LXB_tuned"]]
    keys = ("block_5_changed", "block_20_changed", "circular_bootstrap_changed", "season_bootstrap_changed",
            "calendar_bootstrap_changed")
    ch = [N.get(k, 0) for k in keys]
    st = N.get("seasontest_changed", 0)
    st_txt = "; ".join(x.replace("->", "→").replace("/iot", "/IoT").replace("_", " ").replace("gap LXB", "gap~LXB~").replace("gap B2", "gap~B2~").replace("gap B3", "gap~B3~").replace("gap B0", "gap~B0~").replace("gap B1", "gap~B1~")
                       for x in N.get("seasontest_changed_list", []))
    lines = ["## S8. Exploratory Controllers, Added Cases, and Robustness Runs", "",
             "The runs of this section were not pre-specified and are reported as exploratory (Section 2.10). The "
             "comparisons with B3V, LXB-DA, LXB-F, and B3V-DA, those with the 7.5 min step, and those under the reverse "
             "gate mismatch are given in Table 8 and Section 3.4. Table S7a repeats the IoT chain with "
             "three further random seeds (sensor noise and packet loss), replaces the limit forecast by a "
             "leave-one-year-out mean, and fills the blank supply entries with the last recorded value of the same season; "
             "all use tuned gate coefficients. Across the four seeds, the price of LXB ranged from "
             f"{min(pr) * 100:.2f}% to {max(pr) * 100:.2f}%. The decisions of the pre-specified daily analysis were recomputed with bootstrap "
             "blocks of 5 and 20 days, with circular blocks, with a bootstrap over whole seasons, and with moving blocks "
             "on the full season calendar; "
             + (f"none of the {N['tests_n']} decisions changed under any of these settings" if not any(ch) else
                ", ".join(str(c) for c in ch) + f" of the {N['tests_n']} decisions changed, respectively"
                f"{changed_text(N)}")
             + (f". The season-level analysis of Table 6 differs from the daily analysis in {st} decisions ({st_txt})" if st else
                ". The season-level analysis of Table 6 gives the same decisions as the daily analysis")
             + ". Table S7b gives the volume-weighted satisfaction *R*~vol~ of Section 2.7, Table S7c the sensitivity "
             "cases added after the main runs, Table S7d the execution variants, and Table S7e the attribution of the "
             "price as a ratio of means and the coalition prices of the day with the largest daily price of the sensor-only "
             "constraint set.", "",
             "<!-- widths: 30,20,12,12,13,13 -->", "",
             "**Table S7a.** Robustness of the IoT price and of the advantage of LXB (tuned gate coefficients, ten seasons). "
             "Π~1~ as a ratio of means; for the blank-supply case, the phys reference is the phys run of the same case.", ""]
    lines += tab(tS7)
    lines += ["", "<!-- widths: 16,14,14,12,12,12,12 -->", "",
              "**Table S7b.** Volume-weighted satisfaction *R*~vol~ = Σ min(*V*, *D*)/Σ *D* and worst-user satisfaction "
              "*λ* (tuned gate coefficients, 1830 days). Loss: relative change of *R*~vol~ from phys to IoT. For "
              "LXB-DA, the phys reference is LXB, with which it coincides under ideal execution.", ""]
    lines += tab(tR)
    # S7c: added sensitivity cases
    cases = [("eta_fixed_demand_low", "*η* = 0.75, demand at the node fixed"),
             ("eta_true_low", "Plant *η* = 0.75, controller 0.82"),
             ("rating_outlets", "Regulator ratings 1.05/0.90/1.10/0.95/1.05"),
             ("tailwater_high", "Tail water of the regulators +0.3 m"),
             ("sensor_bias_pos", "Sensor offset +0.025 m"), ("sensor_bias_neg", "Sensor offset −0.025 m")]
    t = [["Case", "*λ* LXB phys", "*λ* LXB IoT", "Π~1~ LXB, %", "*λ* B0 IoT", "*λ* B3 IoT"]]
    t.append(["Baseline", f3(N["lam_LXB_tuned_phys"]), f3(N["lam_LXB_tuned_iot"]), pct(N["price_ratio_LXB_tuned"]),
              f3(N["lam_B0_tuned_iot"]), f3(N["lam_B3_tuned_iot"])])
    for c, lab in cases:
        if f"sens_{c}_lam_iot" not in N:
            continue
        t.append([lab, f3(N[f"sens_{c}_lam_phys"]), f3(N[f"sens_{c}_lam_iot"]), pct(N[f"sens_{c}_pi1_ratio"]),
                  f3(N[f"sens_{c}_B0_lam_iot"]), f3(N[f"sens_{c}_B3_lam_iot"])])
    lines += ["", "<!-- widths: 34,13,13,13,13,14 -->", "",
              "**Table S7c.** Sensitivity cases added after the main runs (tuned gate coefficients, ten seasons; "
              "descriptive). For the sensor offsets, the phys reference is the baseline run.", ""]
    lines += ["| " + " | ".join(md(c) for c in t[0]) + " |", "|" + "---|" * len(t[0])] + \
        ["| " + " | ".join(md(c) for c in r) + " |" for r in t[1:]]
    # S7d: execution variants
    x = lambda k: N.get(k, float("nan"))
    t = [["Controller and step", "Coefficients", "*λ* phys", "*λ* IoT", "Π~1~, %", "*r* R-1 IoT"]]
    for lab, tn, ph, io, prk, rr in (
            ("LXB, 15 min", "tuned", N["lam_LXB_tuned_phys"], N["lam_LXB_tuned_iot"], N["price_ratio_LXB_tuned"],
             N["r_LXB_iot_R-1"]),
            ("LXB-F, 15 min", "tuned", x("x_final_share_LXB-F_tuned_phys_lam"), x("x_final_share_LXB-F_tuned_iot_lam"),
             x("x_final_share_LXB-F_tuned_phystoiot_price_ratio"), x("x_final_share_LXB-F_tuned_iot_r_R1")),
            ("LXB, 15 min", "untuned", N["lam_LXB_untuned_phys"], N["lam_LXB_untuned_iot"],
             (N["lam_LXB_untuned_phys"] - N["lam_LXB_untuned_iot"]) / N["lam_LXB_untuned_phys"],
             N["r_R1_LXB_untuned_iot"]),
            ("LXB-F, 15 min", "untuned", x("x_final_share_LXB-F_untuned_phys_lam"),
             x("x_final_share_LXB-F_untuned_iot_lam"), x("x_final_share_LXB-F_untuned_phystoiot_price_ratio"),
             x("x_final_share_LXB-F_untuned_iot_r_R1")),
            ("B3V-DA, 15 min", "tuned", float("nan"), x("x_b3v_deadband_B3V-DA_tuned_iot_lam_iot"), float("nan"),
             x("x_b3v_deadband_B3V-DA_tuned_iot_r_R1")),
            ("B3V-DA, 15 min", "untuned", float("nan"), x("x_b3v_deadband_B3V-DA_untuned_iot_lam_iot"), float("nan"),
             x("x_b3v_deadband_B3V-DA_untuned_iot_r_R1")),
            ("LXB, 7.5 min", "tuned", x("x_dt_450_LXB_tuned_phys_lam"), x("x_dt_450_LXB_tuned_iot_lam"),
             x("x_dt_450_LXB_tuned_phystoiot_price_ratio"), x("x_dt_450_LXB_tuned_iot_r_R1")),
            ("B3, 7.5 min", "tuned", x("x_dt_450_B3_tuned_phys_lam"), x("x_dt_450_B3_tuned_iot_lam"),
             x("x_dt_450_B3_tuned_phystoiot_price_ratio"), x("x_dt_450_B3_tuned_iot_r_R1")),
            ("LXB-DA, 7.5 min {^a^}", "tuned", float("nan"), x("x_dt_450_LXB-DA_tuned_iot_lam"),
             x("x_dt_450_LXB-DA_tuned_phystoiot_price_ratio"), x("x_dt_450_LXB-DA_tuned_iot_r_R1"))):
        fm = lambda v: "—" if v != v else f3(v)
        t.append([lab, tn, fm(ph), fm(io), "—" if prk != prk else pct(prk, 2 if abs(prk) < 0.01 else 1), fm(rr)])
    lines += ["", "<!-- widths: 26,15,14,14,14,17 -->", "",
              "**Table S7d.** Execution variants (ten seasons). LXB-F: final-share execution program; B3V-DA: B3V with "
              "the pulse rule; 7.5 min: control, command, and plant step of 7.5 min. ^a^ Price against the phys run of "
              "LXB with the same step.", ""]
    lines += ["| " + " | ".join(md(c) for c in t[0]) + " |", "|" + "---|" * len(t[0])] + \
        ["| " + " | ".join(md(c) for c in r) + " |" for r in t[1:]]
    # S7e: attribution
    sh = pd.read_csv(os.path.join(TABLES, "shapley_ratio_of_means.csv"))
    t = [["Season", "Π~1~ (ratio of means), %", "*φ*~S~, pp", "*φ*~Q~, pp", "*φ*~C~, pp", "*φ*~E~, pp"]]
    for r in sh.itertuples():
        t.append(["2010–2019" if r.season == "all" else str(r.season), f"{100 * r.price:.2f}",
                  minus(f"{100 * r.phi_sensor:+.3f}"), minus(f"{100 * r.phi_quantisation:+.2f}"),
                  minus(f"{100 * r.phi_communication:+.3f}"), f"{100 * r.phi_energy:.0f}"])
    lines += ["", "<!-- widths: 16,20,16,16,16,16 -->", "",
              "**Table S7e.** Shapley attribution of the price of LXB as a ratio of means (tuned gate coefficients; "
              "descriptive). The pre-specified attribution of the mean daily price (H7b) is given in Table S6.", ""]
    lines += ["| " + " | ".join(md(c) for c in t[0]) + " |", "|" + "---|" * len(t[0])] + \
        ["| " + " | ".join(md(c) for c in r) + " |" for r in t[1:]]
    day = N["day_coalitions_date"]
    co = pd.read_csv(os.path.join(TABLES, f"coalitions_{day}.csv"))
    cells = "; ".join(f"{r.coalition.replace('IoT (SQCE)', 'SQCE')} {minus(f'{100 * r.price:.2f}')}%"
                      for r in co.itertuples() if r.coalition != "phys")
    share = N.get("day_coalitions_share", np.nan)
    ts = pd.Timestamp(day); date_txt = f"{ts.day} {ts.strftime('%B %Y')}"
    lines += ["", f"The largest daily price of the sensor-only constraint set occurred on {date_txt} "
              f"(*λ*^phys^ = {md(sci(N['day_coalitions_lam_phys'])) if N['day_coalitions_lam_phys'] < 0.01 else format(N['day_coalitions_lam_phys'], '.3f')}); this day carries "
              f"{100 * share:.0f}% of the summed magnitudes of the daily sensor prices of {day[:4]}. "
              + f"The daily prices of the 15 constraint sets on that day were: {cells}."
              + (" Each value is the relative change of a satisfaction close to zero, so this single day dominates "
                 f"the mean-daily *φ*~S~ of {day[:4]}." if share > 0.5 and N["day_coalitions_lam_phys"] < 0.01 else "")]
    open(os.path.join(TABLES, "supplementary_s8.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    d = load()
    N = {}
    # --- Table 7: lambda by method and chain
    g = d.groupby(["method", "tuned", "iot"])["lambda"].mean()
    gd = d[d.year.isin(DROUGHT)].groupby(["method", "tuned", "iot"])["lambda"].mean()
    t6 = [["Method", "Tuned phys", "Tuned IoT", "Π{~1~}, %", "Untuned phys", "Untuned IoT",
           "2011 + 2018 phys", "2011 + 2018 IoT"]]
    for m in METHODS:
        p, q = g[(m, "tuned", "phys")], g[(m, "tuned", "iot")]
        t6.append([m, f3(p), f3(q), pct((p - q) / p), f3(g[(m, "untuned", "phys")]), f3(g[(m, "untuned", "iot")]),
                   f3(gd[(m, "tuned", "phys")]), f3(gd[(m, "tuned", "iot")])])
        N[f"lam_{m}_tuned_phys"] = p; N[f"lam_{m}_tuned_iot"] = q
        N[f"lam_{m}_untuned_phys"] = g[(m, "untuned", "phys")]; N[f"lam_{m}_untuned_iot"] = g[(m, "untuned", "iot")]
        N[f"lam_{m}_drought_phys"] = gd[(m, "tuned", "phys")]; N[f"lam_{m}_drought_iot"] = gd[(m, "tuned", "iot")]
        N[f"price_ratio_{m}_tuned"] = (p - q) / p
    # by user, and node levels
    for v in ("phys", "iot"):
        r = d[(d.tuned == "tuned") & (d.iot == v)].groupby("method")[[f"r_{u}" for u in USERS]].mean()
        for m in METHODS:
            for u in USERS:
                N[f"r_{m}_{v}_{u}"] = r.loc[m, f"r_{u}"]
    d["dev"] = np.maximum((d.h_max - 3.0).abs(), (d.h_min - 3.0).abs())
    lv = d[d.tuned == "tuned"].groupby(["method", "iot"]).agg(dev=("dev", "mean"), hmin=("h_min", "min"),
                                                              hmax=("h_max", "max"))
    for (m, v), row in lv.iterrows():
        N[f"leveldev_{m}_{v}"] = row.dev; N[f"hmin_{m}_{v}"] = row.hmin; N[f"hmax_{m}_{v}"] = row.hmax
    # worst user under the IoT chain (days with lambda < 1)
    q = d[(d.tuned == "tuned") & (d.iot == "iot")]
    for m in ("LXB", "B0", "B3"):
        y = q[(q.method == m) & (q["lambda"] < 0.999)]
        rr = y[[f"r_{u}" for u in USERS]].to_numpy()
        worst = np.abs(rr - rr.min(axis=1, keepdims=True)) < 1e-6           # ties counted for every tied user
        N[f"worst_R1_share_{m}"] = float(worst[:, USERS.index("R-1")].mean())
    # --- IoT price
    x, pi = daily_price(d, "LXB", "tuned")
    N["pi_mean"] = pi.mean(); N["pi_median"] = pi.median(); N["pi_ratio"] = (x.p.mean() - x.i.mean()) / x.p.mean()
    N["pi_days"] = int(len(pi)); N["lamphys_zero_days"] = int((x.p == 0).sum())
    N["full_to_zero_days"] = int(((x.p > 0.999) & (x.i < 0.01)).sum())
    z = x[(x.p > 0.999) & (x.i < 0.01)]
    N["full_to_zero_dates"] = sorted(set(z.index.get_level_values(1).str[5:]))
    N["full_to_zero_years"] = int(z.index.get_level_values(0).nunique())
    low = pi[x.p[x.p > 0] <= 0.25]
    N["pi_low_days"] = int(len(low)); N["pi_low_share_days"] = len(low) / len(pi)
    N["pi_low_mean"] = low.mean(); N["pi_low_median"] = low.median()
    # P2, P3 (Equation (17)): Z2 = mean r, Z3 = sum_j |r_j[p] - r_j[p-1]| (as in evaluate_hypotheses.py)
    rc = [f"r_{u}" for u in USERS]
    for tn in ("tuned", "untuned"):
        zz = {}
        for v in ("phys", "iot"):
            t = d[(d.method == "LXB") & (d.tuned == tn) & (d.iot == v)].sort_values(["year", "date"]).copy()
            t["Z2"] = t[rc].mean(axis=1)
            t["Z3"] = t.groupby("year")[rc].diff().abs().sum(axis=1, min_count=1)
            zz[v] = t.set_index(["year", "date"])
        ok = zz["phys"]["lambda"] > 0
        ok2 = (zz["phys"].Z2 > 0) & zz["iot"].Z2.reindex(zz["phys"].index).notna()   # P2 has Z2_phys in the denominator
        z2p, z2i = zz["phys"].Z2[ok2], zz["iot"].Z2.reindex(zz["phys"].index)[ok2]
        p2 = (z2p - z2i) / z2p
        N[f"pi2_mean_{tn}"] = p2.mean(); N[f"pi2_median_{tn}"] = p2.median()
        N[f"pi2_ratio_{tn}"] = (z2p.mean() - z2i.mean()) / z2p.mean()
        d3 = (zz["iot"].Z3 - zz["phys"].Z3).dropna()
        N[f"pi3_mean_{tn}"] = d3.mean(); N[f"z3_phys_mean_{tn}"] = zz["phys"].Z3.mean()
        N[f"pi3_rel_{tn}"] = d3.mean() / zz["phys"].Z3.mean()
        N[f"lamphys_zero_days_{tn}"] = int((~ok).sum())
    st = d[d.method.isin(METHODS)].groupby(["method", "year", "tuned", "iot"]).storage_change_share_season.first()
    N["storage_share_absmax_all"] = float(st.abs().max())
    N["storage_share_absmax_LXB"] = float(st.loc[("LXB",)].abs().max())
    # Oracle and LXB, untuned IoT: satisfaction of R-1
    for m in ("Oracle", "LXB"):
        t = d[(d.method == m) & (d.tuned == "untuned") & (d.iot == "iot")]
        N[f"r_R1_{m}_untuned_iot"] = t["r_R-1"].mean()
    yo = d[(d.tuned == "untuned") & (d.iot == "iot")].groupby(["method", "year"])["lambda"].mean()
    N["years_LXB_above_Oracle_untuned_iot"] = int((yo.loc["LXB"] > yo.loc["Oracle"]).sum())
    x2, pi2 = daily_price(d, "LXB", "tuned", early_excluded=True)
    N["pi_mean_excl_early_april"] = pi2.mean(); N["pi_ratio_excl_early_april"] = (x2.p.mean() - x2.i.mean()) / x2.p.mean()
    N["early_april_days"] = int(len(x) - len(x2))
    if os.path.exists(DEMAND):
        dem = pd.read_csv(DEMAND)
        r1 = dem[(dem.variant == "A") & (dem.j == 2)].set_index(["month", "decade"]).q_mean_m3s
        N["R1_demand_apr1_m3s"] = r1.loc[(4, 1)]; N["R1_demand_apr1_m3_day"] = r1.loc[(4, 1)] * 86400
        N["R1_demand_peak_m3s"] = r1.max()
    yr = pi.groupby(level=0).mean()
    N["pi_years_positive"] = int((yr > 0).sum()); N["pi_year_min"] = yr.min(); N["pi_year_max"] = yr.max()
    lx = q[q.method == "LXB"].groupby("year").first()
    N["msgs_per_day_LXB"] = float(lx.messages.mean() / 183); N["drop_share_LXB"] = float(lx.dropped.sum() / lx.messages.sum())
    N["battery_min_LXB"] = float(lx.battery_min_wh.min()); N["radio_off_LXB"] = int(lx.radio_off_steps.sum())
    # diagnostics
    season = d.groupby(["method", "year", "tuned", "iot"]).first()
    N["mass_error_max"] = float(season.mass_error.abs().max())
    N["fallbacks_LXB_tuned_phys"] = int(season.loc[("LXB", slice(None), "tuned", "phys")].lp_fallbacks.sum())
    N["fallbacks_LXB_tuned_iot"] = int(season.loc[("LXB", slice(None), "tuned", "iot")].lp_fallbacks.sum())
    N["interlock_B1_tuned_phys"] = int(season.loc[("B1", slice(None), "tuned", "phys")].interlock_steps.sum())
    N["relief_B1_tuned_phys"] = int(season.loc[("B1", slice(None), "tuned", "phys")].relief_steps.sum())
    for m in METHODS + ["LXB-noS3"]:
        for (tn, v), grp in season.loc[m].groupby(level=["tuned", "iot"]):
            N[f"fallbacks_{m}_{tn}_{v}"] = int(grp.lp_fallbacks.sum())
    early = x.index.get_level_values(1).str[5:].to_series(index=x.index).between("04-01", "04-10")
    N["pi_share_early_april"] = float(pi[early[x.p > 0]].sum() / pi.sum())
    N["pi_share_low"] = float(low.sum() / pi.sum())
    robust(N)
    # --- Shapley values
    s = pd.read_csv(os.path.join(ROOT, "results/shapley_by_year_normal.csv"))
    for k in ("sensor", "quantisation", "communication", "energy"):
        N[f"phi_{k}"] = s[f"phi_{k}"].mean()
    N["phiQ_positive_years"] = int((s.phi_quantisation > 0).sum())
    N["phi_2014_S"] = float(s.set_index("year").loc[2014, "phi_sensor"])
    N["phi_2014_Q"] = float(s.set_index("year").loc[2014, "phi_quantisation"])
    # --- hypotheses
    h = pd.read_csv(os.path.join(ROOT, "results/hypotheses_summary_normal.csv"))

    def num(x, tiny):
        if tiny:
            return "0" if x == 0 else ("+" if x > 0 else "−") + sci(abs(x))
        return minus(f"{x:+.3f}")

    def est(r):
        if r.hypothesis == "H6" and r.estimate == 0 and r.ci_low == 0 and r.ci_high == 0:
            return "0 (no events)"
        vals = [v for v in (r.estimate, r.ci_low, r.ci_high) if pd.notna(v)]
        if not vals:
            return "—"
        tiny = max(abs(v) for v in vals) < 5e-4 and any(v != 0 for v in vals)
        ci = f" [{num(r.ci_low, tiny)}, {num(r.ci_high, tiny)}]" if pd.notna(r.ci_low) else ""
        return num(r.estimate, tiny) + ci

    def decision(r):
        return "Descriptive" if r.role == "descriptive" else dec.get(r.decision, r.decision)

    def sign(r):
        return f"{r.sign_share * 10:.0f}/10" if pd.notna(r.sign_share) else "—"

    def season_cell(x, r):
        """p-value of the exact sign-flip test on the seasonal means; the decision if it differs."""
        if x is None or pd.isna(x.p_holm):
            return "—"
        c = "< 0.001" if x.p_holm < 0.001 else f"{x.p_holm:.3f}"
        return c + (f" ({DEC.get(x.decision, x.decision).lower()})" if x.decision != r.decision else "")
    dec = DEC
    tS6 = [["Hyp.", "Comparison", "Chain", "Role", "Estimate [95% CI]", "p (Holm)", "Sign", "Decision",
            "Seasons as units: p (Holm)"]]
    st_p = os.path.join(ROOT, "results/hypotheses_summary_normal_season_seasontest.csv")
    HS = ({(x.hypothesis, x.comparison, x.variant): x for x in pd.read_csv(st_p).itertuples()}
          if os.path.exists(st_p) else {})
    for _, r in h.iterrows():
        comp = r.comparison.replace("Π1_LXB", "Π{~1,LXB~}").replace("Π1_B1", "Π{~1,B1~}").replace("Π1", "Π{~1~}").replace("φ_Q", "*φ*{~Q~}") \
            .replace("φ_C", "*φ*{~C~}").replace("φ_S", "*φ*{~S~}").replace("Δλ_LXB", "Δ*λ*{~LXB~}") \
            .replace("Δλ_B1", "Δ*λ*{~B1~}").replace("Z3", "*Z*{~3~}").replace("Z2", "*Z*{~2~}").replace("lambda:", "*λ*:") \
            .replace("gap_LXB", "gap{~LXB~}").replace("gap_B", "gap{~B")
        comp = comp.replace("gap{~B0", "gap{~B0~}").replace("gap{~B1", "gap{~B1~}").replace("gap{~B2", "gap{~B2~}") \
            .replace("gap{~B3", "gap{~B3~}")
        if r.hypothesis == "H3" and r.comparison.startswith("Z2"):      # mean satisfaction, as in the protocol
            comp = comp.replace("*Z*{~2~}:", "*Z*{~2~}/6:")
        if pd.isna(r.p_holm):
            p = "—"
        else:
            p = "< 0.001" if r.p_holm < 0.001 else f"{r.p_holm:.3f}"
        hyp = r.hypothesis if r.hypothesis != "H7" else ("H7b" if r.comparison.startswith("φ") else "H7a")
        tS6.append([hyp, comp, r.variant.replace(": ", " ").replace("phys → iot", "phys → IoT")
                    .replace("/iot", "/IoT").replace("→ iot", "→ IoT"), r.role, est(r), p, sign(r),
                    decision(r), season_cell(HS.get((r.hypothesis, r.comparison, r.variant)), r)])
    H = {(r.hypothesis, r.comparison, r.variant): r for _, r in h.iterrows()}
    h1 = h[h.hypothesis == "H1"]
    N["H1_superior"] = int((h1.decision == "superior").sum()); N["H1_noninferior"] = int((h1.decision == "non-inferior").sum())
    N["H1_n"] = int(len(h1))
    N["H1_min"] = float(h1.estimate.min()); N["H1_max"] = float(h1.estimate.max())

    def g1(hyp, comp, var):
        return H[(hyp, comp, var)]
    rH2 = g1("H2", "Δλ_LXB − Δλ_B1", "tuned/phys → untuned/iot")
    rH2b = g1("H2", "Δλ_LXB − Δλ_B1", "tuned/phys → untuned/phys")
    rH2c = g1("H2", "Δλ_LXB − Δλ_B1", "tuned/phys → tuned/iot")
    rH3 = g1("H3", "Z3: LXB − LXB-noS3", "tuned/phys")
    rH4 = g1("H4", "Π1 (LXB) − 0", "tuned: phys → iot"); rH4u = g1("H4", "Π1 (LXB) − 0", "untuned: phys → iot")
    hc = pd.read_csv(os.path.join(ROOT, "results/hypotheses_summary_normal_circular.csv"))
    c4 = hc[(hc.hypothesis == "H4") & (hc.variant == "tuned: phys → iot")].iloc[0]
    N["H4_circ_lo"] = float(c4.ci_low); N["H4_circ_hi"] = float(c4.ci_high)
    hs = pd.read_csv(os.path.join(ROOT, "results/hypotheses_summary_normal_season.csv"))
    s4 = hs[(hs.hypothesis == "H4") & (hs.variant == "tuned: phys → iot")].iloc[0]
    N["H4_season_lo"] = float(s4.ci_low); N["H4_season_hi"] = float(s4.ci_high)
    cal_p = os.path.join(ROOT, "results/hypotheses_summary_normal_calendar.csv")
    if os.path.exists(cal_p):
        hk = pd.read_csv(cal_p)
        k4 = hk[(hk.hypothesis == "H4") & (hk.variant == "tuned: phys → iot")].iloc[0]
        N["H4_cal_lo"] = float(k4.ci_low); N["H4_cal_hi"] = float(k4.ci_high)
    st = pd.read_csv(st_p) if os.path.exists(st_p) else None
    if st is not None:
        m_ = st.merge(h, on=["hypothesis", "comparison", "variant", "role"], suffixes=("", "_0"))
        chg = m_[m_.decision != m_.decision_0]
        N["seasontest_changed"] = int(len(chg))
        N["seasontest_changed_list"] = [f"{x.hypothesis} {x.comparison} {x.variant}: {x.decision_0} -> {x.decision}"
                                        for x in chg.itertuples()]
        for x in m_[m_.hypothesis == "H1"].itertuples():
            N[f"st_H1_{x.comparison.split(' − ')[-1]}_{x.variant.replace('/', '_')}_p"] = float(x.p_holm)
        h1s = m_[m_.hypothesis == "H1"]
        N["H1_superior_seasons"] = int((h1s.decision == "superior").sum())
    rH7a = g1("H7", "Π1_LXB − Π1_B1 (IoT-open)", "tuned: phys → iot")
    rH7b = g1("H7", "φ_Q + φ_C − φ_S", "tuned")
    # principal reporting: the ten seasons as the units of inference (season bootstrap interval, exact sign-flip test);
    # the pre-specified daily analysis is given alongside
    HS_ = {} if st is None else {(r.hypothesis, r.comparison, r.variant): r for _, r in st.iterrows()}
    sg = lambda r: HS_.get((r.hypothesis, r.comparison, r.variant), r)
    h1p = st[st.hypothesis == "H1"] if st is not None else h1

    def dec2(r):
        s_ = sg(r)
        out = DEC.get(s_.decision, s_.decision)
        return out if s_.decision == r.decision else f"{out} (daily analysis: {DEC.get(r.decision, r.decision).lower()})"

    def h1_chain(v):                       # protocol: non-inferior or superior against all four, superior against one
        x = h1p[h1p.variant == v].decision
        return x.isin(["superior", "non-inferior"]).all() and (x == "superior").any()
    chains = sorted(h1.variant.unique())
    n_ok = sum(h1_chain(v) for v in chains)
    h1_text = (f"Supported in all {len(chains)} chains" if n_ok == len(chains) else
               f"Supported in {n_ok} of {len(chains)} chains")
    ni = h1p[h1p.decision == "non-inferior"]
    ni_txt = ", ".join(f"{c.split(' − ')[-1]}, {v.replace('/iot', ' IoT').replace('/phys', ' phys')}"
                       for c, v in zip(ni.comparison, ni.variant))
    h3tol = h[(h.hypothesis == "H3") & (h.role == "tolerance")]
    h3_tol_ok = len(h3tol) > 0 and h3tol.decision.isin(["superior", "non-inferior"]).all()
    h6 = h[h.hypothesis == "H6"]
    h6_none = len(h6) > 0 and (h6.decision == "not testable").all()
    h6_na = len(h6) == 0 or (h6.decision == "not available").all()
    phiC = N["phi_communication"]
    h7b_text = DEC.get(rH7b.decision, rH7b.decision)
    if rH7b.decision == "supported":
        h7b_text += (" (carried by *φ*{~Q~}; *φ*{~C~} ≈ 0)" if phiC <= 0.0 or
                     abs(phiC) < 0.1 * abs(N["phi_quantisation"]) else "")
    t7 = [["Hypothesis", "Test (paired by day unless stated)", "Estimate [95% CI]; sign stability", "Decision"],
          ["H1", "LXB − B0, B1, B2, B3; daily *λ*; four chains (16 comparisons)",
           minus(f"{N['H1_min']:+.3f} to {N['H1_max']:+.3f}")
           + f"; superior in {int((h1p.decision == 'superior').sum())}"
           + (f", non-inferior in {len(ni)} ({ni_txt})" if len(ni) else "")
           + f"; daily analysis: superior in {N['H1_superior']}",
           h1_text],
          ["H2", "Δ*λ*{~LXB~} − Δ*λ*{~B1~}, tuned phys → untuned IoT", f"{est(sg(rH2))}; {sign(rH2)}",
           minus(f"{dec2(rH2)} (secondary: IoT only {rH2c.estimate:+.3f}, {sg(rH2c).decision}; model error only "
                 f"{rH2b.estimate:+.3f}, {sg(rH2b).decision})")],
          ["H3", "*Z*{~3~}: LXB − LXB-noS3, tuned phys", f"{est(sg(rH3))}; *λ* and *Z*{{~2~}}/6 "
           + ("non-inferior within *ε*{~λ~}" if h3_tol_ok else "outside the tolerance"),
           DEC[rH3.decision] if h3_tol_ok or rH3.decision != "supported" else "Not supported (tolerance not met)"],
          ["H4", "Mean daily Π{~1~} of LXB, tuned (secondary: untuned)",
           minus(f"{est(sg(rH4))}") + "; pre-specified moving block "
           + minus(f"[{rH4.ci_low:+.3f}, {rH4.ci_high:+.3f}]; untuned {rH4u.estimate:+.3f}; {sign(rH4)}"),
           dec2(rH4)],
          ["H5", "gap{~LXB~} − gap{~b~}", "Identical to −(H1 difference)", "Descriptive"],
          ["H6", "Share of user–days with command loss at outlets 2–5, LXB − B0, B3, days with *S* < *Q*{~c~}",
           "Operating records not available" if h6_na else
           "No such step for any method or chain" if h6_none else "; ".join(est(r) for _, r in h6.iterrows()),
           "Not available" if h6_na else "Not testable" if h6_none else
           ", ".join(sorted(set(DEC.get(x, x) for x in h6.decision)))],
          ["H7a", "Π{~1~}: LXB − B1 (IoT open loop), tuned", f"{est(sg(rH7a))}; {sign(rH7a)}", dec2(rH7a)],
          ["H7b", "*φ*{~Q~} + *φ*{~C~} − *φ*{~S~}, seasons", f"{est(rH7b)}; {sign(rH7b)}", h7b_text]]
    N["tests_n"] = int(len(h))
    N["H1_chains_supported"] = int(n_ok)
    for k, r in (("H2", rH2), ("H2b", rH2b), ("H2c", rH2c), ("H4", rH4), ("H4u", rH4u), ("H7a", rH7a), ("H7b", rH7b)):
        N[f"{k}_est"] = float(r.estimate); N[f"{k}_lo"] = float(r.ci_low); N[f"{k}_hi"] = float(r.ci_high)
    # --- sensitivity
    sens = pd.read_csv(os.path.join(ROOT, "results/sensitivity_summary.csv"))
    lxs = sens[(sens.method == "LXB") & ~sens.case.str.startswith("normal")]
    N["sens_lam_iot_min_excl_severe"] = float(lxs[lxs.case != "energy_severe"].lam_iot.min())
    N["sens_lam_iot_max"] = float(lxs.lam_iot.max())
    for _, r in lxs.iterrows():
        for k in ("lam_iot", "lam_phys", "pi1_ratio", "pi1_median", "d_B0_iot", "d_B3_iot", "radio_off_share",
                  "battery_min_wh", "blocked_share", "lost_share", "failed_share"):
            if k in r.index and pd.notna(r[k]):
                N[f"sens_{r.case}_{k}"] = float(r[k])
    for _, r in sens[~sens.case.str.startswith("normal")].iterrows():
        N[f"sens_{r.case}_{r.method}_lam_iot"] = float(r.lam_iot)
        N[f"sens_{r.case}_{r.method}_lam_phys"] = float(r.lam_phys)
    N["sens_d_B0_min"] = float(lxs.d_B0_iot.min()); N["sens_d_B0_max"] = float(lxs.d_B0_iot.max())
    N["sens_d_B3_min"] = float(lxs.d_B3_iot.min()); N["sens_d_B3_max"] = float(lxs.d_B3_iot.max())
    demand_floor(d, N)
    demand_floor_common(d, N)
    os.makedirs(TABLES, exist_ok=True)
    attribution(N)
    link_counters(N)
    overdelivery(N)
    rev = exploratory(d, N)
    t8 = tS7 = tR = None
    if rev:
        rows, t8, tS7, tR = rev
        t6 += rows
    out = {"table_lambda": t6, "table_hypotheses": t7, "tableS6": tS6, "table_posthoc": t8, "tableS7": tS7,
           "tableS7_rvol": tR,
           "numbers": {k: (v if isinstance(v, (list, str, int)) else float(v)) for k, v in N.items()}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Supplementary S7 (Table S6), appended to supplementary.md by build_appendix_supp.py
    md = lambda c: c.replace("{^", "^").replace("^}", "^").replace("{~", "~").replace("~}", "~")
    h3s = "no data"
    if "h3strict_lambda" in N:
        fm = lambda v: ("−" if v < 0 else "+") + sci(abs(v)).replace("{^", "^").replace("^}", "^")
        L, Z = N["h3strict_lambda"], N["h3strict_Z2_(sum)"]
        h3s = (f"*λ*: {fm(L[0])} [{fm(L[1])}, {fm(L[2])}], {L[3]}; *Z*~2~: {fm(Z[0])} [{fm(Z[1])}, {fm(Z[2])}], {Z[3]}")
    lines = ["## S7. Results of All Hypothesis Tests", "",
             "Table S6 gives two analyses of every test. The columns from the estimate to the decision give the "
             "pre-specified daily analysis, recorded as the original analysis; the last column gives the decision with the "
             "ten seasons as the units of inference, which is the principal analysis of the article (Section 2.9). "
             "Decisions follow the pre-specified rules (Section 2.9): superiority (or a "
             "supported decrease) requires the 95% confidence interval to exclude zero on the predicted side, a Holm-adjusted "
             "*p*-value below 0.05, and the expected sign in at least 7 of 10 seasons; non-inferiority requires only a lower "
             "limit above −*ε*~λ~ (*ε*~λ~ = 0.01). An interval that excludes zero on the predicted side without the "
             "*p*-value or sign condition is reported as inconclusive. Confidence intervals come from a moving-block "
             "bootstrap with 10-day blocks within seasons (10,000 replicates; for the Shapley contrast of H7, a bootstrap over the ten seasonal values, "
             "decided by the lower confidence limit alone, without a *p*-value, shown as —); *p*-values from the paired Wilcoxon "
             "signed-rank test, Holm-corrected within the families of Section 2.9. Chain: tuned or untuned gate "
             "coefficients and the phys or IoT execution chain. H5 reproduces H1 with the opposite sign and is reported as "
             "descriptive (Section 2.9). "
             + ("H6 is not testable, because no step without sufficient head occurred at the small regulators. "
                if h6_none else "")
             + 
             "Because daily differences are serially dependent, the daily Wilcoxon *p*-values are indicative only; values below "
             "0.001 are shown as < 0.001. The last column repeats each test with the ten seasons as the units of inference: the "
             "exact two-sided sign-flip test of the ten seasonal mean differences (1024 sign patterns, Holm-corrected within "
             "the same families; smallest attainable two-sided value 0.002), with the decision recomputed from the season "
             "bootstrap interval, this *p*-value, and the sign condition; a decision is shown only where it differs.", "",
             "In the tolerance checks of H3, the pre-specified protocol evaluates *Z*~2~ as the mean satisfaction of the six users "
             "(*Z*~2~/6) and applies the margin *ε*~λ~ = 0.01 to both *λ* and *Z*~2~. An exploratory check with *Z*~2~ as "
             "the sum of satisfactions and the solver tolerances *ε*~1~ = 10^−6^ for *λ* and *ε*~2~ = 10^−4^ for *Z*~2~ "
             f"gave: {h3s}.", "",
             "<!-- widths: 5,16,12,9,21,9,6,11,11 -->", "",
             "**Table S6.** All hypothesis tests of the main runs.", "",
             "| " + " | ".join(tS6[0]) + " |", "|" + "---|" * len(tS6[0])]
    lines += ["| " + " | ".join(md(c) for c in r) + " |" for r in tS6[1:]]
    open(os.path.join(TABLES, "supplementary_s7.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    if rev:
        write_s8(tS7, tR, N)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # provenance of the tables: the code base and every stored result and summary that was available
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from water01.simulation.provenance import all_code_sha256, files_sha256
    from pathlib import Path
    res = [p for p in Path(ROOT, "results").rglob("*.csv") if "tables" not in p.parts and "experiment_check" not in p.parts
           and "verification" not in p.parts]
    digest, n = files_sha256(res, Path(ROOT))
    json.dump({"code_sha256_all": all_code_sha256(ROOT), "results_sha256": digest, "results_files": n},
              open(os.path.join(TABLES, "PROVENANCE.json"), "w", encoding="utf-8"), indent=1)
    print(f"-> {OUT}: Table 7 ({len(t6) - 1}), Table 6 ({len(t7) - 1}), Table S6 ({len(tS6) - 1}), {len(N)} numbers")
    if not os.path.exists(DEMAND):
        print("Regenerated from the stored results: Tables 6-8, S6, S7a-S7e, the price, Shapley and sensitivity numbers. "
              "Skipped (need DATA/processed/demand_decadal.csv): the demand-floor checks, the demand of R-1, the "
              "delivered volume relative to the demand.")


if __name__ == "__main__":
    main()
