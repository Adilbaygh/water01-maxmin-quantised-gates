"""Section 2.3, Equation (6): gate equation, tuned/untuned protocol and the Dustlik node (PK 114+40).

The node is the downstream internal boundary of the reach. Outflow = 5 regulators + the check structure. The
tailwater level of the check structure is taken from the Manning rating curve of the next Kegeyli reach
(PK 114+40 to 366+00), so Q_C is obtained from an implicit equation. Gate coefficients and regulator tailwater
levels are not given in the passport and are assumed (covered by the sensitivity analysis). All levels are measured
from the reach bed; no bed-level step at the structure is assumed.
"""
import math
from bisect import bisect_right
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from ..domain.geometry import Reach, lower_reach
from ..domain.passport import active, value
from .saint_venant import G

SQRT_2G = math.sqrt(2 * G)
_LAW = {"cfg": None}


def _law():
    """Gate-law settings of the active configuration, cached for each configuration object."""
    cfg = active()
    if _LAW["cfg"] is not cfg:
        _LAW.update(cfg=cfg, h_t=float(cfg.value("gate_head_transition_m")),
                    p=float(cfg.value("gate_clear_smoothing_exponent")), cc=float(cfg.value("gate_contraction")))
    return _LAW


def max_openings():
    """Maximum gate openings (passport): 5 regulators + check structure, m."""
    return np.r_[np.asarray(value("regulator_gate_height_m"), float), value("barrier_gate_height_m")]


def head_term(head, h_t=None):
    """√(head⁺) of Equation (6) with a C¹ transition above zero head (h_t = gate_head_transition_m):
    s = √head for head ≥ h_t, s = √h_t·t²(2.5 − 1.5t) with t = head/h_t for 0 < head < h_t, and s = 0 for
    head ≤ 0. No water passes a gate at zero or negative head (the outlet canals are not modelled, so there is no
    reverse flow), and the derivative is continuous, so Newton iterations do not cycle when the head crosses zero."""
    h_t = _law()["h_t"] if h_t is None else h_t
    if head >= h_t:
        return math.sqrt(head)
    if head <= 0.0:
        return 0.0
    t = head / h_t
    return math.sqrt(h_t) * t * t * (2.5 - 1.5 * t)


def head_term_slope(head, h_t=None):
    """Derivative of head_term with respect to the head."""
    h_t = _law()["h_t"] if h_t is None else h_t
    if head >= h_t:
        return 0.5 / math.sqrt(head)
    if head <= 0.0:
        return 0.0
    t = head / h_t
    return (5.0 * t - 4.5 * t * t) / math.sqrt(h_t)


def effective_opening(opening, upstream_depth, p=None):
    """Height of the flow section of a gate: the opening a while the gate is in the water and the upstream depth h_u
    once it is raised clear of the water (free-surface flow through the structure), min(a, h_u) smoothed by the
    p-norm (a^−p + h_u^−p)^(−1/p). The smoothing acts only where a and h_u are within a factor of two of each other;
    elsewhere the smaller value is returned exactly."""
    a, h = float(opening), float(upstream_depth)
    if a <= 0.0 or h <= 0.0:
        return 0.0
    if a <= 0.5 * h:
        return a
    if h <= 0.5 * a:
        return h
    p = _law()["p"] if p is None else p
    m, M = (a, h) if a < h else (h, a)
    return m * (1.0 + (m / M) ** p) ** (-1.0 / p)


def opening_for_effective(e, upstream_depth, p=None):
    """Inverse of effective_opening: the opening that gives the flow height e; inf when e ≥ h_u (unreachable)."""
    e, h = float(e), float(upstream_depth)
    if e <= 0.0:
        return 0.0
    if e <= 0.5 * h:
        return e
    if e >= h:
        return math.inf
    p = _law()["p"] if p is None else p
    return h * ((h / e) ** p - 1.0) ** (-1.0 / p)


def gate_discharge(opening_m, upstream_level, downstream_level, width_m, cd, free_flow=False, contraction=None):
    """(6): q = C_d b a_e √(2g) s(h_u − h_d), with s = head_term (√ of the positive head) and a_e = the opening, or
    the upstream depth when the gate is raised clear of the water (effective_opening). For free flow, h_d is
    replaced by the contracted depth C_c·a. All levels are measured from the reach bed (no sill step)."""
    a = float(opening_m)
    if a <= 0.0:
        return 0.0
    law = _law()
    hu = float(upstream_level)
    hd = (law["cc"] if contraction is None else contraction) * a if free_flow else float(downstream_level)
    s = head_term(hu - hd, law["h_t"])
    if s == 0.0:
        return 0.0
    return float(cd * width_m * effective_opening(a, hu, law["p"]) * SQRT_2G * s)


def opening_for_flow(flow, upstream_level, downstream_level, width_m, cd):
    """Inverse relation (submerged flow): the opening that passes `flow`. Raises an error at zero or negative head
    (no command can pass water); returns inf when the flow cannot be passed even with the gate raised clear of the
    water."""
    head = float(upstream_level) - float(downstream_level)
    if head <= 0.0:
        raise ValueError("No head across the gate: command lost")
    q = max(float(flow), 0.0)
    if q == 0.0:
        return 0.0
    return opening_for_effective(q / (cd * width_m * SQRT_2G * head_term(head)), upstream_level)


EM_BLEND_M = 0.05             # m: band of the tail water above the conjugate depth over which the relations are blended
SMALL_REGULATORS = (1, 2, 3, 4)  # outlets 2-5 (R-1, Khalkabad-2, Kanly-Yab, K-2): the energy-momentum option


def em_discharge(opening_m, upstream_level, downstream_level, width_m, cc, h_t=None, w=EM_BLEND_M):
    """Energy-momentum discharge of a sluice gate (m3/s), an option for the small regulators (gate_relation_plant,
    gate_relation_controller; default: relation (6) in its submerged form).

    Contracted jet of depth y1 = cc*a_e. Free jet: energy from the upstream section to the contracted section,
    h_u + q^2/(2g h_u^2) = y1 + q^2/(2g y1^2) (q per unit width). The jet is free when the tail water h_d lies below
    the depth y2 conjugate to y1. Otherwise, the depth y over the contracted jet follows from the same energy equation
    with y instead of y1 for the pressure term and the momentum balance y^2/2 + q^2/(g y1) = h_d^2/2 + q^2/(g h_d),
    whose larger root is taken; the drowned discharge is blended into the free one over h_d - y2 in [0, w] with a C1
    step. The head term uses the C1 transition of (6), and the contraction coefficient equals the discharge
    coefficient of (6); for a drowned jet of a small opening the two relations then differ by about 1%, and the
    energy-momentum discharge is larger where the jet is free or nearly free."""
    a = float(opening_m); hu = float(upstream_level); hd = float(downstream_level)
    if a <= 0.0 or hu <= 0.0:
        return 0.0
    law = _law()
    h_t = law["h_t"] if h_t is None else h_t
    ae = effective_opening(a, hu, law["p"])
    if ae <= 0.0:
        return 0.0
    y1 = cc * ae
    if y1 >= hu:
        return 0.0
    corr = 1.0 / math.sqrt(1.0 - (y1 / hu) ** 2)
    q_free = width_m * y1 * SQRT_2G * head_term(hu - y1, h_t) * corr
    qu = q_free / width_m
    y2 = 0.5 * y1 * (math.sqrt(1.0 + 8.0 * qu * qu / (G * y1 ** 3)) - 1.0)
    if hd <= y2:
        return float(q_free)
    inv = 1.0 / y1
    k = 4.0 * (1.0 / hd - inv) / (inv * inv - 1.0 / (hu * hu))
    disc = max(k * k + 4.0 * (hd * hd + k * hu), 0.0)
    y = max(0.5 * (-k + math.sqrt(disc)), y1)
    q_sub = width_m * y1 * SQRT_2G * head_term(hu - y, h_t) * corr
    t = (hd - y2) / w
    if t >= 1.0:
        return float(q_sub)
    s = t * t * (3.0 - 2.0 * t)
    return float(q_free + (q_sub - q_free) * s)


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
    relation: str = "submerged"     # "submerged": relation (6) for every gate; "energy_momentum": em_discharge at the
                                    # small regulators (outlets 2-5), relation (6) at Abad-Yarmish and the barrier
    leak_opening_m: float = 0.0     # leakage of the regulators, as an equivalent opening (plant only; 0: gates seal)

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
        self._q_list, self._h_list = self._q_tab.tolist(), self._h_tab.tolist()
        self._q_last = None                     # last check-structure discharge (starting value of the next solve)
        if self.relation not in ("submerged", "energy_momentum"):
            raise ValueError(f"Unknown gate relation: {self.relation}")

    def _regulator_flow(self, j, a, h_up, cd):
        """Discharge of regulator j (0-4) at opening a: relation (6), or the energy-momentum relation at the small
        regulators; with leakage, a closed or almost closed gate passes at least the flow of the leakage opening."""
        if self.leak_opening_m > 0.0:
            a = max(float(a), self.leak_opening_m)
        if a <= 0.0:
            return 0.0
        if self.relation == "energy_momentum" and j in SMALL_REGULATORS:
            return em_discharge(a, h_up, self.tailwater_m[j], self.reg_width[j], cd)
        return gate_discharge(a, h_up, self.tailwater_m[j], self.reg_width[j], cd)

    def tailwater_barrier(self, Q):
        return float(np.interp(Q, self._q_tab, self._h_tab))

    def _tailwater_and_slope(self, Q):
        """Tabulated normal depth of the lower reach at Q (linear interpolation, as tailwater_barrier) and its slope."""
        q, h = self._q_list, self._h_list
        if Q <= q[0]:
            return h[0], (h[1] - h[0]) / (q[1] - q[0])
        if Q >= q[-1]:
            return h[-1], 0.0
        i = bisect_right(q, Q) - 1
        slope = (h[i + 1] - h[i]) / (q[i + 1] - q[i])
        return h[i] + (Q - q[i]) * slope, slope

    def offtakes(self, h_up, openings):
        """Discharge of the 5 regulators (submerged flow, constant tailwater level)."""
        if self.relation == "submerged" and self.leak_opening_m <= 0.0:
            return self.offtake_factor * np.array([gate_discharge(a, h_up, hd, w, self.cd)
                                                   for a, hd, w in zip(openings, self.tailwater_m, self.reg_width)])
        return self.offtake_factor * np.array([self._regulator_flow(j, a, h_up, self.cd)
                                               for j, a in enumerate(openings)])

    def barrier(self, h_up, opening, cd=None):
        """Check-structure discharge: Q = C_d b a_e √(2g) s(h_up − h_tw(Q)), h_tw = normal depth in the lower reach.
        The implicit equation is solved by Newton's method safeguarded by bisection on [0, Q(h_tw = 0)]."""
        cd = self.cd if cd is None else cd
        if opening <= 0 or h_up <= 0:
            return 0.0
        law = _law()
        K = cd * self.bar_width * effective_opening(opening, h_up, law["p"]) * SQRT_2G
        h_t = law["h_t"]
        q_hi = K * head_term(h_up, h_t)
        if q_hi <= 0.0:
            return 0.0
        tw, _ = self._tailwater_and_slope(q_hi)
        if q_hi - K * head_term(h_up - tw, h_t) <= 0.0:
            return q_hi
        lo, hi = 0.0, q_hi
        Q = self._q_last if (self._q_last is not None and 0.0 < self._q_last < q_hi) else 0.5 * q_hi
        tol = 1e-13 * max(1.0, q_hi)
        for _ in range(100):
            tw, slope = self._tailwater_and_slope(Q)
            head = h_up - tw
            f = Q - K * head_term(head, h_t)
            if f == 0.0:
                break
            if f < 0.0:
                lo = Q
            else:
                hi = Q
            df = 1.0 + K * head_term_slope(head, h_t) * slope
            Qn = Q - f / df
            if not lo < Qn < hi:
                Qn = 0.5 * (lo + hi)
            if abs(Qn - Q) <= tol or hi - lo <= tol:
                Q = Qn
                break
            Q = Qn
        self._q_last = Q
        return Q

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
        if self.relation == "submerged":
            reg = [gate_discharge(a, h_up, hd, w, cd)
                   for a, hd, w in zip(self.reg_max, self.tailwater_m, self.reg_width)]
        else:
            reg = [self._regulator_flow(j, a, h_up, cd) for j, a in enumerate(self.reg_max)]
        return np.r_[self.offtake_factor * np.array(reg), self.barrier(h_up, self.bar_max, cd)]

    def openings_for(self, flows6, h_up, cd=None):
        """Inverse computation: openings [m] for the required discharges (using the estimated level and the
        controller-model C_d). Openings are capped at the gate height; at zero or negative head, or when even the
        full opening cannot pass the discharge, the gate is fully opened and the command is marked as lost.
        Returns: (openings, mask of outlets whose command was lost)."""
        cd = self.cd if cd is None else cd
        a = np.zeros(6); lost = np.zeros(6, bool)
        for j in range(5):
            q = max(float(flows6[j]), 0.0)
            if q == 0.0:
                continue
            head = h_up - self.tailwater_m[j]
            if head <= 0.0:
                a[j] = self.reg_max[j]; lost[j] = True; continue
            if self.relation == "energy_momentum" and j in SMALL_REGULATORS:
                q_full = em_discharge(self.reg_max[j], h_up, self.tailwater_m[j], self.reg_width[j], cd)
                if q >= q_full:
                    a[j] = self.reg_max[j]; lost[j] = q > q_full + 1e-12; continue
                a[j] = brentq(lambda x: em_discharge(x, h_up, self.tailwater_m[j], self.reg_width[j], cd) - q,
                              0.0, self.reg_max[j], xtol=1e-12)
                continue
            a[j] = opening_for_flow(q, h_up, self.tailwater_m[j], self.reg_width[j], cd)
            if a[j] > self.reg_max[j]:
                a[j] = self.reg_max[j]; lost[j] = True
        q6 = max(float(flows6[5]), 0.0)
        if q6 > 0.0:
            q_full = self.barrier(h_up, self.bar_max, cd)
            if q6 >= q_full:
                a[5] = self.bar_max; lost[5] = q6 > q_full + 1e-9
            else:
                try:
                    a[5] = brentq(lambda x: self.barrier(h_up, x, cd) - q6, 0.0, self.bar_max, xtol=1e-9)
                except ValueError:
                    # q6 is within the solver tolerance of q_full (about 1e-11 m3/s): the warm-started evaluations of
                    # the implicit barrier relation then differ in sign; the barrier is opened fully
                    a[5] = self.bar_max
        return a, lost
