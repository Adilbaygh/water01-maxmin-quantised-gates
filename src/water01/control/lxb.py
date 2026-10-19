"""Sections 2.5, 2.8, LXB: three-stage lexicographic allocation with a receding horizon.

Two levels:
- daily plan (plan_window): at the start of each day, a three-stage LP (with Stage 1b) over a 10-day window;
  yesterday is fixed (estimated delivered volume), today uses the observed supply, later days the limit forecast;
- 15-minute execution (IntradayExecutor): LP with the ID model (8), command constraint (9), level bounds and
  gate rate; re-solved at every step from the measured (estimated) level and delivered volume.
lxb_receding: hydraulics-free static variant (for code checks and check_tolerance only).
"""
import numpy as np

from ..domain.passport import value
from ..optimization.lexlp import solve_intraday, solve_lexicographic
from .interface import Command, Controller


def plan_window(D, A_today, A_forecast, U, p, fixed_prev=None, weights=None, horizon_days=None, epsilon_1=None,
                epsilon_2=None, protect_today=True, stage3=True):
    """Daily plan for day p. D, A_forecast, U cover the whole period [J×P], [P]. fixed_prev: yesterday's volumes (J)
    or None. Returns: (today's volumes x_p, tomorrow's plan x_{p+1} or a copy of today's)."""
    horizon_days = value("horizon_days") if horizon_days is None else horizon_days
    J, P = D.shape
    p0 = max(p - 1, 0); p1 = min(p + horizon_days, P)
    cols = list(range(p0, p1))
    A_win = np.array([A_today if q == p else A_forecast[q] for q in cols])
    if p > 0 and fixed_prev is not None:
        fixed = {(j, 0): float(fixed_prev[j]) for j in range(J)}
        A_win[0] = max(A_win[0], float(np.sum(fixed_prev)))
    else:
        fixed = {}
    sol = solve_lexicographic(D[:, cols], A_win, U[:, cols], weights, fixed, epsilon_1, epsilon_2,
                              protect_day=cols.index(p) if protect_today else None, stage3=stage3)
    i = cols.index(p)
    x_today = sol["x"][:, i]
    x_next = sol["x"][:, i + 1] if i + 1 < len(cols) else x_today
    return x_today, x_next


def lxb_receding(D, A_actual, A_forecast, U=None, weights=None, horizon_days=None, epsilon_1=None, epsilon_2=None,
                 protect_today=True):
    """Each day the LP is solved with today's actual water and the limit forecast for later days; only today's
    allocation is executed. The previous day is included as fixed for the continuity term of Stage 3.
    protect_today: Stage 1b (11b), today's worst-case satisfaction is maximised while retaining the window λ*."""
    horizon_days = value("horizon_days") if horizon_days is None else horizon_days
    D = np.atleast_2d(np.asarray(D, float)); J, P = D.shape
    U = np.full((J, P), np.inf) if U is None else np.asarray(U, float)
    x = np.zeros((J, P))
    for p in range(P):
        p0 = max(p - 1, 0); p1 = min(p + horizon_days, P)
        cols = list(range(p0, p1))
        A_win = np.array([A_actual[q] if q <= p else A_forecast[q] for q in cols])
        fixed = {(j, 0): x[j, p - 1] for j in range(J)} if p > 0 else {}
        sol = solve_lexicographic(D[:, cols], A_win, U[:, cols], weights, fixed, epsilon_1, epsilon_2,
                                  protect_day=cols.index(p) if protect_today else None)
        x[:, p] = sol["x"][:, cols.index(p)]
    return x


def blocked_durations(steps_today, lookahead, fine, block, dt):
    """Move blocking: the first `fine` steps have length Δt (the ID delay d ≤ fine lies in this part); the remaining
    steps of today and the next-day lookahead are grouped into blocks of `block` steps (no block crosses the day
    boundary). Returns: (interval lengths, number of intervals belonging to today)."""
    def split(n, first_fine):
        f = min(first_fine, n); out = [1] * f; rest = n - f
        while rest > 0:
            b = min(block, rest); out.append(b); rest -= b
        return out
    today = split(steps_today, fine)
    nxt = split(lookahead, max(fine - steps_today, 0))      # the 15-minute part may extend past the day boundary
    return np.array(today + nxt, float) * dt, len(today)


def clip_roundoff(q, tol=None):
    """Discharges within the HiGHS primal tolerance of zero (|q| ≤ 10⁻⁹ m³/s, e.g. −7.3·10⁻¹³ or +10⁻¹²) are
    round-off and are set to zero, so that a round-off residual is not executed as a small gate opening. A larger
    negative value indicates a genuine error and raises an exception."""
    tol = value("lp_primal_feasibility_tolerance") if tol is None else tol
    q = np.array(q, float)
    if (q < -tol).any():
        raise ValueError(f"Execution LP returned a negative discharge: {q.min():.3g} m³/s (tolerance {tol:g})")
    q[q <= tol] = 0.0
    return q


class IntradayExecutor:
    """15-minute execution LP (optimization.lexlp.solve_intraday), shared by LXB, Oracle and B2.
    Re-solved at every step from the measured (estimated) level and delivered volume; the first step is applied."""

    def __init__(self, objective="maxmin", share="remaining"):
        self.objective, self.share = objective, share
        self.q_prev = None; self.last = {}

    def reset(self):
        self.q_prev = None; self.last = {}

    def __call__(self, state, supply, constraints, horizon, target, next_rate, weights=None):
        m, hz = constraints, horizon
        steps_today = hz.steps_per_day - state.step
        tau, n_today = blocked_durations(steps_today, hz.lookahead_steps, hz.fine_steps, hz.block_steps, m.dt)
        K = tau.size
        q_future = np.full(K, supply.inflow_now)
        if supply.inflow_next is not None:                     # Oracle: tomorrow's inflow is known
            q_future[n_today:] = supply.inflow_next
        remaining = np.maximum(target - state.delivered_today, 0.0)
        sol = solve_intraday(state.inflow_history, q_future, state.level, remaining, next_rate, n_today, K, m.dt,
                             m.eta, m.A_s, m.d, m.chords, m.capacity, m.h_lo, m.h_hi, m.h_ref, self.q_prev,
                             m.dq_max, durations=tau, objective=self.objective, weights=weights,
                             **({} if self.share == "remaining" else
                                dict(share=self.share, delivered_today=np.asarray(state.delivered_today, float),
                                     target_today=np.asarray(target, float))))
        q = clip_roundoff(sol["q"][:, 0])
        self.q_prev = q
        self.last = {"mu": sol["mu"], "nu": sol["nu"], "slack": sol["slack"], "h_pred": sol["h"][1]}
        return q


class LXBController(Controller):
    """Proposed method: daily three-stage plan (with Stage 1b; feedback from yesterday's estimated volume and today's
    observed supply) + 15-minute execution LP (ID model (8), constraint (9), level, gate rate)."""
    name = "LXB"
    stage3 = True                                            # H3 ablation: False in LXBNoStage3Controller

    def __init__(self):
        self.exec = IntradayExecutor("maxmin")
        self.reset()

    def reset(self):
        self.exec.reset(); self.target = None; self.next_rate = None

    def step(self, state, demand, supply, constraints, horizon):
        m, hz = constraints, horizon
        if state.new_day or self.target is None:
            U = m.daily_capacity(hz.steps_per_day)[:, None] * np.ones((1, demand.D.shape[1]))
            self.target, x_next = plan_window(demand.D, supply.available_today, supply.forecast, U, state.day,
                                              state.delivered_prev, demand.weights, hz.days, m.epsilon_1,
                                              m.epsilon_2, stage3=self.stage3)
            self.next_rate = x_next / (hz.steps_per_day * m.dt)
        q = self.exec(state, supply, m, hz, self.target, self.next_rate)
        return Command(flows=q, target=self.target.copy(), info=dict(self.exec.last))


class LXBFinalShareController(LXBController):
    """Exploratory variant (LXB-F): as LXB, but the execution LP maximises the common share of the whole daily plan
    reached at the end of the day (final daily satisfaction relative to the plan) instead of the common share of the
    remaining plan (solve_intraday, share="final"). Daily plan as in LXB."""
    name = "LXB-F"

    def __init__(self):
        self.exec = IntradayExecutor("maxmin", share="final")
        self.reset()


class LXBNoStage3Controller(LXBController):
    """H3 ablation: LXB without Stage 3 (13) in the daily plan; the Stage 2 solution is executed, otherwise as LXB."""
    name = "LXB-noS3"
    stage3 = False


def pulse_adjust(q, q_db, remaining, dt, target=None):
    """LXB-DA pulse rule (regulators j ≤ 5; the last outlet, the check structure, is unchanged).
    If 0 < q_j < q_j^db: R_j ≥ min(q_j^db Δt, x_j) / 2 -> q_j = q_j^db (one step), otherwise q_j = 0.
    The threshold never exceeds half of the daily plan, so at least one pulse is issued per day even when the pulse
    volume exceeds the daily demand (e.g. R-1 in early April); over-delivery is at most one pulse volume.
    Returns: (adjusted discharges, number of pulses)."""
    q = np.array(q, float); q_db = np.asarray(q_db, float); remaining = np.asarray(remaining, float)
    target = np.full(q.size, np.inf) if target is None else np.asarray(target, float)
    pulses = 0
    for j in range(q.size - 1):
        if q_db[j] <= 0 or not (0.0 < q[j] < q_db[j]):
            continue
        q[j] = q_db[j] if remaining[j] >= 0.5 * min(q_db[j] * dt, target[j]) else 0.0
        pulses += int(q[j] > 0)
    return q, pulses


class LXBDeadbandAwareController(LXBController):
    """Sensitivity variant: LXB whose execution layer accounts for the actuator deadband (LXB-DA).
    If the execution LP commands regulator j ≤ 5 a positive discharge smaller than the discharge at the smallest
    executable opening q_j^db (constraints.pulse_flow), the actuator cannot realise that opening. The pulse rule is
    then applied (pulse_adjust): if the remaining plan for today R_j = x_j − V̂_j is sufficient, q_j^db is commanded
    for one step, otherwise 0 (full closure is always executable). Daily plan and execution LP are as in LXB."""
    name = "LXB-DA"

    def step(self, state, demand, supply, constraints, horizon):
        cmd = super().step(state, demand, supply, constraints, horizon)
        m = constraints
        if m.pulse_flow is None:
            return cmd
        remaining = np.maximum(self.target - np.asarray(state.delivered_today, float), 0.0)
        q, pulses = pulse_adjust(cmd.flows, m.pulse_flow(state.level), remaining, m.dt, self.target)
        info = dict(cmd.info); info["pulses"] = pulses
        return Command(flows=np.minimum(q, m.capacity), target=cmd.target, info=info)
