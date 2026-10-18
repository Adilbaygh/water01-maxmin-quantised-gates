"""Sections 2.1 and 2.3: trapezoidal cross-section, Manning formula, Q_c and prismatic reach.

Base values are taken from the passport registry (domain.passport).
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from .passport import value

def _bm(bottom_width, side_slope):
    """All values are read from the active configuration at call time (so that scenarios take effect)."""
    return (value("b_actual_m") if bottom_width is None else bottom_width,
            value("side_slope") if side_slope is None else side_slope)


def area(depth, bottom_width=None, side_slope=None):
    b, m = _bm(bottom_width, side_slope)
    depth = np.asarray(depth, dtype=float)
    return depth * (b + m * depth)


def top_width(depth, bottom_width=None, side_slope=None):
    b, m = _bm(bottom_width, side_slope)
    return b + 2.0 * m * np.asarray(depth, dtype=float)


def wetted_perimeter(depth, bottom_width=None, side_slope=None):
    b, m = _bm(bottom_width, side_slope)
    depth = np.asarray(depth, dtype=float)
    return b + 2 * depth * np.sqrt(1 + m ** 2)


def hydraulic_radius(depth, bottom_width=None, side_slope=None):
    return area(depth, bottom_width, side_slope) / wetted_perimeter(depth, bottom_width, side_slope)


def manning_discharge(depth, slope=None, roughness=None, bottom_width=None, side_slope=None):
    slope = value("S0") if slope is None else slope
    roughness = value("n_manning") if roughness is None else roughness
    a = area(depth, bottom_width, side_slope); r = hydraulic_radius(depth, bottom_width, side_slope)
    return a / roughness * r ** (2 / 3) * np.sqrt(slope)


def critical_supply(h_min=None, **kwargs):
    """Q_c corresponding to normal depth H_min; a purely geometric derived quantity."""
    return float(manning_discharge(value("H_min_m") if h_min is None else h_min, **kwargs))


@dataclass
class Reach:
    """Prismatic trapezoidal reach (Saint-Venant computational domain). N is the number of nodes."""
    L: float = None                 # None: read from configuration (L_m, b_actual_m, side_slope, S0, n_manning,
    b: float = None                 #       preissmann_nodes)
    m: float = None
    S0: float = None
    n: float = None
    N: int = None
    x: np.ndarray = field(init=False)
    dx: float = field(init=False)

    def __post_init__(self):
        for attr, key in (("L", "L_m"), ("b", "b_actual_m"), ("m", "side_slope"), ("S0", "S0"), ("n", "n_manning"),
                          ("N", "preissmann_nodes")):
            if getattr(self, attr) is None:
                setattr(self, attr, value(key))
        if self.N < 3:
            raise ValueError("N ≥ 3")
        self.x = np.linspace(0.0, self.L, self.N)
        self.dx = self.L / (self.N - 1)

    def area(self, h):
        return h * (self.b + self.m * h)

    def top(self, h):
        return self.b + 2.0 * self.m * h

    def perimeter(self, h):
        return self.b + 2.0 * h * np.sqrt(1.0 + self.m ** 2)

    def friction_slope(self, Q, h):
        """(4): S_f = n² Q|Q| / (A² R^{4/3})."""
        A = self.area(h); R = A / self.perimeter(h)
        return self.n ** 2 * Q * np.abs(Q) / (A ** 2 * R ** (4.0 / 3.0))

    def manning_Q(self, h):
        A = self.area(h); R = A / self.perimeter(h)
        return A * R ** (2.0 / 3.0) * np.sqrt(self.S0) / self.n

    def normal_depth(self, Q):
        if Q <= 0:
            return 0.0
        return brentq(lambda h: self.manning_Q(h) - Q, 1e-9, 50.0, xtol=1e-12)   # numerical bracket

    def volume(self, h):
        """Discrete volume (consistent with the box scheme): Σ Δx · (A_i + A_{i+1})/2."""
        A = self.area(h)
        return float(self.dx * 0.5 * np.sum(A[:-1] + A[1:]))


def lower_reach():
    """Reach downstream of the check structure (PK 114+40 to 366+00), used for the tailwater level (assumed)."""
    p = value("lower_reach")
    return Reach(L=p["L"], b=p["b"], m=p["m"], S0=p["S0"], n=p["n"], N=3)
