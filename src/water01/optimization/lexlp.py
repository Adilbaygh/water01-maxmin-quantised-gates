"""Section 2.5, Equations (11a)-(13): three-stage lexicographic LP (HiGHS, scipy.optimize.linprog).

Variables: x_{j,p} is the volume (m3) delivered to user j on day p.
Satisfaction: r_{j,p} = x_{j,p} / D_{j,p}, only for pairs with D_{j,p} > 0 (the set A+).
Objective functions: optimization.objectives; constraints: optimization.constraints.

Two levels:
- solve_lexicographic: three-stage LP over daily volumes (plan; receding horizon, 10 days);
- solve_intraday: 15-minute execution LP that executes the daily plan subject to the ID model (8), the command
  constraint (9), level bounds and gate-rate constraints (closed loop, simulation.plant_loop).
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, lil_matrix, vstack

from ..domain.passport import value
from .constraints import daily_balance, effective_supply, retained_bounds, variable_bounds
from .objectives import (satisfaction, var_index, variation_links, variation_rows, weighted_satisfaction_coeffs,
                         worst_case_rows)


# HiGHS tolerances (default 1e-7). Secondary objectives (smooth discharge, gate movement) can differ by less than
# 1e-7; at the default tolerance such solutions are treated as ties, and the one selected may depend on the solver
# version and platform. Tighter tolerances make the results reproducible across platforms.
def lp_options():
    """HiGHS tolerances from the configuration (lp_primal/dual_feasibility_tolerance)."""
    return {"primal_feasibility_tolerance": value("lp_primal_feasibility_tolerance"),
            "dual_feasibility_tolerance": value("lp_dual_feasibility_tolerance")}


FALLBACKS = {"count": 0}


def _lp(c, **kw):
    """HiGHS: first with tight tolerances (configuration); if no solution is returned (e.g. status "Unknown", a
    numerical issue), the default tolerances are tried, then the interior-point method. Uses of the fallback path
    are counted in FALLBACKS (written to the results file)."""
    res = linprog(c, method="highs", options=lp_options(), **kw)
    if res.success:
        return res
    for method, opts in (("highs", {}), ("highs-ipm", {})):
        alt = linprog(c, method=method, options=opts, **kw)
        if alt.success:
            FALLBACKS["count"] += 1
            return alt
    return res


def _check(res, stage):
    if not res.success:
        raise RuntimeError(f"{stage}: {res.message}")
    return res


LEX_CHECK = {"violations": 0}      # solves in which a retained optimum was violated beyond round-off (diagnostic)
CHECK_TOL = 1e-7                    # satisfaction units


def _check_retained(x, D, pairs, floor, c2, z2, epsilon_2):
    """Counts a violation when a later stage lowered a satisfaction below its retained floor (λ* − ε1, or μ* − ε1
    for today) or the weighted satisfaction below Z2* − ε2, beyond round-off."""
    r = satisfaction(x, D)
    low = any(r[j, p] < floor[j, p] - CHECK_TOL for j, p in pairs)
    z2_low = c2 is not None and float(-(np.asarray(c2) @ x.ravel())) < z2 - epsilon_2 - CHECK_TOL
    if low or z2_low:
        LEX_CHECK["violations"] += 1


def solve_lexicographic(D, A, U=None, weights=None, fixed=None, epsilon_1=None, epsilon_2=None, protect_day=None,
                        stage3=True):
    """D [J×P] demand volumes, A [P] available water, U [J×P] upper bounds, weights [J],
    fixed: {(j,p): x} volumes already executed (held fixed).
    protect_day: column of the day executed today in the receding horizon. If given, Stage 1b (11b) separately
    maximises today's worst-case satisfaction (while retaining the window λ*), so that a pessimistic forecast does
    not needlessly sacrifice today's worst-off user for the future.
    stage3=False: H3 ablation; Stage 3 is not solved and the Stage 2 solution is returned (Z3_star = NaN).
    Returns: x, r, lambda_star, mu_today, Z2_star, Z3_star and the result of each stage."""
    epsilon_1 = value("epsilon_1") if epsilon_1 is None else epsilon_1     # None: from configuration
    epsilon_2 = value("epsilon_2") if epsilon_2 is None else epsilon_2
    D = np.atleast_2d(np.asarray(D, float)); J, P = D.shape
    A = np.asarray(A, float).reshape(P)
    U = np.full((J, P), np.inf) if U is None else np.asarray(U, float).reshape(J, P)
    w = np.ones(J) if weights is None else np.asarray(weights, float)
    if (D < 0).any() or (A < 0).any():
        raise ValueError("Negative demand or available water")
    pos = D > 0
    n = J * P
    idx = var_index(P)

    lb, ub, is_fixed = variable_bounds(D, U, fixed)
    xb = [(lb[j, p], ub[j, p]) for j in range(J) for p in range(P)]
    Ab = daily_balance(J, P)
    A_eff = effective_supply(A, lb)

    if not pos.any():
        x = np.zeros((J, P))
        return {"x": x, "r": satisfaction(x, D), "lambda_star": np.nan, "Z2_star": 0.0, "Z3_star": 0.0, "stages": {}}

    # λ and Z2 cover only pairs not yet decided; executed pairs enter only the Z3 continuity terms
    pairs = [(j, p) for j in range(J) for p in range(P) if pos[j, p] and not is_fixed[j, p]]
    if not pairs:
        x = lb.copy()
        return {"x": x, "r": satisfaction(x, D), "lambda_star": np.nan, "Z2_star": 0.0, "Z3_star": 0.0, "stages": {}}

    A1 = lil_matrix((P, n + 1)); A1[:, :n] = Ab

    # ---- Stage 1 (11a): max λ, λ ≤ x/D
    G, c1 = worst_case_rows(pairs, D, n, idx)
    r1 = _check(_lp(c1, A_ub=vstack([G, A1]).tocsr(), b_ub=np.r_[np.zeros(len(pairs)), A_eff],
                    bounds=xb + [(0, 1)]), "Stage 1")
    lam = float(r1.x[-1])
    floor = np.where(pos & ~is_fixed, lam - epsilon_1, -np.inf)

    # ---- Stage 1b (11b): max μ for today, λ* retained on the other days
    mu = None
    if protect_day is not None and any(p == protect_day for _, p in pairs):
        today = [(j, p) for j, p in pairs if p == protect_day]
        Gt, c1b = worst_case_rows(today, D, n, idx)
        r1b = _check(_lp(c1b, A_ub=vstack([Gt, A1]).tocsr(), b_ub=np.r_[np.zeros(len(today)), A_eff],
                         bounds=retained_bounds(lb, ub, D, floor) + [(0, 1)]), "Stage 1b")
        mu = float(r1b.x[-1])
        for j, p in today:
            floor[j, p] = max(floor[j, p], mu - epsilon_1)

    xb2 = retained_bounds(lb, ub, D, floor)

    # ---- Stage 2 (12): max Σ w_j r_{j,p}
    c2 = weighted_satisfaction_coeffs(pairs, D, w, n, idx)
    r2 = _check(_lp(c2, A_ub=Ab.tocsr(), b_ub=A_eff, bounds=xb2), "Stage 2")
    z2 = float(-r2.fun)

    if not stage3:                                            # H3 ablation: Stages 1 and 2, without Stage 3
        x = r2.x.reshape(J, P)
        _check_retained(x, D, pairs, floor, None, z2, epsilon_2)
        return {"x": x, "r": satisfaction(x, D), "lambda_star": lam, "mu_today": mu, "Z2_star": z2,
                "Z3_star": float("nan"), "stages": {"stage1": r1, "stage2": r2}, "stage2_x": x}

    # ---- Stage 3 (13): min Σ |r_{j,p} − r_{j,p−1}|, Z2 ≥ Z2*−ε2
    links = variation_links(pos)
    m = len(links); nv = n + m
    rows, c3 = variation_rows(links, D, n, idx)
    rhs = [0.0] * len(rows)
    row = np.zeros(nv); row[:n] = c2; rows.append(row); rhs.append(-(z2 - epsilon_2))  # −Z2 ≤ −(Z2*−ε2)
    bal = np.zeros((P, nv)); bal[:, :n] = Ab.toarray()
    A3 = np.vstack([np.array(rows), bal])
    b3 = np.r_[rhs, A_eff]
    r3 = _check(_lp(c3, A_ub=A3, b_ub=b3, bounds=xb2 + [(0, None)] * m), "Stage 3")

    x = r3.x[:n].reshape(J, P)
    _check_retained(x, D, pairs, floor, c2, z2, epsilon_2)
    r = satisfaction(x, D)
    return {"x": x, "r": r, "lambda_star": lam, "mu_today": mu, "Z2_star": z2, "Z3_star": float(r3.fun),
            "stages": {"stage1": r1, "stage2": r2, "stage3": r3},
            "stage2_x": r2.x.reshape(J, P)}


def solve_weighted_sum(D, A, U=None, weights=None, fixed=None):
    """Daily plan of B2: a single LP, max Σ w_j r_{j,p} (weighted sum; λ is not protected).
    Constraints are the same as in solve_lexicographic: Σ_j x ≤ A_p, x ≤ min(U, D), executed days fixed."""
    D = np.atleast_2d(np.asarray(D, float)); J, P = D.shape
    A = np.asarray(A, float).reshape(P)
    U = np.full((J, P), np.inf) if U is None else np.asarray(U, float).reshape(J, P)
    w = np.ones(J) if weights is None else np.asarray(weights, float)
    lb, ub, is_fixed = variable_bounds(D, U, fixed)
    pairs = [(j, p) for j in range(J) for p in range(P) if D[j, p] > 0 and not is_fixed[j, p]]
    if not pairs:
        x = lb.copy()
        return {"x": x, "r": satisfaction(x, D)}
    c = weighted_satisfaction_coeffs(pairs, D, w, J * P, var_index(P))
    res = _check(_lp(c, A_ub=daily_balance(J, P).tocsr(), b_ub=effective_supply(A, lb),
                     bounds=[(lb[j, p], ub[j, p]) for j in range(J) for p in range(P)]),
                 "weighted LP")
    x = res.x.reshape(J, P)
    return {"x": x, "r": satisfaction(x, D), "Z2": float(-res.fun)}


def delayed_inflow(q_in_hist, q_in_future, tau, dt, d):
    """Delayed inflow η-free term of (8) for each interval: the last d inflows and the inflow of every future
    interval are expanded to Δt steps, shifted by d steps, and averaged over each interval, so that the delay is
    d·Δt also where intervals are longer than Δt."""
    tau = np.asarray(tau, float)
    n_steps = np.rint(tau / dt).astype(int)
    if np.any(np.abs(n_steps * dt - tau) > 1e-6) or np.any(n_steps < 1):
        raise ValueError("interval lengths must be whole multiples of Δt")
    hist = np.asarray(q_in_hist, float)[len(q_in_hist) - d:] if d > 0 else np.empty(0)
    fine = np.r_[hist, np.repeat(np.asarray(q_in_future, float), n_steps)]   # fine[i] = Q_in at step i − d
    edges = np.r_[0, np.cumsum(n_steps)]
    return np.array([fine[edges[k]:edges[k + 1]].mean() for k in range(tau.size)])


def solve_intraday(q_in_hist, q_in_future, h0, remaining_today, rate_next, steps_today, K, dt, eta, A_s, d,
                   chord_set, capacity, h_lo, h_hi, h_ref, q_prev=None, dq_max=None, level_weight=None,
                   slack_weight=None, next_weight=None, track_weight=None, move_weight=None, terminal_band=None,
                   durations=None, objective="maxmin", weights=None):
    """15-minute execution LP (Sections 2.4-2.5). Variables: q_j[k] (J outlets, K steps), h_L[k+1],
    μ (today), ν (start of tomorrow), level deviation e[k] ≥ |h_L − h_ref|, level-bound violation s[k] ≥ 0,
    excess withdrawal today at the regulators o_j ≥ 0.

    Objective (Appendix C, (C1)): max μ + next_weight·ν − level_weight·Σ_k (τ_k/Στ) e_k − slack_weight·(Σs + Σo + t)
               − 10³·slack_weight·Σ_jk (τ_k/n̂_j)(σ_jk + ρ_jk) − (track_weight/J)·Σ_jk (τ_k/Στ) u_jk/ŝ_j
               − (move_weight/J)·Σ_jk g_jk/ŝ_j,
    u_j[k] ≥ |q_j[k] − q̄_j| is the deviation from a smooth discharge (q̄_j: today, remainder / remaining time;
    tomorrow, the planned rate); without it the LP may distribute the daily volume arbitrarily in time (e.g. within
    a few hours).
    Terminal condition (soft, slack_weight): end-of-day level |h_L(24:00) − h_ref| ≤ terminal_band, so that today's
    water is delivered from today's inflow and not from reach storage. Without it, in the untuned case (delivery
    underestimated) LXB would open the check structure sharply at the end of the day and drain the reach.
    g_j[k] ≥ |q_j[k] − q_j[k−1]| is gate movement (consistent with IAW). ŝ_j = max(q̄_j, r̄_j, 10⁻³·c̄_j): each user is
    measured relative to its own planned rate; normalising by capacity would give penalties of about 10⁻⁸ for large
    outlets, below the HiGHS tolerance, making the choice among tied solutions platform-dependent.
      today (steps_today steps):          Σ_k q_j Δt ≥ μ·remaining_today_j;
      tomorrow (remaining K − steps_today): Σ_k q_j Δt ≥ ν·rate_next_j·Δt·(K − steps_today).
    Today and tomorrow have separate variables so that tomorrow's forecast does not pull down today's worst-off
    user (the execution-level analogue of Stage 1b in the daily plan; next_weight ≪ 1 gives a weighted
    lexicographic order).
    (8): A_s (h[k+1] − h[k]) = Δt (η Q_in[k−d] − Σ_j q_j[k]);  (9): q_j[k] ≤ α_jm + β_jm h_L[k];  q_j ≤ c̄_j;
    h_lo − s ≤ h_L ≤ h_hi + s;  |q_j[k] − q_j[k−1]| ≤ Δq_max;
    regulators do not take more than the share μ today: Σ_k q_j Δt ≤ μ·remaining_today_j + o_j (soft), so every
    user receives the same share of its plan; surplus water passes through the check structure to lower Kegeyli.
    objective="maxmin": LXB (μ above); objective="weighted": B2, with a separate μ_j for each user and
    objective max Σ w_j μ_j / Σ w (weighted sum, does not protect the worst-off); all other constraints are the same.
    q_in_hist: last d inflows (oldest first); q_in_future: K forecast inflows (m³/s).
    durations: interval lengths [s] (move blocking); None means all equal Δt; the first d intervals must equal Δt
    (the delay acts there). q is constant within an interval. steps_today: number of intervals belonging to today.
    Returns: q [J×K], h [K+1], μ, ν, total level violation."""
    cfgw = lambda x, key: value(key) if x is None else x                   # weights from configuration
    level_weight = cfgw(level_weight, "execution_level_weight"); slack_weight = cfgw(slack_weight, "execution_slack_weight")
    next_weight = cfgw(next_weight, "execution_next_weight"); track_weight = cfgw(track_weight, "execution_track_weight")
    move_weight = cfgw(move_weight, "execution_move_weight"); terminal_band = cfgw(terminal_band, "terminal_band_m")
    tau = np.full(K, float(dt)) if durations is None else np.asarray(durations, float)
    if np.any(tau[:d] != dt):
        raise ValueError("The first d intervals must have length Δt")
    J = len(capacity)
    nq = J * K; ih = nq; im = ih + K; inu = im + 1; ie = inu + 1; is_ = ie + K; io = is_ + K; iu = io + J - 1
    weighted = objective == "weighted"
    if objective not in ("maxmin", "weighted"):
        raise ValueError("objective: 'maxmin' or 'weighted'")
    ig = iu + nq                                               # g_j[k]: gate movement
    it_ = ig + nq                                              # terminal level violation
    imj = it_ + 1                                              # μ_j (weighted only)
    isc = imj + (J if weighted else 0)                         # violation of (9) (soft, very large penalty)
    irt = isc + nq                                             # gate-rate violation
    nv = irt + nq
    mu_col = (lambda j: imj + j) if weighted else (lambda j: im)
    qi = lambda j, k: j * K + k
    R, C, V, b_ub = [], [], [], []
    ER, EC, EV, b_eq = [], [], [], []
    row_n = [0]

    def ub(entries, rhs):
        r = row_n[0]
        for c_, v_ in entries:
            R.append(r); C.append(c_); V.append(v_)
        b_ub.append(rhs); row_n[0] += 1

    q_in = delayed_inflow(q_in_hist, q_in_future, tau, dt, d)
    # (8) ID model (equality)
    for k in range(K):
        ent = [(ih + k, 1.0)] + ([(ih + k - 1, -1.0)] if k > 0 else []) + [(qi(j, k), tau[k] / A_s) for j in range(J)]
        for c_, v_ in ent:
            ER.append(k); EC.append(c_); EV.append(v_)
        b_eq.append(tau[k] / A_s * eta * q_in[k] + (h0 if k == 0 else 0.0))
    for k in range(K):
        for j in range(J):                                     # (9)
            alpha, beta = chord_set[j]
            for a_m, b_m in zip(alpha, beta):
                if k == 0:
                    ub([(qi(j, 0), 1.0), (isc + qi(j, 0), -1.0)], a_m + b_m * h0)
                else:
                    ub([(qi(j, k), 1.0), (ih + k - 1, -b_m), (isc + qi(j, k), -1.0)], a_m)
        ub([(ih + k, 1.0), (is_ + k, -1.0)], h_hi)             # level bounds h[k+1]
        ub([(ih + k, -1.0), (is_ + k, -1.0)], -h_lo)
        ub([(ih + k, 1.0), (ie + k, -1.0)], h_ref)              # deviation
        ub([(ih + k, -1.0), (ie + k, -1.0)], -h_ref)
    after = K - steps_today
    # μ, ν: volume requirements μ·need ≤ Σ q τ. Each row is divided by max(need, 1 m³): when the remainder is at
    # round-off level (e.g. 2·10⁻¹³ m³), a coefficient 1/need of ~10¹⁵ would cause a HiGHS "Model error".
    # For need ≥ 1 m³ the row is normalised by need; need < 1 m³ is regarded as already fulfilled.
    for j in range(J):
        need_today = remaining_today[j]
        if need_today > 0 and steps_today > 0:
            s_ = max(need_today, 1.0)
            ub([(qi(j, k), -tau[k] / s_) for k in range(steps_today)] + [(mu_col(j), need_today / s_)], 0.0)
        need_next = rate_next[j] * tau[steps_today:].sum()
        if need_next > 0 and after > 0:
            s_ = max(need_next, 1.0)
            ub([(qi(j, k), -tau[k] / s_) for k in range(steps_today, K)] + [(inu, need_next / s_)], 0.0)
    if dq_max is not None:                                     # gate rate
        for j in range(J):
            for k in range(K):
                for sgn in (1.0, -1.0):
                    if k == 0:
                        if q_prev is not None:
                            ub([(qi(j, 0), sgn), (irt + qi(j, 0), -1.0)], dq_max[j] + sgn * q_prev[j])
                    else:                              # between blocks: scaled to the distance between midpoints
                        ub([(qi(j, k), sgn), (qi(j, k - 1), -sgn), (irt + qi(j, k), -1.0)],
                           dq_max[j] * 0.5 * (tau[k] + tau[k - 1]) / dt)
    for j in range(J - 1):                                     # soft: a regulator takes no more than the share μ
        need_today = max(remaining_today[j], 0.0)
        scale = max(need_today, 1.0)
        ub([(qi(j, k), tau[k] / scale) for k in range(steps_today)] + [(mu_col(j), -need_today / scale), (io + j, -1.0)],
           0.0)
    if 0 < steps_today < K + 1 and terminal_band is not None:  # terminal level (end of day = h[steps_today])
        ub([(ih + steps_today - 1, 1.0), (it_, -1.0)], h_ref + terminal_band)
        ub([(ih + steps_today - 1, -1.0), (it_, -1.0)], -(h_ref - terminal_band))
    t_today = tau[:steps_today].sum()
    scale = np.zeros(J)
    for j in range(J):                                         # smooth-discharge tracking: u ≥ |q − q̄|
        qbar_today = remaining_today[j] / t_today if t_today > 0 else 0.0
        scale[j] = max(qbar_today, rate_next[j], 1e-3 * capacity[j], 1e-9)
        for k in range(K):
            qbar = qbar_today if k < steps_today else rate_next[j]
            ub([(qi(j, k), 1.0), (iu + qi(j, k), -1.0)], qbar)
            ub([(qi(j, k), -1.0), (iu + qi(j, k), -1.0)], -qbar)
        for k in range(K):                                     # gate movement: g ≥ |q[k] − q[k−1]|
            if k == 0:
                if q_prev is not None:
                    ub([(qi(j, 0), 1.0), (ig + qi(j, 0), -1.0)], q_prev[j])
                    ub([(qi(j, 0), -1.0), (ig + qi(j, 0), -1.0)], -q_prev[j])
            else:
                ub([(qi(j, k), 1.0), (qi(j, k - 1), -1.0), (ig + qi(j, k), -1.0)], 0.0)
                ub([(qi(j, k), -1.0), (qi(j, k - 1), 1.0), (ig + qi(j, k), -1.0)], 0.0)
    bounds = [(0.0, capacity[j]) for j in range(J) for _ in range(K)]
    bounds += [(None, None)] * K + [(0.0, 1.0), (0.0, 1.0)] + [(0.0, None)] * K + [(0.0, None)] * K + [(0.0, None)] * (J - 1)
    bounds += [(0.0, None)] * nq + [(0.0, None)] * nq + [(0.0, None)]
    if weighted:
        bounds += [(0.0, 1.0)] * J
        bounds[im] = (0.0, 0.0)                                # the common μ is not used
    bounds += [(0.0, None)] * nq + [(0.0, None)] * nq
    c = np.zeros(nv); c[im] = -1.0; c[inu] = -next_weight
    if weighted:
        w = np.ones(J) if weights is None else np.asarray(weights, float)
        c[im] = 0.0
        c[imj:imj + J] = -w / w.sum()
    c[ie:ie + K] = level_weight * tau / tau.sum()
    c[is_:is_ + K] = slack_weight; c[io:io + J - 1] = slack_weight; c[it_] = slack_weight
    # (9) and the gate rate are physical constraints, but at very low levels (e.g. on zero-supply days) the
    # chord/tangent becomes negative and conflicts with q ≥ 0. They are therefore soft: the penalty for 1 m³ of
    # violation is 10³·slack_weight times the value of delivering 1 m³ to that user, so violations never pay off.
    for j in range(J):
        need_j = max(remaining_today[j], rate_next[j] * tau[steps_today:].sum(), 1.0)
        c[isc + j * K: isc + (j + 1) * K] = 1e3 * slack_weight * tau / need_j
        c[irt + j * K: irt + (j + 1) * K] = 1e3 * slack_weight * tau / need_j
    for j in range(J):
        c[iu + j * K: iu + (j + 1) * K] = track_weight * tau / tau.sum() / scale[j] / J
        c[ig + j * K: ig + (j + 1) * K] = move_weight / scale[j] / J
    A_ub = coo_matrix((V, (R, C)), shape=(row_n[0], nv)).tocsr()
    A_eq = coo_matrix((EV, (ER, EC)), shape=(K, nv)).tocsr()
    res = _check(_lp(c, A_ub=A_ub, b_ub=np.array(b_ub), A_eq=A_eq, b_eq=np.array(b_eq), bounds=bounds), "execution LP")
    z = res.x
    mu = float(np.min(z[imj:imj + J])) if weighted else float(z[im])
    return {"q": z[:nq].reshape(J, K), "h": np.r_[h0, z[ih:ih + K]], "mu": mu, "nu": float(z[inu]),
            "slack": float(z[is_:is_ + K].sum()), "mu_j": z[imj:imj + J] if weighted else None,
            "command_violation": float(z[isc:isc + nq].max(initial=0.0)), "rate_violation": float(z[irt:irt + nq].max(initial=0.0))}
