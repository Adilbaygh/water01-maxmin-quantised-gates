"""Closed loop: B0, B1, B2, B3, LXB and Oracle run on the Saint–Venant plant under the same scenario (Section 2.10).

Usage:  python scripts/run_closed_loop.py [start date] [number of days] [scenario]   (example: 2018-07-01 10 normal)
Scenarios: configs/scenarios/*.yaml (normal, low_supply, communication_loss, sensor_udl, design_geometry).
Settings: tuned and untuned, IoT constraints disabled ("phys" execution). Some parameters are assumed (C_d,
downstream levels of the regulators, gate speed); the output is preliminary and is not a hypothesis test.
Output: results/closed_loop_<start>_<days>.csv (daily λ[p] and user satisfaction r_j[p]).
ΔV is the change of pool storage (end − start of the period) relative to the expected volume: a negative value
means that the method has "borrowed" from the pool, which can inflate λ artificially over short windows.
"""
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.passport import USERS  # noqa: E402
from water01.optimization.objectives import satisfaction  # noqa: E402
from water01.simulation.provenance import config_inputs, write_metadata  # noqa: E402
from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402


DATA = ("DATA/processed/rashod_2010_2019_daily.csv", "DATA/processed/demand_decadal.csv")


def main(start="2018-07-01", days=10, scenario="normal"):
    cfg = load_config(scenario=scenario)
    print(f"Scenario: {cfg.scenario}")
    rows = []
    for method in ("B0", "B1", "B2", "B3", "LXB", "Oracle"):
        for tuned in (True, False):
            t0 = time.time()
            out = run_closed_loop_period(method, ROOT / "DATA/processed/rashod_2010_2019_daily.csv",
                                         ROOT / "DATA/processed/demand_decadal.csv", cfg, start, days, tuned=tuned)
            res = out["result"]; r = satisfaction(res.delivered, out["D"])
            h = res.trace["h_true"]
            print(f"{method:6s} {'tuned  ' if tuned else 'untuned'} λ = {out['lambda']:.4f}  Z2 = {out['Z2']:.3f}  "
                  f"Z3 = {out['Z3']:.3f}  h_L ∈ [{h.min():.2f}, {h.max():.2f}] m  "
                  f"ΔV = {100 * out['storage_change_share']:+.2f} %  "
                  f"commands lost = {int(res.command_lost_steps.sum())}  "
                  f"mass error = {res.mass_error:.0e}  ({time.time() - t0:.0f} s)")
            dates = pd.date_range(start, periods=days, freq="D")
            for p in range(days):
                row = {"method": method, "tuned": tuned, "date": dates[p].date(), "lambda": out["lambda_daily"][p],
                       "storage_change_share_period": out["storage_change_share"],
                       "h_min": h[p * 96:(p + 1) * 96].min(), "h_max": h[p * 96:(p + 1) * 96].max()}
                row.update({f"r_{u}": r[j, p] for j, u in enumerate(USERS)})
                rows.append(row)
    (ROOT / "results").mkdir(exist_ok=True)
    tag = "" if cfg.scenario == "normal" else f"_{cfg.scenario}"
    out_csv = ROOT / f"results/closed_loop_{start}_{days}{tag}.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    meta = write_metadata(out_csv, ROOT, config_inputs(cfg, ROOT) + DATA, {"start": start, "days": days, "iot": "off"},
                          cfg)
    print(f"-> {out_csv.relative_to(ROOT)}, {meta.relative_to(ROOT)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0] if len(a) > 0 else "2018-07-01", int(a[1]) if len(a) > 1 else 10, a[2] if len(a) > 2 else "normal")
