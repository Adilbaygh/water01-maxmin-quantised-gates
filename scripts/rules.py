"""Execution rules for a quantised max-min plan, registered as controllers of the simulation core.

Every rule keeps the daily plan of LXB (the three-stage lexicographic programme of water01.control.lxb) and the
fifteen-minute execution programme of LXB, which computes the commands of all six outlets. A rule changes only the
commands of the five regulators (j = 1, ..., 5); the check structure (j = 6) is never changed.

Notation (article, Section 2): k = ceil(delta / rho) resolution steps form the smallest executable opening a_min of a
closed gate; the quantum q_j(h) is the step volume at a_min, the pulse volume p_j(h) is the step volume at the pulse
opening a_min + rho, g_j(h) = q_j(h) / k is the step volume of one resolution step. With relation (6) the discharge of a
small opening is proportional to the opening, so q_j(h) = p_j(h) k / (delta / rho + 1).

Rules:
  LXB-Txxx  theta pulse rule, theta = xxx / 100. When the execution programme commands a regulator a positive discharge
            smaller than the pulse discharge, the regulator receives one pulse if the remaining plan R_j is positive and
            R_j >= theta min{p_j, x_j}, and is closed otherwise. LXB-T050 coincides with LXB-DA of the simulation core;
            LXB-T000 rounds up.
  LXB-ES    equal split. A daily plan x_j between one quantum at the upper level bound and the pulse-regime limit is
            delivered in m_j open steps separated by closed steps; at the k-th open step the regulator receives the
            remaining part of the cumulative target k x_j / m_j. A plan below one quantum uses the theta pulse rule with
            theta = 0.5. m_j = min(ceil(N / 2), max(1, floor(x_j / (q_j^hi + g_j^hi)))).
  LXB-CO    carry-over. The theta pulse rule (theta = 0.5) applied to the plan plus the estimated debt of the previous
            day: x~_j(s) = x_j(s) + e_j(s - 1), e_j(s) = x~_j(s) - V^_j(s), e_j(0) = 0; the regulator is closed for the
            day when x~_j(s) <= 0.

The simulation core is not modified; the rules are added to water01.control.CONTROLLERS when register() is called.
LOG holds, for the run in progress in this process, one record per day with the base plan, the executed target, the
mode of each regulator and the numbers of pulses and equal-split open steps.
"""
import math

import numpy as np

from water01.control import CONTROLLERS
from water01.control.interface import Command
from water01.control.lxb import LXBController, plan_window
from water01.domain.passport import value

N_REGULATORS = 5
LOG = {}                                    # day index -> record (reset by the runner before each run)
THETAS = {"LXB-T000": 0.0, "LXB-T025": 0.25, "LXB-T050": 0.5, "LXB-T075": 0.75}


def quantum_steps():
    """k: resolution steps in the smallest opening executed from a closed gate (the actuator executes a change of at
    least the deadband, compared in whole steps)."""
    return int(math.ceil(value("gate_deadband_fraction") / value("gate_resolution_fraction") - 1e-9))


def quantum_ratio():
    """q / p: ratio of the quantum flow to the pulse flow of the controller's model (relation (6) is linear in the
    opening; the pulse opening of the core is deadband + one resolution step)."""
    return quantum_steps() / (value("gate_deadband_fraction") / value("gate_resolution_fraction") + 1.0)


def record(day):
    rec = LOG.get(day)
    if rec is None:
        rec = {"x": np.full(6, np.nan), "xt": np.full(6, np.nan), "mode": ["LP"] * N_REGULATORS,
               "m": np.zeros(N_REGULATORS, int), "pulses": np.zeros(N_REGULATORS, int),
               "es_open": np.zeros(N_REGULATORS, int)}
        LOG[day] = rec
    return rec


class RuleController(LXBController):
    """LXB with an execution rule for the regulators: subclasses override target() and adjust()."""
    name = "LXB-RULE"
    theta = 0.5

    def step(self, state, demand, supply, constraints, horizon):
        m, hz = constraints, horizon
        if state.new_day or self.target is None:
            U = m.daily_capacity(hz.steps_per_day)[:, None] * np.ones((1, demand.D.shape[1]))
            x, x_next = plan_window(demand.D, supply.available_today, supply.forecast, U, state.day,
                                    state.delivered_prev, demand.weights, hz.days, m.epsilon_1, m.epsilon_2,
                                    stage3=self.stage3)
            self.next_rate = x_next / (hz.steps_per_day * m.dt)
            self.target = self.daily_target(state, np.asarray(x, float))
            rec = record(state.day)
            rec["x"] = np.asarray(x, float).copy(); rec["xt"] = self.target.copy()
            self.new_day(state, m, hz)
        q = self.exec(state, supply, m, hz, self.target, self.next_rate)
        q = self.adjust(state, np.array(q, float), m, hz)
        q = np.minimum(q, m.capacity)
        self.exec.q_prev = q                  # the next execution programme starts from the commanded discharge
        info = dict(self.exec.last)
        return Command(flows=q, target=self.target.copy(), info=info)

    # hooks
    def daily_target(self, state, x):
        return x.copy()

    def new_day(self, state, m, hz):
        pass

    def adjust(self, state, q, m, hz):
        return self.pulse(state, q, m, range(N_REGULATORS))

    def pulse(self, state, q, m, outlets):
        """Theta pulse rule for the given regulators (only where the commanded discharge lies inside the deadband)."""
        if m.pulse_flow is None:              # ideal execution: no quantisation, the rule is inactive
            return q
        q_db = np.asarray(m.pulse_flow(state.level), float)
        remaining = np.maximum(self.target - np.asarray(state.delivered_today, float), 0.0)
        rec = record(state.day)
        for j in outlets:
            if q_db[j] <= 0 or not (0.0 < q[j] < q_db[j]):
                continue
            give = remaining[j] > 0.0 and remaining[j] >= self.theta * min(q_db[j] * m.dt, self.target[j])
            q[j] = q_db[j] if give else 0.0
            if give:
                rec["pulses"][j] += 1
                rec["mode"][j] = "PULSE"
        return q


class EqualSplitController(RuleController):
    """LXB-ES: equal split for plans of at least one quantum in the pulse regime, theta = 0.5 below one quantum."""
    name = "LXB-ES"
    theta = 0.5

    def reset(self):
        super().reset()
        self.schedule = {}

    def new_day(self, state, m, hz):
        self.schedule = {}
        if m.pulse_flow is None:
            return
        N, dt = hz.steps_per_day, m.dt
        k = quantum_steps(); ratio = quantum_ratio()
        q_hi = np.asarray(m.pulse_flow(m.h_hi), float) * ratio * dt          # quantum at the upper level bound
        g_hi = q_hi / k
        p_now = np.asarray(m.pulse_flow(state.level), float) * dt
        cap = np.asarray(m.capacity, float)
        if m.max_flows is not None:
            cap = np.minimum(cap, np.asarray(m.max_flows(m.h_lo), float))
        c_step = cap * dt
        rec = record(state.day)
        for j in range(N_REGULATORS):
            x = float(self.target[j])
            if not (q_hi[j] > 0 and x >= q_hi[j] and x < N * p_now[j]
                    and x <= math.ceil(N / 2) * (c_step[j] - g_hi[j])):
                continue
            mj = int(min(math.ceil(N / 2), max(1, math.floor(x / (q_hi[j] + g_hi[j])))))
            steps = [int(math.floor(i * N / mj)) for i in range(mj)]
            self.schedule[j] = {s: i + 1 for i, s in enumerate(steps)}
            self.schedule[j]["m"] = mj
            rec["mode"][j] = "ES"; rec["m"][j] = mj

    def adjust(self, state, q, m, hz):
        rest = [j for j in range(N_REGULATORS) if j not in self.schedule]
        q = self.pulse(state, q, m, rest)
        if not self.schedule:
            return q
        rec = record(state.day)
        for j, sch in self.schedule.items():
            i = sch.get(state.step)
            if i is None:
                q[j] = 0.0                                                       # closed step
                continue
            v = i * float(self.target[j]) / sch["m"] - float(state.delivered_today[j])
            q[j] = max(v, 0.0) / m.dt
            rec["es_open"][j] += int(v > 0.0)
        return q


class CarryOverController(RuleController):
    """LXB-CO: theta pulse rule (theta = 0.5) on the plan plus the estimated debt of the previous day."""
    name = "LXB-CO"
    theta = 0.5

    def reset(self):
        super().reset()
        self.xt_raw = None

    def daily_target(self, state, x):
        xt = x.copy()
        raw = x[:N_REGULATORS].copy()
        if self.xt_raw is not None and state.delivered_prev is not None:
            debt = self.xt_raw - np.asarray(state.delivered_prev, float)[:N_REGULATORS]
            raw = x[:N_REGULATORS] + debt
        self.xt_raw = raw
        xt[:N_REGULATORS] = np.maximum(raw, 0.0)
        return xt


def make_theta(name, theta):
    cls = type(name.replace("-", "_"), (RuleController,), {"name": name, "theta": theta})
    return cls


def register():
    for name, theta in THETAS.items():
        CONTROLLERS[name] = make_theta(name, theta)
    CONTROLLERS["LXB-ES"] = EqualSplitController
    CONTROLLERS["LXB-CO"] = CarryOverController
    return sorted(list(THETAS) + ["LXB-ES", "LXB-CO"])
