"""Internal controller model and its parameters (Section 2.4).

The controller does not see the plant: it knows only the ID model (8) parameters (A_s, d, η), the chords of the
command constraint (9), the passport capacities and the level bounds. The chords are built in the simulation layer
from the node model (with the controller's C_d) and passed in here; the control layer does not import hydraulics.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class ControllerModel:
    """The `constraints` of the interface: the controller's internal model and constraints."""
    dt: float                      # control step Δt, s
    eta: float                     # conveyance efficiency (nominal)
    A_s: float                     # ID model storage (surface) area, m²
    d: int                         # delay, steps
    chords: list                   # [(α, β)] × 6, for (9)
    capacity: np.ndarray           # c̄_j, m³/s (6)
    h_lo: float                    # H_min^op
    h_hi: float                    # H_max − f_b
    h_ref: float                   # H_norm
    dq_max: np.ndarray             # gate rate limit, m³/s per step (6)
    epsilon_1: float               # fairness tolerances (configuration: fairness)
    epsilon_2: float
    pulse_flow: object = None      # h ↦ [6] discharge at the smallest executable opening (LXB-DA)

    def daily_capacity(self, steps_per_day):
        return self.capacity * steps_per_day * self.dt
