"""Section 2.8, B1: fair delivery plan without feedback (simple fairness baseline; Fair-Canal-Delivery [17]).

At the start of the period a three-stage lexicographic plan for the whole period is computed once from the limit
forecast (S^lim). At the start of each day the planned discharges are converted to gate openings at the nominal
level (H_norm) and are not changed during the day. Level measurements, actual supply and delivered volume are not
used (open loop). The node relies only on its natural self-regulation (at a fixed opening the discharge depends on
the level).
"""
import numpy as np

from ..optimization.lexlp import solve_lexicographic
from .interface import Command, Controller


class B1Controller(Controller):
    name = "B1"

    def __init__(self):
        self.reset()

    def reset(self):
        self.plan = None; self.target = None

    def step(self, state, demand, supply, constraints, horizon):
        m = constraints
        if self.plan is None:
            P = demand.D.shape[1]
            U = m.daily_capacity(horizon.steps_per_day)[:, None] * np.ones((1, P))
            self.plan = solve_lexicographic(demand.D, supply.forecast, U, demand.weights, None,
                                            m.epsilon_1, m.epsilon_2)["x"]
        if not state.new_day:
            return Command.hold()
        self.target = self.plan[:, state.day]
        q = np.minimum(self.target / (horizon.steps_per_day * m.dt), m.capacity)
        return Command(flows=q, conversion_level=np.full(6, m.h_ref), target=self.target.copy())
