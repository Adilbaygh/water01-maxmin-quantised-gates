"""Section 2.3, Equation (6): gate equation, tuned/untuned protocol and the Dustlik node (PK 114+40).

The node is the downstream internal boundary of the reach. Outflow = 5 regulators + the check structure. The
tailwater level of the check structure is taken from the Manning rating curve of the next Kegeyli reach
(PK 114+40 to 366+00), so Q_C is obtained from an implicit equation. Gate coefficients and regulator tailwater
levels are not given in the passport and are assumed (covered by the sensitivity analysis). All levels are measured
from the reach bed; no bed-level step at the structure is assumed.
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from ..domain.geometry import Reach, lower_reach
from ..domain.passport import value
from .saint_venant import G

def max_openings():
    """Maximum gate openings (passport): 5 regulators + check structure, m."""
    return np.r_[np.asarray(value("regulator_gate_height_m"), float), value("barrier_gate_height_m")]


def _sqrt_head(head):
    """Smooth form of √(head⁺): √(h₀·ln(1 + e^{head/h₀})), h₀ = gate_head_regularisation_m (softplus).
    Equals √head for head ≫ h₀ (relative difference < 10⁻⁴ for head ≥ 10 h₀) and decays quickly to zero for
    head < 0. There is no kink, so Newton iterations do not cycle when the head across a gate crosses zero
    (e.g. August 2011 under B1, Abad-yarmish gate fully open, h_L = 1.50 m)."""
    h0 = value("gate_head_regularisation_m")
    x = head / h0
    if x > 30.0:
        return float(np.sqrt(head))
    if x < -30.0:
        return 0.0
    return float(np.sqrt(h0 * np.log1p(np.exp(x))))


def gate_discharge(opening_m, upstream_level, downstream_level, width_m, cd, free_flow=False, contraction=None):
    """(6): q = C_d b a √(2g [h_u − h_d]^+). For free flow, h_d is replaced by the contracted depth C_c·a."""
    contraction = value("gate_contraction") if contraction is None else contraction
    a = max(float(opening_m), 0.0)
    hd = contraction * a if free_flow else float(downstream_level)
    head = float(upstream_level) - hd
    return float(cd * width_m * a * np.sqrt(2 * G) * _sqrt_head(head))


def opening_for_flow(flow, upstream_level, downstream_level, width_m, cd):
    """Inverse relation (submerged flow): required opening. Raises an error if the head is near zero (no command)."""
    head = float(upstream_level) - float(downstream_level)
    if head <= 1e-6:
        raise ValueError("No head across the gate: command lost")
    return max(float(flow), 0.0) / (cd * width_m * np.sqrt(2 * G * head))


def untuned_factors(tuned, controller_gate_factor=None, offtake_factor=None):
    """Untuned test: the controller underestimates gate discharge by 10%, the actual offtake exceeds the plan by 5%.
    Returns: (C_d multiplier in the controller model, offtake multiplier in the plant)."""
    if tuned:
        return 1.0, 1.0
    return (value("untuned_controller_gate_factor") if controller_gate_factor is None else controller_gate_factor,
            value("untuned_offtake_factor") if offtake_factor is None else offtake_factor)


@dataclass
class DustlikNode:
    """Node with 6 outlets: j = 1..5 regulators, j = 6 check structure (lower Kegeyli).
    offtake_factor: actual offtake multiplier in the plant (1.05 in the untuned test)."""
    cd: float = None                # None: from configuration (gate_cd, regulator_tailwater_m, passport)
    tailwater_m: tuple = None
    lower: Reach = None
    offtake_factor: float = 1.0

    def __post_init__(self):
        self.cd = value("gate_cd") if self.cd is None else self.cd
        self.tailwater_m = tuple(value("regulator_tailwater_m")) if self.tailwater_m is None else self.tailwater_m
        self.lower = lower_reach() if self.lower is None else self.lower
        self.reg_width = tuple(value("regulator_width_m")); self.bar_width = value("barrier_width_m")
        self.reg_max = tuple(value("regulator_gate_height_m")); self.bar_max = value("barrier_gate_height_m")
        self.max_opening = max_openings()
        # check-structure tailwater: tabulated normal depth (avoids calling brentq every time)
        self._q_tab = np.r_[0.0, np.geomspace(1e-3, 250.0, 3000)]
        self._h_tab = np.array([self.lower.normal_depth(q) for q in self._q_tab])

    def tailwater_barrier(self, Q):
        return float(np.interp(Q, self._q_tab, self._h_tab))

    def offtakes(self, h_up, openings):
        """Discharge of the 5 regulators (submerged flow, constant tailwater level)."""
        return self.offtake_factor * np.array([gate_discharge(a, h_up, hd, w, self.cd)
                                               for a, hd, w in zip(openings, self.tailwater_m, self.reg_width)])

    def barrier(self, h_up, opening, cd=None):
        """Check-structure discharge: Q = C_d b a √(2g (h_up − h_tw(Q))), h_tw = normal depth in the lower reach."""
        cd = self.cd if cd is None else cd
        if opening <= 0 or h_up <= 0:
            return 0.0
        f = lambda Q: Q - gate_discharge(opening, h_up, self.tailwater_barrier(Q), self.bar_width, cd)
        q_hi = gate_discharge(opening, h_up, 0.0, self.bar_width, cd)
        if f(q_hi) <= 0:
            return q_hi
        return brentq(f, 0.0, q_hi, xtol=1e-10)

    def flows(self, h_up, openings6):
        """Discharge of all 6 outlets [m³/s]: 5 regulators + check structure."""
        return np.r_[self.offtakes(h_up, openings6[:5]), self.barrier(h_up, openings6[5])]

    def outflow(self, h_up, regulator_openings, barrier_opening):
        return float(self.offtakes(h_up, regulator_openings).sum() + self.barrier(h_up, barrier_opening))

    def outflow_for(self, gates):
        """Convenience wrapper for domain.state.NodeGates: h_L -> Q_out."""
        return lambda h_up: self.outflow(h_up, gates.regulators, gates.barrier)

    def max_flows(self, h_up, cd=None):
        """Discharge f_j(h_L) with fully open gates, for command constraint (9) (without capacity limits); the
        regulators include the offtake factor of this node (1 for the controller model)."""
        cd = self.cd if cd is None else cd
        reg = [gate_discharge(a, h_up, hd, w, cd) for a, hd, w in zip(self.reg_max, self.tailwater_m, self.reg_width)]
        return np.r_[self.offtake_factor * np.array(reg), self.barrier(h_up, self.bar_max, cd)]

    def openings_for(self, flows6, h_up, cd=None):
        """Inverse computation: openings [m] for the required discharges (using the estimated level and the
        controller-model C_d). Openings are capped at the gate height; with no head the gate is fully opened
        (command lost).
        Returns: (openings, mask of outlets whose command was lost)."""
        cd = self.cd if cd is None else cd
        a = np.zeros(6); lost = np.zeros(6, bool)
        for j in range(5):
            q = max(float(flows6[j]), 0.0)
            if q == 0.0:
                continue
            head = h_up - self.tailwater_m[j]
            if head <= 1e-6:
                a[j] = self.reg_max[j]; lost[j] = True; continue
            a[j] = opening_for_flow(q, h_up, self.tailwater_m[j], self.reg_width[j], cd)
            if a[j] > self.reg_max[j]:
                a[j] = self.reg_max[j]; lost[j] = True
        q6 = max(float(flows6[5]), 0.0)
        if q6 > 0.0:
            q_full = self.barrier(h_up, self.bar_max, cd)
            if q6 >= q_full:
                a[5] = self.bar_max; lost[5] = q6 > q_full + 1e-9
            else:
                a[5] = brentq(lambda x: self.barrier(h_up, x, cd) - q6, 0.0, self.bar_max, xtol=1e-9)
        return a, lost
