"""Helpers shared by the analysis scripts: run tables, quanta of the regulators, daily water at the node."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from water01.domain.passport import USERS, value  # noqa: E402
from water01.hydraulics.node import DustlikNode  # noqa: E402
from water01.simulation.scenarios import (daily_arrays, derive_limit, load_config, load_demand,  # noqa: E402
                                          load_supply)

REGULATORS = tuple(USERS[:5])
RUNS = ROOT / "results/runs"
OUT = ROOT / "results/analysis"
SUP = ROOT / "DATA/processed/rashod_2010_2019_daily.csv"
DEM = ROOT / "DATA/processed/demand_decadal.csv"
YEARS = tuple(range(2010, 2020))


def load(case, method, years=YEARS):
    """Daily rows of all stored seasons of (case, method)."""
    frames = []
    for y in years:
        f = RUNS / case / f"{method}_{y}.csv"
        if f.exists():
            frames.append(pd.read_csv(f, parse_dates=["date"]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def available(case="phys"):
    """Seasons for which a result exists."""
    return sorted({int(p.stem.split("_")[-1]) for p in (RUNS / case).glob("*.csv")})


class Quanta:
    """Step volumes of the five regulators in the plant of a scenario: one resolution step v(h), quantum q(h) = k v(h),
    pulse p(h) = (k + 1) v(h); gate relation (2) of the article with the configured gate coefficient, gates that
    seal."""

    def __init__(self, scenario="normal"):
        self.cfg = load_config(scenario=scenario)
        self.k = int(math.ceil(value("gate_deadband_fraction") / value("gate_resolution_fraction") - 1e-9))
        self.res = float(value("gate_resolution_fraction"))
        self.deadband = float(value("gate_deadband_fraction"))
        self.dt = float(value("dt_s"))
        self.node = DustlikNode()
        self.amax = np.asarray(self.node.max_opening, float)[:5]

    def volume(self, h, steps):
        a = steps * self.res * self.amax
        return np.asarray(self.node.offtakes(float(h), a), float) * self.dt

    def v(self, h):
        return self.volume(h, 1)

    def q(self, h):
        return self.volume(h, self.k)

    def p(self, h):
        return self.volume(h, self.k + 1)

    def table(self, h_values):
        """Quanta at an array of levels: dict of arrays [len(h) x 5]."""
        h_values = np.asarray(h_values, float)
        return {name: np.array([getattr(self, name)(h) for h in h_values]) for name in ("v", "q", "p")}


def node_water(year, scenario="normal"):
    """Daily water at the node A = eta S day (m3) and daily demand D [6 x P] of a season (as in the closed loop)."""
    cfg = load_config(scenario=scenario)
    supply = load_supply(SUP)
    demand = load_demand(DEM, cfg.demand_variant)
    supply = supply.assign(S_m3s=supply.S_m3s * value("supply_scale"))
    dates = pd.date_range(f"{year}-{cfg.season_start}", periods=cfg.season_days, freq="D")
    D, A, _ = daily_arrays(supply, demand, derive_limit(supply), dates, value("eta"))
    return dates, np.asarray(A, float), np.asarray(D, float)


def regulator_days(df, quanta, users=REGULATORS):
    """Long table: one row per (season day, regulator) with plan, executed target, volumes and day quanta."""
    rows = []
    hmin = df["h_min"].to_numpy(); hmax = df["h_max"].to_numpy()
    qmin = np.array([quanta.q(h) for h in hmin]); qmax = np.array([quanta.q(h) for h in hmax])
    pmax = np.array([quanta.p(h) for h in hmax]); vmax = np.array([quanta.v(h) for h in hmax])
    # step volumes at the levels estimated by the controller (equal to the above when the level is exact): the
    # bounds for the estimated volumes use the information of the controller
    hest = df["h_est_max"].to_numpy() if "h_est_max" in df else hmax
    pmax_e = np.array([quanta.p(h) for h in hest]); vmax_e = np.array([quanta.v(h) for h in hest])
    for j, u in enumerate(users):
        part = pd.DataFrame({
            "year": df["year"].to_numpy(), "date": df["date"].to_numpy(), "user": u, "j": j,
            "D": df[f"D_{u}"].to_numpy(), "x": df[f"x_{u}"].to_numpy(), "xt": df[f"xt_{u}"].to_numpy(),
            "V": df[f"V_{u}"].to_numpy(), "Vhat": df[f"Vhat_{u}"].to_numpy(), "open": df[f"open_{u}"].to_numpy(),
            "pulses": df[f"pulses_{u}"].to_numpy(), "esopen": df[f"esopen_{u}"].to_numpy(),
            "m": df[f"m_{u}"].to_numpy(), "mode": df[f"mode_{u}"].to_numpy(),
            "q_min": qmin[:, j], "q_max": qmax[:, j], "p_max": pmax[:, j], "v_max": vmax[:, j],
            "p_max_est": pmax_e[:, j], "v_max_est": vmax_e[:, j]})
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def markdown(df, floatfmt=".4g"):
    """Plain Markdown table without external dependencies."""
    cols = list(df.columns)

    def fmt(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else format(float(v), floatfmt)
        return str(v)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"
