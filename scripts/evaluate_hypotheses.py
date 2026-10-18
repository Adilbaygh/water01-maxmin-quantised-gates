"""Evaluation of hypotheses H1-H7 (Section 2.9; requirements/hypotheses.md) from results/experiment/<scenario>/*.csv.

  H1  LXB - B0...B3, daily lambda, "increase", Holm family of 4, for every variant (tuned/untuned x phys/iot);
  H2  d_lambda = lambda(tuned, phys) - lambda(perturbed); d_lambda_LXB - d_lambda_B1, "decrease". The primary
      perturbation is untuned + IoT; untuned + phys and tuned + IoT are secondary;
  H3  LXB - LXB-noS3 (tuned, phys): Z3[p] = sum_j |r_j[p] - r_j[p-1]|, "decrease"; lambda and Z2/6 (mean
      satisfaction) as tolerance checks ("increase", non-inferiority margin epsilon_lambda);
  H4  LXB: P1[p] = (lambda_phys - lambda_IoT) / lambda_phys on days with lambda_phys[p] > 0, "increase" (> 0),
      tuned (primary) and untuned (secondary);
  H5  Oracle gap: gap_LXB - gap_b = lambda_b - lambda_LXB. The Oracle cancels in the paired difference, so H5 is
      the sign-reversed copy of H1 and is reported as descriptive;
  H6  days with S < Q_c: steps at which the head at a small regulator cannot pass the planned rate, LXB - B0/B3,
      "decrease"; not testable when no such step occurs;
  H7  (a) P1_LXB[p] - P1_B1[p] (B1 under the IoT chain as the open-loop reference), "decrease", tuned;
      (b) Shapley values (18) per season, v(F) = mean daily P1 of LXB (tuned) over the 16 coalitions;
          d_y = phi_Q + phi_C - phi_S; interval from a season bootstrap; supported if the lower bound > 0.
Output: results/hypotheses_summary_<scenario>[_<scheme>].csv and .md with .meta.json; earlier files are moved to
results/superseded/.
Usage: python scripts/evaluate_hypotheses.py [--scenario normal]
       python scripts/evaluate_hypotheses.py --scenario block_5 --data normal    # 5-day bootstrap blocks
       python scripts/evaluate_hypotheses.py --bootstrap circular               # circular blocks (or season)
"""
import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.passport import USERS, value  # noqa: E402
from water01.evaluation.hypotheses import evaluate_family, holm_families  # noqa: E402
from water01.evaluation.metrics import shapley  # noqa: E402
from water01.simulation.provenance import config_inputs, write_metadata  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402

SMALL = USERS[1:5]
KEY = ["year", "date"]                                     # pairing key: season and date
VARIANTS = [("tuned", "phys"), ("tuned", "iot"), ("untuned", "phys"), ("untuned", "iot")]
CODE = {"S": "sensor", "Q": "quantisation", "C": "communication", "E": "energy"}


def load_all(scenario):
    """All result files; the variant is taken from the tuned and iot columns. (method, tuned, iot, year, date) must
    be unique."""
    files = sorted((ROOT / "results/experiment" / scenario).glob("*.csv"))
    if not files:
        sys.exit(f"No results in results/experiment/{scenario}; run scripts/run_experiment.py first")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    missing = {"method", "year", "date", "tuned", "iot"} - set(df.columns)
    if missing:
        sys.exit(f"Columns missing from the result files: {sorted(missing)}")
    df["tuned"] = df.tuned.astype(str); df["iot"] = df.iot.astype(str)
    df["year"] = df.year.astype(int); df["date"] = pd.to_datetime(df.date).dt.strftime("%Y-%m-%d")
    if (pd.to_datetime(df.date).dt.year != df.year).any():
        sys.exit("The year column does not match the year of the date")
    dup = df.duplicated(["method", "tuned", "iot"] + KEY)
    if dup.any():
        sys.exit("Duplicate (method, tuned, iot, year, date): "
                 f"{df[dup][['method', 'tuned', 'iot'] + KEY].head().to_dict('records')}")
    rc = [f"r_{u}" for u in USERS if f"r_{u}" in df]
    df = df.sort_values(["method", "tuned", "iot"] + KEY).reset_index(drop=True)
    if rc:
        dr = df.groupby(["method", "tuned", "iot", "year"])[rc].diff().abs()
        df["Z3"] = dr.sum(axis=1, min_count=1)              # day-to-day change (NaN on the first day)
        df["Z2"] = df[rc].mean(axis=1)                      # w_j = 1: mean satisfaction (Z2/6)
    return df


def load(tuned, iot, scenario):
    """One variant."""
    df = load_all(scenario)
    df = df[(df.tuned == tuned) & (df.iot == iot)].copy()
    if df.empty:
        sys.exit(f"No results for tuned={tuned}, iot={iot}")
    return df


def sel(df, method, tuned, iot):
    return df[(df.method == method) & (df.tuned == tuned) & (df.iot == iot)]


def paired(df, a, b, col):
    """a - b for every (year, date); both methods must cover the same days."""
    x = df[df.method == a].set_index(KEY)[col]; y = df[df.method == b].set_index(KEY)[col]
    if not (x.index.is_unique and y.index.is_unique):
        raise ValueError(f"duplicate (year, date) in {a} or {b}")
    if not x.index.sort_values().equals(y.index.sort_values()):
        raise ValueError(f"{a} and {b} cover different days")
    idx = x.index.sort_values()
    return (x.loc[idx] - y.loc[idx]).to_numpy(), idx.get_level_values("year").to_numpy()


def series(df, method, tuned, iot, col):
    s = sel(df, method, tuned, iot).set_index(KEY)[col]
    if s.empty:
        raise KeyError(f"{method} {tuned} {iot}: no results")
    if not s.index.is_unique:
        raise ValueError(f"{method} {tuned} {iot}: duplicate (year, date)")
    return s


def aligned(a, b):
    if not a.index.sort_values().equals(b.index.sort_values()):
        raise ValueError("the series cover different days")
    idx = a.index.sort_values()
    return a.loc[idx], b.loc[idx], idx.get_level_values("year").to_numpy()


def daily_price(df, method, tuned, iot):
    """P1[p] = (lambda_phys - lambda_F) / lambda_phys on days with lambda_phys[p] > 0; also returns the number of
    days with lambda_phys = 0."""
    ph, it, _ = aligned(series(df, method, tuned, "phys", "lambda"), series(df, method, tuned, iot, "lambda"))
    ok = ph > 0
    return ((ph - it) / ph)[ok], int((~ok).sum())


SCHEME = "block"                                           # bootstrap scheme, set from --bootstrap


def run_family(rows, h, comparison, variant, diffs, years, kind, seed, role="primary", note="", eps=None):
    if not diffs:
        rows.append(dict(hypothesis=h, comparison=comparison, variant=variant, role=role, decision="no data", note=note))
        return
    for r in evaluate_family(diffs, years, kind, eps=eps, seed=seed, scheme=SCHEME):
        n = len(diffs[r.baseline])
        rows.append(dict(hypothesis=h, comparison=f"{comparison}{r.baseline}", variant=variant, role=role,
                         estimate=r.estimate, ci_low=r.ci_low, ci_high=r.ci_high, p_raw=r.p_raw, p_holm=r.p_holm,
                         sign_share=r.sign_share, n_days=n, decision=r.decision, note=note))


def shapley_by_year(df, tuned="tuned", n_boot=None, seed=0, alpha=None):
    """H7(b): phi_S, phi_Q, phi_C, phi_E per season; d_y = phi_Q + phi_C - phi_S; season bootstrap interval."""
    n_boot = value("bootstrap_replicates") if n_boot is None else n_boot
    alpha = value("alpha") if alpha is None else alpha
    codes = ["".join(c) for r in range(1, 5) for c in itertools.combinations("SQCE", r)]
    out = []
    for y in sorted(sel(df, "LXB", tuned, "phys").year.unique()):
        v = {frozenset(): 0.0}
        d = df[df.year == y]
        for c in codes:
            iot = "iot" if c == "SQCE" else c
            if sel(d, "LXB", tuned, iot).empty:
                return None
            pi, _ = daily_price(d, "LXB", tuned, iot)
            v[frozenset(CODE[k] for k in c)] = float(pi.mean())
        phi = shapley(v)
        out.append(dict(year=y, **{f"phi_{k}": val for k, val in phi.items()}))
    t = pd.DataFrame(out)
    t["d"] = t.phi_quantisation + t.phi_communication - t.phi_sensor
    rng = np.random.default_rng(seed)
    boot = [rng.choice(t.d.to_numpy(), t.d.size, replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return t, float(t.d.mean()), float(lo), float(hi), float((t.d > 0).mean())


RECORDS_SUPPLY = ROOT / "DATA/processed/rashod_2010_2019_daily.csv"   # days with S < Q_c (H6); closed records


def evaluate(df, seed, supply_csv=RECORDS_SUPPLY):
    fam = holm_families(); rows = []
    methods = set(df.method)
    if not Path(supply_csv).exists():
        sys.exit(f"{Path(supply_csv).name} is needed for H6 (days with S < Q_c); the operating records "
                 "(DATA/processed) are available to reviewers on request")
    sup = pd.read_csv(supply_csv, parse_dates=["date"])
    low = set(sup[sup.kegeyli_Q.fillna(0) < value("Q_c_m3s")].date.dt.strftime("%Y-%m-%d"))
    for tuned, iot in VARIANTS:                                       # H1, H5, H6 for every variant
        v = df[(df.tuned == tuned) & (df.iot == iot) & df.method.isin(["B0", "B1", "B2", "B3", "LXB", "Oracle"])]
        if v.empty:
            continue
        var = f"{tuned}/{iot}"
        d, yrs = {}, None
        for b in fam["H1"]:
            if {"LXB", b} <= set(v.method):
                d[b], yrs = paired(v, "LXB", b, "lambda")
        run_family(rows, "H1", "LXB − ", var, d, yrs, "increase", seed)
        d = {}
        if "Oracle" in set(v.method):
            for b in fam["H5"]:
                if {"LXB", b} <= set(v.method):
                    d[b], yrs = paired(v, b, "LXB", "lambda")
        run_family(rows, "H5", "gap_LXB − gap_", var, d, yrs, "decrease", seed, role="descriptive",
                   note="sign-reversed copy of H1 (the Oracle cancels in the paired difference)")
        v6 = v[v.date.isin(low)].copy()
        v6["lost_small"] = v6[[f"lost_{u}" for u in SMALL]].sum(axis=1)
        d = {}
        for b in fam["H6"]:
            if {"LXB", b} <= set(v6.method) and len(v6):
                d[b], yrs = paired(v6, "LXB", b, "lost_small")
        total = int(v6[v6.method.isin(["LXB"] + list(fam["H6"]))].lost_small.sum())
        note = f"steps without sufficient head at the small regulators: {total}"
        if d and total == 0:
            rows.extend(dict(hypothesis="H6", comparison=f"LXB − {b}", variant=var, role="primary", estimate=0.0,
                             n_days=len(d[b]), decision="not testable", note=note) for b in d)
        else:
            run_family(rows, "H6", "LXB − ", var, d, yrs, "decrease", seed, note=note)
    # H2: d_lambda = lambda(tuned, phys) - lambda(perturbed); LXB - B1
    for (t, i), role in ((("untuned", "iot"), "primary"), (("untuned", "phys"), "secondary"),
                         (("tuned", "iot"), "secondary")):
        try:
            dl = {}
            for m in ("LXB", "B1"):
                nom, per, _ = aligned(series(df, m, "tuned", "phys", "lambda"), series(df, m, t, i, "lambda"))
                dl[m] = nom - per
            a, b, yrs = aligned(dl["LXB"], dl["B1"])
            run_family(rows, "H2", "Δλ_LXB − Δλ_", f"tuned/phys → {t}/{i}", {"B1": (a - b).to_numpy()}, yrs,
                       "decrease", seed, role=role)
        except (KeyError, ValueError):
            rows.append(dict(hypothesis="H2", comparison="Δλ_LXB − Δλ_B1", variant=f"{t}/{i}", role=role,
                             decision="no data"))
    # H3: LXB − LXB-noS3, tuned phys
    if {"LXB", "LXB-noS3"} <= methods:
        for col, kind in (("Z3", "decrease"), ("lambda", "increase"), ("Z2", "increase")):
            a, b, yrs = aligned(series(df, "LXB", "tuned", "phys", col),
                                series(df, "LXB-noS3", "tuned", "phys", col))
            ok = a.notna().to_numpy() & b.notna().to_numpy()
            run_family(rows, "H3", f"{col}: LXB − ", "tuned/phys", {"LXB-noS3": (a - b).to_numpy()[ok]}, yrs[ok],
                       kind, seed, role="primary" if col == "Z3" else "tolerance")
    else:
        rows.append(dict(hypothesis="H3", comparison="LXB − LXB-noS3", variant="tuned/phys", decision="no data",
                         note="run_experiment.py --ablation"))
    # H4: P1 > 0 (LXB); no margin, so the labels are supported / rejected / inconclusive
    for t in ("tuned", "untuned"):
        try:
            pi, zero = daily_price(df, "LXB", t, "iot")
            run_family(rows, "H4", "Π1 (LXB) − ", f"{t}: phys → iot", {"0": pi.to_numpy()},
                       pi.index.get_level_values("year").to_numpy(), "increase", seed, eps=0.0,
                       role="primary" if t == "tuned" else "secondary", note=f"days with λ_phys = 0: {zero}")
            rows[-1]["decision"] = {"superior": "supported"}.get(rows[-1]["decision"], rows[-1]["decision"])
        except (KeyError, ValueError):
            rows.append(dict(hypothesis="H4", comparison="Π1 (LXB)", variant=t, decision="no data"))
    # H7(a): P1_LXB - P1_B1 (B1 under the IoT chain)
    try:
        p_fb, _ = daily_price(df, "LXB", "tuned", "iot"); p_op, _ = daily_price(df, "B1", "tuned", "iot")
        common = p_fb.index.intersection(p_op.index).sort_values()
        run_family(rows, "H7", "Π1_LXB − Π1_", "tuned: phys → iot",
                   {"B1 (IoT-open)": (p_fb.loc[common] - p_op.loc[common]).to_numpy()},
                   common.get_level_values("year").to_numpy(), "decrease", seed,
                   note="days with λ_phys > 0 for both methods")
    except (KeyError, ValueError):
        rows.append(dict(hypothesis="H7", comparison="Π1_LXB − Π1_B1", variant="tuned", decision="no data"))
    sh = shapley_by_year(df, seed=seed)
    table = None
    if sh is None:
        rows.append(dict(hypothesis="H7", comparison="φ_Q + φ_C − φ_S", variant="tuned", decision="no data",
                         note="run_experiment.py --shapley (16 coalitions)"))
    else:
        table, est, lo, hi, share = sh
        rows.append(dict(hypothesis="H7", comparison="φ_Q + φ_C − φ_S", variant="tuned", role="primary",
                         estimate=est, ci_low=lo, ci_high=hi, sign_share=share, n_days=len(table),
                         decision="supported" if lo > 0 else ("rejected" if hi < 0 else "inconclusive"),
                         note="n = seasons; " + ", ".join(f"{k} = {table[k].mean():+.4f}"
                                                         for k in table.columns if k.startswith("phi_"))))
    res = pd.DataFrame(rows)
    for c in ("role", "note", "estimate", "ci_low", "ci_high", "p_raw", "p_holm", "sign_share", "n_days"):
        if c not in res:
            res[c] = np.nan
    res["role"] = res.role.fillna("primary")
    return res, table


def to_markdown(res):
    lines = ["| Hypothesis | Comparison | Variant | Role | Estimate | 95% CI | p (Holm) | Sign | Decision |",
             "|---|---|---|---|---|---|---|---|---|"]
    f = lambda x, fmt: "" if pd.isna(x) else format(x, fmt)
    for r in res.itertuples():
        ci = "" if pd.isna(r.ci_low) else f"[{r.ci_low:+.4f}, {r.ci_high:+.4f}]"
        lines.append(f"| {r.hypothesis} | {r.comparison} | {r.variant} | {r.role} | {f(r.estimate, '+.4f')} | {ci} "
                     f"| {f(r.p_holm, '.3g')} | {f(r.sign_share, '.0%')} | {r.decision} |")
    return "\n".join(lines) + "\n"


def archive_previous(path):
    """Move earlier output files (.csv, .md, .meta.json) to results/superseded/ with a time stamp."""
    dest = path.parent / "superseded"
    stamp = pd.Timestamp.now().strftime("%Y%m%d-%H%M%S")
    for p in (path, path.with_suffix(".md"), path.with_name(path.name + ".meta.json")):
        if p.exists():
            dest.mkdir(exist_ok=True)
            stem, ext = p.name.split(".", 1)
            p.replace(dest / f"{stem}_superseded_{stamp}.{ext}")


def main():
    global SCHEME
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="normal")
    ap.add_argument("--data", default=None,
                    help="result folder results/experiment/<data> (default: the scenario name); e.g. "
                         "--scenario block_5 --data normal changes only the bootstrap block length")
    ap.add_argument("--bootstrap", default="block", choices=("block", "circular", "season"),
                    help="bootstrap scheme of the daily comparisons (pre-specified: block)")
    a = ap.parse_args()
    SCHEME = a.bootstrap
    cfg = load_config(scenario=a.scenario)
    res, table = evaluate(load_all(a.data or cfg.scenario), cfg.seed)
    print(to_markdown(res))
    suffix = "" if a.bootstrap == "block" else f"_{a.bootstrap}"
    path = ROOT / f"results/hypotheses_summary_{cfg.scenario}{suffix}.csv"
    archive_previous(path)
    res.to_csv(path, index=False)
    path.with_suffix(".md").write_text(to_markdown(res), encoding="utf-8")
    if table is not None and not suffix:
        table.to_csv(ROOT / f"results/shapley_by_year_{cfg.scenario}.csv", index=False)
    write_metadata(path, ROOT, config_inputs(cfg, ROOT) + ("requirements/hypotheses.md",),
                   {"scenario": cfg.scenario, "data": a.data or cfg.scenario, "bootstrap": a.bootstrap}, cfg)
    print(f"-> {path.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
