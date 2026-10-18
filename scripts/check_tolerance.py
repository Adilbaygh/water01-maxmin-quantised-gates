"""Check that the ε1 tolerance does not place LXB below B3: 2010–2019, all irrigation-season decades (180).

Daily allocation without hydraulics. Criterion: λ_LXB ≥ λ_B3 − ε_λ in every decade.
Output: results/check_tolerance.csv and a short summary.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.control import b3_proportional, lxb_receding  # noqa: E402
from water01.domain.passport import PARAMETERS  # noqa: E402
from water01.evaluation.metrics import compute  # noqa: E402
from water01.simulation.provenance import config_inputs, write_metadata  # noqa: E402
from water01.simulation.scenarios import (SECONDS_PER_DAY, daily_arrays, derive_limit, load_config,  # noqa: E402
                                          load_demand, load_supply)


def main():
    cfg = load_config()
    supply = load_supply(ROOT / "DATA/processed/rashod_2010_2019_daily.csv")
    demand = load_demand(ROOT / "DATA/processed/demand_decadal.csv", cfg.demand_variant)
    limit = derive_limit(supply)
    eta = PARAMETERS["eta"].value
    cap = np.array(PARAMETERS["outlet_capacity_m3s"].value)[:, None] * SECONDS_PER_DAY
    rows = []
    for (y, m, dec), g in supply.assign(y=supply.date.dt.year).groupby(["y", "month", "decade"]):
        dates = pd.DatetimeIndex(g.date)
        D, A, A_lim = daily_arrays(supply, demand, limit, dates, eta)
        U = cap * np.ones((1, len(dates)))
        lam_b3 = compute(b3_proportional(D, A, U), D)["lambda"]
        lam_lxb = compute(lxb_receding(D, A, A_lim, U, horizon_days=cfg.horizon_days,
                                       epsilon_1=cfg.epsilon_1, epsilon_2=cfg.epsilon_2), D)["lambda"]
        rows.append({"year": y, "month": m, "decade": dec, "lambda_B3": lam_b3, "lambda_LXB": lam_lxb,
                     "diff": lam_lxb - lam_b3})
    df = pd.DataFrame(rows)
    (ROOT / "results").mkdir(exist_ok=True)
    df.to_csv(ROOT / "results/check_tolerance.csv", index=False)
    write_metadata(ROOT / "results/check_tolerance.csv", ROOT,
                   config_inputs(cfg, ROOT) + ("DATA/processed/rashod_2010_2019_daily.csv",
                                               "DATA/processed/demand_decadal.csv"), {"epsilon_1": cfg.epsilon_1}, cfg)
    worst = df["diff"].min()
    print(f"decades: {len(df)}; ε1 = {cfg.epsilon_1:g}; ε_λ = {cfg.epsilon_lambda:g}")
    print(f"λ_LXB − λ_B3: min {worst:.2e}, median {df['diff'].median():.2e}, max {df['diff'].max():.2e}")
    print(f"decades with LXB < B3 − ε_λ: {(df['diff'] < -cfg.epsilon_lambda).sum()}")
    print(f"decades with LXB < B3 − 10·ε1: {(df['diff'] < -10 * cfg.epsilon_1).sum()}")
    print(f"decades with LXB > B3 + 1e-3: {(df['diff'] > 1e-3).sum()}")


if __name__ == "__main__":
    main()
