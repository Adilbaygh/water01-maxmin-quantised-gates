"""Section 2.8, B0: current practice (proportional/priority allocation + PI level control).

- Regulators: at the start of the day the expected water is divided in proportion to the irrigated area (passport,
  Table 2; with capacity limits); discharges are converted to openings at the nominal level (H_norm) and kept
  constant during the day.
- Check structure: PI control holding the node level at H_norm [9,16], with feedforward
  q_ff = η·Q_in − Σ q_j(plan) and correction K_p·e + (K_p/T_i)·∫e dt, e = ĥ_L − H_norm; the integral has
  anti-windup. Tuning (assumed): closed-loop time constant T_c, K_p = A_s/T_c, T_i = κ·T_c.
No planning, demand or fairness criterion: the allocation depends only on area.
"""
import numpy as np

from ..domain.passport import value
from .interface import Command, Controller


class B0Controller(Controller):
    name = "B0"

    def __init__(self, areas_ha=None, Tc_s=None, kappa=None):
        self.areas = np.asarray(value("irrigated_area_ha") if areas_ha is None else areas_ha, float)
        self.Tc = value("b0_pi_time_constant_s") if Tc_s is None else Tc_s
        self.kappa = value("b0_pi_integral_factor") if kappa is None else kappa
        self.reset()

    def reset(self):
        self.target = None; self.integral = 0.0; self.q_reg = None

    def step(self, state, demand, supply, constraints, horizon):
        m = constraints
        day_s = horizon.steps_per_day * m.dt
        cmd = Command()
        if state.new_day or self.target is None:
            share = self.areas / self.areas.sum()
            self.target = np.minimum(share * supply.available_today, m.daily_capacity(horizon.steps_per_day))
            self.q_reg = self.target[:5] / day_s
            cmd.flows[:5] = self.q_reg
            cmd.conversion_level[:5] = m.h_ref
        Kp = m.A_s / self.Tc; Ti = self.kappa * self.Tc
        e = state.level - m.h_ref
        q_ff = m.eta * supply.inflow_now - self.q_reg.sum()
        q_un = q_ff + Kp * (e + self.integral / Ti)
        q6 = float(np.clip(q_un, 0.0, m.capacity[5]))
        if q6 == q_un or (q6 == 0.0 and e > 0) or (q6 == m.capacity[5] and e < 0):
            self.integral += e * m.dt                            # anti-windup (conditional integration)
        cmd.flows[5] = q6
        cmd.target = self.target.copy(); cmd.info = {"pi_error": e}
        return cmd
