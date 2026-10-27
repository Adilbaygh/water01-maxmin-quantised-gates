"""Section 2.10: running the methods on identical scenarios.

- run_closed_loop_period: main path, controller -> gates -> Dustlik node -> Saint-Venant plant ->
  measurement -> state estimate -> controller (simulation.plant_loop). Metrics use the true (plant) volumes.
- run_smoke: static daily allocation without hydraulics. Code check only; not used as a result.
"""
import numpy as np
import pandas as pd

import dataclasses
import math

from ..control import CONTROLLERS, Demand, Horizon, b3_proportional, lxb_receding, oracle
from ..control.model import ControllerModel
from ..domain.geometry import Reach
from ..domain.passport import PARAMETERS, optional, value
from ..evaluation.metrics import compute
from ..hydraulics.node import DustlikNode, untuned_factors
from ..optimization.constraints import command_limit, lower_to_function
from ..optimization.lexlp import reset_warm_start
from .plant_loop import IoTConfig, run_closed_loop
from .scenarios import SECONDS_PER_DAY, daily_arrays, derive_limit, load_demand, load_limit_2021, load_supply


def run_smoke(supply_csv, demand_csv, start="2018-07-01", days=10, variant=None, horizon_days=None,
              epsilon_1=None, epsilon_2=None):
    variant = value("demand_variant") if variant is None else variant
    horizon_days = value("horizon_days") if horizon_days is None else horizon_days
    epsilon_1 = value("epsilon_1") if epsilon_1 is None else epsilon_1
    epsilon_2 = value("epsilon_2") if epsilon_2 is None else epsilon_2
    supply = load_supply(supply_csv)
    demand = load_demand(demand_csv, variant)
    limit = derive_limit(supply)
    dates = pd.date_range(start, periods=days, freq="D")
    eta = PARAMETERS["eta"].value
    D, A, A_lim = daily_arrays(supply, demand, limit, dates, eta)
    U = np.array(PARAMETERS["outlet_capacity_m3s"].value)[:, None] * SECONDS_PER_DAY * np.ones((1, days))
    runs = {
        "B3": b3_proportional(D, A, U),
        "LXB": lxb_receding(D, A, A_lim, U, horizon_days=horizon_days, epsilon_1=epsilon_1, epsilon_2=epsilon_2),
        "Oracle": oracle(D, A, U, epsilon_1=epsilon_1, epsilon_2=epsilon_2),
    }
    out = {"period": f"{dates[0].date()}…{dates[-1].date()}", "days": days, "users": D.shape[0],
           "supply_at_node_m3s": [round(a / SECONDS_PER_DAY, 2) for a in A],
           "demand_at_node_m3s": [round(d / SECONDS_PER_DAY, 2) for d in D.sum(axis=0)],
           "note": "STATIC daily allocation without hydraulics — code check only, NOT a result (see run_closed_loop_period)", "methods": {}}
    for name, x in runs.items():
        if (x.sum(axis=0) > A + 1e-6).any():
            raise AssertionError(f"{name}: allocated more than the available water")
        m = compute(x, D)
        out["methods"][name] = {"lambda": round(m["lambda"], 4), "Z2": round(m["Z2"], 3), "Z3": round(m["Z3"], 4),
                                "used_share": round(float(x.sum() / A.sum()), 4) if A.sum() > 0 else None}
    return out



def build_controller_model(node_model, cfg, dt=None):
    """ControllerModel: ID model (8) with A_s and d identified from the SV plant; (9) from the controller's model of
    the node (regulators: chords, check structure: tangent); level bounds from the configuration
    (H_min^op, H_max − f_b). All values are taken from the active configuration."""
    dt = value("dt_s") if dt is None else dt
    bp = np.array(value("command_breakpoints_m"))
    f = np.array([node_model.max_flows(h) for h in bp])          # [M × 6]
    h_ref, dh = value("H_norm_m"), 1e-3
    f_ref = node_model.max_flows(h_ref)
    slope = (node_model.max_flows(h_ref + dh) - node_model.max_flows(h_ref - dh)) / (2 * dh)
    chord_set = []
    for j in range(6):
        if j < 5:
            # regulators: the discharge vanishes at the tail-water level, so the chords start there (value 0); the
            # breakpoints below it and within 5 cm above it are dropped. The interpolant is then conservative from the
            # tail-water level upwards, and below it the first chord is negative (no command is feasible without slack)
            tw = node_model.tailwater_m[j]
            bj = np.r_[tw, bp[bp > tw + 0.05]]
            fj = np.r_[0.0, f[bp > tw + 0.05, j]]
            alpha, beta = command_limit(bj, fj, h_ref, f_ref[j], slope[j])
            grid = np.linspace(tw, bj[-1], 401)
        else:
            # barrier: the tail water rises with the discharge, so f_6 is convex over most of the range and its
            # tangent at H_norm lies below it; where the gates leave the water, the flow height is limited by the
            # depth, which can make f_6 locally concave (e.g. with a smoother lower reach), so the tangent is checked
            # on a dense grid as well
            alpha, beta = command_limit(bp, f[:, j], h_ref, f_ref[j], slope[j], mixed="tangent")
            grid = np.linspace(bp[0], bp[-1], 441)
        true = np.array([node_model.max_flows(x)[j] for x in grid])
        # Below the gate height the full-gate discharge is not concave (the flow height of a gate raised clear of the
        # water grows with the depth), so a line may exceed it between breakpoints: each line that is the active
        # minimum where the bound exceeds the discharge is lowered by its largest excess there.
        alpha = lower_to_function(alpha, beta, grid, true)
        beta = np.asarray(beta, float)
        chord_set.append((alpha, beta))
        lim = np.min(alpha[:, None] + beta[:, None] * grid[None, :], axis=0)
        if np.any(lim > true + 1e-9):
            raise ValueError(f"command constraint (9) of outlet {j + 1} is not conservative")
    cap = np.array(value("outlet_capacity_m3s"), float)
    return ControllerModel(
        dt=dt, eta=value("eta"), A_s=value("A_s_identified_m2"),
        d=math.ceil(value("tau_identified_s") / dt - 1e-12), chords=chord_set, capacity=cap,
        h_lo=cfg.h_min_operating_m, h_hi=value("H_max_m") - cfg.freeboard_m, h_ref=value("H_norm_m"),
        dq_max=value("gate_rate_fraction_per_step") * cap, epsilon_1=cfg.epsilon_1, epsilon_2=cfg.epsilon_2,
        max_flows=node_model.max_flows)


def pulse_flow_for(node_model, iot):
    """LXB-DA: regulator discharge at the smallest opening that the actuator always executes (deadband plus one
    resolution step, as a fraction of the travel). None when the actuator is not quantised (ideal execution), so
    that LXB-DA coincides with LXB under ideal execution."""
    if iot is None or iot.gate_resolution is None:
        return None
    a_db = (iot.gate_deadband + iot.gate_resolution) * np.asarray(node_model.max_opening, float)
    return lambda h: np.r_[node_model.offtakes(h, a_db[:5]), 0.0]


LIMIT_2021 = "DATA/processed/limit_2021_kegeyli_decadal.csv"


def select_limit(supply, year=None):
    """Forecast S^lim (configuration: limit_source). decadal_mean_2010_2019: base case (derived);
    limit_2021: official 2021 decadal limit (observed; sensitivity case limit_2021);
    decadal_mean_loo: 9-year decadal mean excluding the evaluated year (so that the forecast does not contain the
    year itself; year is required)."""
    src = value("limit_source")
    if src == "decadal_mean_2010_2019":
        return derive_limit(supply)
    if src == "decadal_mean_loo":
        if year is None:
            raise ValueError("year is required for decadal_mean_loo")
        rest = supply[supply.date.dt.year != int(year)]
        if rest.empty or rest.date.dt.year.nunique() == supply.date.dt.year.nunique():
            raise ValueError(f"decadal_mean_loo: year {year} is not in the data")
        return derive_limit(rest)
    if src == "limit_2021":
        from ..domain.config import ROOT
        return load_limit_2021(ROOT / LIMIT_2021)
    raise ValueError(f"Unknown limit_source: {src}")


def run_closed_loop_period(method, supply_csv, demand_csv, cfg, start, days, tuned=True, iot=None, eta_true=None,
                           seed=0, dt=None, reach=None, h_init=None, progress=None):
    """Runs one method (a key of CONTROLLERS) in closed loop with the Saint-Venant plant.
    cfg: active configuration (scenarios.load_config). eta_true: true η in the plant (the controller knows the
    nominal η); None means equal to nominal. dt, h_init: from the configuration if None. The supply is multiplied
    by supply_scale (scenario), whereas the limit forecast comes from the historical record (unchanged)."""
    reset_warm_start()                                         # each run starts its LP solves from scratch
    dt = value("dt_s") if dt is None else dt
    supply = load_supply(supply_csv); demand = load_demand(demand_csv, cfg.demand_variant)
    # the limit forecast is always derived from the record with blank entries as zero, so that a scenario that fills
    # blank entries changes the realised supply only
    limit = select_limit(load_supply(supply_csv, blank_policy="zero"), pd.Timestamp(start).year)
    supply = supply.assign(S_m3s=supply.S_m3s * value("supply_scale"))
    dates = pd.date_range(start, periods=days, freq="D")
    eta = value("eta")
    if eta_true is None:                                       # plant/controller mismatch of η (sensitivity case)
        eta_true = optional("eta_true", eta)
    D, A, A_lim = daily_arrays(supply, demand, limit, dates, eta)
    cd_factor, offtake_factor = untuned_factors(tuned)
    rating = optional("outlet_rating_factors")                 # outlet-specific rating error (sensitivity case)
    # gate relation of the small regulators in the plant and in the controller's model, and gate leakage in the
    # plant (scenario additions; default: relation (6) in both, gates that seal)
    node_true = DustlikNode(offtake_factor=offtake_factor if rating is None
                            else offtake_factor * np.asarray(rating, float),
                            relation=optional("gate_relation_plant", "submerged"),
                            leak_opening_m=float(optional("gate_leakage_opening_m", 0.0)))
    node_model = DustlikNode(cd=value("gate_cd") * cd_factor, relation=optional("gate_relation_controller", "submerged"))
    model = dataclasses.replace(build_controller_model(node_model, cfg, dt), pulse_flow=pulse_flow_for(node_model, iot))
    horizon = Horizon.from_config()
    if horizon.steps_per_day * dt != SECONDS_PER_DAY:
        raise ValueError("dt and steps_per_day are inconsistent")
    ctrl = CONTROLLERS[method]()
    S = supply.set_index("date").loc[dates].S_m3s.to_numpy()
    pv = None
    if iot is not None and iot.energy:                         # (16): NASA POWER hourly irradiance -> PV energy
        from ..iot.energy import load_nasa_power, pv_energy_per_step
        pv = pv_energy_per_step(load_nasa_power(dates), dt)
    demand = Demand(D, np.asarray(value("weights"), float))   # configured user weights w_j
    res = run_closed_loop(ctrl, reach or Reach(), node_true, node_model, model, horizon, demand, S, A_lim,
                          eta_true, value("h_init_m") if h_init is None else h_init, iot, seed,
                          cfg.preissmann_theta, progress, pv)
    met = compute(res.delivered, D)
    return {"method": method, "period": f"{dates[0].date()}…{dates[-1].date()}", "tuned": tuned,
            "ideal_iot": (iot or IoTConfig()).ideal, "lambda": met["lambda"], "lambda_daily": met["lambda_daily"],
            "Z2": met["Z2"], "Z3": met["Z3"], "storage_change_m3": res.storage_change_m3,
            "storage_change_share": res.storage_change_m3 / max(float(A.sum()), 1.0), "D": D, "result": res}
