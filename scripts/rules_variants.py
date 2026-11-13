"""Execution rules of the sensitivity analyses, registered beside the rules of scripts/rules.py.

The rules keep the daily plan and the fifteen-minute execution programme of LXB and change only the commands of the
five regulators, as the rules of scripts/rules.py; scripts/rules.py itself is not modified.

Rules:
  LXB-T050S  theta pulse rule (theta = 0.5) with closure at the start of the day: at the first step of a day, a
             regulator that the actuator reports open and whose commanded discharge lies inside the pulse regime
             (positive and smaller than the pulse discharge) is closed; the theta rule works from the second step.
             Every pulse-regime day then starts with a closed gate, as assumed in Theorem 3 (H3).
  LXB-COS    carry-over (LXB-CO) with the same closure at the start of the day.
  LXB-ESL    equal split with few openings and a trimming step: equal open steps of at most the step capacity and,
             as far as the ceil(N/2) open steps of a day allow, at most the volume that changes the pool level by
             2 mm over the identified storage area (0.392 km^2 x 2 mm = 784 m^3), followed by a last open step of one
             quantum and one resolution step that corrects the earlier errors; a plan smaller than twice this last
             step is delivered in one open step; open steps away from the day break (Remark A1 with unequal
             increments).
  LXB-ESM    equal split with the fewest open steps: a daily plan x_j between one quantum at the upper level bound and
             the pulse-regime limit is delivered in m_j = max(1, ceil(x_j / (c_j - g_j^hi))) open steps, c_j the
             step capacity at the lower level bound and g_j^hi one resolution step at the upper level bound; every open
             step opens a closed gate and the k-th open step receives the remaining part of the cumulative target
             k x_j / m_j, as in LXB-ES, so that the half-step accuracy of Theorem 1(b) is kept with the smallest number
             of gate openings. A plan below one quantum uses the theta pulse rule with theta = 0.5.

LOG records of scripts/rules.py are used; LXB-T050S and LXB-COS add the key "start_closed" (regulators closed at the
first step of the day).
"""
import math

import numpy as np

from water01.control import CONTROLLERS

import rules

N_REGULATORS = rules.N_REGULATORS


class StartClosureMixin:
    """Closure at the start of the day for regulators that are open at the day break and in the pulse regime."""

    def adjust(self, state, q, m, hz):
        if state.step != 0 or m.pulse_flow is None:
            return super().adjust(state, q, m, hz)
        q_db = np.asarray(m.pulse_flow(state.level), float)
        position = np.asarray(state.openings, float)
        rec = rules.record(state.day)
        closed = rec.setdefault("start_closed", np.zeros(N_REGULATORS, int))
        rest = []
        for j in range(N_REGULATORS):
            if position[j] > 0.0 and q_db[j] > 0.0 and 0.0 < q[j] < q_db[j]:
                q[j] = 0.0
                closed[j] = 1
            else:
                rest.append(j)
        return self.adjust_rest(state, q, m, hz, rest)

    def adjust_rest(self, state, q, m, hz, outlets):
        return self.pulse(state, q, m, outlets)


class StartClosureTheta(StartClosureMixin, rules.RuleController):
    name = "LXB-T050S"
    theta = 0.5


class StartClosureCarryOver(StartClosureMixin, rules.CarryOverController):
    name = "LXB-COS"
    theta = 0.5


class MinimalEqualSplitController(rules.EqualSplitController):
    """LXB-ESM: the cumulative-target equal split of LXB-ES with the smallest feasible number of open steps."""
    name = "LXB-ESM"
    theta = 0.5

    def new_day(self, state, m, hz):
        self.schedule = {}
        if m.pulse_flow is None:
            return
        N, dt = hz.steps_per_day, m.dt
        k = rules.quantum_steps(); ratio = rules.quantum_ratio()
        q_hi = np.asarray(m.pulse_flow(m.h_hi), float) * ratio * dt          # quantum at the upper level bound
        g_hi = q_hi / k                                                      # one resolution step at the upper bound
        p_now = np.asarray(m.pulse_flow(state.level), float) * dt
        cap = np.asarray(m.capacity, float)
        if m.max_flows is not None:
            cap = np.minimum(cap, np.asarray(m.max_flows(m.h_lo), float))
        c_step = cap * dt
        rec = rules.record(state.day)
        for j in range(N_REGULATORS):
            x = float(self.target[j])
            room = c_step[j] - g_hi[j]
            if not (q_hi[j] > 0 and room > 0 and x >= q_hi[j] and x < N * p_now[j]
                    and x <= math.ceil(N / 2) * room):
                continue
            mj = int(min(math.ceil(N / 2), max(1, math.ceil(x / room - 1e-12))))
            steps = [int(math.floor(i * N / mj)) for i in range(mj)]
            self.schedule[j] = {s: i + 1 for i, s in enumerate(steps)}
            self.schedule[j]["m"] = mj
            rec["mode"][j] = "ES"; rec["m"][j] = mj


class LevelCappedEqualSplitController(rules.EqualSplitController):
    """LXB-ESL: equal split with few openings and a trimming step. A plan x of at least one quantum (and within the limits
    of LXB-ES) is delivered in m open steps whose increments of the cumulative target are: x itself if x < 2 y and one
    step can pass it, and otherwise n equal increments (x - y) / n followed by a last increment y = q^hi + g^hi (one
    quantum and one resolution step at the upper level bound). n is the smallest number of increments not larger than u,
    but at most floor((x - y) / y), so that no increment is smaller than y, and at most ceil(N/2) - 1, so that the
    m = n + 1 open steps fit between closed steps. The volume u of a large open step is the step capacity at the lower
    level bound minus one resolution step, but at most the volume that changes the pool level by LEVEL_STEP_M over the
    identified storage area (or y, if this is larger), so that the level stays nearly constant within a large open step
    (H2); the last, small step corrects the errors of the earlier ones. The open steps are placed at
    floor((i + 1/2) N / m), away from the day break. Every increment d satisfies [d - g/2, d + g/2] within [q^max, C],
    which keeps the half-step bound of Theorem 1(b) (Remark A1); the other plans are executed as under LXB-T050."""
    name = "LXB-ESL"
    theta = 0.5
    LEVEL_STEP_M = 0.002

    def new_day(self, state, m, hz):
        from water01.domain.passport import value
        self.schedule = {}
        if m.pulse_flow is None:
            return
        N, dt = hz.steps_per_day, m.dt
        k = rules.quantum_steps(); ratio = rules.quantum_ratio()
        q_hi = np.asarray(m.pulse_flow(m.h_hi), float) * ratio * dt
        g_hi = q_hi / k
        p_now = np.asarray(m.pulse_flow(state.level), float) * dt
        cap = np.asarray(m.capacity, float)
        if m.max_flows is not None:
            cap = np.minimum(cap, np.asarray(m.max_flows(m.h_lo), float))
        c_step = cap * dt
        u_level = float(value("A_s_identified_m2")) * self.LEVEL_STEP_M
        rec = rules.record(state.day)
        for j in range(N_REGULATORS):
            x = float(self.target[j])
            room = c_step[j] - g_hi[j]
            if not (q_hi[j] > 0 and room > 0 and x >= q_hi[j] and x < N * p_now[j]
                    and x <= math.ceil(N / 2) * room):
                continue
            y = q_hi[j] + g_hi[j]
            u = max(min(room, u_level), y)
            if x < 2 * y:
                if x > c_step[j]:
                    continue                                           # one open step cannot pass the plan
                inc = [x]                                              # too small for a large and a trimming step
            else:
                n = math.ceil((x - y) / u - 1e-12)
                n = max(1, min(n, math.floor((x - y) / y + 1e-12), math.ceil(N / 2) - 1))
                if (x - y) / n > room or (x - y) / n < y:
                    continue                                           # outside the range of Remark A1
                inc = [(x - y) / n] * n + [y]
            mj = len(inc)
            steps = [int(math.floor((i + 0.5) * N / mj)) for i in range(mj)]
            self.schedule[j] = {"targets": dict(zip(steps, np.cumsum(inc).tolist())), "m": mj}
            rec["mode"][j] = "ES"; rec["m"][j] = mj

    def adjust(self, state, q, m, hz):
        rest = [j for j in range(N_REGULATORS) if j not in self.schedule]
        q = self.pulse(state, q, m, rest)
        if not self.schedule:
            return q
        rec = rules.record(state.day)
        for j, sch in self.schedule.items():
            T = sch["targets"].get(state.step)
            if T is None:
                q[j] = 0.0                                                       # closed step
                continue
            v = T - float(state.delivered_today[j])
            q[j] = max(v, 0.0) / m.dt
            rec["es_open"][j] += int(v > 0.0)
        return q


NEW_RULES = {"LXB-T050S": StartClosureTheta, "LXB-COS": StartClosureCarryOver, "LXB-ESM": MinimalEqualSplitController,
             "LXB-ESL": LevelCappedEqualSplitController}


def register():
    """Registers the rules of scripts/rules.py and the rules of this module; returns the names of all of them."""
    names = rules.register()
    CONTROLLERS.update(NEW_RULES)
    return sorted(set(names) | set(NEW_RULES))
