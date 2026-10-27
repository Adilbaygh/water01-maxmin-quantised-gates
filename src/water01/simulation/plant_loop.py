"""Sections 2.3-2.6, 2.10: running the reference plant and the closed control loop.

Closed loop (every Δt = 15 min):
    controller (LXB / B3) -> outlet discharges -> gate openings (controller C_d, estimated level) ->
    quantisation and deadband (14) -> LoRaWAN message budget and loss (15) -> actuator ->
    Dustlik node (true C_d, untuned offtake) -> Saint-Venant plant (Preissmann) ->
    level measurement z = h + ν (7) -> state estimate (with ID prediction) -> next step.
Controllers are called through the common interface (control.interface): command = controller.step(state=...,
demand=..., supply=..., constraints=..., horizon=...). The controller itself updates its daily plan on state.new_day.

The true delivered volume is taken from the plant (with the Preissmann θ-weighting, consistent with the mass
balance), while the controller knows only its own estimate (measured level + actuator state + gate equation), so
measurement and reconstruction errors appear in the results rather than being hidden behind the controller's
estimate.

The energy constraint (16) is iot.energy.EnergyNode (NASA POWER hourly irradiance), enabled by IoT factor E.
Inflow: Q(0, t) = S(t), the daily record at the head gauging station (assumed: the stage-discharge relation of the
head regulator is not modelled); the controller knows the daily S. If supply_ramp_hours > 0 (sensitivity case), the
plant inflow changes linearly from the previous day's value at the start of the day; the controller is not aware of
this (unknown intra-day variation).
"""
from dataclasses import dataclass, field

import numpy as np

from ..control.interface import ControlState, Supply
from ..domain.passport import optional, value
from ..domain.state import DeliveryLedger
from ..hydraulics.preissmann import PreissmannSolver
from ..hydraulics.saint_venant import inflow_bc, outflow_bc, steady_profile
from ..iot.communication import LinkState, transmit
from ..iot.devices import quantize
from ..iot.telemetry import measure, update
from ..optimization.constraints import id_step


def simulate(solver, duration_s, before_step=None):
    """Runs the plant in open loop for duration_s. before_step(solver) is called before every step.
    Returns: arrays t, h_L, Q_in, Q_out and the relative discrete mass-balance error."""
    r = solver.r
    t, hL, qin, qout = [solver.t], [solver.h[-1]], [solver.Q[0]], [solver.Q[-1]]
    V0 = r.volume(solver.h); net = 0.0
    n_steps = int(round(duration_s / solver.dt))
    for _ in range(n_steps):
        if before_step is not None:
            before_step(solver)
        solver.step()
        net += solver.last_net_inflow
        t.append(solver.t); hL.append(solver.h[-1]); qin.append(solver.Q[0]); qout.append(solver.Q[-1])
    mass_error = abs(r.volume(solver.h) - V0 - net) / V0
    return {"t": np.array(t), "h_L": np.array(hL), "Q_in": np.array(qin), "Q_out": np.array(qout),
            "mass_error": float(mass_error)}


def step_response(reach, Q0, h_down, dQ, duration_s, dt_s, eta=1.0, theta=None, step_start=True):
    """ID model identification protocol (Section 2.4): steady profile at Q0 with conveyance losses η, constant
    downstream outflow (Q0·η), inflow changed by dQ at t = 0. With step_start, the inflow changes at the start of
    the first step, as in the closed loop (gate_change_at_step_start). Returns: the result of simulate()."""
    h0, Qp = steady_profile(reach, Q0, h_down, eta=eta)
    q_out = float(Qp[-1])
    s = PreissmannSolver(reach, dt_s, h0, Qp, inflow_bc(lambda t: Q0 + dQ), outflow_bc(lambda t, hN: q_out),
                         theta=theta, eta=eta)
    if step_start:
        s.Q[0] = Q0 + dQ
    return simulate(s, duration_s)


@dataclass
class IoTConfig:
    """IoT constraints (Section 2.6). With all of them disabled, execution is "ideal" (phys)."""
    sensor_accuracy_m: float = 0.0          # 0: error-free measurement; > 0: U(−a, a) (from the datasheet)
    sensor_bias_m: float = 0.0              # persistent offset of the level sensor (sensitivity case)
    sensor_drift_m_per_day: float = 0.0     # linear drift of the offset from the start of the run (sensitivity case)
    sensor_resolution_m: float = None       # sensor step (from the datasheet); None: no rounding
    gate_resolution: float = None           # as a fraction of the stroke; None: no quantisation
    gate_deadband: float = 0.0
    message_window_steps: int = None        # None: unconstrained communication
    message_budget: int = None
    loss_probability: float = 0.0
    estimator_blend: float = None           # None: from configuration (estimator_blend)
    energy: bool = False                    # (16): solar-battery balance and radio policy (NASA POWER)
    # stress options of the IoT layer (scenario additions; 0: inactive). Communication factor C:
    uplink_loss_probability: float = 0.0    # telemetry packet (level and gate report) lost: no measurement this step
    channel_burst_fraction: float = 0.0     # Gilbert-Elliott channel: long-run share of steps in the bad state, in
    channel_burst_mean_steps: float = 1.0   # which every packet of the step is lost; mean length of a bad period
    command_delay_probability: float = 0.0  # a delivered command is executed at the start of the next step
    backhaul_outage_rate_per_day: float = 0.0   # gateway backhaul outages (no telemetry and no commands):
    backhaul_outage_mean_hours: float = 0.0     # onset rate per day and mean duration
    # energy factor E: outages of the mains supply of the gate drives (the gates cannot move, so neither commands
    # nor the local low-level and high-level rules are executed; the solar-powered IoT node keeps reporting)
    grid_outage_rate_per_day: float = 0.0
    grid_outage_mean_hours: float = 0.0

    @property
    def ideal(self):
        return (self.sensor_accuracy_m == 0 and self.sensor_bias_m == 0 and self.sensor_drift_m_per_day == 0
                and not self.sensor_resolution_m
                and self.gate_resolution is None and not self.gate_deadband and self.message_budget is None
                and self.loss_probability == 0 and not self.energy and self.uplink_loss_probability == 0
                and self.channel_burst_fraction == 0 and self.command_delay_probability == 0
                and self.backhaul_outage_rate_per_day == 0 and self.grid_outage_rate_per_day == 0)

    @property
    def stress(self):
        """True when a stress option of the IoT layer is active (its counters are then written to the result)."""
        return (self.uplink_loss_probability > 0 or self.channel_burst_fraction > 0
                or self.command_delay_probability > 0 or self.backhaul_outage_rate_per_day > 0
                or self.grid_outage_rate_per_day > 0)


def two_state_chain(rng, n, p_enter, p_leave):
    """Boolean sequence of a two-state Markov chain over n steps (True: the bad or outage state), started from its
    stationary distribution. One uniform draw per step, so the sequence depends on the stream only and not on the
    controller (common random numbers)."""
    u = rng.random(n + 1)
    out = np.zeros(n, bool)
    if p_enter <= 0.0:
        return out
    s = bool(u[0] < p_enter / (p_enter + p_leave))
    for k in range(n):
        out[k] = s
        s = bool(u[k + 1] >= p_leave) if s else bool(u[k + 1] < p_enter)
    return out


def outage_sequence(rng, n, rate_per_day, mean_hours, dt_s):
    """Outage steps: onsets at rate_per_day per day of operation, geometric durations with mean mean_hours."""
    if rate_per_day <= 0.0:
        return np.zeros(n, bool)
    if mean_hours <= 0.0:
        raise ValueError("an outage option requires a positive mean duration")
    return two_state_chain(rng, n, rate_per_day * dt_s / 86_400.0, min(1.0, dt_s / (3600.0 * mean_hours)))


def burst_sequence(rng, n, fraction, mean_steps):
    """Bad-state steps of the Gilbert-Elliott channel: long-run share `fraction`, mean bad-period length mean_steps."""
    if fraction <= 0.0:
        return np.zeros(n, bool)
    if not 0.0 < fraction < 1.0 or mean_steps < 1.0:
        raise ValueError("channel_burst_fraction must lie in (0, 1) and channel_burst_mean_steps must be at least 1")
    leave = 1.0 / mean_steps
    return two_state_chain(rng, n, leave * fraction / (1.0 - fraction), leave)


@dataclass
class ClosedLoopResult:
    delivered: np.ndarray                   # true V_j[p], m³ (6 × P)
    delivered_est: np.ndarray               # controller's estimate
    targets: np.ndarray                     # daily plan
    trace: dict = field(default_factory=dict)
    mass_error: float = 0.0
    messages_sent: int = 0
    messages_dropped: int = 0
    command_lost_steps: np.ndarray = None   # per outlet: steps at which the true head cannot pass the planned rate (H6)
    extra_substeps: int = 0                 # number of cases in which the step had to be split for Newton
    storage_change_m3: float = 0.0          # V(end) − V(start); negative: water "borrowed" from reach storage
    interlock_steps: int = 0                # steps with the RTU low-level interlock active
    relief_steps: int = 0                   # steps with high-level relief through the check structure
    battery_min_wh: float = None            # (16) minimum charge; None without the energy factor
    radio_off_steps: int = 0                # steps with the radio off because the charge was below the reserve
    energy_used_wh: float = 0.0             # IoT node consumption (RTU + gateway + messages)
    messages_blocked: int = 0               # command packets not sent because the window budget was exhausted
    messages_lost: int = 0                  # command packets sent but lost on the channel
    low_head_steps: int = 0                 # steps with an open regulator whose head falls below h_t (Eq. (6))
    low_head_volume_m3: float = 0.0         # volume delivered by such regulators in such steps
    gate_clear_steps: int = 0               # steps with an open gate raised clear of the water (opening ≥ depth)
    exec_violations: np.ndarray = None      # [3 × P] daily maxima of the executed step's violations of (9) (m³/s),
                                            # of the gate-rate limit (m³/s) and of the level bounds (m); NaN without
                                            # an execution LP
    # counters of the stress options (IoTConfig.stress)
    telemetry_lost_steps: int = 0           # steps with the link up whose telemetry packet was lost
    burst_steps: int = 0                    # steps in the bad state of the channel
    backhaul_off_steps: int = 0             # steps with the backhaul down
    grid_off_steps: int = 0                 # steps with the gate drives without mains supply
    commands_delayed: int = 0               # delivered command packets executed one step late
    delayed_dropped: int = 0                # delayed commands not executed because the next step had no link or mains
    safety_blocked_steps: int = 0           # steps of a mains outage at which the low-level or high-level rule applied


def command_to_openings(cmd, node_model, h_est, current):
    """Converts a command to openings (using the controller's model of the node).
    discharge -> opening (level: conversion_level or estimated h_L); opening -> itself; NaN -> current position kept.
    Returns: (openings, mask of outlets with insufficient head)."""
    a = np.array(current, float).copy(); lost = np.zeros(6, bool)
    for j in range(6):
        if np.isfinite(cmd.openings[j]):
            a[j] = min(cmd.openings[j], node_model.max_opening[j])
        elif np.isfinite(cmd.flows[j]):
            lvl = cmd.conversion_level[j] if np.isfinite(cmd.conversion_level[j]) else h_est
            q = np.zeros(6); q[j] = cmd.flows[j]
            aj, lj = node_model.openings_for(q, lvl)
            a[j], lost[j] = aj[j], lj[j]
    return a, lost


class CanalPlant:
    """Reference plant: Saint-Venant reach (Preissmann) + Dustlik node (true C_d and offtake multiplier).
    observe(): what the sensors see (with ν); truth(): for Oracle and the recorder only; advance(): one Δt step."""

    def __init__(self, reach, node, supply_m3s, eta, h_init, dt, steps_per_day, theta, rng, sensor_accuracy_m=0.0,
                 sensor_resolution_m=None, sensor_bias_m=0.0, sensor_drift_m_per_day=0.0):
        self.reach, self.node, self.theta, self.dt, self.spd = reach, node, theta, dt, steps_per_day
        self.sensor_bias_m = sensor_bias_m; self.sensor_drift = sensor_drift_m_per_day
        self.S = np.asarray(supply_m3s, float); self.P = self.S.size
        self.rng, self.sensor_accuracy_m, self.sensor_resolution_m = rng, sensor_accuracy_m, sensor_resolution_m
        day_s = steps_per_day * dt
        self._day_of = lambda t: min(int((t - 1e-6) // day_s), self.P - 1) if t > 0 else 0
        self.h0, self.Q0 = steady_profile(reach, self.S[0], h_init, eta=eta)
        self.openings = np.zeros(6)
        self.ramp_s = 3600.0 * value("supply_ramp_hours")       # 0: step change at the start of the day (base case)
        self.solver = PreissmannSolver(reach, dt, self.h0, self.Q0, inflow_bc(self.inflow),
                                       outflow_bc(lambda t, hN: node.outflow(hN, self.openings[:5], self.openings[5])),
                                       theta=theta, eta=eta, substeps=optional("plant_substeps", 1))
        self.delivered = DeliveryLedger(6, self.P)
        self.gate_jump = bool(optional("gate_change_at_step_start", False))
        self.jump_theta = optional("gate_change_first_theta", None)    # time weight of the step after a gate change
        self.h_t = float(value("gate_head_transition_m"))             # transition head of the gate law (6)
        self.low_head_steps = 0; self.low_head_volume = 0.0; self.gate_clear_steps = 0
        self.V0 = reach.volume(self.solver.h); self.net = 0.0; self.substeps = 0
        self.k = 0

    def inflow(self, t):
        """Inflow at the head regulator, m³/s. ramp_s = 0: S[p] throughout the day (step at the start of the day).
        ramp_s > 0: linear transition from S[p−1] to S[p] over ramp_s at the start of the day (sensitivity case
        supply_ramp)."""
        p = self._day_of(t)
        if self.ramp_s <= 0.0 or p == 0:
            return self.S[p]
        frac = min(1.0, (t - p * self.spd * self.dt) / self.ramp_s)
        return self.S[p - 1] + (self.S[p] - self.S[p - 1]) * frac

    def initialise_gates(self, openings, executable=None):
        """Initial openings; the barrier opening balances the initial steady profile.

        executable(a) maps continuous openings to the openings that the actuator can realise (IoT chain:
        quantisation from the closed position); it is applied to the regulators before the barrier is balanced
        and to the barrier afterwards."""
        a = np.array(openings, float)
        if executable is not None:
            a[:5] = executable(a)[:5]
        q_reg = self.node.flows(self.h0[-1], a)[:5]
        q_bar = np.zeros(6); q_bar[5] = max(self.Q0[-1] - q_reg.sum(), 0.0)
        a[5] = self.node.openings_for(q_bar, self.h0[-1])[0][5]
        if executable is not None:
            a[5] = executable(a)[5]
        self.openings = a
        self._flows_old = self.node.flows(self.solver.h[-1], a)
        # the solver's outflow equals the node outflow of the executed (quantised) openings
        self.solver.Q[-1] = self.node.outflow(float(self.solver.h[-1]), a[:5], a[5])
        return a

    @property
    def day(self):
        return self.k // self.spd

    @property
    def step_in_day(self):
        return self.k % self.spd

    def observe(self):
        """Sensors: node level z = h + ν (7), actuator positions (RTU report), head-regulator discharge
        (assumed to be observed exactly)."""
        h = float(self.solver.h[-1])
        u = self.rng.uniform(-1.0, 1.0)        # drawn at every step, whether or not the sensor error is active
        bias = (self.sensor_bias_m if not self.sensor_drift
                else self.sensor_bias_m + self.sensor_drift * self.solver.t / 86_400.0)
        z = (measure(h, self.sensor_accuracy_m, resolution_m=self.sensor_resolution_m, unit_noise=u, bias_m=bias)
             if self.sensor_accuracy_m > 0 or self.sensor_bias_m != 0 or self.sensor_drift or self.sensor_resolution_m
             else h)
        return Observation(t=self.solver.t, day=self.day, step=self.step_in_day, level=z,
                           inflow=float(self.S[min(self.day, self.P - 1)]), openings=self.openings.copy())

    def truth(self):
        return {"level": float(self.solver.h[-1]), "delivered": self.delivered.volume}

    def advance(self, openings, dt):
        """One Δt with the given actuator positions (Preissmann θ-weighted true delivery and mass balance)."""
        if not np.isclose(dt, self.dt):
            raise ValueError("The plant step must equal Δt")
        new_openings = np.array(openings, float)
        if self.gate_jump:                                       # the daily supply also changes at the step start
            self.solver.Q[0] = self.inflow(self.solver.t + 1e-6)
        if self.gate_jump and not np.array_equal(new_openings, self.openings):
            # the gates move at the start of the step: the node outflow at the old time level and the volume ledger
            # start from the discharge of the new openings at the current level (instantaneous gate change)
            hN = float(self.solver.h[-1])
            self.solver.Q[-1] = self.node.outflow(hN, new_openings[:5], new_openings[5])
            self._flows_old = self.node.flows(hN, new_openings)
            self.solver.first_theta = self.jump_theta
        self.openings = new_openings
        h_start = float(self.solver.h[-1])
        self.solver.step()
        self.net += self.solver.last_net_inflow
        vol = np.zeros(6)
        for dt_i, hN, th in self.solver.last_substeps:          # θ-weighted volume over the substeps
            flows_new = self.node.flows(hN, self.openings)
            vol += dt_i * (th * flows_new + (1 - th) * self._flows_old)
            self._flows_old = flows_new
        self.delivered.add(self.day, vol / dt, dt)
        # regime diagnostics at the lowest node level of the step (its start or the end of any hydraulic substep):
        # an open regulator with a head below the transition head h_t of the gate law (where the head term departs
        # from √Δh), and an open gate raised clear of the water (opening at or above the upstream depth, where the
        # flow height is limited by the depth)
        h_min = min([h_start] + [p[1] for p in self.solver.last_substeps])
        head = h_min - np.asarray(self.node.tailwater_m, float)
        low = (self.openings[:5] > 0) & (head < self.h_t)
        if low.any():
            self.low_head_steps += 1
            self.low_head_volume += float(vol[:5][low].sum())
        if np.any((self.openings > 0) & (self.openings >= h_min)):
            self.gate_clear_steps += 1
        self.substeps += int(self.solver.substeps > self.solver.base_substeps)   # Newton fallbacks only
        self.k += 1
        return self._flows_old

    def mass_error(self):
        return abs(self.reach.volume(self.solver.h) - self.V0 - self.net) / self.V0

    def storage_change(self):
        return float(self.reach.volume(self.solver.h) - self.V0)


@dataclass
class Observation:
    t: float
    day: int
    step: int
    level: float                  # measured h_L (with ν)
    inflow: float                 # head-regulator discharge, m³/s
    openings: np.ndarray          # actuator positions, m


class StateEstimator:
    """State estimate (Section 2.4): measured level + ID prediction (7)-(8); delivered volume reconstructed from the
    actuator positions and the controller's C_d. Oracle receives the true state (perfect_information)."""

    def __init__(self, node_model, constraints, theta, P, h0, inflow0, iot):
        self.node, self.m, self.theta, self.iot = node_model, constraints, theta, iot
        self.ledger = DeliveryLedger(6, P)
        self.h = float(h0); self.hist = [inflow0] * constraints.d
        self._old = None
        # True: the gates hold the new openings over the whole step, so the reconstructed flow at the start of the
        # step is evaluated with the new openings at the previous level estimate (False: previous openings)
        self.constant_openings = bool(optional("ledger_constant_openings", False))
        # the same time weight as the plant: a fully implicit first step after a gate change (gate_change_first_theta)
        self.gate_jump = bool(optional("gate_change_at_step_start", False))
        self.jump_theta = optional("gate_change_first_theta", None)
        self._prev_openings = None

    def start(self, openings):
        self._old = self.node.flows(self.h, openings)
        self._prev_openings = np.array(openings, float).copy()

    def state(self, obs, plant=None):
        """ControlState for the controller. If plant is given (Oracle), the true level and volume are used."""
        led = plant.truth()["delivered"] if plant is not None else self.ledger.volume
        lvl = plant.truth()["level"] if plant is not None else self.h
        p = obs.day
        return ControlState(p, obs.step, obs.t, lvl, led[:, p].copy(), led[:, p - 1].copy() if p > 0 else None,
                            list(self.hist), obs.openings.copy())

    def update(self, obs_after, inflow_used):
        """Updates the estimate with the post-step measurement and reconstructs the delivery."""
        m = self.m
        h_prev = self.h
        if (self.iot.sensor_accuracy_m > 0 or self.iot.sensor_bias_m != 0 or self.iot.sensor_drift_m_per_day != 0
                or obs_after.level is None):                                                    # None: no telemetry
            q_rec = self.node.flows(self.h, obs_after.openings)
            pred = id_step(self.h, self.hist[0] if m.d > 0 else inflow_used, q_rec[:5], q_rec[5], m.A_s, m.dt, m.eta)
            self.h = update(obs_after.level, self.h, 0.0, 10.0, pred, self.iot.estimator_blend)  # None -> config
        else:
            self.h = float(obs_after.level)
        new = self.node.flows(self.h, obs_after.openings)
        old = self.node.flows(h_prev, obs_after.openings) if self.constant_openings else self._old
        changed = self._prev_openings is not None and not np.array_equal(obs_after.openings, self._prev_openings)
        th = self.jump_theta if (self.gate_jump and changed and self.jump_theta is not None) else self.theta
        self.ledger.add(obs_after.day if obs_after.step > 0 else obs_after.day - 1, th * new + (1 - th) * old, m.dt)
        self._old = new
        self._prev_openings = np.array(obs_after.openings, float).copy()
        if m.d > 0:
            self.hist = (self.hist + [inflow_used])[-m.d:]


class Actuator:
    """Command -> gate openings (controller's model of the node) -> quantisation and deadband (14) ->
    LoRaWAN message budget and loss (15) -> actuator position."""

    def __init__(self, node_model, iot, initial):
        self.node, self.iot = node_model, iot
        self.position = np.array(initial, float)
        self.limited = iot.message_budget is not None or iot.loss_probability > 0 or iot.channel_burst_fraction > 0
        self.link = LinkState(iot.message_window_steps or 1,
                              iot.message_budget if iot.message_budget is not None else 10 ** 9)
        self.packets_sent = 0                                   # packets actually transmitted (energy balance)
        self.lost_steps = np.zeros(6, int); self.last_lost = np.zeros(6, bool)
        self.interlock_steps = 0
        self.relief_steps = 0; self.relief_active = False
        self.tx_steps = 0                                       # steps at which the commanded opening changed
        self.pending = None                                     # delivered command executed at the next step
        self.delayed = 0; self.delayed_dropped = 0

    def relief(self, measured_level, open_level, release_level):
        """High level (Section 2.6): the Dustlik node has no emergency spillway (passport, Annex 4), so surplus water is
        passed to the next reach of the main canal, i.e. through the check structure to lower Kegeyli.
        When the measured level reaches open_level, the RTU fully opens the check structure and keeps it open until
        the level falls to release_level (hysteresis); the other gates follow the command. Returns: whether relief
        is active."""
        if measured_level >= open_level:
            self.relief_active = True
        elif self.relief_active and measured_level <= release_level:
            self.relief_active = False
        if self.relief_active:
            self.position[5] = self.node.max_opening[5]; self.relief_steps += 1
            return True
        return False

    def interlock(self, measured_level, threshold):
        """Local RTU low-level interlock (fail-safe): if the measured level is below the threshold, all gates are
        closed, without radio or budget, identically for all methods. Returns: whether the interlock acted."""
        if measured_level < threshold:
            self.position = np.zeros(6); self.interlock_steps += 1
            return True
        return False

    def executable(self, openings, previous):
        """Openings that the actuator realises from `previous` (quantisation and deadband, Equation (14))."""
        if self.iot.gate_resolution is None:
            a = np.array(openings, float)
            if self.iot.gate_deadband:                          # deadband without quantisation (closure always executed)
                keep = (np.abs(a - previous) < self.iot.gate_deadband * self.node.max_opening - 1e-12) & (a > 0)
                a[keep] = np.asarray(previous, float)[keep]
            return a
        frac = [quantize(a / amax, self.iot.gate_resolution, prev / amax, self.iot.gate_deadband)
                for a, amax, prev in zip(openings, self.node.max_opening, previous)]
        return np.array(frac) * self.node.max_opening

    def hold(self):
        """No command reaches the gates at this step (radio off, backhaul or mains outage); a delayed command that
        was due at this step is not executed."""
        if self.pending is not None:
            self.pending = None; self.delayed_dropped += 1
        return self.position.copy()

    def apply(self, command, level, step_index, link_draw=1.0, channel_bad=False, delay=False):
        """link_draw ∈ [0, 1) is the packet-loss draw of this step, taken from the communication stream at every
        step, so that packet losses do not depend on how many packets a controller sends. channel_bad: the channel
        is in its bad state (the packet is lost); delay: a delivered packet is executed at the start of the next
        step (a command delayed at the previous step is executed first)."""
        if self.pending is not None:
            self.position = self.pending; self.pending = None
        a_req, lost = command_to_openings(command, self.node, level, self.position)
        self.lost_steps += lost; self.last_lost = lost
        a_req = self.executable(a_req, self.position)
        changed = (not np.allclose(a_req, self.position)
                   if self.iot.gate_resolution is not None or self.iot.gate_deadband
                   else not np.array_equal(a_req, self.position))
        if changed:                                             # a packet is sent only when an opening changes
            self.tx_steps += 1
            if self.limited:
                sent_before = self.link.sent_total
                if transmit(self.link, step_index,
                            delivered=link_draw >= self.iot.loss_probability and not channel_bad):
                    self._execute(a_req, delay)
                self.packets_sent += self.link.sent_total - sent_before
            else:
                self._execute(a_req, delay); self.packets_sent += 1
        return self.position.copy()

    def _execute(self, a_req, delay):
        if delay:
            self.pending = a_req.copy(); self.delayed += 1
        else:
            self.position = a_req.copy()


class Recorder:
    """Per-step trace and daily plan."""
    KEYS = ("t", "h_true", "h_est", "q_in", "q_cmd", "q_true", "openings", "mu", "command_lost")

    def __init__(self, P):
        self.trace = {k: [] for k in self.KEYS}
        self.targets = np.full((6, P), np.nan)

    def write(self, day, command, **values):
        if command.target is not None:
            self.targets[:, day] = command.target
        values.setdefault("q_cmd", command.flows.copy()); values.setdefault("mu", command.info.get("mu", np.nan))
        values.setdefault("command_lost", np.zeros(6, bool))
        for k in self.KEYS:
            self.trace[k].append(values[k])

    def arrays(self):
        return {k: np.array(v) for k, v in self.trace.items()}


def run_closed_loop(controller, plant_reach, node_true, node_model, constraints, horizon, demand, supply_m3s,
                    forecast_m3, eta_true, h_init, iot=None, seed=0, theta=None, progress=None, pv_wh=None):
    """Single loop for all controllers (Section 2.10):

        for k in time_grid:
            observation = plant.observe()                       # sensors (with ν)
            state       = estimator.state(observation)          # Oracle: true state
            command     = controller.step(state=state, demand=demand, supply=supply, constraints=constraints,
                                          horizon=horizon)
            applied     = actuator.apply(command, …)
            plant.advance(applied, dt)
            estimator.update(plant.observe(), …);  recorder.write(…)

    node_true: node in the plant; node_model: the controller's model of it (C_d × 0.90 in the untuned test);
    supply_m3s: daily supply; forecast_m3: daily forecast η·S^lim (true η·S for Oracle).
    progress(p, P) is called at the end of each day (progress reporting for long runs; no effect on results).
    pv_wh: PV energy per step (required with iot.energy; from NASA POWER, prepared by the runner).
    With the energy factor, the radio is switched off when the charge falls below the reserve: the controller
    receives no measurements (prediction-only estimate) and commands do not arrive (gates stay in place); the
    local RTU interlock and relief rules keep operating. A backhaul outage acts in the same way (the node keeps its
    energy use). A lost telemetry packet leaves the controller without the measurement and the gate report of the
    step. During a mains outage of the gate drives the gates do not move: neither commands nor the local rules are
    executed (steps at which a local rule applied are counted)."""
    iot = iot or IoTConfig()
    theta = value("preissmann_theta") if theta is None else theta
    # Independent random streams for sensor noise and packet loss (common random numbers): each stream is drawn
    # once per control step, so every coalition of IoT constraints and every controller sees the same sensor
    # innovation and the same packet-loss draw at the same step.
    # The stress options use further streams (spawned children 2-6); children 0 and 1 are the same as with two
    # children, so runs without these options are unchanged.
    streams = np.random.SeedSequence(seed).spawn(7)
    sensor_rng, link_rng = (np.random.default_rng(s) for s in streams[:2])
    m, hz = constraints, horizon
    dt, spd = m.dt, hz.steps_per_day
    S = np.asarray(supply_m3s, float); P = S.size
    N = P * spd
    if iot.stress:
        up_rng, delay_rng, channel_rng, backhaul_rng, grid_rng = (np.random.default_rng(s) for s in streams[2:])
        up_lost = up_rng.random(N) < iot.uplink_loss_probability
        delayed = delay_rng.random(N) < iot.command_delay_probability
        burst = burst_sequence(channel_rng, N, iot.channel_burst_fraction, iot.channel_burst_mean_steps)
        backhaul_down = outage_sequence(backhaul_rng, N, iot.backhaul_outage_rate_per_day,
                                        iot.backhaul_outage_mean_hours, dt)
        grid_down = outage_sequence(grid_rng, N, iot.grid_outage_rate_per_day, iot.grid_outage_mean_hours, dt)
    else:
        up_lost = delayed = burst = backhaul_down = grid_down = np.zeros(N, bool)
    telemetry_lost = safety_blocked = 0
    oracle = getattr(controller, "perfect_information", False)
    forecast = m.eta * S * spd * dt if oracle else np.asarray(forecast_m3, float)
    controller.reset()

    def supply_at(p):
        nxt = S[p + 1] if (oracle and p + 1 < P) else (S[p] if oracle else None)
        return Supply(inflow_now=S[p], available_today=m.eta * S[p] * spd * dt, forecast=forecast, inflow_next=nxt)

    interlock_level = value("rtu_low_level_interlock_m")
    relief_open, relief_release = value("relief_open_level_m"), value("relief_release_level_m")
    plant = CanalPlant(plant_reach, node_true, S, eta_true, h_init, dt, spd, theta, sensor_rng, iot.sensor_accuracy_m,
                       iot.sensor_resolution_m, iot.sensor_bias_m, iot.sensor_drift_m_per_day)
    estimator = StateEstimator(node_model, m, theta, P, plant.h0[-1], S[0], iot)
    recorder = Recorder(P)
    energy = None
    if iot.energy:
        from ..iot.energy import EnergyNode
        if pv_wh is None or len(pv_wh) < P * spd:
            raise ValueError("The energy factor requires PV energy per step (pv_wh)")
        energy = EnergyNode(np.asarray(pv_wh, float), dt)

    # initial command (at the initial level) and balanced initial openings
    obs0 = Observation(0.0, 0, 0, float(plant.h0[-1]), float(S[0]), np.zeros(6))
    cmd0 = controller.step(state=estimator.state(obs0, plant if oracle else None), demand=demand,
                           supply=supply_at(0), constraints=m, horizon=hz).validate()
    a0, _ = command_to_openings(cmd0, node_model, plant.h0[-1], np.zeros(6))
    actuator = Actuator(node_model, iot, np.zeros(6))
    # initial openings: under quantisation they are those the actuator realises from the closed position
    actuator.position = plant.initialise_gates(
        a0, None if iot.gate_resolution is None else (lambda a: actuator.executable(a, np.zeros(6))))
    estimator.start(actuator.position)

    day_target = np.zeros(6)                                   # daily plan of the current day (H6 reference)
    exec_viol = np.full((3, P), np.nan)                        # daily maxima of the execution LP's violations
    viol_keys = ("first_command_violation", "first_rate_violation", "first_level_slack")
    head_lost_steps = np.zeros(6, int)
    known_openings = actuator.position.copy()                  # gate positions last reported over the radio
    radio_prev = True                                          # telemetry during the previous step

    for k in range(N):                                         # time_grid
        p = k // spd
        if k == 0:
            observation, command = obs0, cmd0
        else:
            observation = last_obs                             # measurement at the end of the previous step
            if not radio_prev:                                 # no telemetry: the controller knows the reported gates
                observation = Observation(last_obs.t, last_obs.day, last_obs.step, last_obs.level, last_obs.inflow,
                                          known_openings.copy())
            state = estimator.state(observation, plant if oracle else None)
            command = controller.step(state=state, demand=demand, supply=supply_at(p), constraints=m,
                                      horizon=hz).validate()
        info = getattr(command, "info", None) or {}
        if viol_keys[0] in info:
            exec_viol[:, p] = np.fmax(exec_viol[:, p], [float(info[key]) for key in viol_keys])
        level_for_gates = plant.truth()["level"] if oracle else estimator.h
        radio = energy is None or energy.radio_on
        link = radio and not backhaul_down[k]                  # the controller can reach the node at this step
        link_draw = link_rng.random()                          # drawn at every step (common random numbers)
        tx0 = actuator.packets_sent
        if grid_down[k]:                                       # no mains supply: the gates cannot move
            applied = actuator.hold()
            safety_blocked += int(observation.level < interlock_level or observation.level >= relief_open)
        else:
            applied = (actuator.apply(command, level_for_gates, k, link_draw, bool(burst[k]), bool(delayed[k]))
                       if link else actuator.hold())
            if actuator.interlock(observation.level, interlock_level):
                applied = actuator.position.copy()
            elif actuator.relief(observation.level, relief_open, relief_release):
                applied = actuator.position.copy()
        q_true = plant.advance(applied, dt)
        # H6: a regulator lacks head when, at the true level, even its full opening cannot pass the planned rate
        if command.target is not None:
            day_target = np.asarray(command.target, float)
        req = day_target / (spd * dt)
        head_lost = np.zeros(6, bool)
        head_lost[:5] = (req[:5] > 0) & (node_true.max_flows(plant.truth()["level"])[:5] < req[:5] * (1 - 1e-6))
        head_lost_steps += head_lost
        last_obs = plant.observe()                             # observation: z = h + ν (once per step)
        telemetry = link and not (up_lost[k] or burst[k])      # the telemetry packet of the step arrives
        telemetry_lost += int(link and not telemetry)
        if telemetry:
            known_openings = last_obs.openings.copy()
            estimator.update(last_obs, S[p])
        else:                                                  # no telemetry: prediction only, last reported gates
            estimator.update(Observation(last_obs.t, last_obs.day, last_obs.step, None, last_obs.inflow,
                                         known_openings.copy()), S[p])
        radio_prev = telemetry
        if energy is not None:                                 # (16): load and messages (uplink + downlink)
            energy.advance(k, int(radio) + (actuator.packets_sent - tx0))
        recorder.write(p, command, t=plant.solver.t, h_true=plant.truth()["level"], h_est=estimator.h, q_in=S[p],
                       q_true=q_true, openings=applied.copy(), command_lost=head_lost)
        if progress is not None and (k + 1) % spd == 0:
            progress(p + 1, P)
    return ClosedLoopResult(plant.delivered.volume, estimator.ledger.volume, recorder.targets, recorder.arrays(),
                            float(plant.mass_error()), 0 if iot is None or iot.ideal else actuator.packets_sent,  # 0 if phys
                            actuator.link.dropped if actuator.limited else 0, head_lost_steps, plant.substeps, plant.storage_change(),
                            actuator.interlock_steps, actuator.relief_steps,
                            None if energy is None else float(energy.min_wh),
                            0 if energy is None else energy.radio_off_steps,
                            0.0 if energy is None else float(energy.used_wh),
                            actuator.link.blocked if actuator.limited else 0,
                            actuator.link.lost if actuator.limited else 0,
                            plant.low_head_steps, plant.low_head_volume, plant.gate_clear_steps, exec_viol,
                            telemetry_lost, int(burst.sum()), int(backhaul_down.sum()), int(grid_down.sum()),
                            actuator.delayed, actuator.delayed_dropped, safety_blocked)
