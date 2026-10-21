"""Figures of the Results section (Figures 4–6), following the MDPI Water guidelines (same style as fig_methods.py).

Figure 4: daily worst-user satisfaction λ, phys → IoT, six methods (tuned, untuned, 2011 + 2018).
Figure 5: IoT price of LXB: daily λ_phys and λ_IoT; Shapley contributions by year; satisfaction by user
          (IoT).
Figure 6: descriptive sensitivity (14 cases): LXB λ_IoT, Π1, LXB − B0 and LXB − B3.
Data: results/experiment/normal/*.csv, results/tables/shapley_ratio_of_means.csv, results/sensitivity_summary.csv.
Usage: python scripts/fig_results.py [ROOT]  ->  results/figures/Figure4..6.{png,pdf}
"""
import glob
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = os.path.join(ROOT, "results", "figures")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    "font.family": ["Liberation Sans", "DejaVu Sans"], "font.size": 7.5, "mathtext.fontset": "dejavusans",
    "axes.linewidth": 0.6, "savefig.dpi": 600, "pdf.fonttype": 42, "axes.spines.top": False,
    "axes.spines.right": False, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.labelcolor": "#1F2328",
    "xtick.color": "#1F2328", "ytick.color": "#1F2328", "legend.frameon": False,
})
W = 17.4 / 2.54
INK, MUTED, GRID = "#1F2328", "#5A6270", "#E4E7EB"
BLUE, ORANGE, GREEN, VERM, PURPLE, SKY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"
METHODS = ["Oracle", "LXB", "B2", "B3", "B0", "B1"]
USERS = ["Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli"]


def load():
    frames = []
    for f in glob.glob(os.path.join(ROOT, "results/experiment/normal/*_20??_*_*.csv")):
        m, y, t, v = os.path.basename(f)[:-4].split("_")
        if m in METHODS and v in ("phys", "iot"):
            frames.append(pd.read_csv(f))
    d = pd.concat(frames, ignore_index=True)
    assert d.groupby(["method", "tuned", "iot"]).size().eq(1830).all() and len(d) == 6 * 4 * 1830
    return d


def grid(ax, axis="x"):
    ax.grid(axis=axis, color=GRID, lw=0.5); ax.set_axisbelow(True)


def panel(ax, s, x=-0.02, y=1.02):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=8.5, fontweight="bold", ha="right", va="bottom", color=INK)


def fig4(d):
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.35), sharey=True, gridspec_kw={"wspace": 0.12})
    sets = [("(a)", "Tuned, 2010–2019", (d.tuned == "tuned")),
            ("(b)", "Untuned, 2010–2019", (d.tuned == "untuned")),
            ("(c)", "Tuned, 2011 and 2018", (d.tuned == "tuned") & d.year.isin([2011, 2018]))]
    ys = np.arange(len(METHODS))[::-1]
    for ax, (lab, title, sel) in zip(axes, sets):
        g = d[sel].groupby(["method", "iot"])["lambda"].mean().unstack()
        for yv, m in zip(ys, METHODS):
            p, q = g.loc[m, "phys"], g.loc[m, "iot"]
            ax.plot([q, p], [yv, yv], color="#9AA3AE", lw=1.2, solid_capstyle="butt", zorder=1)
            ax.scatter([p], [yv], s=26, color=INK, zorder=3, linewidths=0)
            ax.scatter([q], [yv], s=26, facecolor="white", edgecolor=BLUE, linewidths=1.2, zorder=4,
                       marker="D")
            ax.text(max(q - 0.015 if q < p - 0.06 else q + 0.015, 0.06), yv + 0.27, f"{q:.2f}", ha="center",
                    va="bottom", fontsize=6.3, color=MUTED)
        ax.set_xlim(0, 0.9); ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8]); grid(ax)
        ax.set_title(title, fontsize=7.5, color=INK, pad=3, loc="left")
        ax.set_xlabel(r"Mean daily $\lambda$")
        panel(ax, lab, x=-0.03)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(ys); axes[0].set_yticklabels(METHODS); axes[0].set_ylim(-0.6, len(METHODS) - 0.3)
    h1 = axes[0].scatter([], [], s=26, color=INK, label="phys (ideal sensing, actuation, communication)")
    h2 = axes[0].scatter([], [], s=26, facecolor="white", edgecolor=BLUE, linewidths=1.2, marker="D",
                         label="IoT (sensor error, quantisation and deadband, packet budget and loss, energy)")
    fig.legend(handles=[h1, h2], loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.02), fontsize=7)
    fig.subplots_adjust(left=0.07, right=0.995, top=0.9, bottom=0.31)
    save(fig, "Figure4")


def fig5(d):
    fig = plt.figure(figsize=(W, 2.55))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.15, 1.0], wspace=0.55)
    # (a) daily λ_phys and λ_IoT, LXB tuned
    ax = fig.add_subplot(gs[0])
    t = d[(d.method == "LXB") & (d.tuned == "tuned")]
    x = pd.DataFrame({"p": t[t.iot == "phys"].set_index(["year", "date"])["lambda"],
                      "i": t[t.iot == "iot"].set_index(["year", "date"])["lambda"]})
    early = pd.Series(x.index.get_level_values(1).str[5:], index=x.index).between("04-01", "04-10")
    ax.plot([0, 1], [0, 1], color="#9AA3AE", lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.scatter(x.p[~early], x.i[~early], s=5, color=BLUE, alpha=0.45, linewidths=0, zorder=2,
               label="other days")
    ax.scatter(x.p[early], x.i[early], s=11, facecolor="white", edgecolor=VERM, linewidths=0.8, marker="s",
               zorder=3, label="1–10 April")
    n0 = int(((x.p > 0.999) & (x.i < 0.01)).sum())
    ax.annotate(f"{n0} days: " + r"$\lambda^{\mathrm{phys}}>0.999$," + "\n" + r"$\lambda^{\mathrm{IoT}}<0.01$",
                xy=(0.985, 0.02), xytext=(0.36, 0.16),
                fontsize=6.3, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    ax.set_xlim(-0.02, 1.03); ax.set_ylim(-0.02, 1.03)
    ax.set_xlabel(r"$\lambda^{\mathrm{phys}}$ (daily)"); ax.set_ylabel(r"$\lambda^{\mathrm{IoT}}$ (daily)")
    ax.legend(loc="upper left", fontsize=6.3, handletextpad=0.2, borderaxespad=0.1)
    grid(ax, "both"); panel(ax, "(a)", x=-0.18)
    # (b) Shapley contributions by year
    ax = fig.add_subplot(gs[1])
    # attribution of the ratio-of-means price of each season (make_results_tables.py); the mean-daily attribution
    # of H7b is dominated by single days with a near-zero lambda_phys (Section 3.3)
    s = pd.read_csv(os.path.join(ROOT, "results/tables/shapley_ratio_of_means.csv"))
    s = s[s.season != "all"].assign(year=lambda t: t.season.astype(int))
    yrs = s.year.to_numpy(); xi = np.arange(len(yrs)); w = 0.26
    e_zero = bool((s.phi_energy.abs() < 1e-12).all())
    series = [("phi_quantisation", BLUE, r"$\phi_Q$ quantisation, deadband"),
              ("phi_sensor", ORANGE, r"$\phi_S$ sensor"),
              ("phi_communication", GREEN, r"$\phi_C$ communication")]
    if not e_zero:
        series.append(("phi_energy", MUTED, r"$\phi_E$ energy"))
    w = 0.78 / len(series)
    for k, (col, c, lab) in enumerate(series):
        ax.bar(xi + (k - (len(series) - 1) / 2) * w, s[col] * 100, width=w - 0.04, color=c, label=lab, linewidth=0)
    vals = np.concatenate([s[col].to_numpy() * 100 for col, _, _ in series])
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xticks(xi); ax.set_xticklabels([str(y)[2:] for y in yrs]); ax.set_xlabel("Season (20xx)")
    ax.set_ylabel(r"Shapley value, pp of $\Pi_1$ (ratio of means)")
    lo, hi = min(vals.min(), 0.0), max(vals.max(), 0.0)
    ax.set_ylim(lo - 0.1 * (hi - lo) - 0.5, hi + 0.35 * (hi - lo) + 0.5)    # room for the legend
    ax.legend(loc="upper left", fontsize=6.3, handlelength=1.0, borderaxespad=0.2)
    if e_zero:
        ax.text(0.98, 0.70, "$\\phi_E$ = 0\nin every season", transform=ax.transAxes, ha="right", va="bottom",
                fontsize=6.3, color=MUTED)
    grid(ax, "y"); panel(ax, "(b)", x=-0.14)
    # (c) satisfaction by user, IoT tuned
    ax = fig.add_subplot(gs[2])
    q = d[(d.tuned == "tuned") & (d.iot == "iot")]
    ys = np.arange(len(USERS))[::-1]
    for m, c, mk in [("LXB", BLUE, "D"), ("B0", VERM, "o"), ("B3", ORANGE, "s")]:
        r = q[q.method == m][[f"r_{u}" for u in USERS]].mean().to_numpy()
        ax.scatter(r, ys, s=22, color=c, marker=mk, label=m, zorder=3, linewidths=0)
    ax.set_yticks(ys); ax.set_yticklabels(USERS); ax.set_xlim(0, 1.0); ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "0.25", "0.5", "0.75", "1"])
    ax.set_xlabel("Mean satisfaction $r_j$ (IoT chain)"); ax.tick_params(axis="y", length=0)
    ax.legend(loc="center left", bbox_to_anchor=(0.02, 0.45), fontsize=6.3, handletextpad=0.1, borderaxespad=0.1)
    grid(ax, "x"); panel(ax, "(c)", x=-0.62)
    fig.subplots_adjust(left=0.065, right=0.98, top=0.94, bottom=0.17)
    save(fig, "Figure5")


# (label, case); the baseline case label is written by summarize_sensitivity.py
CASES = [("Baseline", "normal (deadband_low seasons)"), ("Intraday supply ramp (6 h)", "supply_ramp"),
         ("2021 limit as forecast", "limit_2021"), ("Demand by area (B)", "demand_area"),
         ("Demand by capacity (C)", "demand_capacity"), (r"$\eta$ = 0.75", "eta_low"),
         (r"$\eta$ = 0.92", "eta_high"), ("Design geometry", "design_geometry"),
         ("Deadband 0.25%", "deadband_low"), ("Deadband 1%", "deadband_high"),
         ("Solar kit 30 W / 481 Wh", "energy_moderate"), ("Solar kit 20 W", "energy_severe"),
         ("Packet loss 10%", "communication_loss"),
         ("Budget 2 packets/h", "communication_budget_2"), ("Budget 1 packet/h", "communication_budget_1"),
         (r"$\eta$ = 0.75, demand fixed", "eta_fixed_demand_low"),
         (r"Plant $\eta$ 0.75, controller 0.82", "eta_true_low"),
         ("Outlet ratings 0.90–1.10", "rating_outlets"), ("Tail water +0.3 m", "tailwater_high"),
         ("Sensor offset +25 mm", "sensor_bias_pos"), ("Sensor offset −25 mm", "sensor_bias_neg")]


def fig6():
    t = pd.read_csv(os.path.join(ROOT, "results/sensitivity_summary.csv"))
    lx = t[t.method == "LXB"].set_index("case")
    rows = [(lab, lx.loc[c]) for lab, c in CASES if c in lx.index]
    assert all(r.years == 10 for _, r in rows)
    fig, axes = plt.subplots(1, 3, figsize=(W, 0.6 + 0.153 * len(rows)), sharey=True, gridspec_kw={"wspace": 0.1,
                                                                               "width_ratios": [1, 1, 1.25]})
    ys = np.arange(len(rows))[::-1]
    base = rows[0][1]
    specs = [("(a)", r"LXB mean daily $\lambda^{\mathrm{IoT}}$", lambda r: [r.lam_iot], [INK], ["o"], (0.6, 0.85)),
             ("(b)", r"IoT price $\Pi_1$ (ratio of means), %", lambda r: [100 * r.pi1_ratio], [INK], ["o"], (0, 24)),
             ("(c)", r"Advantage in mean daily $\lambda^{\mathrm{IoT}}$",
              lambda r: [r.d_B0_iot, r.d_B3_iot], [VERM, ORANGE], ["o", "s"], (0, 0.8))]
    for ax, (lab, xl, f, cols, mks, lim) in zip(axes, specs):
        ref = f(base)
        for v, c in zip(ref, cols):
            ax.axvline(v, color=c, lw=0.6, ls=(0, (3, 2)), alpha=0.8, zorder=1)
        for yv, (name, r) in zip(ys, rows):
            for v, c, mk in zip(f(r), cols, mks):
                ax.scatter([v], [yv], s=20, color=c, marker=mk, zorder=3, linewidths=0)
        allv = np.array([v for _, r in rows for v in f(r)] + list(ref), float)
        allv = allv[np.isfinite(allv)]
        lo_, hi_ = min(lim[0], allv.min()), max(lim[1], allv.max())          # never clip a value
        pad = 0.03 * (hi_ - lo_)
        ax.set_xlim(lo_ - (pad if lo_ < lim[0] else 0), hi_ + (pad if hi_ > lim[1] else 0)); ax.set_xlabel(xl); grid(ax); ax.tick_params(axis="y", length=0)
        panel(ax, lab, x=-0.02 if lab != "(a)" else -0.02)
    axes[2].scatter([], [], s=20, color=VERM, marker="o", label="LXB − B0")
    axes[2].scatter([], [], s=20, color=ORANGE, marker="s", label="LXB − B3")
    axes[2].legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, fontsize=6.5, handletextpad=0.1,
                   borderaxespad=0.2)
    axes[0].set_yticks(ys); axes[0].set_yticklabels([n for n, _ in rows])
    axes[0].set_ylim(-0.7, len(rows) - 0.3)
    for ax in axes:
        ax.axhspan(len(rows) - 1.5, len(rows) - 0.5, color="#F2F3F5", zorder=0, lw=0)
    fig.subplots_adjust(left=0.2, right=0.99, top=1 - 0.26 / (0.6 + 0.153 * len(rows)),
                        bottom=0.44 / (0.6 + 0.153 * len(rows)))
    save(fig, "Figure6")


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"))
    plt.close(fig)
    print(f"-> {OUT}/{name}.png/.pdf")


if __name__ == "__main__":
    data = load()
    fig4(data); fig5(data); fig6()
