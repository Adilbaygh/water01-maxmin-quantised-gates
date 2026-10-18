"""Section 2.3: four-point Preissmann scheme (Cunge et al., 1980), ψ = 0.5 in space, θ in time.

At each Δt step, 2N nonlinear equations are solved by Newton's method. The Jacobian is banded (2 lower and
2 upper diagonals), so it is computed with 4-colour finite differences and solved with solve_banded.
Unknown ordering: [h0, Q0, h1, Q1, ..., h_{N−1}, Q_{N−1}].
q_l is evaluated explicitly at each step from Q(0) at the previous time level, so the Jacobian stays banded.
"""
import numpy as np
from scipy.linalg import solve_banded

from ..domain.passport import value
from ..domain.state import CanalState
from .saint_venant import G, lateral_inflow, momentum_source

REFERENCE_PLANT_AVAILABLE = True


class PreissmannSolver:
    """Saint-Venant solver for a single reach.

    upstream(t, h0, Q0) -> residual (must vanish); e.g. Q0 − Q_in(t) or a gate equation.
    downstream(t, hN, QN) -> residual; e.g. QN − Q_out(hN) (Dustlik node) or hN − h_set.
    """

    def __init__(self, reach, dt, h, Q, upstream, downstream, theta=None, eta=1.0, tol=None, max_iter=None):
        theta = value("preissmann_theta") if theta is None else theta
        tol = value("newton_tolerance") if tol is None else tol
        max_iter = value("newton_max_iter") if max_iter is None else max_iter
        self.fd_step = value("jacobian_fd_step")
        if not 0.5 <= theta <= 1.0:
            raise ValueError("θ ∈ [0.5, 1]")
        self.r, self.dt, self.theta, self.eta = reach, float(dt), float(theta), float(eta)
        self.h = np.array(h, float); self.Q = np.array(Q, float)
        self.up, self.down = upstream, downstream
        self.tol, self.max_iter = tol, max_iter
        self.t = 0.0
        self.last_iterations = 0
        self.last_ql = 0.0
        self.substeps = 1

    @property
    def state(self):
        return CanalState(self.t, self.h.copy(), self.Q.copy())

    def residual(self, z, ho, Qo, t_new, ql, dt=None):
        r, th, dx = self.r, self.theta, self.r.dx
        dt = self.dt if dt is None else dt
        h = z[0::2]; Q = z[1::2]
        A, Ao = r.area(h), r.area(ho)
        F = np.empty_like(z)
        F[0] = self.up(t_new, h[0], Q[0])
        # (2) continuity
        cont = (0.5 * ((A[:-1] - Ao[:-1]) + (A[1:] - Ao[1:])) / dt
                + (th * (Q[1:] - Q[:-1]) + (1 - th) * (Qo[1:] - Qo[:-1])) / dx - ql)
        # (3) momentum
        conv_n = Q ** 2 / A; conv_o = Qo ** 2 / Ao
        Abar = th * 0.5 * (A[:-1] + A[1:]) + (1 - th) * 0.5 * (Ao[:-1] + Ao[1:])
        Sn = momentum_source(r, h, Q, ql); So = momentum_source(r, ho, Qo, ql)
        mom = (0.5 * ((Q[:-1] - Qo[:-1]) + (Q[1:] - Qo[1:])) / dt
               + (th * (conv_n[1:] - conv_n[:-1]) + (1 - th) * (conv_o[1:] - conv_o[:-1])) / dx
               + G * Abar * (th * (h[1:] - h[:-1]) + (1 - th) * (ho[1:] - ho[:-1])) / dx
               - (th * 0.5 * (Sn[:-1] + Sn[1:]) + (1 - th) * 0.5 * (So[:-1] + So[1:])))
        F[1:-1:2] = cont
        F[2:-1:2] = mom
        F[-1] = self.down(t_new, h[-1], Q[-1])
        return F

    def _jacobian_banded(self, z, F0, args):
        """4-colour finite differences. The unknowns of node i (columns 2i, 2i+1) appear only in rows 2i−1..2i+2
        (cells i−1 and i, boundary conditions), so columns j and j+4 never share a row. Each column derivative is
        taken only from these rows (a wider window would mix in the effect of the neighbouring column)."""
        n = z.size; ab = np.zeros((5, n))
        for c in range(4):
            cols = np.arange(c, n, 4)
            dz = self.fd_step * np.maximum(1.0, np.abs(z[cols]))
            zp = z.copy(); zp[cols] += dz
            dF = (self.residual(zp, *args) - F0)
            for j, d in zip(cols, dz):
                i = j // 2
                lo, hi = max(0, 2 * i - 1), min(n, 2 * i + 3)
                ab[2 + np.arange(lo, hi) - j, j] = dF[lo:hi] / d
        return ab

    def _advance(self, dt):
        """One internal (Newton) step. Raises RuntimeError if it does not converge."""
        ho, Qo = self.h.copy(), self.Q.copy()
        ql = lateral_inflow(self.r, Qo[0], self.eta)
        t_new = self.t + dt
        z = np.empty(2 * ho.size); z[0::2] = ho; z[1::2] = Qo
        args = (ho, Qo, t_new, ql, dt)
        F = self.residual(z, *args)
        for it in range(1, self.max_iter + 1):
            dz = solve_banded((2, 2), self._jacobian_banded(z, F, args), -F)
            if not np.all(np.isfinite(dz)):
                break
            # damped Newton (backtracking): the step is halved if the residual does not decrease. Near zero head the
            # smoothed gate equation is steep, and a full step may cycle around the root.
            norm0 = np.linalg.norm(F); alpha = 1.0
            for _ in range(8):
                z_try = z + alpha * dz
                z_try[0::2] = np.maximum(z_try[0::2], 1e-3)
                F_try = self.residual(z_try, *args)
                if np.linalg.norm(F_try) < norm0 or alpha < 1e-2:
                    break
                alpha *= 0.5
            z, F = z_try, F_try
            # convergence is tested on the full Newton step (a short damped step must not signal false convergence)
            if np.max(np.abs(dz)) < self.tol * max(1.0, np.max(np.abs(z))):
                th = self.theta
                self.h, self.Q, self.t = z[0::2], z[1::2], t_new
                self.last_iterations = it
                flux = dt * (th * (self.Q[0] - self.Q[-1]) + (1 - th) * (Qo[0] - Qo[-1]) + ql * self.r.L)
                return ql * dt, flux, (dt, float(self.h[-1]))
        raise RuntimeError(f"Newton: no convergence in {self.max_iter} iterations (t = {t_new:.0f} s, Δt = {dt:.0f} s)")

    def step(self):
        """One Δt step. If Newton does not converge (e.g. head across a gate near zero, where the smoothed gate
        equation is steep), the step is split into 2, 4 or 8 equal substeps. last_ql: step-averaged q_l; last_net_inflow:
        discrete net inflow volume over the step; last_substeps: substeps (Δt_i, h_L).
        Returns: (h, Q)."""
        h0, Q0, t0 = self.h.copy(), self.Q.copy(), self.t
        for n_sub in (1, 2, 4, 8):
            self.h, self.Q, self.t = h0.copy(), Q0.copy(), t0
            try:
                parts = [self._advance(self.dt / n_sub) for _ in range(n_sub)]
            except RuntimeError:
                continue
            self.last_ql = sum(p[0] for p in parts) / self.dt
            self.last_net_inflow = sum(p[1] for p in parts)      # Δt(θ ΔQ_new + (1−θ) ΔQ_old + q_l L): mass balance
            self.last_substeps = [p[2] for p in parts]           # [(Δt_i, h_L)]: for computing node volumes
            self.substeps = n_sub
            return self.h, self.Q
        self.h, self.Q, self.t = h0, Q0, t0
        raise RuntimeError(f"Newton did not converge even with the step split into 8 (t = {t0 + self.dt:.0f} s)")
