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
from scipy.optimize import OptimizeResult, linprog
from scipy.sparse import coo_matrix, csc_matrix, csr_matrix, lil_matrix, vstack

from ..domain.passport import optional, value
from .constraints import daily_balance, effective_supply, retained_bounds, variable_bounds
from .objectives import (satisfaction, var_index, variation_links, variation_rows, weighted_satisfaction_coeffs,
                         worst_case_rows)


def _cache_highs_option_checks():
    """SciPy's HiGHS wrapper validates every option of every solve by constructing a new HiGHS options manager, which
    costs several milliseconds per solve. The validation depends only on the option name and value, so its result is
    cached; the options passed to the solver, and therefore the solutions, are unchanged."""
    try:
        from scipy.optimize._highspy import _highs_wrapper as wrapper
    except ImportError:                                         # other SciPy layout: no caching
        return
    original = getattr(wrapper, "check_option", None)
    if original is None or getattr(original, "cached", False):
        return
    cache = {}

    def check_option(highs_inst, option, value):
        key = (option, type(value).__name__, repr(value))
        if key not in cache:
            cache[key] = original(highs_inst, option, value)
        return cache[key]

    check_option.cached = True
    wrapper.check_option = check_option


_cache_highs_option_checks()


# HiGHS tolerances (default 1e-7). Secondary objectives (smooth discharge, gate movement) can differ by less than
# 1e-7; at the default tolerance such solutions are treated as ties, and the one selected may depend on the solver
# version and platform. Tighter tolerances make the results reproducible across platforms.
def lp_options():
    """HiGHS tolerances from the configuration (lp_primal/dual_feasibility_tolerance)."""
    return {"primal_feasibility_tolerance": value("lp_primal_feasibility_tolerance"),
            "dual_feasibility_tolerance": value("lp_dual_feasibility_tolerance")}


FALLBACKS = {"count": 0}
COLD_RESTARTS = {"count": 0}        # warm-started solves repeated from scratch (diagnostic, written to the results)

try:                                # HiGHS bindings shipped with SciPy (the solver behind linprog(method="highs"))
    from scipy.optimize._highspy import _core as _HIGHS
except ImportError:                 # other SciPy layout: every LP is solved with linprog
    _HIGHS = None

# Simplex basis of the last optimal solve of each LP (call site and dimensions). Consecutive LPs of a run differ only
# in their data, so the previous optimal basis is a good starting point for the dual simplex method; it changes the
# number of iterations, not the optimality conditions. The bases are cleared at the start of every run
# (reset_warm_start), so that the solutions of a run do not depend on the runs solved before it in the same process.
_WARM = {}


def reset_warm_start():
    """Forget the stored simplex bases (called at the start of every closed-loop run)."""
    _WARM.clear()


def _solve_warm(c, tag, A_ub=None, b_ub=None, A_eq=None, b_eq=None, bounds=None):
    """One dual-simplex solve with HiGHS (tolerances from the configuration, no presolve), started from the stored
    basis of the same LP when there is one. The model is the one linprog(method="highs") passes to HiGHS: rows of
    A_ub (≤ b_ub) followed by rows of A_eq (= b_eq). Returns an OptimizeResult, or None if HiGHS did not report an
    optimal solution."""
    c = np.asarray(c, float); n = c.size
    mats, lhs, rhs = [], [], []
    if A_ub is not None:
        b = np.asarray(b_ub, float).ravel()
        mats.append(csr_matrix(A_ub)); lhs.append(np.full(b.size, -np.inf)); rhs.append(b)
    if A_eq is not None:
        b = np.asarray(b_eq, float).ravel()
        mats.append(csr_matrix(A_eq)); lhs.append(b); rhs.append(b)
    A = csc_matrix(vstack(mats)) if mats else csc_matrix((0, n))
    A.sort_indices()
    lo, hi = (np.concatenate(v) if v else np.empty(0) for v in (lhs, rhs))
    if bounds is None:
        lb, ub = np.zeros(n), np.full(n, np.inf)
    else:
        bd = np.array(bounds, dtype=float).reshape(n, 2)       # None -> NaN -> unbounded
        lb = np.where(np.isnan(bd[:, 0]), -np.inf, bd[:, 0]); ub = np.where(np.isnan(bd[:, 1]), np.inf, bd[:, 1])
    m = hi.size
    h = _HIGHS._Highs()
    for key, val in (("output_flag", False), ("presolve", "off"), ("solver", "simplex"), ("simplex_strategy", 1),
                     *lp_options().items()):
        h.setOptionValue(key, val)
    lp = _HIGHS.HighsLp()
    lp.num_col_ = n; lp.num_row_ = m
    lp.a_matrix_.num_col_ = n; lp.a_matrix_.num_row_ = m
    lp.a_matrix_.format_ = _HIGHS.MatrixFormat.kColwise
    lp.col_cost_ = c; lp.col_lower_ = lb; lp.col_upper_ = ub; lp.row_lower_ = lo; lp.row_upper_ = hi
    lp.a_matrix_.start_ = A.indptr; lp.a_matrix_.index_ = A.indices; lp.a_matrix_.value_ = A.data
    if h.passModel(lp) == _HIGHS.HighsStatus.kError:
        return None
    key = (tag, n, m)
    if key in _WARM:
        h.setBasis(_WARM[key])                                  # an unusable basis is rejected by HiGHS
    h.run()
    if h.getModelStatus() != _HIGHS.HighsModelStatus.kOptimal:
        _WARM.pop(key, None)
        return None
    _WARM[key] = h.getBasis()
    info = h.getInfo()
    return OptimizeResult(x=np.array(h.getSolution().col_value), fun=float(info.objective_function_value),
                          success=True, status=0, nit=int(info.simplex_iteration_count),
                          message="Optimization terminated successfully. (HiGHS Status 7: Optimal)")


def _lp(c, tag="lp", **kw):
    """HiGHS dual simplex with tight tolerances (configuration), warm-started from the previous optimal basis of the
    same LP (_solve_warm); if it does not report an optimal solution, the LP is solved from scratch by
    linprog(method="highs") with the same tolerances (counted in COLD_RESTARTS), then with the default tolerances,
    then with the interior-point method. Uses of the last two are counted in FALLBACKS. Both counters are written
    to the results file."""
    if _HIGHS is not None:
        res = _solve_warm(c, tag, **kw)
        if res is not None:
            return res
        COLD_RESTARTS["count"] += 1
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
    r1 = _check(_lp(c1, "stage1", A_ub=vstack([G, A1]).tocsr(), b_ub=np.r_[np.zeros(len(pairs)), A_eff],
                    bounds=xb + [(0, 1)]), "Stage 1")
    lam = float(r1.x[-1])
    floor = np.where(pos & ~is_fixed, lam - epsilon_1, -np.inf)

    # ---- Stage 1b (11b): max μ for today, λ* retained on the other days
    mu = None
    if protect_day is not None and any(p == protect_day for _, p in pairs):
        today = [(j, p) for j, p in pairs if p == protect_day]
        Gt, c1b = worst_case_rows(today, D, n, idx)
        r1b = _check(_lp(c1b, "stage1b", A_ub=vstack([Gt, A1]).tocsr(), b_ub=np.r_[np.zeros(len(today)), A_eff],
                         bounds=retained_bounds(lb, ub, D, floor) + [(0, 1)]), "Stage 1b")
        mu = float(r1b.x[-1])
        for j, p in today:
            floor[j, p] = max(floor[j, p], mu - epsilon_1)

    xb2 = retained_bounds(lb, ub, D, floor)

    # ---- Stage 2 (12): max Σ w_j r_{j,p}
    c2 = weighted_satisfaction_coeffs(pairs, D, w, n, idx)
    r2 = _check(_lp(c2, "stage2", A_ub=Ab.tocsr(), b_ub=A_eff, bounds=xb2), "Stage 2")
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
    r3 = _check(_lp(c3, "stage3", A_ub=A3, b_ub=b3, bounds=xb2 + [(0, None)] * m), "Stage 3")

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
    res = _check(_lp(c, "weighted", A_ub=daily_balance(J, P).tocsr(), b_ub=effective_supply(A, lb),
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
                   durations=None, objective="maxmin", weights=None, share="remaining", delivered_today=None,
                   target_today=None, first_limit=None):
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
    share="remaining" (LXB): μ is the common share of the remaining daily plan, μ·(x_j − V̂_j) ≤ Σ_k q_j Δt, so that a
    user who has already received a larger share keeps receiving the same share of its remainder (proportional
    recovery). share="final" (exploratory LXB-F): μ is the common share of the whole daily plan at the end of the day,
    μ·x_j ≤ V̂_j + Σ_k q_j Δt, i.e. the final daily satisfaction relative to the plan; delivered_today (V̂_j) and
    target_today (x_j) are then required.
    first_limit: [J] discharges with fully open gates at the known current level h0; when given, (9) for the first
    action is q_j[0] ≤ first_limit_j (exact) instead of the chords.
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
    # Constraint rows are assembled block by block with NumPy; the rows and their order are those of the original
    # row-by-row construction (each row is listed with its local index, its columns, coefficients and right side).
    blocks_r, blocks_c, blocks_v, blocks_b = [], [], [], []
    nrow = 0

    def add(rows_local, cols, vals, rhs):
        nonlocal nrow
        rhs = np.atleast_1d(np.asarray(rhs, float))
        blocks_r.append(np.asarray(rows_local, np.int64) + nrow)
        blocks_c.append(np.asarray(cols, np.int64))
        blocks_v.append(np.asarray(vals, float))
        blocks_b.append(rhs)
        nrow += rhs.size

    def cat(*parts):
        return np.concatenate([x if isinstance(x, np.ndarray) else np.array([x]) for x in parts])

    q_in = delayed_inflow(q_in_hist, q_in_future, tau, dt, d)
    jj, kk = np.arange(J), np.arange(K)
    # (8) ID model (equality): h[k] − h[k−1] + Σ_j (τ_k/A_s) q_j[k] = (τ_k/A_s) η Q_in[k] (+ h0 for k = 0)
    ER = np.concatenate([kk, kk[1:], np.repeat(kk, J)])
    EC = np.concatenate([ih + kk, ih + kk[1:] - 1, (jj[None, :] * K + kk[:, None]).ravel()])
    EV = np.concatenate([np.ones(K), -np.ones(K - 1), np.repeat(tau / A_s, J)])
    b_eq = tau / A_s * eta * q_in
    b_eq[0] += h0
    # (9) chords and level bounds, interval by interval
    n_chords = [len(chord_set[j][0]) for j in range(J)]
    alpha = np.concatenate([np.asarray(chord_set[j][0], float) for j in range(J)])
    beta = np.concatenate([np.asarray(chord_set[j][1], float) for j in range(J)])
    cj = np.repeat(jj, n_chords)                               # outlet of each chord
    SM = alpha.size
    if first_limit is not None:                                # interval 0: exact limit at the known level
        r = np.arange(J)
        add(cat(r, r), cat(jj * K, isc + jj * K), cat(np.ones(J), -np.ones(J)), np.asarray(first_limit, float)[:J])
    else:
        r = np.arange(SM)
        add(cat(r, r), cat(cj * K, isc + cj * K), cat(np.ones(SM), -np.ones(SM)), alpha + beta * h0)
    lvl_rows = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    lvl_cols = np.array([ih, is_, ih, is_, ih, ie, ih, ie])
    lvl_vals = np.array([1.0, -1.0, -1.0, -1.0, 1.0, -1.0, -1.0, -1.0])
    lvl_rhs = np.array([h_hi, -h_lo, h_ref, -h_ref], float)
    add(lvl_rows, lvl_cols, lvl_vals, lvl_rhs)
    if K > 1:                                                  # intervals 1..K−1: SM chord rows, then 4 level rows
        r = np.arange(SM)
        ch_rows, ch_cols = cat(r, r, r), cat(cj * K, np.full(SM, ih - 1), isc + cj * K)
        ch_vals = cat(np.ones(SM), -beta, -np.ones(SM))
        blk = SM + 4
        ks = np.arange(1, K)
        off = (ks - 1) * blk
        rows = np.concatenate([(off[:, None] + ch_rows[None, :]).ravel(), (off[:, None] + SM + lvl_rows[None, :]).ravel()])
        cols = np.concatenate([(ks[:, None] + ch_cols[None, :]).ravel(), (ks[:, None] + lvl_cols[None, :]).ravel()])
        vals = np.concatenate([np.tile(ch_vals, K - 1), np.tile(lvl_vals, K - 1)])
        rhs = np.concatenate([np.tile(alpha, (K - 1, 1)), np.tile(lvl_rhs, (K - 1, 1))], axis=1).ravel()
        add(rows, cols, vals, rhs)
    after = K - steps_today
    # μ, ν: volume requirements μ·need ≤ Σ q τ. Each row is divided by max(need, 1 m³): when the remainder is at
    # round-off level (e.g. 2·10⁻¹³ m³), a coefficient 1/need of ~10¹⁵ would cause a HiGHS "Model error".
    # For need ≥ 1 m³ the row is normalised by need, otherwise by 1 m³; every positive remainder stays active.
    final = share == "final"
    if share not in ("remaining", "final"):
        raise ValueError("share: 'remaining' or 'final'")
    if final and (delivered_today is None or target_today is None):
        raise ValueError("share='final' requires delivered_today and target_today")
    ks_today, ks_next = np.arange(steps_today), np.arange(steps_today, K)
    for j in range(J):
        need_today = remaining_today[j]
        if final:                                              # μ·x_j − Σ q τ ≤ V̂_j
            x_j, v_j = float(target_today[j]), float(delivered_today[j])
            if x_j > 0 and steps_today > 0:
                s_ = max(x_j, 1.0)
                add(np.zeros(steps_today + 1), cat(j * K + ks_today, mu_col(j)),
                    cat(-tau[:steps_today] / s_, x_j / s_), v_j / s_)
        elif need_today > 0 and steps_today > 0:
            s_ = max(need_today, 1.0)
            add(np.zeros(steps_today + 1), cat(j * K + ks_today, mu_col(j)),
                cat(-tau[:steps_today] / s_, need_today / s_), 0.0)
        need_next = rate_next[j] * tau[steps_today:].sum()
        if need_next > 0 and after > 0:
            s_ = max(need_next, 1.0)
            add(np.zeros(after + 1), cat(j * K + ks_next, inu), cat(-tau[steps_today:] / s_, need_next / s_), 0.0)
    k1 = np.arange(1, K); n1 = K - 1
    rp, rm = 2 * np.arange(n1), 2 * np.arange(n1) + 1
    pair_rows = cat(rp, rp, rp, rm, rm, rm)                    # rows of the |q[k] − q[k−1]| pairs (k ≥ 1)
    pair_vals = cat(np.ones(n1), -np.ones(n1), -np.ones(n1), -np.ones(n1), np.ones(n1), -np.ones(n1))
    if dq_max is not None:                                     # gate rate
        rate_cols = cat(k1, k1 - 1, irt + k1, k1, k1 - 1, irt + k1)
        for j in range(J):
            if q_prev is not None:
                add([0, 0, 1, 1], [j * K, irt + j * K, j * K, irt + j * K], [1.0, -1.0, -1.0, -1.0],
                    [dq_max[j] + 1.0 * q_prev[j], dq_max[j] + -1.0 * q_prev[j]])
            if n1 > 0:                                         # between blocks: scaled to the distance between midpoints
                add(pair_rows, rate_cols + j * K, pair_vals, np.repeat(dq_max[j] * 0.5 * (tau[1:] + tau[:-1]) / dt, 2))
    for j in range(J - 1):                                     # soft: a regulator takes no more than the share μ
        if final:                                              # V̂_j + Σ q τ ≤ μ·x_j + o_j
            x_j, v_j = float(target_today[j]), float(delivered_today[j])
            scale_j = max(x_j, 1.0)
            add(np.zeros(steps_today + 2), cat(j * K + ks_today, mu_col(j), io + j),
                cat(tau[:steps_today] / scale_j, -x_j / scale_j, -1.0), -v_j / scale_j)
            continue
        need_today = max(remaining_today[j], 0.0)
        scale_j = max(need_today, 1.0)
        add(np.zeros(steps_today + 2), cat(j * K + ks_today, mu_col(j), io + j),
            cat(tau[:steps_today] / scale_j, -need_today / scale_j, -1.0), 0.0)
    if 0 < steps_today < K + 1 and terminal_band is not None:  # terminal level (end of day = h[steps_today])
        add([0, 0, 1, 1], [ih + steps_today - 1, it_, ih + steps_today - 1, it_], [1.0, -1.0, -1.0, -1.0],
            [h_ref + terminal_band, -(h_ref - terminal_band)])
    t_today = tau[:steps_today].sum()
    scale = np.zeros(J)
    r2p, r2m = 2 * kk, 2 * kk + 1
    track_rows = cat(r2p, r2p, r2m, r2m)
    track_vals = cat(np.ones(K), -np.ones(K), -np.ones(K), -np.ones(K))
    track_cols = cat(kk, iu + kk, kk, iu + kk)
    move_cols = cat(k1, k1 - 1, ig + k1, k1, k1 - 1, ig + k1)
    for j in range(J):                                         # smooth-discharge tracking: u ≥ |q − q̄|
        qbar_today = remaining_today[j] / t_today if t_today > 0 else 0.0
        scale[j] = max(qbar_today, rate_next[j], 1e-3 * capacity[j], 1e-9)
        qbar = np.where(kk < steps_today, qbar_today, rate_next[j])
        add(track_rows, track_cols + j * K, track_vals, np.column_stack([qbar, -qbar]).ravel())
        if q_prev is not None:                                 # gate movement: g ≥ |q[k] − q[k−1]|
            add([0, 0, 1, 1], [j * K, ig + j * K, j * K, ig + j * K], [1.0, -1.0, -1.0, -1.0], [q_prev[j], -q_prev[j]])
        if n1 > 0:
            add(pair_rows, move_cols + j * K, pair_vals, np.zeros(2 * n1))
    R, C, V = np.concatenate(blocks_r), np.concatenate(blocks_c), np.concatenate(blocks_v)
    b_ub = np.concatenate(blocks_b)
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
    # terminal condition: by default as heavy as the other soft constraints; a scenario can lower it
    c[is_:is_ + K] = slack_weight; c[io:io + J - 1] = slack_weight
    c[it_] = optional("execution_terminal_weight", slack_weight)
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
    A_ub = coo_matrix((V, (R, C)), shape=(nrow, nv)).tocsr()
    A_eq = coo_matrix((EV, (ER, EC)), shape=(K, nv)).tocsr()
    res = _check(_lp(c, "execution", A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds), "execution LP")
    z = res.x
    mu = float(np.min(z[imj:imj + J])) if weighted else float(z[im])
    return {"q": z[:nq].reshape(J, K), "h": np.r_[h0, z[ih:ih + K]], "mu": mu, "nu": float(z[inu]),
            "slack": float(z[is_:is_ + K].sum()), "mu_j": z[imj:imj + J] if weighted else None,
            "command_violation": float(z[isc:isc + nq].max(initial=0.0)), "rate_violation": float(z[irt:irt + nq].max(initial=0.0)),
            # violations at the executed (first) interval: (9) and gate rate in m³/s, level bounds in m
            "first_command_violation": max(0.0, float(z[isc:isc + nq].reshape(J, K)[:, 0].max())),
            "first_rate_violation": max(0.0, float(z[irt:irt + nq].reshape(J, K)[:, 0].max())),
            "first_level_slack": max(0.0, float(z[is_]))}
