"""Descriptive sensitivity table (Section 2.10). Not a hypothesis test.

Reads results/experiment/normal/ (baseline) and results/sensitivity/<case>/ (run_experiment.py --sensitivity).
For every case × method (LXB, B0, B3), over the years computed for that case only (the baseline uses the same years):
  lam_phys, lam_iot  — mean of the daily λ = min_j r_j;
  pi1, pi1_median    — for LXB, mean and median of the daily Π1 = (λ_phys − λ_iot)/λ_phys (days with λ_phys > 0);
  pi1_ratio          — ratio of means rather than mean of ratios, (mean λ_phys − mean λ_iot)/mean λ_phys: a single
                       day with λ_phys ≈ 0 can pull the daily ratio down to about −100 (energy_moderate, 2016), so
                       this value and the median are reported as robust summaries in the descriptive table;
  pi1_extreme_days   — number of days with |Π1[p]| > 1;
  d_B0, d_B3         — LXB − baseline, mean daily λ difference (iot and phys);
  r_min_user         — least satisfied user under iot and its mean r;
  radio_off_share    — share of steps with the radio off (energy factor); battery_min_wh — lowest charge in the season;
  dropped_share      — share of messages lost or over budget.
For iot-only cases (deadband, energy, communication), phys is the baseline (normal) result: the IoT assumptions do
not affect phys.
Usage: python scripts/summarize_sensitivity.py  ->  results/sensitivity_summary.csv and .md
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_experiment import SENS_METHODS, SENSITIVITY  # noqa: E402

BASE = ROOT / "results/experiment/normal"
SENS = ROOT / "results/sensitivity"
USERS = ["Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli"]
STATIC = ("storage_change_share_season", "mass_error", "messages", "dropped", "lp_fallbacks", "interlock_steps",
          "relief_steps", "battery_min_wh", "radio_off_steps", "energy_used_wh", "extra_substeps")


def read(folder, method, year, iot):
    f = folder / f"{method}_{year}_tuned_{iot}.csv"
    return pd.read_csv(f) if f.exists() else None


def years_of(folder, iots):
    """Years for which all methods and iot variants of the case are complete."""
    ys = []
    for y in range(2010, 2020):
        if all((folder / f"{m}_{y}_tuned_{i}.csv").exists() for m in SENS_METHODS for i in iots):
            ys.append(y)
    return ys


def collect(folder, years, iot):
    out = {}
    for m in SENS_METHODS:
        frames = [read(folder, m, y, iot) for y in years]
        out[m] = pd.concat(frames, ignore_index=True) if frames and all(f is not None for f in frames) else None
    return out


def season_sum(df, col):
    """Seasonal columns repeat on every day: one value per year is taken."""
    return float(df.groupby("year")[col].first().sum())


def row_for(case, folder_phys, folder_iot, years):
    phys = collect(folder_phys, years, "phys"); iot = collect(folder_iot, years, "iot")
    rows = []
    for m in SENS_METHODS:
        p, q = phys[m], iot[m]
        r = {"case": case, "method": m, "years": len(years),
             "lam_phys": p["lambda"].mean(), "lam_iot": q["lambda"].mean()}
        if m == "LXB":
            lp = p.set_index(["year", "date"])["lambda"]; li = q.set_index(["year", "date"])["lambda"]
            ok = lp > 0
            pi = ((lp - li) / lp)[ok]
            r["pi1"] = float(pi.mean()); r["pi1_median"] = float(pi.median())
            r["pi1_ratio"] = float((lp.mean() - li.mean()) / lp.mean())
            r["pi1_extreme_days"] = int((pi.abs() > 1).sum())
        for b in ("B0", "B3"):
            if m == "LXB":
                for v, d in (("iot", iot), ("phys", phys)):
                    r[f"d_{b}_{v}"] = float((d["LXB"]["lambda"].to_numpy() - d[b]["lambda"].to_numpy()).mean())
        means = {u: q[f"r_{u}"].mean() for u in USERS}
        worst = min(means, key=means.get)
        r["r_min_user"] = f"{worst} {means[worst]:.3f}"
        steps = 96 * len(q)
        r["radio_off_share"] = season_sum(q, "radio_off_steps") / steps
        r["battery_min_wh"] = float(q.groupby("year").battery_min_wh.first().min()) \
            if q.battery_min_wh.notna().any() else np.nan
        sent = season_sum(q, "messages")
        r["dropped_share"] = season_sum(q, "dropped") / sent if sent > 0 else np.nan
        r["lp_fallbacks"] = season_sum(q, "lp_fallbacks") + season_sum(p, "lp_fallbacks")
        rows.append(r)
    return rows


def main():
    global BASE, SENS
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(BASE)); ap.add_argument("--sens", default=str(SENS))
    ap.add_argument("--out", default=str(ROOT / "results/sensitivity_summary"))
    a = ap.parse_args()
    BASE, SENS = Path(a.base), Path(a.sens)
    rows = []
    cases = [c for c in SENSITIVITY if (SENS / c).exists()]
    if not cases:
        sys.exit("No results in results/sensitivity; run run_experiment.py --sensitivity first")
    for c in cases:
        iots = SENSITIVITY[c]
        folder_phys = SENS / c if "phys" in iots else BASE
        ys = [y for y in years_of(SENS / c, iots) if all(read(folder_phys, m, y, "phys") is not None
                                                          for m in SENS_METHODS)]
        if not ys:
            print(f"{c}: no complete year, skipped"); continue
        rows += row_for(c, folder_phys, SENS / c, ys)
        # baseline over the same years; the case label is data matched by fig_results.py
        rows += row_for(f"normal ({c} seasons)", BASE, BASE, ys)
    t = pd.DataFrame(rows)
    t.to_csv(a.out + ".csv", index=False)
    lines = ["| Case | Method | Years | λ phys | λ IoT | Π1 (ratio of means) | Π1 median | LXB−B0 IoT | LXB−B3 IoT | "
             "Lowest r (IoT) | Radio off | Battery min, Wh | Message loss |", "|" + "---|" * 13]
    for _, r in t.iterrows():
        f = lambda k, fmt="{:+.4f}": fmt.format(r[k]) if k in r and pd.notna(r[k]) else ""
        lines.append(f"| {r.case} | {r.method} | {r.years} | {r.lam_phys:.4f} | {r.lam_iot:.4f} | {f('pi1_ratio', '{:.4f}')} | {f('pi1_median', '{:.4f}')} | "
                     f"{f('d_B0_iot')} | {f('d_B3_iot')} | {r.r_min_user} | {r.radio_off_share:.3%} | "
                     f"{f('battery_min_wh', '{:.0f}')} | {f('dropped_share', '{:.2%}')} |")
    Path(a.out + ".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"-> {a.out}.csv, {a.out}.md")


if __name__ == "__main__":
    main()
