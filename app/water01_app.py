"""Water-01 graphical interface: explore the published results and run the model.

Start from the repository root:
    python -m pip install -r requirements.txt -r requirements-gui.txt
    streamlit run app/water01_app.py

Pages
- Overview: the study in brief and the main numbers, computed from the stored results.
- Results explorer: daily worst-user satisfaction, user satisfaction and node level of every stored run.
- IoT price: the executability price of each controller and its Shapley attribution.
- Hypothesis tests: confirmatory and exploratory tests, bootstrap variants, sensitivity cases.
- Run the model: closed-loop simulation of a chosen period with the Saint-Venant plant.
- Reproducibility: code checksum, environment, and the commands that regenerate every result.

The interface only reads the stored results and calls the model; it does not change any file of the repository.
"""
import io
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RES = ROOT / "results"
NORMAL = RES / "experiment" / "normal"
EXPLORATORY = RES / "exploratory"
FIGURES = RES / "figures"
RECORDS = {"supply": ROOT / "DATA/processed/rashod_2010_2019_daily.csv",
           "demand": ROOT / "DATA/processed/demand_decadal.csv"}
SYNTHETIC = {"supply": ROOT / "DATA/synthetic/supply_daily.csv",
             "demand": ROOT / "DATA/synthetic/demand_decadal.csv"}

USERS = ["Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli"]
METHODS = ["LXB", "Oracle", "B0", "B1", "B2", "B3"]
EXPL_METHODS = {"B3V": "b3_feedback", "LXB-DA": "deadband_aware"}
METHOD_LABEL = {"LXB": "LXB (proposed)", "Oracle": "Oracle", "B0": "B0 current practice",
                "B1": "B1 open-loop plan", "B2": "B2 weighted sum", "B3": "B3 proportional rationing",
                "B3V": "B3V (exploratory)", "LXB-DA": "LXB-DA (exploratory)", "LXB-noS3": "LXB without stage 3"}
# Okabe-Ito order, fixed per method so that a method keeps its colour on every page
COLOR = {"LXB": "#0072B2", "Oracle": "#56B4E9", "B0": "#D55E00", "B1": "#CC79A7", "B2": "#009E73",
         "B3": "#E69F00", "B3V": "#F0E442", "LXB-DA": "#000000", "LXB-noS3": "#999999"}
CHAINS = {"tuned / phys": ("tuned", "phys"), "tuned / IoT": ("tuned", "iot"),
          "untuned / phys": ("untuned", "phys"), "untuned / IoT": ("untuned", "iot")}
YEARS = list(range(2010, 2020))
FACTORS = {"sensor": "S  sensor error", "quantisation": "Q  quantisation and deadband",
           "communication": "C  packet budget and loss", "energy": "E  solar energy balance"}

st.set_page_config(page_title="Water-01 · IoT executability price", page_icon="💧", layout="wide")


# ---------------------------------------------------------------- data access
def run_file(method, year, tuned, chain):
    folder = EXPLORATORY / EXPL_METHODS[method] if method in EXPL_METHODS else NORMAL
    return folder / f"{method}_{year}_{tuned}_{chain}.csv"


@st.cache_data(show_spinner=False)
def read_run(method, year, tuned, chain):
    f = run_file(method, year, tuned, chain)
    if not f.exists():
        return None
    return pd.read_csv(f, parse_dates=["date"])


@st.cache_data(show_spinner="Reading the stored results ...")
def season_table():
    """Seasonal means of every stored main and exploratory run."""
    rows = []
    for m in METHODS + list(EXPL_METHODS):
        for (t, c) in CHAINS.values():
            for y in YEARS:
                d = read_run(m, y, t, c)
                if d is None:
                    continue
                rows.append(dict(method=m, tuned=t, chain=c, year=y, lam=d["lambda"].mean(),
                                 **{u: d[f"r_{u}"].mean() for u in USERS},
                                 h_min=d.h_min.min(), messages=d.messages.iloc[0], dropped=d.dropped.iloc[0]))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def read_csv(path):
    p = ROOT / path
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(show_spinner=False)
def numbers():
    p = RES / "tables" / "results_tables.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def price(phys, iot):
    return (phys - iot) / phys if phys > 0 else float("nan")


def fig_layout(fig, title=None, y_title=None, x_title=None, height=380):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=40 if title else 10, b=10),
                      title=dict(text=title, x=0, xanchor="left", font=dict(size=15)) if title else None,
                      legend=dict(orientation="h", yanchor="top", y=-0.18, x=0), hovermode="x unified")
    if y_title:
        fig.update_yaxes(title_text=y_title)
    if x_title:
        fig.update_xaxes(title_text=x_title)
    return fig


def md_table(rows):
    """Table from the generated results_tables.json (first row = header); markdown sub/superscripts removed."""
    clean = lambda c: (c.replace("{~", "").replace("~}", "").replace("{^", "^").replace("^}", "")
                       .replace("*", ""))
    return pd.DataFrame([[clean(c) for c in r] for r in rows[1:]], columns=[clean(c) for c in rows[0]])


# ---------------------------------------------------------------- pages
def page_overview():
    st.title("IoT executability price of lexicographic water allocation")
    st.markdown(
        "Saint–Venant simulation of one pool of the **Kegeyli irrigation canal** (Uzbekistan) and the six outlets "
        "of the Dustlik node, 2010–2019. A daily **lexicographic max–min plan** is executed every 15 min by the "
        "receding-horizon controller **LXB** and compared with current practice (B0), an open-loop fair plan "
        "(B1), a weighted-sum controller (B2), proportional rationing (B3) and an Oracle, under ideal execution "
        "(*phys*) and through a simulated **IoT chain** (*IoT*: sensor error, actuator quantisation and deadband, "
        "LoRaWAN packet budget and loss, solar energy balance). The **IoT executability price** "
        r"$\Pi_1=(\lambda^{\mathrm{phys}}-\lambda^{\mathrm{IoT}})/\lambda^{\mathrm{phys}}$ is the relative loss of "
        r"$\lambda$, the worst user's daily delivered-to-demanded volume.")
    tab = season_table()
    if tab.empty:
        st.warning("No stored results were found in results/experiment/normal.")
        return
    g = tab.groupby(["method", "tuned", "chain"]).lam.mean()
    cols = st.columns(4)
    lp, li = g[("LXB", "tuned", "phys")], g[("LXB", "tuned", "iot")]
    cols[0].metric("LXB, mean daily λ (phys)", f"{lp:.3f}")
    cols[1].metric("LXB, mean daily λ (IoT)", f"{li:.3f}", f"{-100 * price(lp, li):.1f}% (IoT price)",
                   delta_color="off")
    cols[2].metric("B0 current practice, λ (IoT)", f"{g[('B0', 'tuned', 'iot')]:.3f}",
                   f"{-100 * price(g[('B0', 'tuned', 'phys')], g[('B0', 'tuned', 'iot')]):.0f}%", delta_color="off")
    if ("LXB-DA", "tuned", "iot") in g:
        cols[3].metric("LXB-DA deadband-aware, λ (IoT)", f"{g[('LXB-DA', 'tuned', 'iot')]:.3f}",
                       f"{-100 * price(lp, g[('LXB-DA', 'tuned', 'iot')]):.1f}%", delta_color="off")

    st.subheader("Mean daily worst-user satisfaction, 2010–2019")
    fig = go.Figure()
    order = [m for m in METHODS + list(EXPL_METHODS) if (m, "tuned", "iot") in g]
    for chain, sym, name in (("phys", "circle", "phys (ideal execution)"), ("iot", "diamond-open", "IoT chain")):
        fig.add_trace(go.Scatter(
            x=[g.get((m, "tuned", chain), np.nan) for m in order], y=[METHOD_LABEL[m] for m in order],
            mode="markers", name=name, marker=dict(symbol=sym, size=12, color="#222" if chain == "phys" else "#0072B2",
                                                   line=dict(width=2))))
    fig.update_xaxes(range=[0, 0.9])
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_layout(fig, x_title="mean daily λ (tuned gate coefficients)", height=380),
                    width="stretch")
    st.caption("Exploratory controllers: B3V = proportional rationing with feedback on delivered volumes; "
               "LXB-DA = LXB with a deadband-aware execution rule (no phys run; it coincides with LXB under "
               "ideal execution).")

    figs = sorted(FIGURES.glob("Figure*.png"))
    if figs:
        st.subheader("Figures of the article")
        choice = st.selectbox("Figure", [f.stem for f in figs], index=min(1, len(figs) - 1))
        st.image(str(FIGURES / f"{choice}.png"), width="stretch")


def page_explorer():
    st.title("Results explorer")
    st.caption("Every stored run: one CSV per controller × season × execution chain in results/experiment/normal "
               "(exploratory controllers in results/exploratory).")
    with st.sidebar:
        st.header("Selection")
        methods = st.multiselect("Controllers", METHODS + list(EXPL_METHODS), default=["LXB", "B0", "B3"],
                                 format_func=lambda m: METHOD_LABEL[m])
        chain_label = st.radio("Execution chain", list(CHAINS), index=1)
        year = st.selectbox("Season", YEARS, index=YEARS.index(2018))
    tuned, chain = CHAINS[chain_label]
    data = {m: read_run(m, year, tuned, chain) for m in methods}
    missing = [m for m, d in data.items() if d is None]
    data = {m: d for m, d in data.items() if d is not None}
    if missing:
        st.info(f"Not stored for this chain: {', '.join(missing)} (LXB-DA has IoT runs only).")
    if not data:
        return

    fig = go.Figure()
    for m, d in data.items():
        fig.add_trace(go.Scatter(x=d.date, y=d["lambda"], name=METHOD_LABEL[m], mode="lines",
                                 line=dict(color=COLOR[m], width=2)))
    fig.update_yaxes(range=[-0.02, 1.05])
    st.plotly_chart(fig_layout(fig, f"Daily worst-user satisfaction λ[p], {year}, {chain_label}", "λ[p]"),
                    width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for m, d in data.items():
            fig.add_trace(go.Bar(y=USERS, x=[d[f"r_{u}"].mean() for u in USERS], name=METHOD_LABEL[m],
                                 orientation="h", marker_color=COLOR[m]))
        fig.update_xaxes(range=[0, 1.05])
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(barmode="group", hovermode="y unified")
        st.plotly_chart(fig_layout(fig, "Mean satisfaction of each user", x_title="mean r_j"),
                        width="stretch")
    with c2:
        fig = go.Figure()
        for m, d in data.items():
            fig.add_trace(go.Scatter(x=d.date, y=d.h_min, name=f"{m} min", mode="lines",
                                     line=dict(color=COLOR[m], width=1.5)))
            fig.add_trace(go.Scatter(x=d.date, y=d.h_max, name=f"{m} max", mode="lines", showlegend=False,
                                     line=dict(color=COLOR[m], width=1.5, dash="dot")))
        st.plotly_chart(fig_layout(fig, "Daily minimum (solid) and maximum (dotted) node level", "h_L, m"),
                        width="stretch")

    rows = []
    for m, d in data.items():
        rows.append({"controller": m, "mean λ": d["lambda"].mean(), "days with λ = 0": int((d["lambda"] < 1e-9).sum()),
                     **{f"r {u}": d[f"r_{u}"].mean() for u in USERS}, "min level, m": d.h_min.min(),
                     "command packets": int(d.messages.iloc[0]), "lost or blocked": int(d.dropped.iloc[0])})
    st.dataframe(pd.DataFrame(rows).set_index("controller").style.format(precision=3), width="stretch")
    m0 = next(iter(data))
    st.download_button(f"Download the {m0} file", data[m0].to_csv(index=False).encode(),
                       file_name=run_file(m0, year, tuned, chain).name, mime="text/csv")


def page_price():
    st.title("IoT executability price and its sources")
    tab = season_table()
    if tab.empty:
        st.warning("No stored results.")
        return
    tuned = st.radio("Gate coefficients", ["tuned", "untuned"], horizontal=True)
    g = tab[tab.tuned == tuned].groupby(["method", "chain"]).lam.mean().unstack()
    if "LXB-DA" in g.index:
        g.loc["LXB-DA", "phys"] = g.loc["LXB", "phys"]
    g["price, %"] = 100 * (g["phys"] - g["iot"]) / g["phys"]
    g = g.reindex([m for m in METHODS + list(EXPL_METHODS) if m in g.index])
    fig = go.Figure(go.Bar(x=[METHOD_LABEL[m] for m in g.index], y=g["price, %"],
                           marker_color=[COLOR[m] for m in g.index],
                           text=[f"{v:.1f}%" for v in g["price, %"]], textposition="outside"))
    st.plotly_chart(fig_layout(fig, f"IoT price Π₁ as a ratio of seasonal means ({tuned} gate coefficients)",
                               "Π₁, %"), width="stretch")
    st.dataframe(g.rename(columns={"phys": "mean λ phys", "iot": "mean λ IoT"}).style.format(precision=3),
                 width="stretch")

    st.subheader("Daily price of LXB")
    year = st.select_slider("Season", YEARS, value=2014)
    ph, io_ = read_run("LXB", year, tuned, "phys"), read_run("LXB", year, tuned, "iot")
    if ph is not None and io_ is not None:
        early = (ph.date.dt.month == 4) & (ph.date.dt.day <= 10)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ph["lambda"][~early], y=io_["lambda"][~early], mode="markers", name="other days",
                                 marker=dict(color="#0072B2", size=7, opacity=0.6), text=ph.date.dt.date[~early]))
        fig.add_trace(go.Scatter(x=ph["lambda"][early], y=io_["lambda"][early], mode="markers", name="1–10 April",
                                 marker=dict(color="#D55E00", size=10, symbol="square-open", line=dict(width=2)),
                                 text=ph.date.dt.date[early]))
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#999", dash="dash"),
                                 showlegend=False, hoverinfo="skip"))
        fig.update_layout(hovermode="closest")
        st.plotly_chart(fig_layout(fig, f"Daily λ with ideal execution and with the IoT chain, {year}",
                                   "λ IoT", "λ phys", height=420), width="stretch")

    st.subheader("Shapley attribution to the four device constraints (tuned)")
    sh = read_csv("results/shapley_by_year_normal.csv")
    if sh is not None:
        fig = go.Figure()
        for k, name, c in (("phi_quantisation", "φQ quantisation and deadband", "#0072B2"),
                           ("phi_sensor", "φS sensor error", "#E69F00"),
                           ("phi_communication", "φC communication", "#009E73"),
                           ("phi_energy", "φE energy", "#999999")):
            fig.add_trace(go.Bar(x=sh.year, y=100 * sh[k], name=name, marker_color=c))
        fig.update_layout(barmode="group", hovermode="x unified")
        st.plotly_chart(fig_layout(fig, "Contributions to the mean daily price, by season", "percentage points"),
                        width="stretch")
        st.caption("Each season needs 16 runs (all subsets of S, Q, C, E). The large values of 2014 come from one "
                   "day on which the pool released only a residual (λ phys = 8 × 10⁻⁶), see Section 3.3 of the "
                   "article.")


def page_tests():
    st.title("Hypothesis tests and sensitivity")
    t1, t2, t3, t4 = st.tabs(["Pre-specified tests", "Exploratory comparisons", "Sensitivity cases",
                              "Verification"])
    with t1:
        variant = st.selectbox("Bootstrap", {"normal": "10-day moving blocks (pre-specified)",
                                             "normal_circular": "circular blocks", "normal_season": "whole seasons",
                                             "block_5": "5-day blocks", "block_20": "20-day blocks"}.items(),
                               format_func=lambda kv: kv[1])[0]
        h = read_csv(f"results/hypotheses_summary_{variant}.csv")
        if h is not None:
            show = h[["hypothesis", "comparison", "variant", "role", "estimate", "ci_low", "ci_high", "p_holm",
                      "sign_share", "decision"]]
            st.dataframe(show.style.format({"estimate": "{:+.4f}", "ci_low": "{:+.4f}", "ci_high": "{:+.4f}",
                                            "p_holm": "{:.2g}", "sign_share": "{:.1f}"}),
                         width="stretch", height=520)
        n = numbers()
        if n:
            st.markdown("**Table 6 of the article**")
            st.dataframe(md_table(n["table_hypotheses"]), width="stretch", hide_index=True)
    with t2:
        scheme = st.radio("Bootstrap", ["moving blocks", "circular blocks"], horizontal=True)
        e = read_csv("results/exploratory_tests.csv" if scheme == "moving blocks"
                     else "results/exploratory_tests_circular.csv")
        if e is not None:
            st.dataframe(e[["hypothesis", "comparison", "variant", "estimate", "ci_low", "ci_high", "p_holm",
                            "sign_share", "decision"]].style.format(
                {"estimate": "{:+.4g}", "ci_low": "{:+.4g}", "ci_high": "{:+.4g}", "p_holm": "{:.2g}"}),
                width="stretch")
        st.caption("E1 LXB vs B3/B3V; E2 LXB-DA vs LXB; E3 price of LXB-DA vs LXB; E4 B3V vs LXB; "
                   "E5 stricter tolerances of H3; E6 reverse gate mismatch.")
    with t3:
        s = read_csv("results/sensitivity_summary.csv")
        if s is not None:
            lx = s[s.method == "LXB"].copy()
            lx["price, %"] = 100 * lx.pi1_ratio
            fig = go.Figure(go.Scatter(x=lx["price, %"], y=lx.case, mode="markers",
                                       marker=dict(size=11, color="#0072B2")))
            st.plotly_chart(fig_layout(fig, "IoT price of LXB in each case (ratio of means)", x_title="Π₁, %",
                                       height=520), width="stretch")
            st.dataframe(s, width="stretch", height=420)
    with t4:
        c = read_csv("results/verification/convergence.csv")
        if c is not None:
            st.markdown("**Grid and time-step convergence** (6 h transient, Table S2a)")
            st.dataframe(c, width="stretch", hide_index=True)
        r = read_csv("results/verification/rerun/comparison.csv")
        if r is not None:
            st.markdown("**Rerun of a stored season** (largest absolute difference per file)")
            st.dataframe(r, width="stretch", hide_index=True)


def input_choice():
    have_records = all(p.exists() for p in RECORDS.values())
    options = ["Synthetic inputs (DATA/synthetic, public)"]
    if have_records:
        options.insert(0, "Operating records (DATA/processed)")
    choice = st.radio("Input data", options, index=0)
    if choice.startswith("Synthetic"):
        if not all(p.exists() for p in SYNTHETIC.values()):
            st.error("The synthetic inputs are missing: run `python scripts/make_synthetic_inputs.py`.")
            st.stop()
        st.caption("Generated supply and demand with the structure of the records. Results differ from the article.")
        return SYNTHETIC, "synthetic"
    return RECORDS, "records"


def page_run():
    st.title("Run the model")
    st.markdown("Closed-loop simulation: controller → actuator chain → Dustlik node → Saint–Venant plant → sensors "
                "→ state estimate → controller, with a 15 min step. LXB, B2 and the Oracle solve linear programs at "
                "every step and need about 2–4 s per simulated day.")
    from water01.control import CONTROLLERS
    from water01.optimization.objectives import satisfaction

    scenarios = sorted(p.stem for p in (ROOT / "configs/scenarios").glob("*.yaml"))
    with st.form("run"):
        c1, c2, c3 = st.columns(3)
        with c1:
            paths, source = input_choice()
            scenario = st.selectbox("Scenario (configs/scenarios)", scenarios, index=scenarios.index("normal"))
        with c2:
            methods = st.multiselect("Controllers", list(CONTROLLERS), default=["LXB", "B3"],
                                     format_func=lambda m: METHOD_LABEL.get(m, m))
            tuned = st.toggle("Tuned gate coefficients", value=True)
        with c3:
            factors = st.multiselect("Active IoT constraints (none = ideal execution)", list(FACTORS),
                                     default=list(FACTORS), format_func=FACTORS.get)
            start = st.date_input("First day", value=pd.Timestamp("2018-06-01"),
                                  min_value=pd.Timestamp("2010-04-01"), max_value=pd.Timestamp("2019-09-30"))
            days = st.slider("Number of days", 1, 61, 5)
        go_run = st.form_submit_button("Run", type="primary")
    if go_run:
        execute(paths, source, scenario, methods, tuned, factors, start, days)
    if "last_run" in st.session_state:
        show_run(st.session_state["last_run"], satisfaction)


@st.cache_resource
def simulation_lock():
    """One lock per server process: the model keeps its active configuration in a module-level variable, so two
    sessions must not run simulations with different scenarios at the same time."""
    return threading.Lock()


def execute(paths, source, scenario, methods, tuned, factors, start, days):
    lock = simulation_lock()
    if not lock.acquire(blocking=False):
        st.warning("Another simulation is running on this server. Please wait until it has finished and run again.")
        return
    try:
        _execute(paths, source, scenario, methods, tuned, factors, start, days)
    finally:
        from water01.simulation.scenarios import load_config
        load_config()                                               # back to the reference configuration
        lock.release()


def _execute(paths, source, scenario, methods, tuned, factors, start, days):
    from water01.simulation.runner import run_closed_loop_period
    from water01.simulation.scenarios import iot_scenario, load_config
    start = pd.Timestamp(start)
    end = start + pd.Timedelta(days=days - 1)
    if not (4 <= start.month <= 9 and 4 <= end.month <= 9 and start.year == end.year):
        st.error("The period must lie within one vegetation season (1 April – 30 September).")
        return
    if not methods:
        st.error("Choose at least one controller.")
        return

    cfg = load_config(scenario=scenario)
    iot = iot_scenario(cfg, tuple(factors)) if factors else None
    outs = {}
    bar = st.progress(0.0, text="Starting ...")
    for i, m in enumerate(methods):
        t0 = time.time()

        def progress(p, P, i=i, m=m):
            bar.progress((i + p / P) / len(methods), text=f"{m}: day {p} of {P}")
        try:
            outs[m] = run_closed_loop_period(m, paths["supply"], paths["demand"], cfg, str(start.date()), days,
                                             tuned=tuned, iot=iot, seed=cfg.seed + start.year, progress=progress)
        except Exception as exc:                                    # shown to the user, the app keeps running
            st.error(f"{m}: {exc}")
            continue
        outs[m]["seconds"] = time.time() - t0
    bar.empty()
    if not outs:
        return
    st.session_state["last_run"] = dict(outs=outs, start=start, days=days, source=source, scenario=scenario,
                                        tuned=tuned, factors=factors)


def show_run(run, satisfaction):
    outs, start, days = run["outs"], run["start"], run["days"]
    dates = pd.date_range(start, periods=days, freq="D")
    chain = "IoT: " + ", ".join(run["factors"]) if run["factors"] else "ideal execution"
    st.success(f"{len(outs)} run(s), {dates[0].date()} – {dates[-1].date()}, {run['source']} inputs, scenario "
               f"{run['scenario']}, {'tuned' if run['tuned'] else 'untuned'} coefficients, {chain}.")
    rows, frames = [], []
    for m, o in outs.items():
        res = o["result"]; r = satisfaction(res.delivered, o["D"])
        rows.append({"controller": m, "mean daily λ": float(np.mean(o["lambda_daily"])), "Z2": o["Z2"], "Z3": o["Z3"],
                     **{f"r {u}": float(np.nanmean(r[j])) for j, u in enumerate(USERS)},
                     "storage change / inflow": o["storage_change_share"], "packets": res.messages_sent,
                     "lost or blocked": res.messages_dropped, "mass error": res.mass_error, "time, s": o["seconds"]})
        f = pd.DataFrame({"controller": m, "date": dates.date, "lambda": o["lambda_daily"]})
        for j, u in enumerate(USERS):
            f[f"r_{u}"] = r[j]; f[f"V_{u}"] = res.delivered[j]
        frames.append(f)
    st.dataframe(pd.DataFrame(rows).set_index("controller").style.format(precision=3), width="stretch")

    fig = go.Figure()
    for m, o in outs.items():
        fig.add_trace(go.Scatter(x=dates, y=o["lambda_daily"], name=METHOD_LABEL.get(m, m), mode="lines+markers",
                                 line=dict(color=COLOR.get(m, "#444"), width=2)))
    fig.update_yaxes(range=[-0.02, 1.05])
    st.plotly_chart(fig_layout(fig, "Daily worst-user satisfaction λ[p]", "λ[p]"), width="stretch")

    m = st.selectbox("Details of", list(outs))
    tr = outs[m]["result"].trace
    t = pd.to_datetime(start) + pd.to_timedelta(np.asarray(tr["t"], float), unit="s")
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=tr["h_true"], name="true level", line=dict(color="#0072B2")))
        fig.add_trace(go.Scatter(x=t, y=tr["h_est"], name="estimated level", line=dict(color="#E69F00", dash="dot")))
        st.plotly_chart(fig_layout(fig, f"{m}: node level", "h_L, m"), width="stretch")
    with c2:
        q = np.asarray(tr["q_true"], float)
        fig = go.Figure()
        for j, u in enumerate(USERS[:5]):
            fig.add_trace(go.Scatter(x=t, y=q[:, j], name=u, mode="lines"))
        st.plotly_chart(fig_layout(fig, f"{m}: regulator discharges (Lower Kegeyli omitted)", "m³/s"),
                        width="stretch")
    buf = io.StringIO(); pd.concat(frames).to_csv(buf, index=False)
    st.download_button("Download the daily results (CSV)", buf.getvalue().encode(), file_name="water01_run.csv",
                       mime="text/csv")


def code_checksum():
    from water01.simulation.provenance import code_sha256
    return code_sha256(ROOT)


def page_repro():
    st.title("Reproducibility")
    from water01.simulation.provenance import environment_info, read_pins
    man = RES / "experiment" / "MANIFEST_all.json"
    local = code_checksum()
    stored = None
    metas = sorted(NORMAL.glob("*.meta.json"))
    if metas:
        stored = json.loads(metas[0].read_text(encoding="utf-8")).get("code_sha256")
    elif man.exists():
        stored = json.loads(man.read_text(encoding="utf-8")).get("code_sha256")
    c1, c2, c3 = st.columns(3)
    c1.metric("Stored result files", len(list(RES.rglob("*.csv"))))
    c2.metric("Code checksum of this copy", local[:12])
    c3.metric("Code checksum of the stored results", (stored or "—")[:12])
    if stored and stored == local:
        st.success("The source code of this copy is the code that computed the stored results.")
    elif stored:
        st.warning("The source code differs from the code that computed the stored results; reruns may differ.")
    if man.exists():
        m = json.loads(man.read_text(encoding="utf-8"))
        st.caption(f"Manifest {man.relative_to(ROOT).as_posix()}: {m.get('expected_files', '—')} expected result "
                   f"files; code {str(m.get('code_sha256', ''))[:12]}; protocol {str(m.get('protocol_sha256', ''))[:12]}.")

    env = environment_info(); pins = read_pins(ROOT / "requirements.txt")
    st.subheader("Software environment")
    st.dataframe(pd.DataFrame([{"package": k, "pinned": pins.get(k, ""), "installed": env.get(k)}
                               for k in ("numpy", "scipy", "pandas", "PyYAML")] +
                              [{"package": "Python", "pinned": "3.13", "installed": env["python"]},
                               {"package": "HiGHS (in SciPy)", "pinned": "1.8.0", "installed": env["highs"]}]),
                 hide_index=True, width="stretch")
    st.subheader("Input data")
    have = all(p.exists() for p in RECORDS.values())
    st.markdown(
        "- `DATA/raw/nasa_power/`: hourly NASA POWER irradiance (open data), used by the energy model.\n"
        "- `DATA/synthetic/`: generated supply and demand with the structure of the records "
        "(`scripts/make_synthetic_inputs.py`).\n"
        f"- `DATA/processed/`: processed operating records of the irrigation system — "
        f"{'**present in this copy**' if have else '**not present**'}. They are third-party data, not part of the "
        "public repository, and are available to reviewers on request. Their SHA-256 checksums are stored in "
        "every `.meta.json` file.")
    st.subheader("Commands")
    st.code("""python -m pytest -q                                  # tests (synthetic inputs if the records are absent)
python scripts/make_results_tables.py                # tables and numbers of the article -> results/tables/
python scripts/fig_results.py                        # Figures 4-6 -> results/figures/
python scripts/run_experiment.py --verify --years 2018 --methods LXB --tuned tuned --iot iot   # needs the records
python scripts/run_experiment.py --all --jobs 4      # full sweep (needs the records, about 2 days on 4 cores)""",
            language="bash")


pages = [st.Page(page_overview, title="Overview", icon="🏠", default=True),
         st.Page(page_explorer, title="Results explorer", icon="📈", url_path="explorer"),
         st.Page(page_price, title="IoT price", icon="📉", url_path="price"),
         st.Page(page_tests, title="Hypothesis tests", icon="🧪", url_path="tests"),
         st.Page(page_run, title="Run the model", icon="▶️", url_path="run"),
         st.Page(page_repro, title="Reproducibility", icon="🔁", url_path="reproducibility")]
st.navigation(pages).run()
