"""Figures of the article from the stored runs and the analysis tables -> results/figures/*.png and *.pdf.

  exclusion     daily plan of every regulator in quanta, x / q_min, under floor rounding (LXB), with the exclusion
                threshold 1 - 1/(2k) of Theorem 1(a); one panel per deadband case
  theta         error of the theta pulse rule on pulse-regime days, (V - x~) / p_max, with the bounds of Theorem 3
  equal_split   error of the equal split, |V - x~| / (g_max / 2), against the theta rule (theta = 0.5) on the same
                regulator-days (Theorem 1(b))
  periods       accounting-period error |sum V - sum x| / sum D of the carry-over rule and of the theta rule
                (theta = 0.5) against the length of the period T, with the bound of Theorem 4
  april         daily worst-case satisfaction in the first decade of April (ideal execution, floor rounding, theta
                rule, carry-over)
Usage: python scripts/make_figures.py [--figures exclusion,theta,equal_split,periods,april]
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_common import OUT, REGULATORS, ROOT, Quanta, load, regulator_days  # noqa: E402

FIG = ROOT / "results/figures"
# categorical slots (validated light-mode palette: blue, orange, aqua, yellow), ink and chrome
C = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100", "ink": "#0b0b0b",
     "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7"}
EPS = 1e-6

plt.rcParams.update({
    "font.family": "Liberation Sans", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.edgecolor": C["axis"],
    "axes.labelcolor": C["ink"], "xtick.color": C["ink2"], "ytick.color": C["ink2"], "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": C["grid"], "grid.linewidth": 0.5, "axes.axisbelow": True,
    "legend.frameon": False, "savefig.dpi": 600, "figure.dpi": 150, "pdf.fonttype": 42,
    # symbols as in the text (italic variables, superscript min/max), in the font of the labels
    "mathtext.fontset": "custom", "mathtext.rm": "Liberation Sans", "mathtext.it": "Liberation Sans:italic",
    "mathtext.bf": "Liberation Sans:bold", "mathtext.sf": "Liberation Sans", "mathtext.cal": "Liberation Sans"})

CASE_K = {"q_main": "normal", "q_deadband_low": "deadband_low", "q_deadband_high": "deadband_high"}


def save(fig, name):
    """PNG at 600 dpi in RGB (the journal's requirement for raster figures) and a vector PDF."""
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    from PIL import Image
    with Image.open(FIG / f"{name}.png") as im:
        rgb = Image.new("RGB", im.size, "white")
        rgb.paste(im, mask=im.getchannel("A") if im.mode == "RGBA" else None)
    rgb.save(FIG / f"{name}.png", dpi=(600, 600), optimize=True)
    print(f"{name}: written")


def fig_schematic():
    """Figure 1: (a) volume delivered in one step from a closed gate against the requested volume; (b) daily delivery
    against the daily plan under the execution rules (abstract actuator, constant level, k = 5, N = 96)."""
    sys.path.insert(0, str(ROOT / "src"))
    from quantmaxmin.execution import Actuator, equal_split_day, equal_split_m, floor_rule_day, nearest, theta_rule_day
    k, N = 5, 96
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 2.5))
    v = np.linspace(0, 12, 1201)
    out = np.array([Actuator(k).command(nearest(x, 1.0)) for x in v])
    a1.plot(v, v, color=C["muted"], lw=0.8, ls="--")
    a1.step(v, out, where="post", color=C["blue"], lw=1.6)
    a1.axvline(k - 0.5, color=C["ink"], lw=0.6, ls=":")
    a1.annotate(r"$k-1/2$", (k - 0.5, 9.6), xytext=(k - 0.4, 9.6), fontsize=7, color=C["ink"])
    a1.set_xlabel(r"requested volume of the step, in units of $g$"); a1.set_ylabel(r"delivered volume, in units of $g$")
    a1.set_title("(a) one step from a closed gate", loc="left", color=C["ink"])
    a1.set_xlim(0, 12); a1.set_ylim(0, 12)
    q, p = k * 1.0, (k + 1) * 1.0
    x = np.linspace(0.02, 4.0, 400) * q
    g = [1.0] * N
    floor = [floor_rule_day(xx, g, k) for xx in x]
    th0 = [theta_rule_day(xx, g, k, 0.0)[0] for xx in x]
    th5 = [theta_rule_day(xx, g, k, 0.5)[0] for xx in x]
    es = []
    for xx in x:
        m = equal_split_m(xx, q, 1.0, 10 * q, N)
        es.append(equal_split_day(xx, g, k, 10 ** 6, m)[0] if m else np.nan)
    a2.plot(x / q, x / q, color=C["muted"], lw=0.8, ls="--", label="plan")
    a2.plot(x / q, np.array(th0) / q, color=C["yellow"], lw=1.4, ls="-", label=r"pulse rule, $\theta = 0$")
    a2.plot(x / q, np.array(th5) / q, color=C["blue"], lw=1.4, ls="-", label=r"pulse rule, $\theta = 0.5$")
    a2.plot(x / q, np.array(es) / q, color=C["aqua"], lw=1.6, ls="-", label="equal split")
    a2.plot(x / q, np.array(floor) / q, color=C["orange"], lw=1.0, ls=(0, (3, 1.5)), label="floor rounding", zorder=5)
    a2.set_xlabel(r"daily plan $x/q$"); a2.set_ylabel(r"daily delivery $V/q$")
    a2.set_title(r"(b) one day, $N = 96$ steps", loc="left", color=C["ink"])
    a2.set_xlim(0, 4); a2.set_ylim(0, 4.8)
    a2.legend(loc="upper left", fontsize=6)
    fig.tight_layout()
    save(fig, "fig_schematic")


def fig_exclusion():
    cases = [c for c in CASE_K if not load(c, "LXB", (2010,)).empty]
    if not cases:
        return
    fig, axes = plt.subplots(len(cases), 1, figsize=(6.3, 1.55 * len(cases) + 0.4), sharex=True, squeeze=False)
    rng = np.random.default_rng(1)
    for ax, case in zip(axes[:, 0], cases):
        qa = Quanta(CASE_K[case])
        rd = regulator_days(load(case, "LXB"), qa)
        rd = rd[rd["x"] > EPS]
        thr = 1 - 1 / (2 * qa.k)
        for i, u in enumerate(REGULATORS):
            g = rd[rd["user"] == u]
            ratio = g["x"] / g["q_min"]
            y = i + rng.uniform(-0.28, 0.28, len(g))
            shut = (g["open"] == 0).to_numpy()
            ax.scatter(ratio[~shut], y[~shut], s=2, lw=0, color=C["blue"], alpha=0.5, rasterized=True)
            ax.scatter(ratio[shut], y[shut], s=6, lw=0, color=C["orange"], rasterized=True)
        ax.axvline(thr, color=C["ink"], lw=0.8, ls="--")
        # the label goes in the row with the widest empty band to the right of the threshold, clear of the points
        first = {i: (rd.loc[rd["user"] == u, "x"] / rd.loc[rd["user"] == u, "q_min"]).loc[lambda s: s > thr].min()
                 for i, u in enumerate(REGULATORS)}
        row = max(first, key=lambda i: first[i] if np.isfinite(first[i]) else np.inf)
        ax.text(thr * 1.08, row, rf"$1-1/(2k) = {thr:.3g}$", color=C["ink"], fontsize=7, va="center", ha="left",
                bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"), zorder=4)
        ax.set_yticks(range(len(REGULATORS)), list(REGULATORS))
        ax.set_ylim(-0.6, len(REGULATORS) - 0.4)
        ax.invert_yaxis()
        ax.set_xscale("log")
        ax.grid(axis="y", visible=False)
        ax.set_title(r"deadband $\delta$ = " + f"{qa.deadband * 100:.3g}% of the travel, " + rf"$k = {qa.k}$", loc="left",
                     color=C["ink"])
    axes[-1, 0].set_xlabel(r"daily plan in quanta, $x/q^{\min}$")
    h1 = plt.Line2D([], [], ls="", marker="o", ms=3, color=C["blue"], label="gate opened during the day")
    h2 = plt.Line2D([], [], ls="", marker="o", ms=3, color=C["orange"], label="gate never opened")
    fig.legend(handles=[h1, h2], loc="upper right", ncol=2, bbox_to_anchor=(0.99, 1.02))
    save(fig, "fig_exclusion")


def pulse_days(case, rule, theta):
    df = load(case, rule)
    if df.empty:
        return None
    rd = regulator_days(df, Quanta("normal"))
    pure = (rd["pulses"] > 0) & (rd["open"] == rd["pulses"]) & (rd["esopen"] == 0) & (rd["xt"] > EPS)
    r = rd[pure].copy()
    r["err"] = (r["V"] - r["xt"]) / r["p_max"]
    r["lower"] = -theta * np.minimum(r["p_max"], r["xt"]) / r["p_max"]
    return r


def fig_theta():
    series = [("q_main", "LXB-T000", 0.0), ("q_theta", "LXB-T025", 0.25), ("q_main", "LXB-T050", 0.5),
              ("q_theta", "LXB-T075", 0.75)]
    data = [(th, pulse_days(c, m, th)) for c, m, th in series]
    data = [(th, r) for th, r in data if r is not None and len(r)]
    if not data:
        return
    fig, axes = plt.subplots(1, len(data), figsize=(6.3, 1.9), sharey=True, squeeze=False)
    bins = np.linspace(-1.0, 1.1, 43)
    for ax, (th, r) in zip(axes[0], data):
        w = np.full(len(r), 100.0 / len(r))
        ax.hist(r["err"].clip(bins[0], bins[-1]), bins=bins, weights=w, color=C["blue"], edgecolor="white",
                linewidth=0.4)
        ax.axvspan(bins[0], -th, color=C["grid"], alpha=0.6, lw=0)
        ax.axvspan(1.0, bins[-1], color=C["grid"], alpha=0.6, lw=0)
        ax.axvline(-th, color=C["ink"], lw=0.8, ls="--"); ax.axvline(1.0, color=C["ink"], lw=0.8, ls="--")
        ax.set_title(rf"$\theta = {th:g}$  ($n = {len(r)}$)", loc="left", color=C["ink"])
        ax.set_xlabel(r"$(V-\tilde{x})/p^{\max}$")
    axes[0, 0].set_ylabel("regulator-days, %")
    save(fig, "fig_theta")


def fig_equal_split():
    es = load("q_main", "LXB-ES"); half = load("q_main", "LXB-T050")
    if es.empty or half.empty:
        return
    qa = Quanta("normal")
    a = regulator_days(es, qa); b = regulator_days(half, qa)
    a = a[a["mode"] == "ES"]
    m = a.merge(b[["date", "user", "V", "xt"]], on=["date", "user"], suffixes=("", "_t"))
    e_es = (m["V"] - m["xt"]).abs() / (m["g_max"] / 2)
    e_t = (m["V_t"] - m["xt_t"]).abs() / (m["g_max"] / 2)
    fig, ax = plt.subplots(figsize=(3.1, 2.1))
    bins = np.linspace(0, max(2.0, float(np.nanpercentile(e_t, 99))), 41)
    ax.hist(e_t.clip(upper=bins[-1]), bins=bins, color=C["orange"], alpha=0.85, label=r"pulse rule, $\theta = 0.5$",
            edgecolor="white", linewidth=0.4)
    ax.hist(e_es.clip(upper=bins[-1]), bins=bins, color=C["blue"], alpha=0.85, label="equal split",
            edgecolor="white", linewidth=0.4)
    ax.axvline(1.0, color=C["ink"], lw=0.8, ls="--")
    ax.set_xlabel(r"$|V-\tilde{x}|\,/\,(g^{\max}/2)$"); ax.set_ylabel("regulator-days")
    ax.legend(loc="upper right")
    save(fig, "fig_equal_split")


def fig_periods():
    f = OUT / "theorem4_period_blocks.csv"
    if not f.exists():
        return
    pe = pd.read_csv(f)
    pe = pe[(pe["case"] == "q_main") & (pe["user"] == "R-1") & (pe["volume"] == "V")]
    if pe.empty:
        return
    fig, ax = plt.subplots(figsize=(3.1, 2.3))
    for rule, col, lab in (("LXB-T050", C["orange"], r"pulse rule, $\theta = 0.5$"), ("LXB-CO", C["blue"], "carry-over")):
        g = pe[pe["rule"] == rule]
        if g.empty:
            continue
        s = g.assign(a=g["err_sat"].abs()).groupby("T")["a"].agg(["median", "max"])
        ax.plot(s.index, s["max"], color=col, lw=1.6, marker="o", ms=3.5, label=f"{lab}, largest")
        ax.plot(s.index, s["median"], color=col, lw=1.0, ls=":", marker="o", ms=2.5, label=f"{lab}, median")
    g = pe[pe["rule"] == "LXB-CO"]
    if not g.empty:
        b = g.groupby("T")["bound_block"].max()
        ax.plot(b.index, b, color=C["ink"], lw=0.8, ls="--", label=r"bound of the carry-over, $(1+\theta)\,p^{\max}/\sum D$")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel(r"accounting period $T$, days"); ax.set_ylabel(r"$|\sum V-\sum x|/\sum D$, regulator R-1")
    ax.legend(loc="lower left", fontsize=6)
    save(fig, "fig_periods")


def fig_april():
    runs = [("phys", "LXB", C["ink2"], "ideal execution"), ("q_main", "LXB", C["orange"], "floor rounding (LXB)"),
            ("q_main", "LXB-T050", C["blue"], r"pulse rule, $\theta = 0.5$"), ("q_main", "LXB-CO", C["aqua"], "carry-over")]
    have = [(c, m, col, lab) for c, m, col, lab in runs if not load(c, m, (2010,)).empty]
    if len(have) < 2:
        return
    fig, ax = plt.subplots(figsize=(3.1, 2.1))
    for c, m, col, lab in have:
        df = load(c, m, (2010,))
        d = df[(df["date"] >= "2010-04-01") & (df["date"] <= "2010-04-12")]
        ax.plot(d["date"].dt.day, d["r_R-1"], color=col, lw=1.6 if c != "phys" else 1.0,
                ls="-" if c != "phys" else "--", marker="o", ms=3, label=lab)
    ax.set_xlabel("day of April 2010"); ax.set_ylabel(r"satisfaction of R-1, $r$")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="lower right", fontsize=6)
    save(fig, "fig_april")


def fig_carryover():
    """Figure 5: (a) daily satisfaction of R-1 in 1-12 April 2010 under the rules; (b) accounting-period error of
    R-1 under the pulse rule with theta = 0.5 and under the carry-over."""
    f = OUT / "theorem4_period_blocks.csv"
    if not f.exists():
        return
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 2.5))
    runs = [("phys", "LXB", C["muted"], "ideal execution", "--"), ("q_main", "LXB", C["orange"], "floor rounding", "-"),
            ("q_main", "LXB-T050", C["blue"], r"pulse rule, $\theta = 0.5$", "-"), ("q_main", "LXB-CO", C["aqua"], "carry-over", "-")]
    for c, m, col, lab, ls in runs:
        df = load(c, m, (2010,))
        if df.empty:
            continue
        d = df[(df["date"] >= "2010-04-01") & (df["date"] <= "2010-04-12")]
        a1.plot(d["date"].dt.day, d["r_R-1"], color=col, lw=1.4 if ls == "-" else 1.0, ls=ls, marker="o", ms=2.5, label=lab)
    a1.set_xlabel("day of April 2010"); a1.set_ylabel(r"daily satisfaction of R-1, $r$")
    a1.set_ylim(-0.05, 1.3); a1.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    a1.legend(loc="upper center", ncol=2, fontsize=6)
    a1.set_title("(a)", loc="left", color=C["ink"])
    pe = pd.read_csv(f); pe = pe[(pe["case"] == "q_main") & (pe["user"] == "R-1") & (pe["volume"] == "V")]
    handles = []
    for rule, col, lab in (("LXB-T050", C["blue"], r"pulse rule, $\theta = 0.5$"), ("LXB-CO", C["aqua"], "carry-over")):
        g = pe[pe["rule"] == rule]
        if g.empty:
            continue
        st = g.assign(a=g["err_sat"].abs()).groupby("T")["a"].agg(["median", "max"])
        a2.plot(st.index, st["max"], color=col, lw=1.6, marker="o", ms=3)          # largest: solid
        a2.plot(st.index, st["median"], color=col, lw=1.0, ls=":", marker="o", ms=2.5)  # median: dotted
        handles.append(plt.Line2D([], [], color=col, lw=1.6, marker="o", ms=3, label=lab))
    g = pe[pe["rule"] == "LXB-CO"]
    if not g.empty:
        b = g.groupby("T")["bound_block"].max()
        a2.plot(b.index, b, color=C["ink"], lw=0.8, ls="--")
        handles.append(plt.Line2D([], [], color=C["ink"], lw=0.8, ls="--", label="bound of the carry-over"))
    handles += [plt.Line2D([], [], color=C["muted"], lw=1.6, label="largest"),
                plt.Line2D([], [], color=C["muted"], lw=1.0, ls=":", label="median")]
    a2.set_xscale("log"); a2.set_yscale("log")
    a2.set_xlabel(r"accounting period $T$, days"); a2.set_ylabel(r"$|\sum V-\sum x|/\sum D$, R-1")
    a2.set_ylim(1e-6, 1e1)                     # room for the legend below the curves
    a2.legend(handles=handles, loc="lower left", fontsize=6)
    a2.set_title("(b)", loc="left", color=C["ink"])
    fig.tight_layout()
    save(fig, "fig_carryover")


FIGURES = {"schematic": fig_schematic, "exclusion": fig_exclusion, "theta": fig_theta, "equal_split": fig_equal_split, "periods": fig_periods, "carryover": fig_carryover,
           "april": fig_april}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--figures", default=",".join(FIGURES))
    a = ap.parse_args()
    for name in a.figures.split(","):
        FIGURES[name]()


if __name__ == "__main__":
    main()
