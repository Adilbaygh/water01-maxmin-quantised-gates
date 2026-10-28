"""Computations of the theory tab, independent of the graphical toolkit: step volumes of the regulators in the plant
(scripts/analysis_common.py) and the execution rules on the abstract actuator (src/quantmaxmin/execution.py) at a
constant level, as in Section 2 of the article."""
from __future__ import annotations

import math

import numpy as np

from .project import CORE_LOCK, add_import_paths

add_import_paths()

SCENARIOS = ("normal", "deadband_low", "deadband_high", "gate_cd_low", "gate_cd_high")


def step_volumes(scenario: str, h: float) -> dict:
    """Step volumes of the five regulators at the level h (m): one resolution step v, the quantum q = k v, the pulse
    p = (k + 1) v and the volume C of one step of the fully open gate, or of the outlet at its capacity if that is
    less. All volumes in m3 per control step."""
    from analysis_common import REGULATORS, Quanta
    from water01.domain.passport import value
    with CORE_LOCK:
        qa = Quanta(scenario)                                      # activates the scenario
        cap = np.asarray(value("outlet_capacity_m3s"), float)[:5]
        full = np.asarray(qa.node.max_flows(float(h)), float)[:5]
        out = {"users": list(REGULATORS), "k": qa.k, "resolution": qa.res, "deadband": qa.deadband, "dt": qa.dt,
               "N": int(round(86400.0 / qa.dt)), "n_travel": int(round(1.0 / qa.res)),
               "v": qa.v(h), "q": qa.q(h), "p": qa.p(h), "C": np.minimum(cap, full) * qa.dt}
        Quanta("normal")                                           # leaves the baseline active
    return out


def day_rules(x: float, v: float, k: int, theta: float, N: int, C: float) -> dict:
    """One day at a constant level: delivered volume of direct execution, of the pulse rule with threshold theta and
    of the equal split, with the conditions and bounds of Theorems 1 and 3."""
    from quantmaxmin.execution import (direct_execution_day, equal_split_day, equal_split_m, exclusion_threshold,
                                       theta_rule_day)
    g = [float(v)] * N
    q, p = k * v, (k + 1) * v
    n_max = max(int(math.floor(C / v)), k + 1)
    out = {"x": x, "q": q, "p": p, "v": v, "k": k, "theta": theta, "N": N, "C": C,
           "threshold": exclusion_threshold(q, k), "pulse_capacity": N * p}
    out["direct"] = direct_execution_day(x, g, k, n_max=n_max) if x > 0 else 0.0
    out["excluded_predicted"] = 0 < x < out["threshold"]
    if 0 < x < N * p:
        V, pulses = theta_rule_day(x, g, k, theta)
        out["pulse"], out["pulses"] = V, pulses
        out["pulse_lower"] = x - theta * min(p, x)
        out["pulse_upper"] = x + p
        out["pulse_ok"] = out["pulse_lower"] - 1e-9 <= V < out["pulse_upper"]
    else:
        out["pulse"] = out["pulses"] = None
    m = equal_split_m(x, q, v, C, N) if x > 0 else None
    out["m"] = m
    if m is not None:
        V, ok = equal_split_day(x, g, k, n_max, m)
        out["equal"], out["equal_executed"] = V, ok
        out["equal_ok"] = abs(V - x) <= v / 2 + 1e-9
    else:
        out["equal"] = None
    return out


def delivery_curves(v: float, k: int, theta: float, N: int, C: float, x_max: float, points: int = 241) -> dict:
    """Daily delivery against the daily plan for the three rules (Figure 1(b) of the article)."""
    from quantmaxmin.execution import direct_execution_day, equal_split_day, equal_split_m, theta_rule_day
    xs = np.linspace(0.0, x_max, points)
    g = [float(v)] * N
    q = k * v
    n_max = max(int(math.floor(C / v)), k + 1)
    direct, pulse, equal = [], [], []
    for x in xs:
        direct.append(direct_execution_day(x, g, k, n_max=n_max) if x > 0 else 0.0)
        pulse.append(theta_rule_day(x, g, k, theta)[0] if 0 < x < N * (k + 1) * v else np.nan)
        m = equal_split_m(x, q, v, C, N) if x > 0 else None
        equal.append(equal_split_day(x, g, k, n_max, m)[0] if m is not None else np.nan)
    return {"x": xs, "direct": np.array(direct), "pulse": np.array(pulse), "equal": np.array(equal)}


def carry_over_days(plans, v: float, k: int, theta: float, N: int) -> dict:
    """Theorem 4: daily deliveries of the pulse rule with and without carrying the daily debt to the next day."""
    from quantmaxmin.execution import carry_over, theta_rule_day
    plans = np.asarray(plans, float)
    g = [[float(v)] * N for _ in plans]
    V_co, e, xt = carry_over(plans, g, k, theta)
    V_pr = np.array([theta_rule_day(x, gd, k, theta)[0] if x > 0 else 0.0 for x, gd in zip(plans, g)])
    p = (k + 1) * v
    return {"plan": plans, "V_carry": V_co, "debt": e, "target": xt, "V_pulse": V_pr, "p": p,
            "lower": -p, "upper": theta * p}
