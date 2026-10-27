"""Benchmark of the Saint–Venant plant against an independent unsteady-flow solver, EPA SWMM 5 (Section S2).

The pool and the Dustlik node are built a second time as a SWMM 5 model with dynamic-wave routing (the complete
Saint–Venant equations solved on a link-node network, Rossman 2017), with a fixed 2 s routing step and without
inertial damping: 58 junctions and 57 trapezoidal conduits with the geometry, slope and Manning coefficient of the
plant, the head inflow at the first junction, the conveyance loss of Equation (5) as withdrawals at the junctions
(each junction takes the share of the reach length that it represents), and the six outlets as side orifices with
C_d = 0.62 whose sills lie at the bed of the node. The five regulators discharge to outfalls at their constant
tail-water levels; the check structure discharges to an outfall whose stage is set at every routing step to the
normal depth of the lower reach at the current discharge of the check structure (the tail-water relation of the
plant). The SWMM model shares no code with the plant: only the input values are the same.

Three transients are replayed open loop in both models from their own steady states:
1. the gate positions of a closed-loop LXB run (controller gate relation equal to the plant's, IoT chain, quantised
   openings, a gate command every 15 min) over 1–7 July 2018, with the daily head discharges of these days;
2. a synthetic sequence of gate operations: steps of the check-structure opening (−30%, then +45%), opening and
   closing of the regulators, and a reduction of the head discharge by 20%, over two days;
3. the gate positions of a closed-loop LXB-T050 run (pulse rule with theta = 0.5, controller gate relation equal to the
   plant's, IoT chain) over 1–10 April 2016, a period of low supply in which the small regulators are served by
   one-step pulses at the pulse opening (0.6% of the travel).
The node level at the end of each 15 min step, the discharge of each outlet and the daily volumes delivered to the
six outlets are compared. In SWMM, the volumes are integrated over the routing steps.

Usage: python scripts/check_swmm_benchmark.py [--table-only]  ->  results/verification/swmm_benchmark.csv, .md and
       .json
"""
import json
import math
import os
import sys
import tempfile
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SUP = ROOT / "DATA/processed/rashod_2010_2019_daily.csv"
DEM = ROOT / "DATA/processed/demand_decadal.csv"
OUT = ROOT / "results/verification"
ROUTE_S = 2.0                                   # SWMM routing step, s
SPIN_DAYS = 2                                   # SWMM spin-up at the initial inflow and openings
NAMES = ("Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli")


def closed_loop_openings(start="2018-07-01", days=7, method="LXB", scenario="normal"):
    """Gate positions applied in a closed-loop run (tuned, IoT chain) and the daily head discharges."""
    from water01.domain.passport import value
    from water01.simulation.runner import run_closed_loop_period
    from water01.simulation.scenarios import iot_scenario, load_config
    from water01.simulation.scenarios import AVAILABLE_FACTORS
    sys.path.insert(0, str(ROOT / "scripts"))
    import rules
    rules.register()
    cfg = load_config(scenario=scenario)
    out = run_closed_loop_period(method, SUP, DEM, cfg, start, days, tuned=True,
                                 iot=iot_scenario(cfg, AVAILABLE_FACTORS), seed=cfg.seed + int(start[:4]))
    tr = out["result"].trace
    S = pd.read_csv(SUP, parse_dates=["date"]).set_index("date").loc[pd.date_range(start, periods=days)].kegeyli_Q
    return np.asarray(tr["openings"], float), S.fillna(0.0).to_numpy(float) * value("supply_scale")


def synthetic_openings(S0=60.0, days=2):
    """Synthetic gate operations from the steady state at S0: the openings that pass a typical July split."""
    from water01.domain.geometry import Reach
    from water01.domain.passport import value
    from water01.hydraulics.node import DustlikNode
    from water01.hydraulics.saint_venant import steady_profile
    spd = int(value("steps_per_day")); K = days * spd
    reach, node = Reach(), DustlikNode()
    h0, Q0 = steady_profile(reach, S0, value("h_init_m"), eta=value("eta"))
    share = np.array([0.15, 0.0008, 0.004, 0.02, 0.007])
    a = np.zeros(6)
    a[:5], _ = node.openings_for(np.r_[share * Q0[-1], 0.0], h0[-1])[0][:5], None
    O = np.tile(a, (K, 1))
    q_reg = node.flows(h0[-1], a)[:5].sum()
    O[:, 5] = node.openings_for(np.r_[np.zeros(5), Q0[-1] - q_reg], h0[-1])[0][5]
    b0 = O[0, 5]
    O[2 * 4:, 5] = 0.7 * b0                     # 2 h: check structure closed by 30%
    O[10 * 4:, :5] = 1.5 * a[:5]                # 10 h: regulators opened by 50%
    O[20 * 4:, 5] = 1.015 * b0                  # 20 h: check structure opened to 101.5% of the initial opening
    O[30 * 4:, 1] = 0.0                         # 30 h: R-1 closed
    O[36 * 4:, :5] = a[:5]                      # 36 h: regulators back to the initial openings
    S = np.array([S0] + [0.8 * S0] * (days - 1))  # day 2: head discharge reduced by 20%
    return O, S


def replay_plant(O, S):
    """Open-loop replay with the plant (Preissmann, as in the experiment): steady state at S[0] with the openings O[0]
    (the check structure balanced to the steady profile), then the openings O[k] at the steps k."""
    from water01.domain.geometry import Reach
    from water01.domain.passport import value
    from water01.hydraulics.node import DustlikNode
    from water01.simulation.plant_loop import CanalPlant
    dt, spd = float(value("dt_s")), int(value("steps_per_day"))
    reach, node = Reach(), DustlikNode()
    plant = CanalPlant(reach, node, S, value("eta"), value("h_init_m"), dt, spd, value("preissmann_theta"),
                       np.random.default_rng(0))
    a0 = plant.initialise_gates(O[0])
    h_init_profile = plant.solver.h.copy(); Q_init_profile = plant.solver.Q.copy()
    lev, flows = [], []
    for k in range(O.shape[0]):
        flows.append(plant.advance(O[k], dt).copy())
        lev.append(float(plant.solver.h[-1]))
    vol = plant.delivered.volume                                     # [6 × days], m3
    return dict(a0=a0, h0=h_init_profile, Q0=Q_init_profile, level=np.array(lev), flows=np.array(flows), volume=vol,
                h_end=plant.solver.h.copy(), dx=reach.dx, x=reach.x.copy())


def lower_tailwater():
    from water01.hydraulics.node import DustlikNode
    node = DustlikNode()
    return node._q_tab.copy(), node._h_tab.copy()


def inp_text(h0, Q0, a0, S0):
    """SWMM input file of the pool and node (metric units, levels from the bed of the node)."""
    from water01.domain.geometry import Reach
    from water01.domain.passport import value
    r = Reach()
    N = r.N
    z = r.S0 * (r.L - r.x)                                          # bed elevation, 0 at the node
    w = np.array(value("regulator_width_m"), float); hg = np.array(value("regulator_gate_height_m"), float)
    bw, bh = float(value("barrier_width_m")), float(value("barrier_gate_height_m"))
    tw = np.array(value("regulator_tailwater_m"), float); cd = float(value("gate_cd"))
    days = 60
    L = ["[TITLE]", "Kegeyli pool PK 0+00-114+40 and Dustlik node (benchmark of the Preissmann plant)", "",
         "[OPTIONS]", "FLOW_UNITS CMS", "INFILTRATION HORTON", "FLOW_ROUTING DYNWAVE", "LINK_OFFSETS DEPTH",
         "MIN_SLOPE 0", "ALLOW_PONDING NO", "SKIP_STEADY_STATE NO", "START_DATE 01/01/2020", "START_TIME 00:00:00",
         "REPORT_START_DATE 01/01/2020", "REPORT_START_TIME 00:00:00",
         f"END_DATE {(pd.Timestamp('2020-01-01') + pd.Timedelta(days=days)).strftime('%m/%d/%Y')}",
         "END_TIME 00:00:00", "SWEEP_START 01/01", "SWEEP_END 12/31", "DRY_DAYS 0", "REPORT_STEP 01:00:00",
         "WET_STEP 00:15:00", "DRY_STEP 01:00:00", f"ROUTING_STEP {ROUTE_S:g}", "RULE_STEP 00:00:00",
         "INERTIAL_DAMPING NONE", "NORMAL_FLOW_LIMITED FROUDE", "FORCE_MAIN_EQUATION H-W", "VARIABLE_STEP 0.00",
         "LENGTHENING_STEP 0", "MIN_SURFAREA 0.1", "MAX_TRIALS 20", "HEAD_TOLERANCE 0.00001", "SYS_FLOW_TOL 1",
         "LAT_FLOW_TOL 1", "MINIMUM_STEP 0.5", "THREADS 1", "",
         "[JUNCTIONS]", ";;Name Elevation MaxDepth InitDepth SurDepth Aponded"]
    for i in range(N):
        L.append(f"J{i} {z[i]:.6f} 8 {h0[i]:.6f} 0 0")
    L += ["", "[OUTFALLS]", ";;Name Elevation Type Stage Gated"]
    for j in range(5):
        L.append(f"T{j + 1} 0 FIXED {tw[j]:.4f} NO")
    L.append("TB 0 FIXED 2.0 NO")
    L += ["", "[CONDUITS]", ";;Name From To Length Roughness InOffset OutOffset InitFlow MaxFlow"]
    for i in range(N - 1):
        L.append(f"C{i} J{i} J{i + 1} {r.dx:.6f} {r.n:.6f} 0 0 {0.5 * (Q0[i] + Q0[i + 1]):.6f} 0")
    L += ["", "[ORIFICES]", ";;Name From To Type Offset Qcoeff Gated CloseTime"]
    for j in range(5):
        L.append(f"O{j + 1} J{N - 1} T{j + 1} SIDE 0 {cd:.4f} NO 0")
    L.append(f"OB J{N - 1} TB SIDE 0 {cd:.4f} NO 0")
    L += ["", "[XSECTIONS]", ";;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels"]
    for i in range(N - 1):
        L.append(f"C{i} TRAPEZOIDAL 8 {r.b:.4f} {r.m:.4f} {r.m:.4f} 1")
    for j in range(5):
        L.append(f"O{j + 1} RECT_CLOSED {hg[j]:.4f} {w[j]:.4f} 0 0")
    L.append(f"OB RECT_CLOSED {bh:.4f} {bw:.4f} 0 0")
    L += ["", "[REPORT]", "INPUT NO", "CONTROLS NO", "NODES NONE", "LINKS NONE", ""]
    return "\n".join(L) + "\n"


def run_swmm(O, S, plant, label):
    """SWMM replay: spin-up of SPIN_DAYS at S[0] with the plant's initial openings, then the openings O[k] at the
    15 min steps and the daily head discharges S[p]."""
    from swmm.toolkit import shared_enum as se
    from swmm.toolkit import solver
    from water01.domain.geometry import Reach
    from water01.domain.passport import value
    r = Reach(); N = r.N
    eta = float(value("eta")); dt = float(value("dt_s")); spd = int(value("steps_per_day"))
    hg = np.r_[np.array(value("regulator_gate_height_m"), float), float(value("barrier_gate_height_m"))]
    wts = np.full(N, r.dx / r.L); wts[0] *= 0.5; wts[-1] *= 0.5        # share of the reach length per junction
    qt, ht = lower_tailwater()
    tmp = Path(tempfile.mkdtemp(prefix="swmm_"))
    inp, rpt, out = tmp / "pool.inp", tmp / "pool.rpt", tmp / "pool.out"
    inp.write_text(inp_text(plant["h0"], plant["Q0"], plant["a0"], S[0]), encoding="utf-8")
    solver.swmm_open(str(inp), str(rpt), str(out))
    idx = lambda kind, name: solver.project_get_index(kind, name)
    J = [idx(se.ObjectType.NODE, f"J{i}") for i in range(N)]
    Ol = [idx(se.ObjectType.LINK, f"O{j + 1}") for j in range(5)] + [idx(se.ObjectType.LINK, "OB")]
    TB = idx(se.ObjectType.NODE, "TB")
    solver.swmm_start(0)

    def set_inputs(s_head, openings):
        solver.node_set_total_inflow(J[0], s_head * (1.0 - (1.0 - eta) * wts[0]))
        for i in range(1, N):
            solver.node_set_total_inflow(J[i], -(1.0 - eta) * s_head * wts[i])
        for j in range(6):
            solver.link_set_target_setting(Ol[j], float(min(max(openings[j] / hg[j], 0.0), 1.0)))

    def tailwater():
        q = max(solver.link_get_result(Ol[5], se.LinkResult.FLOW), 0.0)
        solver.outfall_set_stage(TB, float(np.interp(q, qt, ht)))

    set_inputs(S[0], plant["a0"])
    t_spin = SPIN_DAYS * 86400.0
    t = 0.0
    while t < t_spin - 1e-6:
        tailwater()
        t = solver.swmm_step() * 86400.0
    h_spin = np.array([solver.node_get_result(j, se.NodeResult.DEPTH) for j in J])
    C = [idx(se.ObjectType.LINK, f"C{i}") for i in range(N - 1)]
    stored = lambda: (sum(solver.link_get_result(c, se.LinkResult.VOLUME) for c in C)
                      + sum(solver.node_get_result(j, se.NodeResult.VOLUME) for j in J))
    V_start, inflow = stored(), 0.0
    K = O.shape[0]
    lev, flows = np.zeros(K), np.zeros((K, 6))
    vol = np.zeros((6, int(math.ceil(K / spd))))
    for k in range(K):
        p = k // spd
        set_inputs(S[p], O[k])
        t_end = t_spin + (k + 1) * dt
        while t < t_end - 1e-6:
            tailwater()
            t_new = solver.swmm_step() * 86400.0
            q = np.array([solver.link_get_result(o, se.LinkResult.FLOW) for o in Ol])
            vol[:, p] += q * (t_new - t)
            inflow += eta * S[p] * (t_new - t)
            t = t_new
        lev[k] = solver.node_get_result(J[-1], se.NodeResult.DEPTH)
        flows[k] = [solver.link_get_result(o, se.LinkResult.FLOW) for o in Ol]
    h_end = np.array([solver.node_get_result(j, se.NodeResult.DEPTH) for j in J])
    replay_error = (stored() - V_start - (inflow - vol.sum())) / inflow       # continuity over the replay period
    solver.swmm_end()
    err = solver.swmm_get_mass_balance()
    solver.swmm_close()
    return dict(level=lev, flows=flows, volume=vol, h_spin=h_spin, h_end=h_end, mass_balance=list(map(float, err)),
                replay_continuity=float(replay_error))


def compare(label, O, S, D=None):
    plant = replay_plant(O, S)
    sw = run_swmm(O, S, plant, label)
    dl = sw["level"] - plant["level"]
    res = dict(case=label, steps=int(O.shape[0]),
               steady_level_plant=float(plant["h0"][-1]), steady_level_swmm=float(sw["h_spin"][-1]),
               steady_profile_max_abs_diff_m=float(np.max(np.abs(sw["h_spin"] - plant["h0"]))),
               level_max_abs_diff_m=float(np.max(np.abs(dl))), level_mean_abs_diff_m=float(np.mean(np.abs(dl))),
               level_range_plant_m=[float(plant["level"].min()), float(plant["level"].max())],
               end_profile_max_abs_diff_m=float(np.max(np.abs(sw["h_end"] - plant["h_end"]))),
               swmm_continuity_error_percent=sw["mass_balance"],
               swmm_replay_continuity_error=sw["replay_continuity"])
    vp, vs = plant["volume"], sw["volume"][:, :plant["volume"].shape[1]]
    for j, n in enumerate(NAMES):
        q_p, q_s = plant["flows"][:, j], sw["flows"][:, j]
        scale = max(float(np.mean(np.abs(q_p))), 1e-12)
        res[f"flow_{n}_max_rel_diff"] = float(np.max(np.abs(q_s - q_p)) / scale)
        res[f"volume_{n}_rel_diff"] = float((vs[j].sum() - vp[j].sum()) / max(vp[j].sum(), 1e-12))
        res[f"volume_{n}_daily_max_rel_diff"] = float(np.max(np.abs(vs[j] - vp[j]) / np.maximum(vp[j], 1e-12)))
    if D is not None:                                               # daily satisfaction from the two sets of volumes
        from water01.optimization.objectives import satisfaction
        lam = lambda V: np.nanmin(satisfaction(V, D[:, :V.shape[1]]), axis=0)
        res["lambda_daily_max_abs_diff"] = float(np.max(np.abs(lam(vs) - lam(vp))))
        res["lambda_mean_plant"] = float(np.mean(lam(vp))); res["lambda_mean_swmm"] = float(np.mean(lam(vs)))
    series = pd.DataFrame({"case": label, "step": np.arange(O.shape[0]), "level_plant": plant["level"],
                           "level_swmm": sw["level"]})
    for j, n in enumerate(NAMES):
        series[f"q_plant_{n}"] = plant["flows"][:, j]; series[f"q_swmm_{n}"] = sw["flows"][:, j]
    return res, series


def main():
    os.chdir(ROOT)
    from water01.simulation.scenarios import load_config
    sys.path.insert(0, str(ROOT / "scripts"))
    load_config(scenario="normal")
    res, ser = [], []
    O, S = closed_loop_openings()
    # demand of 1-7 July (variant A) for the daily worst-user satisfaction
    from water01.domain.passport import value
    from water01.simulation.scenarios import daily_arrays, derive_limit, load_demand, load_supply
    load_config(scenario="normal")
    sup = load_supply(SUP); dem = load_demand(DEM, "A")
    D, _, _ = daily_arrays(sup, dem, derive_limit(sup), pd.date_range("2018-07-01", periods=7), value("eta"))
    r, s = compare("closed-loop LXB gate positions, 1-7 July 2018", O, S, D); res.append(r); ser.append(s)
    O2, S2 = synthetic_openings()
    r, s = compare("synthetic gate operations and head discharge step", O2, S2); res.append(r); ser.append(s)
    O3, S3 = closed_loop_openings("2016-04-01", 10, "LXB-T050", "normal")
    load_config(scenario="normal")
    D3, _, _ = daily_arrays(sup, dem, derive_limit(sup), pd.date_range("2016-04-01", periods=10), value("eta"))
    r, s = compare("closed-loop LXB-T050 gate positions, 1-10 April 2016", O3, S3, D3); res.append(r); ser.append(s)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "swmm_benchmark.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    pd.concat(ser).to_csv(OUT / "swmm_benchmark_series.csv", index=False)
    pd.DataFrame(res).drop(columns=["level_range_plant_m", "swmm_continuity_error_percent"]).to_csv(
        OUT / "swmm_benchmark.csv", index=False)
    write_table(res)


def write_table(res):
    import swmm.toolkit as tk
    from swmm.toolkit import solver
    a, b = res[:2]
    c = res[2] if len(res) > 2 else None
    def pm(x, f):
        small = abs(x) < 0.5 * 10 ** -int(f.split(".")[1][0])
        return format(0.0, f.replace("+", "")) if small else format(x, f).replace("-", "−")
    rows = [("Steady node level, plant / SWMM, m", lambda r: f"{r['steady_level_plant']:.3f} / {r['steady_level_swmm']:.3f}"),
            ("Largest difference of the steady profile, m", lambda r: f"{r['steady_profile_max_abs_diff_m']:.3f}"),
            ("Range of the node level in the plant, m",
             lambda r: f"{r['level_range_plant_m'][0]:.2f}–{r['level_range_plant_m'][1]:.2f}"),
            ("Node level at the end of each step: mean / largest absolute difference, m",
             lambda r: f"{r['level_mean_abs_diff_m']:.3f} / {r['level_max_abs_diff_m']:.3f}")]
    for n in NAMES:
        rows.append((f"Volume delivered to {n} over the period, SWMM − plant",
                     lambda r, n=n: pm(100 * r[f"volume_{n}_rel_diff"], "+.2f") + "%"))
    rows.append(("Daily volume delivered to R-1: largest relative difference",
                 lambda r: pm(100 * r["volume_R-1_daily_max_rel_diff"], ".2f") + "%"))
    rows.append(("Daily worst-user satisfaction: largest absolute difference",
                 lambda r: f"{r['lambda_daily_max_abs_diff']:.4f}" if "lambda_daily_max_abs_diff" in r else "—"))
    rows.append(("SWMM continuity error over the replay", lambda r: pm(100 * r["swmm_replay_continuity_error"], "+.3f") + "%"))
    lines = ["<!-- widths: 46,27,27 -->", "",
             f"**Table S2c.** Plant against an independent solver: EPA SWMM {solver.swmm_version_info()} "
             f"(swmm-toolkit {tk.__version__}; dynamic-wave routing, 57 trapezoidal conduits, routing step {ROUTE_S:g} s, "
             "no inertial damping). Both models are driven open loop from their own steady states with the same gate "
             "positions and head discharges, changed at the start of every 15 min step: (a) the gate positions of a "
             "closed-loop LXB run under the device chain, 1–7 July 2018; (b) synthetic gate "
             "operations at a head discharge of 60 m^3^ s^−1^ (barrier closed by 30% after 2 h and opened to 101.5% of its initial opening after 20 h, "
             "regulators opened by 50% after 10 h and reset after 36 h, R-1 closed after 30 h) with the head discharge "
             "reduced by 20% on the second day; (c) the gate positions of a closed-loop run of the pulse rule with "
             "$\\theta$ = 0.5 under the device chain, 1–10 April 2016, in which the small "
             "regulators are served by one-step pulses at the pulse opening (0.6% of the travel). Levels from the bed "
             "of the node; daily worst-user satisfaction with the baseline demand.", "",
             "| Quantity | (a) Closed-loop gate positions, 1–7 July 2018 | (b) Synthetic gate and supply steps, 2 days "
             "| (c) Closed-loop gate positions with pulses, 1–10 April 2016 |",
             "|---|---|---|---|"]
    if c is None:
        lines[0] = "<!-- widths: 46,27,27 -->"
        lines[-2] = lines[-2].rsplit(" | (c)", 1)[0] + " |"; lines[-1] = "|---|---|---|"
    else:
        lines[0] = "<!-- widths: 34,22,22,22 -->"
    for name, f in rows:
        lines.append(f"| {name} | {f(a)} | {f(b)} |" + (f" {f(c)} |" if c is not None else ""))
    text = "\n".join(lines) + "\n"
    (OUT / "swmm_benchmark.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    if "--table-only" in sys.argv:
        write_table(json.loads((OUT / "swmm_benchmark.json").read_text(encoding="utf-8")))
    else:
        main()
