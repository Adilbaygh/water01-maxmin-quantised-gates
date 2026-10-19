"""Section 2.8, B3: proportional rationing of the available water (constrained method).

At the start of the day every user receives the same share α_p = min(1, A_p/ΣD) (with capacity limits), executed
as in current practice: regulator discharges are constant during the day (plan/day), gate openings are set at each
step from the measured level, and the check structure passes the remainder of the observed inflow.
There is no level forecast, ID model or command constraint.
"""
import numpy as np

from .interface import Command, Controller


def b3_proportional(D, A, U=None):
    """On each day every user receives the same share α_p = min(1, A_p / Σ_j D_{j,p}), with capacity limits."""
    D = np.atleast_2d(np.asarray(D, float)); J, P = D.shape
    U = np.full((J, P), np.inf) if U is None else np.asarray(U, float)
    x = np.zeros((J, P))
    for p in range(P):
        need = np.minimum(D[:, p], U[:, p])
        tot = need.sum()
        x[:, p] = need * (min(1.0, A[p] / tot) if tot > 0 else 0.0)
    return x


class B3Controller(Controller):
    name = "B3"

    def __init__(self):
        self.reset()

    def reset(self):
        self.target = None

    def step(self, state, demand, supply, constraints, horizon):
        m = constraints
        day_s = horizon.steps_per_day * m.dt
        if state.new_day or self.target is None:
            U = m.daily_capacity(horizon.steps_per_day)[:, None]
            self.target = b3_proportional(demand.D[:, [state.day]], [supply.available_today], U)[:, 0]
        q = self.target / day_s
        q[-1] = max(m.eta * supply.inflow_now - q[:-1].sum(), 0.0)      # check structure: remaining water
        return Command(flows=np.minimum(q, m.capacity), target=self.target.copy())


class B3VController(B3Controller):
    """Control variant: the daily share α_p of B3 is kept, but regulator discharges are recomputed at every step
    from the estimated delivered volume (volume feedback):
        q_j = max(x_j − V̂_j, 0) / (time remaining to the end of the day),  j ≤ 5;
        check structure: the remainder of the observed inflow.
    No lexicographic plan, ID model, command constraint (9) or LP; used only to isolate the effect of feedback."""
    name = "B3V"

    def step(self, state, demand, supply, constraints, horizon):
        m = constraints
        day_s = horizon.steps_per_day * m.dt
        if state.new_day or self.target is None:
            U = m.daily_capacity(horizon.steps_per_day)[:, None]
            self.target = b3_proportional(demand.D[:, [state.day]], [supply.available_today], U)[:, 0]
        left_s = max(day_s - state.step * m.dt, m.dt)
        remaining = np.maximum(self.target - np.asarray(state.delivered_today, float), 0.0)
        q = remaining / left_s
        q[-1] = max(m.eta * supply.inflow_now - q[:-1].sum(), 0.0)      # check structure: remaining water
        return Command(flows=np.minimum(q, m.capacity), target=self.target.copy())


class B3VDeadbandAwareController(B3VController):
    """Exploratory variant (B3V-DA): B3V with the pulse rule of LXB-DA (control.lxb.pulse_adjust), to separate the
    effect of the deadband-aware execution rule from that of the lexicographic planner."""
    name = "B3V-DA"

    def step(self, state, demand, supply, constraints, horizon):
        from .lxb import pulse_adjust
        cmd = super().step(state, demand, supply, constraints, horizon)
        m = constraints
        if m.pulse_flow is None:
            return cmd
        remaining = np.maximum(self.target - np.asarray(state.delivered_today, float), 0.0)
        q, pulses = pulse_adjust(cmd.flows, m.pulse_flow(state.level), remaining, m.dt, self.target)
        q[-1] = max(m.eta * supply.inflow_now - q[:-1].sum(), 0.0)      # check structure: remaining water
        return Command(flows=np.minimum(q, m.capacity), target=cmd.target, info={"pulses": pulses})
