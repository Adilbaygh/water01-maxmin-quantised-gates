"""Section 2.3, Equations (2)-(5): Saint-Venant equations (continuous form) and boundary conditions.

  (2) ∂A/∂t + ∂Q/∂x = q_l
  (3) ∂Q/∂t + ∂(Q²/A)/∂x + g A ∂h/∂x = g A (S0 − Sf) + q_l Q/A
  (4) Sf = n² Q|Q| / (A² R^{4/3})                       -- domain.geometry.Reach.friction_slope
  (5) q_l = −(1 − η) Q(0,t) / L                          -- uniformly distributed loss
For a prismatic section ∂(g I1)/∂x = g A ∂h/∂x, so (3) is equivalent to the form given in Section 2.3.
Discretisation: hydraulics.preissmann.
"""
from scipy.integrate import solve_ivp

G = 9.81


def lateral_inflow(reach, Q_head, eta):
    """(5): q_l = −(1 − η) Q(0) / L  [m²/s]."""
    return -(1.0 - eta) * Q_head / reach.L


def momentum_source(reach, h, Q, ql):
    """Right-hand side of (3): g A (S0 − Sf) + q_l Q / A."""
    A = reach.area(h)
    return G * A * (reach.S0 - reach.friction_slope(Q, h)) + ql * Q / A


def froude_squared(reach, h, Q):
    A = reach.area(h)
    return Q * Q * reach.top(h) / (G * A ** 3)


def steady_profile(reach, Q0, h_down, eta=1.0):
    """Steady gradually varied flow profile (Section 2.10, check 5):
    dh/dx = [S0 − Sf − q_l Q/(g A²)] / (1 − Fr²),  Q(x) = Q0 + q_l x.
    Integrated upstream from the depth at the downstream boundary. Subcritical flow is required."""
    ql = lateral_inflow(reach, Q0, eta)

    def rhs(x, y):
        h = y[0]; Q = Q0 + ql * x
        A = reach.area(h)
        fr2 = froude_squared(reach, h, Q)
        if fr2 >= 1.0:
            raise ValueError("Flow is critical or supercritical")
        return [(reach.S0 - reach.friction_slope(Q, h) - ql * Q / (G * A * A)) / (1.0 - fr2)]

    sol = solve_ivp(rhs, (reach.L, 0.0), [h_down], t_eval=reach.x[::-1], rtol=1e-10, atol=1e-12)
    h = sol.y[0][::-1]
    return h, Q0 + ql * reach.x


# --- boundary conditions: residual functions of the form f(t, h, Q) = 0
def inflow_bc(Q_in):
    """Upstream boundary: prescribed discharge Q_in(t) (head regulator under discharge control)."""
    return lambda t, h0, Q0: Q0 - Q_in(t)


def outflow_bc(Q_out):
    """Downstream boundary: node outflow Q_out(t, h_L) (Dustlik node or constant withdrawal)."""
    return lambda t, hN, QN: QN - Q_out(t, hN)


def level_bc(h_set):
    """Downstream boundary: prescribed level h_set(t)."""
    return lambda t, hN, QN: hN - h_set(t)


def normal_depth_bc(reach):
    """Downstream boundary: Manning relation at normal depth (for the uniform-flow test)."""
    return lambda t, hN, QN: QN - reach.manning_Q(hN)
