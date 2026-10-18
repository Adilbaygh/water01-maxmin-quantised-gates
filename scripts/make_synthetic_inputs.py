"""Synthetic input files for running the model without the operating records of the irrigation system.

The processed operating records (DATA/processed/*.csv) are third-party data and are not part of the public repository.
This script writes files with the same structure to DATA/synthetic/, so that the tests, the demonstration runs and the
graphical interface can be used without them. The values are generated and are NOT the records of the Kegeyli canal:
results obtained with them differ from those of the article.

- supply_daily.csv: daily head discharge kegeyli_Q, m3/s, April-September 2010-2019. A seasonal curve is scaled by a
  random factor per year (two low-supply years), held piecewise constant over operating regimes of 3-10 days, and
  rounded to whole m3/s; three days at the start of some seasons and two at the end of every season are left blank, as in the records.
- demand_decadal.csv: decadal demand at the Dustlik node for the variants A, B and C. The seasonal volume of each
  outlet equals the published value (Table S3 of the Supplementary Materials); the distribution over the decades
  follows a generic crop-water curve. As in the records, the smallest outlet (R-1) has a very small demand in the
  first decade of April.

Usage: python scripts/make_synthetic_inputs.py [--seed 7]
"""
import argparse
import calendar
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "DATA" / "synthetic"

USERS = ["Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli"]
# seasonal demand at the node, 10^6 m3 (Supplementary Materials, Table S3)
SEASONAL = {"A": [70.6, 0.41, 2.19, 10.7, 3.53, 483.2],
            "B": [116.1, 0.38, 1.99, 9.72, 3.21, 439.2],
            "C": [156.1, 1.63, 3.25, 13.0, 6.50, 390.1]}
# relative crop-water demand of the 18 decades of April-September
SHAPE = np.array([0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.95, 1.05, 1.15,
                  1.25, 1.30, 1.25, 1.15, 1.05, 0.90, 0.70, 0.50, 0.35])
R1_FIRST_DECADE = 0.01                    # R-1: demand of the first decade of April relative to the generic curve
MONTHS = (4, 5, 6, 7, 8, 9)


def decade_days(year, month, decade):
    return 10 if decade < 3 else calendar.monthrange(year, month)[1] - 20


def demand_table():
    rows = []
    days = np.array([decade_days(2021, m, d) for m in MONTHS for d in (1, 2, 3)], float)
    for v, totals in SEASONAL.items():
        q = np.zeros((6, 18))
        for j, total in enumerate(totals):
            w = SHAPE.copy()
            if j == 1:
                w[0] *= R1_FIRST_DECADE
            q[j] = total * 1e6 * w / float((w * days * 86400.0).sum())
        k = 0
        for m in MONTHS:
            for d in (1, 2, 3):
                share = q[:, k] / q[:, k].sum()
                for j in range(6):
                    qq = round(float(q[j, k]), 6)
                    rows.append(dict(variant=v, month=m, decade=d, days=int(days[k]), j=j + 1, user=USERS[j],
                                     share=round(float(share[j]), 5), D_mln_m3=round(qq * days[k] * 86400 / 1e6, 6),
                                     q_mean_m3s=qq))
                k += 1
    return pd.DataFrame(rows)


def supply_table(seed):
    rng = np.random.default_rng(seed)
    frames = []
    year_factor = rng.lognormal(0.0, 0.18, 10)
    year_factor[[1, 8]] = [0.55, 0.62]                         # two low-supply seasons (2011 and 2018)
    for i, year in enumerate(range(2010, 2020)):
        dates = pd.date_range(f"{year}-04-01", f"{year}-09-30", freq="D")
        t = np.linspace(0.0, 1.0, len(dates))
        base = 28.0 + 52.0 * np.sin(np.pi * np.clip(t * 1.05, 0, 1)) ** 1.5
        q = np.empty(len(dates))
        p = 0
        while p < len(dates):                                  # operating regimes of 3-10 days
            n = int(rng.integers(3, 11))
            q[p:p + n] = base[p] * year_factor[i] * rng.uniform(0.85, 1.15)
            p += n
        q = np.round(np.clip(q, 0.0, 150.0))
        if year % 3 == 1:                                      # blank entries at the start of some seasons
            q[:3] = np.nan
        q[-2:] = np.nan                                        # and at the end of every season
        frames.append(pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "kegeyli_Q": q}))
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    supply_table(args.seed).to_csv(OUT / "supply_daily.csv", index=False)
    demand_table().to_csv(OUT / "demand_decadal.csv", index=False)
    print(f"-> {OUT.relative_to(ROOT).as_posix()}/supply_daily.csv, demand_decadal.csv (synthetic, seed {args.seed})")


if __name__ == "__main__":
    main()
