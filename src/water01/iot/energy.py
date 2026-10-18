"""Section 2.6, Equation (16): IoT node battery balance and NASA POWER irradiance.

The solar-battery kit (Zemu ZM-H90S100-N) powers only the sensor, the RTU (UC300) and the radio (UG67 gateway);
the gates are mains-powered. Energy policy (assumed): when the charge falls below B_min + B_res the gateway is
switched off, so there is no radio link (no telemetry or commands) and the RTU runs its local low/high-level rules
on reserve; once the charge returns to the resume level the gateway is switched on again (hysteresis).
"""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ..domain.passport import value


@dataclass
class BatteryState:
    wh: float
    reserve_violations: int = 0
    empty_steps: int = 0


def step(state, pv_wh, controller_wh, message_wh, capacity_wh, b_min_wh, b_reserve_wh, eta_ch, eta_dis):
    """(16): B[k+1] = min{B_max, B + η_ch E_pv − (E_c + E_m)/η_dis}; B ≥ 0 is the physical bound;
    B < B_min + B_res is counted as a reserve violation (the limit is enforced by the policy, not by the plant)."""
    wh = min(capacity_wh, state.wh + eta_ch * pv_wh - (controller_wh + message_wh) / eta_dis)
    empty = wh < 0.0
    wh = max(wh, 0.0)
    viol = wh < b_min_wh + b_reserve_wh
    return BatteryState(wh, state.reserve_violations + int(viol), state.empty_steps + int(empty))


def load_nasa_power(dates, directory=None):
    """NASA POWER hourly ALLSKY_SFC_SW_DWN (Wh m⁻² h⁻¹, local solar time LST) for the given days: [day × 24].
    Files: <directory>/nasa_power_hourly_<year>.csv (POWER API, community=RE). −999 marks a missing value: error."""
    directory = Path(directory or Path(__file__).resolve().parents[3] / value("nasa_power_dir"))
    dates = pd.DatetimeIndex(dates)
    frames = []
    for y in sorted(set(dates.year)):
        f = directory / f"nasa_power_hourly_{y}.csv"
        if not f.exists():
            raise FileNotFoundError(f"NASA POWER file not found: {f}")
        lines = f.read_text(encoding="utf-8").splitlines()
        start = lines.index("-END HEADER-") + 1
        frames.append(pd.read_csv(f, skiprows=start))
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(dict(year=df.YEAR, month=df.MO, day=df.DY))
    g = df.pivot_table(index="date", columns="HR", values="ALLSKY_SFC_SW_DWN")
    missing = dates.difference(g.index)
    if len(missing):
        raise ValueError(f"Days missing from NASA POWER: {list(missing[:3])}…")
    g = g.loc[dates]
    if g.shape[1] != 24 or (g.values < 0).any() or g.isna().any().any():
        raise ValueError("NASA POWER hourly series contains missing (−999) or incomplete values")
    return g.to_numpy(float)


def pv_energy_per_step(irradiance_hourly, dt_s, pv_peak_w=None, performance_ratio=None):
    """PV energy per Δt step, Wh: E = P_peak · (G/1000 W m⁻²) · PR · Δt.
    All steps within an hour use the mean irradiance of that hour."""
    pv_peak_w = value("pv_peak_w") if pv_peak_w is None else pv_peak_w
    pr = value("pv_performance_ratio") if performance_ratio is None else performance_ratio
    per_hour = int(round(3600.0 / dt_s))
    g = np.repeat(np.asarray(irradiance_hourly, float).ravel(), per_hour)       # W m⁻² (hourly mean)
    return pv_peak_w * g / 1000.0 * pr * dt_s / 3600.0


@dataclass
class EnergyNode:
    """Energy state and radio policy (16). At each step: load E_c = (P_RTU + P_gw·radio)·Δt, messages E_m."""
    pv_wh: np.ndarray
    dt_s: float
    capacity_wh: float = None
    b_min_wh: float = None
    b_reserve_wh: float = None
    resume_wh: float = None
    eta_ch: float = None
    eta_dis: float = None
    rtu_w: float = None
    gateway_w: float = None
    message_wh: float = None
    state: BatteryState = None
    radio_on: bool = True
    radio_off_steps: int = 0
    min_wh: float = field(default=np.inf)
    used_wh: float = 0.0

    def __post_init__(self):
        cfg = lambda x, k: value(k) if x is None else x
        self.capacity_wh = cfg(self.capacity_wh, "battery_capacity_wh")
        self.b_min_wh = cfg(self.b_min_wh, "battery_min_wh")
        self.b_reserve_wh = cfg(self.b_reserve_wh, "battery_reserve_wh")
        self.resume_wh = cfg(self.resume_wh, "battery_resume_wh")
        self.eta_ch = cfg(self.eta_ch, "battery_eta_ch"); self.eta_dis = cfg(self.eta_dis, "battery_eta_dis")
        self.rtu_w = cfg(self.rtu_w, "rtu_power_w"); self.gateway_w = cfg(self.gateway_w, "gateway_power_w")
        self.message_wh = cfg(self.message_wh, "message_energy_wh")
        if self.resume_wh <= self.b_min_wh + self.b_reserve_wh:
            raise ValueError("battery_resume_wh must exceed B_min + B_res (hysteresis)")
        if self.state is None:
            self.state = BatteryState(value("battery_initial_fraction") * self.capacity_wh)
        self.min_wh = self.state.wh

    def advance(self, k, messages):
        """Energy balance of step k; messages: number of radio messages sent/received at this step.
        Returns whether the radio is on at the next step."""
        load = (self.rtu_w + (self.gateway_w if self.radio_on else 0.0)) * self.dt_s / 3600.0
        msg = self.message_wh * messages
        self.used_wh += load + msg
        self.state = step(self.state, float(self.pv_wh[k]), load, msg, self.capacity_wh, self.b_min_wh,
                          self.b_reserve_wh, self.eta_ch, self.eta_dis)
        self.min_wh = min(self.min_wh, self.state.wh)
        if self.radio_on and self.state.wh < self.b_min_wh + self.b_reserve_wh:
            self.radio_on = False
        elif not self.radio_on and self.state.wh >= self.resume_wh:
            self.radio_on = True
        self.radio_off_steps += int(not self.radio_on)
        return self.radio_on
