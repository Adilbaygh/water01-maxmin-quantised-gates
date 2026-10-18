"""Summary of the exploratory cases (descriptive; no hypothesis tests).

Reads results/experiment/normal/ (baseline), results/exploratory/<case>/ (run_experiment.py --exploratory) and, if
present, the hypothesis summaries computed with other bootstrap settings (evaluate_hypotheses.py).
Every lambda is the mean of the daily worst-user satisfaction lambda[p] = min_j r_j[p]. The price P1 is given as the
ratio of means (mean lambda_phys - mean lambda_iot) / mean lambda_phys and as the mean daily P1 on days with
lambda_phys > 0. Only seasons for which every required file exists are used.

Sections:
  1. b3_feedback     B3V (B3 with volume feedback) against LXB and B3, tuned/untuned x phys/IoT;
  2. deadband_aware  LXB-DA (pulse rule) under the IoT chain; price relative to LXB under ideal execution;
  3. seed_1..3       independent seeds: lambda_IoT, price of LXB, LXB - B0 and LXB - B3;
  4. forecast_loo    supply forecast without the simulated season (LXB, phys and IoT);
  5. blank_carry     blank supply entries replaced by the nearest record (LXB, B0, B3);
  6. bootstrap       decisions with 5- and 20-day blocks, circular blocks and a season bootstrap, compared with the
                     pre-specified 10-day moving block;
  7. volume          volume-weighted satisfaction R_vol[p] = sum_j min(V_j, D_j) / sum_j D_j;
  8. untuned_reverse reverse gate mismatch (LXB, B0, B3, B3V).
Usage: python scripts/summarize_exploratory.py  ->  results/exploratory_summary.csv and .md
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
USERS = ["Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli"]
YEARS = range(2010, 2020)


def read(folder, method, year, tuned, iot):
    f = Path(folder) / f"{method}_{year}_{tuned}_{iot}.csv"
    return pd.read_csv(f) if f.exists() else None


def frame(folder, method, tuned, iot, years):
    fr = [read(folder, method, y, tuned, iot) for y in years]
    return pd.concat(fr, ignore_index=True) if fr and all(f is not None for f in fr) else None


def complete_years(specs):
    """specs: [(folder, method, tuned, iot)]; seasons for which every file exists."""
    return [y for y in YEARS if all((Path(f) / f"{m}_{y}_{t}_{i}.csv").exists() for f, m, t, i in specs)]


def price(phys, iot):
    lp = phys.set_index(["year", "date"])["lambda"]; li = iot.set_index(["year", "date"])["lambda"]
    ok = lp > 0
    pi = ((lp - li) / lp)[ok]
    return float((lp.mean() - li.mean()) / lp.mean()), float(pi.mean())


def early_april_full_to_zero(phys, iot):
    p = phys.set_index(["year", "date"])["lambda"]; i = iot.set_index(["year", "date"])["lambda"]
    return int(((p > 0.999) & (i < 0.01)).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "results/experiment/normal"))
    ap.add_argument("--expl", default=str(ROOT / "results/exploratory"))
    ap.add_argument("--out", default=str(ROOT / "results/exploratory_summary"))
    a = ap.parse_args()
    B, R = Path(a.base), Path(a.expl)
    rows, md = [], []

    def add(item, case, method, tuned, chain, metric, val, years):
        rows.append(dict(item=item, case=case, method=method, tuned=tuned, chain=chain, metric=metric,
                         value=val, years=years))

    # 1. B3V
    md += ["## 1. B3 + volume feedback (B3V)", "",
           "| Tuned | Chain | Years | λ B3V | λ B3 | λ LXB | B3V − B3 | LXB − B3V | r R-1 (B3V) |", "|" + "---|" * 9]
    for t in ("tuned", "untuned"):
        for c in ("phys", "iot"):
            f = R / "b3_feedback"
            ys = complete_years([(f, "B3V", t, c), (B, "B3", t, c), (B, "LXB", t, c)])
            if not ys:
                continue
            v, b3, lx = frame(f, "B3V", t, c, ys), frame(B, "B3", t, c, ys), frame(B, "LXB", t, c, ys)
            lv, l3, ll = v["lambda"].mean(), b3["lambda"].mean(), lx["lambda"].mean()
            for k, x in (("lam_B3V", lv), ("lam_B3", l3), ("lam_LXB", ll), ("r_R1_B3V", v["r_R-1"].mean())):
                add("b3_feedback", "b3_feedback", "B3V", t, c, k, x, len(ys))
            md.append(f"| {t} | {c} | {len(ys)} | {lv:.3f} | {l3:.3f} | {ll:.3f} | {lv - l3:+.3f} | {ll - lv:+.3f} | "
                      f"{v['r_R-1'].mean():.3f} |")
        f = R / "b3_feedback"
        ys = complete_years([(f, "B3V", t, "phys"), (f, "B3V", t, "iot")])
        if ys:
            pr, pd_ = price(frame(f, "B3V", t, "phys", ys), frame(f, "B3V", t, "iot", ys))
            add("b3_feedback", "b3_feedback", "B3V", t, "phys→iot", "price_ratio", pr, len(ys))
            # the mean daily ratio is dominated by a few days with lambda_phys close to 0; not shown if |P1| > 1
            dtxt = f"daily {pd_:.1%}" if abs(pd_) <= 1 else "daily n/a (days with λ_phys < 0.01 dominate)"
            md.append(f"| {t} | Π1 B3V | {len(ys)} | ratio {pr:.1%} | {dtxt} | | | | |")
    md.append("")

    # 2. LXB-DA
    md += ["## 2. Deadband-aware execution (LXB-DA, IoT chain)", "",
           "| Tuned | Years | λ LXB-DA | λ LXB | λ LXB phys | Π1 ratio DA | Π1 ratio LXB | Π1 daily DA | r R-1 DA | r R-1 LXB | "
           "1→0 days DA | 1→0 days LXB |", "|" + "---|" * 12]
    for t in ("tuned", "untuned"):
        f = R / "deadband_aware"
        ys = complete_years([(f, "LXB-DA", t, "iot"), (B, "LXB", t, "iot"), (B, "LXB", t, "phys")])
        if not ys:
            continue
        da, lx, ph = frame(f, "LXB-DA", t, "iot", ys), frame(B, "LXB", t, "iot", ys), frame(B, "LXB", t, "phys", ys)
        pda, pdd = price(ph, da); plx, _ = price(ph, lx)
        z_da, z_lx = early_april_full_to_zero(ph, da), early_april_full_to_zero(ph, lx)
        for k, x in (("lam_iot", da["lambda"].mean()), ("price_ratio", pda), ("price_daily", pdd),
                     ("r_R1", da["r_R-1"].mean()), ("full_to_zero_days", z_da)):
            add("deadband_aware", "deadband_aware", "LXB-DA", t, "iot", k, x, len(ys))
        md.append(f"| {t} | {len(ys)} | {da['lambda'].mean():.3f} | {lx['lambda'].mean():.3f} | {ph['lambda'].mean():.3f} | "
                  f"{pda:.1%} | {plx:.1%} | {pdd:.1%} | {da['r_R-1'].mean():.3f} | {lx['r_R-1'].mean():.3f} | {z_da} | {z_lx} |")
    md.append("")

    # 3. Seeds
    md += ["## 3. Independent random seeds (IoT chain, tuned)", "",
           "| Seed | Years | λ LXB | λ B0 | λ B3 | Π1 ratio LXB | LXB − B0 | LXB − B3 |", "|" + "---|" * 8]
    seeds = [("base", B)] + [(s, R / s) for s in ("seed_1", "seed_2", "seed_3")]
    specs = [(f, m, "tuned", "iot") for _, f in seeds for m in ("LXB", "B0", "B3")] + [(B, "LXB", "tuned", "phys")]
    ys = complete_years(specs)
    if ys:
        ph = frame(B, "LXB", "tuned", "phys", ys)
        stats = {k: [] for k in ("LXB", "B0", "B3", "price", "dB0", "dB3")}
        for name, f in seeds:
            fr = {m: frame(f, m, "tuned", "iot", ys) for m in ("LXB", "B0", "B3")}
            lam = {m: fr[m]["lambda"].mean() for m in fr}
            pr, _ = price(ph, fr["LXB"])
            vals = dict(LXB=lam["LXB"], B0=lam["B0"], B3=lam["B3"], price=pr,
                        dB0=lam["LXB"] - lam["B0"], dB3=lam["LXB"] - lam["B3"])
            for k, x in vals.items():
                stats[k].append(x); add("seeds", name, "", "tuned", "iot", k, x, len(ys))
            md.append(f"| {name} | {len(ys)} | {lam['LXB']:.3f} | {lam['B0']:.3f} | {lam['B3']:.3f} | {pr:.1%} | "
                      f"{vals['dB0']:+.3f} | {vals['dB3']:+.3f} |")
        rng = {k: (min(v), max(v)) for k, v in stats.items()}
        md.append(f"| range | | {rng['LXB'][0]:.3f}–{rng['LXB'][1]:.3f} | {rng['B0'][0]:.3f}–{rng['B0'][1]:.3f} | "
                  f"{rng['B3'][0]:.3f}–{rng['B3'][1]:.3f} | {rng['price'][0]:.1%}–{rng['price'][1]:.1%} | "
                  f"{rng['dB0'][0]:+.3f}…{rng['dB0'][1]:+.3f} | {rng['dB3'][0]:+.3f}…{rng['dB3'][1]:+.3f} |")
    md.append("")

    # 4-5. Forecast and blank entries
    for case, methods, title in (("forecast_loo", ("LXB",), "4. Leave-one-year-out forecast"),
                                 ("blank_carry", ("LXB", "B0", "B3"), "5. Blank supply entries filled with the nearest record")):
        f = R / case
        md += [f"## {title}", "", "| Method | Years | λ phys | λ IoT | λ phys (base) | λ IoT (base) | Π1 ratio | Π1 ratio (base) |",
               "|" + "---|" * 8]
        for m in methods:
            ys = complete_years([(f, m, "tuned", "phys"), (f, m, "tuned", "iot"), (B, m, "tuned", "phys"),
                                 (B, m, "tuned", "iot")])
            if not ys:
                continue
            p, i = frame(f, m, "tuned", "phys", ys), frame(f, m, "tuned", "iot", ys)
            pb, ib = frame(B, m, "tuned", "phys", ys), frame(B, m, "tuned", "iot", ys)
            pr, _ = price(p, i); prb, _ = price(pb, ib)
            for k, x in (("lam_phys", p["lambda"].mean()), ("lam_iot", i["lambda"].mean()), ("price_ratio", pr)):
                add(case, case, m, "tuned", "", k, x, len(ys))
            md.append(f"| {m} | {len(ys)} | {p['lambda'].mean():.3f} | {i['lambda'].mean():.3f} | {pb['lambda'].mean():.3f} | "
                      f"{ib['lambda'].mean():.3f} | {pr:.1%} | {prb:.1%} |")
        if case == "blank_carry":
            for v in ("phys", "iot"):
                ys = complete_years([(f, m, "tuned", v) for m in methods])
                if ys:
                    fr = {m: frame(f, m, "tuned", v, ys)["lambda"].mean() for m in methods}
                    md.append(f"| LXB − B0 / LXB − B3 ({v}) | {len(ys)} | {fr['LXB'] - fr['B0']:+.3f} | "
                              f"{fr['LXB'] - fr['B3']:+.3f} | | | | |")
        md.append("")

    # 6. Bootstrap settings
    base_h = ROOT / "results/hypotheses_summary_normal.csv"
    md += ["## 6. Bootstrap settings (decisions compared with the pre-specified 10-day moving block)", ""]
    if base_h.exists():
        h0 = pd.read_csv(base_h)
        key = ["hypothesis", "comparison", "variant", "role"]
        for name, f, cmd in [(f"block {b}", ROOT / f"results/hypotheses_summary_block_{b}.csv",
                              f"--scenario block_{b} --data normal") for b in (5, 20)] + \
                            [(f"{s_} bootstrap", ROOT / f"results/hypotheses_summary_normal_{s_}.csv",
                              f"--bootstrap {s_}") for s_ in ("circular", "season")]:
            if not f.exists():
                md.append(f"- {name}: not computed (python scripts/evaluate_hypotheses.py {cmd})")
                continue
            h = pd.read_csv(f).merge(h0, on=key, suffixes=("", "_10"))
            ch = h[h.decision != h.decision_10]
            add("bootstrap", name, "", "", "", "changed_decisions", len(ch), len(h))
            md.append(f"- {name}: {len(ch)} of {len(h)} decisions differ"
                      + ("" if ch.empty else ": " + "; ".join(f"{r.hypothesis} {r.comparison} {r.variant} "
                                                               f"{r.decision_10} -> {r.decision}" for r in ch.itertuples())))
    else:
        md.append("- results/hypotheses_summary_normal.csv not found")
    md.append("")

    # 7. Volume-weighted satisfaction
    dem = pd.read_csv(ROOT / "DATA/processed/demand_decadal.csv")
    dem = dem[dem.variant == "A"].set_index(["j", "month", "decade"]).q_mean_m3s
    md += ["## 7. Volume-weighted satisfaction R_vol (base results, tuned)", "",
           "| Method | R_vol phys | R_vol IoT | loss | λ phys | λ IoT | Π1 ratio |", "|" + "---|" * 7]
    src = {m: (B, B) for m in ("LXB", "B2", "B0", "B3", "B1", "Oracle")}
    src["B3V"] = (R / "b3_feedback", R / "b3_feedback")
    src["LXB-DA"] = (B, R / "deadband_aware")         # LXB-DA coincides with LXB under ideal execution
    for m, (fp, fi) in src.items():
        mp = "LXB" if m == "LXB-DA" else m
        ys = complete_years([(fp, mp, "tuned", "phys"), (fi, m, "tuned", "iot")])
        if not ys:
            continue
        out = {}
        for v, f_, mm in (("phys", fp, mp), ("iot", fi, m)):
            d = frame(f_, mm, "tuned", v, ys); dt = pd.to_datetime(d.date)
            dec = np.where(dt.dt.day <= 10, 1, np.where(dt.dt.day <= 20, 2, 3))
            num = den = 0.0
            for j, u in enumerate(USERS, 1):
                D = np.array([dem.loc[(j, mo, de)] for mo, de in zip(dt.dt.month, dec)]) * 86400.0
                num += np.minimum(d[f"V_{u}"].to_numpy(), D).sum(); den += D.sum()
            out[v] = (num / den, d)
        loss = (out["phys"][0] - out["iot"][0]) / out["phys"][0]
        pr, _ = price(out["phys"][1], out["iot"][1])
        for k, x in (("R_vol_phys", out["phys"][0]), ("R_vol_iot", out["iot"][0]), ("R_vol_loss", loss)):
            add("volume", "normal", m, "tuned", "", k, x, len(ys))
        md.append(f"| {m} | {out['phys'][0]:.4f} | {out['iot'][0]:.4f} | {loss:.2%} | {out['phys'][1]['lambda'].mean():.3f} | "
                  f"{out['iot'][1]['lambda'].mean():.3f} | {pr:.1%} |")
    md.append("")

    # 8. Reverse gate mismatch
    f = R / "untuned_reverse"
    md += ["## 8. Reverse gate mismatch (untuned_reverse)", "",
           "| Chain | Years | λ LXB | λ B0 | λ B3 | λ B3V | LXB − B3V |", "|" + "---|" * 7]
    for c in ("phys", "iot"):
        ms = ("LXB", "B0", "B3", "B3V")
        ys = complete_years([(f, m, "untuned", c) for m in ms])
        if not ys:
            continue
        lam = {m: frame(f, m, "untuned", c, ys)["lambda"].mean() for m in ms}
        for m in ms:
            add("untuned_reverse", "untuned_reverse", m, "untuned", c, "lam", lam[m], len(ys))
        md.append(f"| {c} | {len(ys)} | {lam['LXB']:.3f} | {lam['B0']:.3f} | {lam['B3']:.3f} | {lam['B3V']:.3f} | "
                  f"{lam['LXB'] - lam['B3V']:+.3f} |")
    md.append("")

    pd.DataFrame(rows).to_csv(a.out + ".csv", index=False)
    Path(a.out + ".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"-> {a.out}.csv, {a.out}.md")


if __name__ == "__main__":
    sys.exit(main())
