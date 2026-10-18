"""State objects: plant, node gates and delivered-volume ledger."""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class CanalState:
    """Reach state at the computational nodes: depth h [m], discharge Q [m³/s], time t [s]."""
    t: float
    h: np.ndarray
    Q: np.ndarray

    def copy(self):
        return CanalState(float(self.t), self.h.copy(), self.Q.copy())

    @property
    def level_downstream(self):
        """h_L: water level upstream of the node (above the reach bed)."""
        return float(self.h[-1])

    @property
    def inflow(self):
        return float(self.Q[0])

    @property
    def outflow(self):
        return float(self.Q[-1])


@dataclass
class NodeGates:
    """Gate openings [m] of the Dustlik node: 5 regulators and the check structure."""
    regulators: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)
    barrier: float = 0.0

    def __post_init__(self):
        if len(self.regulators) != 5:
            raise ValueError("Exactly 5 regulator openings are required")
        if min(self.regulators) < 0 or self.barrier < 0:
            raise ValueError("Openings cannot be negative")


@dataclass
class DeliveryLedger:
    """Daily delivered volume V_j[p] [m³] per user; days already executed are fixed in the LP."""
    users: int
    days: int
    volume: np.ndarray = field(init=False)

    def __post_init__(self):
        self.volume = np.zeros((self.users, self.days))

    def add(self, day, flows_m3s, dt_s):
        """Adds the discharge (m³/s) delivered during one control step to the volume: V_j[p] += q_j Δt."""
        q = np.asarray(flows_m3s, float)
        if q.shape != (self.users,) or (q < 0).any():
            raise ValueError("Invalid discharge vector")
        self.volume[:, day] += q * dt_s

    def fixed(self, day):
        """For the receding horizon: {(j, 0): V_j[day]}, the volumes of this day held fixed in the LP."""
        return {(j, 0): float(self.volume[j, day]) for j in range(self.users)}
