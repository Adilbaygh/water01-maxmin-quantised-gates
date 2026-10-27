"""Section 2.8, ROT: rotation of the small regulators, the comparator for current practice at small outlets.

When water is short, the small outlets of a node are served in turns rather than by small continuous discharges.
ROT combines this practice with the proportional daily targets of B3 and the PI level control of B0:

- daily targets: proportional rationing of the reported daily supply (B3, with capacity limits);
- Abad-Yarmish (outlet 1): served continuously, with the volume still owed that day divided by the time remaining
  (volume feedback, as B3V) and the pulse rule of LXB-DA for a discharge inside the deadband of a quantised actuator;
- small regulators (outlets 2-5): served one at a time, in the passport order (R-1, Khalkabad-2, Kanly-Yab, K-2).
  The outlet in turn receives its working discharge q_w = min(capacity, max(σ·capacity/f, q_db)) until its daily
  target is delivered, where σ = Σ_j x_j / (capacity_j · day) over the small outlets and f = 0.9, so that the turns
  fill 90% of the day under ideal execution, and q_db is the discharge at the smallest executable opening of a
  quantised actuator
  (0 without quantisation). The last part of a turn is the volume still owed divided by Δt when that is at least
  q_db, and otherwise one step at q_db if at least half of min(q_db·Δt, x_j) is still owed (the pulse rule of
  LXB-DA); the turn then passes to the next outlet (also when less than 1% of one working step is still owed);
- check structure: PI control of the node level at H_norm with the feed-forward of the observed inflow less the
  regulator commands (B0), with conditional integration.
There is no internal model, command constraint (9), linear program or level bound.
"""
import numpy as np

from ..domain.passport import value
from .b3 import B3VController, b3_proportional
from .interface import Command

SMALL = (1, 2, 3, 4)
TURN_FILL = 0.9                 # share of the day filled by the turns under ideal execution (setting)


class RotationController(B3VController):
    name = "ROT"

    def __init__(self, Tc_s=None, kappa=None):
        self.Tc = value("b0_pi_time_constant_s") if Tc_s is None else Tc_s
        self.kappa = value("b0_pi_integral_factor") if kappa is None else kappa
        super().__init__()

    def reset(self):
        super().reset()
        self.integral = 0.0; self.sigma = 0.0

    def step(self, state, demand, supply, constraints, horizon):
        m = constraints
        day_s = horizon.steps_per_day * m.dt
        cap = np.asarray(m.capacity, float)
        if state.new_day or self.target is None:
            U = m.daily_capacity(horizon.steps_per_day)[:, None]
            self.target = b3_proportional(demand.D[:, [state.day]], [supply.available_today], U)[:, 0]
            self.sigma = float(sum(self.target[j] / (cap[j] * day_s) for j in SMALL)) / TURN_FILL
        remaining = np.maximum(self.target - np.asarray(state.delivered_today, float), 0.0)
        left_s = max(day_s - state.step * m.dt, m.dt)
        q = np.zeros(6)
        q_db = np.zeros(6) if m.pulse_flow is None else np.asarray(m.pulse_flow(state.level), float)
        q[0] = remaining[0] / left_s                                     # Abad-Yarmish: volume feedback
        if 0.0 < q[0] < q_db[0]:                                         # inside the deadband: pulse rule
            q[0] = q_db[0] if remaining[0] >= 0.5 * min(q_db[0] * m.dt, self.target[0]) else 0.0
        turn = None
        for j in SMALL:                                                  # first outlet still owed water
            q_w = min(cap[j], max(self.sigma * cap[j], q_db[j]))
            if q_w <= 0.0 or remaining[j] <= 0.01 * q_w * m.dt:
                continue                                                 # nothing (left) to deliver
            if remaining[j] >= q_w * m.dt:
                q[j] = q_w
            elif remaining[j] / m.dt >= q_db[j]:
                q[j] = remaining[j] / m.dt                               # last part of the turn, executable
            elif remaining[j] >= 0.5 * min(q_db[j] * m.dt, self.target[j]):
                q[j] = q_db[j]                                           # one pulse at the smallest opening
            else:
                continue                                                 # served: the turn passes on
            turn = j
            break
        Kp = m.A_s / self.Tc; Ti = self.kappa * self.Tc
        e = state.level - m.h_ref
        q_ff = m.eta * supply.inflow_now - q[:5].sum()
        q_un = q_ff + Kp * (e + self.integral / Ti)
        q6 = float(np.clip(q_un, 0.0, cap[5]))
        if q6 == q_un or (q6 == 0.0 and e > 0) or (q6 == cap[5] and e < 0):
            self.integral += e * m.dt                                    # conditional integration (as B0)
        q[5] = q6
        return Command(flows=np.minimum(q, cap), target=self.target.copy(),
                       info={"turn": -1 if turn is None else turn, "pi_error": e})
