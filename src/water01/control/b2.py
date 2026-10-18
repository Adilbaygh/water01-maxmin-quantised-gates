"""Section 2.8, B2: weighted-sum MPC (fairness + hydraulic feasibility).

Same internal model, constraints and feedback as LXB; only the objective differs:
- daily plan: a single LP, max Σ_{j,p} w_j r_{j,p} (the worst-off user is not protected separately);
- 15-minute execution: a separate μ_j for each user, max Σ w_j μ_j.
In the base scenario w_j = 1 (Section 2.5). This comparison isolates the contribution of the lexicographic order
itself: hydraulics and IoT are identical, only the fairness criterion differs.
"""
import numpy as np

from ..domain.passport import value
from ..optimization.lexlp import solve_weighted_sum
from .interface import Command, Controller
from .lxb import IntradayExecutor


def b2_daily_plan(D, A_today, A_forecast, U, p, fixed_prev=None, weights=None, horizon_days=None):
    horizon_days = value("horizon_days") if horizon_days is None else horizon_days
    J, P = D.shape
    p0 = max(p - 1, 0); p1 = min(p + horizon_days, P)
    cols = list(range(p0, p1))
    A_win = np.array([A_today if q == p else A_forecast[q] for q in cols])
    fixed = {}
    if p > 0 and fixed_prev is not None:
        fixed = {(j, 0): float(fixed_prev[j]) for j in range(J)}
        A_win[0] = max(A_win[0], float(np.sum(fixed_prev)))
    x = solve_weighted_sum(D[:, cols], A_win, U[:, cols], weights, fixed)["x"]
    i = cols.index(p)
    return x[:, i], (x[:, i + 1] if i + 1 < len(cols) else x[:, i])


class B2Controller(Controller):
    name = "B2"

    def __init__(self):
        self.exec = IntradayExecutor("weighted")
        self.reset()

    def reset(self):
        self.exec.reset(); self.target = None; self.next_rate = None

    def step(self, state, demand, supply, constraints, horizon):
        m, hz = constraints, horizon
        if state.new_day or self.target is None:
            U = m.daily_capacity(hz.steps_per_day)[:, None] * np.ones((1, demand.D.shape[1]))
            self.target, x_next = b2_daily_plan(demand.D, supply.available_today, supply.forecast, U, state.day,
                                                state.delivered_prev, demand.weights, hz.days)
            self.next_rate = x_next / (hz.steps_per_day * m.dt)
        q = self.exec(state, supply, m, hz, self.target, self.next_rate, demand.weights)
        return Command(flows=q, target=self.target.copy(), info=dict(self.exec.last))
