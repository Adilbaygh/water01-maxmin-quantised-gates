"""Common controller interface (Section 2.8).

    command = controller.step(state=state, demand=demand, supply=supply, constraints=constraints, horizon=horizon)

All controllers (B0, B1, B2, B3, LXB, Oracle) are called in this form. The controller does not see the plant:
- state       -- state known to the controller (estimated level, estimated delivered volume, actuator state);
- demand      -- daily demand D_j[p];
- supply      -- observed inflow and limit forecast (for Oracle, the true future);
- constraints -- internal model and constraints (control.model.ControllerModel);
- horizon     -- planning and execution horizons.
A Command specifies, for each outlet, one of three things: a discharge (m³/s, converted to a gate opening), an
opening (m) or "hold" (both NaN).
"""
from dataclasses import dataclass, field

import numpy as np

N_OUTLETS = 6


@dataclass
class ControlState:
    day: int                       # p: day index (0 = start of period)
    step: int                      # k: step within the day (0 = start of day)
    t: float                       # s
    level: float                   # estimated h_L (true value for Oracle)
    delivered_today: np.ndarray    # estimated V_j[p] so far, m³
    delivered_prev: np.ndarray     # yesterday's estimated V_j[p−1], or None
    inflow_history: list           # last d inflows (oldest first), m³/s
    openings: np.ndarray           # actuator positions (RTU report), m

    @property
    def new_day(self):
        return self.step == 0


@dataclass
class Demand:
    D: np.ndarray                  # [J × P] daily demand, m³
    weights: np.ndarray = None     # w_j (None: all equal to 1)


@dataclass
class Supply:
    inflow_now: float              # observed head-regulator discharge, m³/s
    available_today: float         # water expected at the node today, η·S·day, m³
    forecast: np.ndarray           # [P] expected daily water (η·S^lim; for Oracle the true η·S), m³
    inflow_next: float = None      # tomorrow's inflow (Oracle only), m³/s


@dataclass
class Horizon:
    days: int                      # daily planning window
    steps_per_day: int
    lookahead_steps: int           # execution LP: to the end of the day + next-day lookahead
    fine_steps: int                # move blocking: first part at Δt
    block_steps: int               # then blocks

    @classmethod
    def from_config(cls):
        """All values from the configuration (sections control, numerics)."""
        from ..domain.passport import value
        return cls(value("horizon_days"), value("steps_per_day"), value("execution_lookahead_steps"),
                   value("execution_fine_steps"), value("execution_block_steps"))


@dataclass
class Command:
    flows: np.ndarray = field(default_factory=lambda: np.full(N_OUTLETS, np.nan))      # m³/s
    openings: np.ndarray = field(default_factory=lambda: np.full(N_OUTLETS, np.nan))   # m
    conversion_level: np.ndarray = field(default_factory=lambda: np.full(N_OUTLETS, np.nan))
    # level used to convert discharge to opening: NaN = estimated h_L; a number = nominal level (no feedback)
    target: np.ndarray = None      # daily plan V_j[p] (for logging), m³
    info: dict = field(default_factory=dict)

    @staticmethod
    def hold():
        return Command()

    def validate(self):
        both = np.isfinite(self.flows) & np.isfinite(self.openings)
        if both.any():
            raise ValueError("Both discharge and opening given for the same outlet")
        if (self.flows[np.isfinite(self.flows)] < 0).any() or (self.openings[np.isfinite(self.openings)] < 0).any():
            raise ValueError("Negative command")
        return self


class Controller:
    """Base class. perfect_information = True: the closed loop supplies the true state and future (Oracle)."""
    name = "base"
    perfect_information = False

    def step(self, state, demand, supply, constraints, horizon):
        raise NotImplementedError

    def reset(self):
        """Clears the internal state before a new run."""
