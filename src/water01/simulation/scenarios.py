"""Sections 2.1 and 2.10: configuration (YAML) and input data.

- load_config: configs/kegeyli_reference.yaml + configs/scenarios/<name>.yaml (domain.config);
- loading of supply S(t), decadal limit S^lim and demand D_j[p], with unit checks;
- daily_arrays: daily volume arrays for the selected days.
"""
import calendar
from pathlib import Path

import numpy as np
import pandas as pd

from ..domain.config import activate, load

def load_config(path=None, scenario=None):
    """Loads and activates the configuration: reference YAML (path; None means configs/kegeyli_reference.yaml) +
    scenario (configs/scenarios/<name>.yaml). Returns domain.config.Config, whose values can also be read as
    attributes (cfg.epsilon_1, cfg.seed, ...). All modules read from this active configuration."""
    return activate(load(path, scenario))


# --- input data
SECONDS_PER_DAY = 86_400.0


def decade_of(day):
    return 1 if day <= 10 else (2 if day <= 20 else 3)


def load_supply(path, vegetation_months=(4, 5, 6, 7, 8, 9), blank_policy=None):
    """Daily discharge at the head regulator (m3/s). Blank cells (flagged in a separate column) are filled according
    to supply_blank_days in the configuration: zero -> 0 (assumed, base case); carry_forward -> the nearest earlier
    recorded value in the same season, or the first later recorded value for blank days at the start of the season
    (sensitivity case)."""
    if blank_policy is None:
        try:
            from ..domain.passport import value
            blank_policy = value("supply_blank_days")
        except Exception:                                   # no active configuration (standalone loading)
            blank_policy = "zero"
    df = pd.read_csv(path, parse_dates=["date"])
    if "kegeyli_Q" not in df:
        raise ValueError("Column kegeyli_Q is missing")
    df = df[df.date.dt.month.isin(vegetation_months)].copy()
    df["supply_blank_assumed_zero"] = df.kegeyli_Q.isna()
    if blank_policy == "zero":
        df["S_m3s"] = df.kegeyli_Q.fillna(0.0)
    elif blank_policy == "carry_forward":
        g = df.groupby(df.date.dt.year).kegeyli_Q
        df["S_m3s"] = g.ffill().fillna(g.bfill()).fillna(0.0)
    else:
        raise ValueError(f"Unknown supply_blank_days: {blank_policy}")
    if (df.S_m3s < 0).any():
        raise ValueError("Negative supply found")
    df["month"] = df.date.dt.month
    df["decade"] = df.date.dt.day.map(decade_of)
    return df[["date", "month", "decade", "S_m3s", "supply_blank_assumed_zero"]].reset_index(drop=True)


def derive_limit(supply):
    """S^lim: mean discharge for each (month, decade) over 2010-2019, m3/s (derived)."""
    return supply.groupby(["month", "decade"], as_index=False).S_m3s.mean().rename(columns={"S_m3s": "S_lim_m3s"})


def load_limit_2021(path):
    """Alternative limit: official 2021 decadal profile, m3/s (observed)."""
    df = pd.read_csv(path)
    if "limit_Q_m3s" not in df:
        raise ValueError("Column limit_Q_m3s is missing")
    return df.rename(columns={"limit_Q_m3s": "S_lim_m3s"})[["month", "decade", "S_lim_m3s"]]


def load_demand(path, variant="A"):
    """Decadal demand at the node: q_mean_m3s is the decade-mean discharge (derived, including η)."""
    df = pd.read_csv(path)
    required = {"variant", "month", "decade", "j", "user", "share", "D_mln_m3", "q_mean_m3s"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Demand columns missing: {sorted(missing)}")
    out = df[df.variant.eq(variant)].copy()
    if out.empty:
        raise ValueError(f"Variant {variant} not found")
    # unit check: volume = discharge × days × 86400
    days = out.apply(lambda r: 10 if r.decade < 3 else calendar.monthrange(2021, int(r.month))[1] - 20, axis=1)
    if not np.allclose(out.D_mln_m3, out.q_mean_m3s * days * SECONDS_PER_DAY / 1e6, rtol=2e-3, atol=1e-3):
        raise ValueError("Demand volume and discharge are inconsistent")
    return out.reset_index(drop=True)


def daily_arrays(supply, demand, limit, dates, eta):
    """Arrays for the selected days (daily volume, m3):
    D [J×P] demand; A [P] water actually arriving at the node (η·S); A_lim [P] water expected from the limit
    (η·S^lim)."""
    sup = supply.set_index("date").loc[dates]
    J = int(demand.j.max())
    D = np.zeros((J, len(dates)))
    for p, dt in enumerate(dates):
        dec = demand[(demand.month == dt.month) & (demand.decade == decade_of(dt.day))].sort_values("j")
        D[:, p] = dec.q_mean_m3s.to_numpy() * SECONDS_PER_DAY
    from ..domain.passport import value
    D *= eta / value("demand_eta_reference")                   # Equation (1): D ∝ η; file derived at reference η
    A = eta * sup.S_m3s.to_numpy() * SECONDS_PER_DAY
    lim = limit.set_index(["month", "decade"]).S_lim_m3s
    A_lim = np.array([eta * lim.loc[(dt.month, decade_of(dt.day))] * SECONDS_PER_DAY for dt in dates])
    return D, A, A_lim


# --- IoT scenarios (Sections 2.6-2.7), by Shapley factor
IOT_FACTORS = ("sensor", "quantisation", "communication", "energy")
AVAILABLE_FACTORS = IOT_FACTORS                                    # energy: NASA POWER (DATA/raw/nasa_power)


def iot_scenario(cfg, factors=IOT_FACTORS, sensor=None):
    """IoTConfig for the set of active IoT constraints F ⊆ {S, Q, C, E}. F = ∅ is phys (ideal) execution.
    Sensor: datasheet values (configuration: iot.devices); quantisation/budget: from the configuration."""
    from ..iot.devices import devices
    from .plant_loop import IoTConfig
    factors = set(factors)
    unknown = factors - set(IOT_FACTORS)
    if unknown:
        raise ValueError(f"Unknown factor: {sorted(unknown)}")
    dev = devices()[sensor or cfg.sensor]
    kw = {}
    if "sensor" in factors:
        kw.update(sensor_accuracy_m=dev.accuracy_m, sensor_resolution_m=dev.resolution_m)
    if "quantisation" in factors:
        kw.update(gate_resolution=cfg.gate_resolution_fraction, gate_deadband=cfg.gate_deadband_fraction)
    if "communication" in factors:
        kw.update(message_window_steps=cfg.message_window_steps, message_budget=cfg.message_budget_per_window,
                  loss_probability=cfg.loss_probability)
    if "energy" in factors:
        kw.update(energy=True)
    return IoTConfig(estimator_blend=cfg.estimator_blend, **kw)
