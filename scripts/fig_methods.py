"""Figures of the Materials and Methods section (Figures 1–3), following the MDPI Water guidelines.

- no title inside the figure (the title is in the Word caption);
- width 13.9 cm (text width of the template; Figure 1: 17.4 cm), 600 dpi PNG and vector PDF;
- font Liberation Sans (Arial metrics), 7–8 pt; panels (a), (b);
- colours remain distinguishable for colour-blind readers (Okabe–Ito palette), and
  meaning does not rely on colour alone (line style, marker, label).
Usage: python scripts/fig_methods.py  ->  results/figures/Figure1..3.{png,pdf}
"""
import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon, Circle

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "figures")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    "font.family": ["Liberation Sans", "DejaVu Sans"], "font.size": 7.5, "mathtext.fontset": "dejavusans",
    "axes.linewidth": 0.6, "savefig.dpi": 600, "pdf.fonttype": 42,
})
W_IN = 13.9 / 2.54
INK, MUTED = "#1F2328", "#5A6270"
BLUE, ORANGE, GREEN, VERM, SKY, PURPLE = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7"
FILL = {"blue": "#E6F1F8", "orange": "#FDF3E1", "green": "#E3F4EE", "verm": "#FBE9E0", "grey": "#F2F3F5", "purple": "#F7EAF2"}


# reference number, in the article, of the study of the physical price (Zenodo 10.5281/zenodo.22706044); taken from
# the manuscript sources when they are present
REF_PHYSICAL_PRICE = "[39]"
try:
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import refs as _refs
    REF_PHYSICAL_PRICE = _refs.render("[@kudaybergenov2026b]")
except (ImportError, OSError):
    pass

BOXES = []  # (patch, [text artists]), used to check that text clears its box


def box(ax, x, y, w, h, text, edge=INK, fill="#FFFFFF", fs=7.2, bold=False, ls="-", lw=0.8, ha="center"):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                           fc=fill, ec=edge, lw=lw, ls=ls)
    ax.add_patch(patch)
    tx = x + w / 2 if ha == "center" else x + 0.12
    t = ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, color=INK,
                fontweight="bold" if bold else "normal", linespacing=1.3) if text else None
    BOXES.append((patch, [t] if t else []))
    return patch


def check_clearance(fig, min_mm=1.0):
    """Measure that every text lies at least min_mm inside its box; return the number of violations."""
    fig.canvas.draw(); r = fig.canvas.get_renderer(); px_mm = fig.dpi / 25.4
    bad = 0
    for patch, texts in BOXES:
        pb = patch.get_window_extent(r)
        for t in texts:
            tb = t.get_window_extent(r)
            gaps = [tb.x0 - pb.x0, pb.x1 - tb.x1, tb.y0 - pb.y0, pb.y1 - tb.y1]
            if min(gaps) < min_mm * px_mm:
                bad += 1
                print(f"  TOUCHING: {t.get_text()!r:.40} gaps (left, right, bottom, top) mm: "
                      + ", ".join(f"{g/px_mm:.2f}" for g in gaps))
    return bad


def arrow(ax, p, q, color=INK, lw=0.9, ls="-", rad=0.0, ms=7):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw,
                                 ls=ls, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))


def tag(ax, x, y, n, color=VERM):
    ax.add_patch(Circle((x, y), 0.17, fc=color, ec="none", zorder=5))
    ax.text(x, y, str(n), ha="center", va="center", color="white", fontsize=6.5, fontweight="bold", zorder=6)


def panel(ax, s, x=0.0, y=1.0):
    ax.text(x, y, s, transform=ax.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")


# --------------------------------------------------------------------------- Figure 1
W1_IN = 17.4 / 2.54          # Figure 1: full page width (same as the wide table of the template)
FS1, FS1S = 8.0, 7.5         # primary and secondary labels, pt (at print size)
F_IT = 7.5


def figure1():
    ua, ub = 7.4, 3.0                                   # panel heights (1 unit ≈ 1 cm)
    H = (ua + ub) / 17.4 * W1_IN
    fig = plt.figure(figsize=(W1_IN, H))
    axa = fig.add_axes([0.0, ub / (ua + ub), 1.0, ua / (ua + ub)]); axa.set_xlim(0, 17.4); axa.set_ylim(0, ua); axa.axis("off")
    axb = fig.add_axes([0.0, 0.0, 1.0, ub / (ua + ub)]); axb.set_xlim(0, 17.4); axb.set_ylim(0, ub); axb.axis("off")
    panel(axa, "(a)"); panel(axb, "(b)")
    y0, y1 = 3.75, 4.25                                 # pool (reach) walls
    ym = (y0 + y1) / 2

    # Dustlik main canal
    axa.add_patch(Rectangle((0.35, 1.3), 0.38, 5.2, fc=FILL["blue"], ec=BLUE, lw=0.8))
    axa.text(0.35, 6.75, "Dustlik main canal", ha="left", va="center", fontsize=FS1)
    arrow(axa, (0.54, 6.2), (0.54, 5.4), color=BLUE, lw=0.8, ms=7)
    # head regulator
    axa.add_patch(Rectangle((0.73, y0 - 0.05), 0.6, 0.6, fc="white", ec=INK, lw=0.9))
    for k in range(4):
        axa.plot([0.85 + k * 0.12] * 2, [y0 + 0.02, y1 - 0.02], color=INK, lw=0.6)
    axa.text(0.95, 5.35, "Kegeyli head regulator (Razvilka node, PK 245+00)\n4 gates 3.15 × 3.05 m; 160 m³ s⁻¹",
             ha="left", va="center", fontsize=FS1S, linespacing=1.3)
    axa.plot([1.03, 1.03], [y1 + 0.05, 4.95], color=MUTED, lw=0.5)
    # pilot pool
    x_in, x_out = 1.33, 11.3
    axa.add_patch(Rectangle((x_in, y0), x_out - x_in, y1 - y0, fc=FILL["blue"], ec=BLUE, lw=0.8))
    arrow(axa, (5.8, ym), (7.0, ym), color=BLUE, lw=0.9, ms=7)
    axa.text((x_in + x_out) / 2 + 0.6, 6.45, "Kegeyli canal: pilot pool PK 0+00–114+40, L = 11.44 km",
             ha="center", va="center", fontsize=8.5, fontweight="bold")
    # 20 small off-takes (both banks, unmetered)
    xs = [1.9 + k * (10.6 - 1.9) / 9 for k in range(10)]
    for k, x in enumerate(xs):
        for side in (1, -1):
            yb = y1 if side > 0 else y0
            gravity = (k, side) in ((3, 1), (7, -1))
            axa.add_patch(FancyArrowPatch((x, yb), (x + 0.12, yb + side * 0.42), arrowstyle="-|>", mutation_scale=5,
                                          color=MUTED, lw=0.7, ls=(0, (2, 1.2)) if gravity else "-", shrinkA=0, shrinkB=0))
    axa.text(6.3, 2.95, "20 small off-takes, PK 05–104 (18 pump-fed, 2 gravity):\n"
             "unmetered, represented by the delivery factor η = 0.82", ha="center", va="center", fontsize=FS1S,
             color=INK, linespacing=1.3)
    axa.text(6.3, 2.05, r"$b$ = 36 m, $m$ = 2, $S_0 = 1\times10^{-4}$;   "
             r"$H_{\max}$ / $H_{\mathrm{norm}}$ / $H_{\min}$ = 3.43 / 3.00 / 2.40 m",
             ha="center", va="center", fontsize=FS1S, color=MUTED)
    # Dustlik node
    nx0, nx1 = x_out, 12.55
    axa.add_patch(Rectangle((nx0, 1.6), nx1 - nx0, 4.95, fc=FILL["grey"], ec=INK, lw=0.8, ls=(0, (3, 2))))
    axa.text(nx0 - 0.15, 1.3, "Dustlik hydraulic node, PK 114+40", ha="right", va="center",
             fontsize=FS1, fontweight="bold")
    axa.plot([nx0 - 0.1, nx0 + 0.15], [1.3, 1.62], color=INK, lw=0.6)
    # barrier and lower Kegeyli
    axa.add_patch(Rectangle((nx1, y0 - 0.05), 0.2, 0.6, fc=INK, ec=INK))
    axa.add_patch(Rectangle((nx1 + 0.2, y0), 17.2 - nx1 - 0.2, y1 - y0, fc=FILL["blue"], ec=BLUE, lw=0.8))
    arrow(axa, (15.9, ym), (16.9, ym), color=BLUE, lw=0.9, ms=7)
    axa.text(13.1, 3.42, "j = 6: barrier → lower Kegeyli", ha="left", va="center", fontsize=FS1)
    axa.text(13.1, 3.0, "5 gates 8.0 × 2.5 m; 120 m³ s⁻¹", ha="left", va="center", fontsize=FS1S, color=MUTED)
    regs_u = [("j = 1: Abad-Yarmish, 48 m³ s⁻¹", 6.25), ("j = 2: R-1, 0.5 m³ s⁻¹", 5.7), ("j = 3: Khalkabad-2, 1.0 m³ s⁻¹", 5.15)]
    regs_d = [("j = 4: Kanly-Yab, 4.0 m³ s⁻¹", 2.45), ("j = 5: K-2, 2.0 m³ s⁻¹", 1.9)]
    for k, (nm, y) in enumerate(regs_u):
        x = 11.55 + 0.22 * k
        axa.plot([x, x], [y1, y], color=BLUE, lw=0.7); axa.plot([x, 12.75], [y, y], color=BLUE, lw=0.7)
        arrow(axa, (12.75, y), (13.0, y), color=BLUE, lw=0.7, ms=6)
        axa.text(13.1, y, nm, va="center", fontsize=FS1)
    for k, (nm, y) in enumerate(regs_d):
        x = 11.65 + 0.22 * k
        axa.plot([x, x], [y0, y], color=BLUE, lw=0.7); axa.plot([x, 12.75], [y, y], color=BLUE, lw=0.7)
        arrow(axa, (12.75, y), (13.0, y), color=BLUE, lw=0.7, ms=6)
        axa.text(13.1, y, nm, va="center", fontsize=FS1)
    axa.text(13.1, 1.05, "Σ outlet capacities = 175.5 m³ s⁻¹\n> 160 m³ s⁻¹ inflow capacity", fontsize=FS1S,
             color=VERM, va="center", linespacing=1.25)

    def gauge(x, y):
        axa.add_patch(Polygon([[x - 0.14, y], [x + 0.14, y], [x, y + 0.25]], closed=True, fc=ORANGE, ec=INK, lw=0.5, zorder=4))

    def sensor(x, y):
        axa.add_patch(Circle((x, y), 0.11, fc="white", ec=GREEN, lw=1.2, zorder=4))
    gauge(1.62, y1 + 0.02); gauge(10.95, y1 + 0.02); gauge(12.15, 6.25 + 0.02); gauge(16.2, y1 + 0.02)
    sensor(1.62, ym); sensor(10.95, ym); sensor(13.3, ym); sensor(0.54, 3.2)
    # legend
    ly = 0.3
    axa.add_patch(Polygon([[0.45, ly - 0.11], [0.73, ly - 0.11], [0.59, ly + 0.14]], closed=True, fc=ORANGE, ec=INK, lw=0.5))
    axa.text(0.9, ly, "gauge with daily records", va="center", fontsize=FS1S)
    axa.add_patch(Circle((4.05, ly), 0.11, fc="white", ec=GREEN, lw=1.2))
    axa.text(4.3, ly, "planned level sensor", va="center", fontsize=FS1S)
    axa.add_patch(FancyArrowPatch((7.55, ly - 0.15), (7.67, ly + 0.2), arrowstyle="-|>", mutation_scale=5, color=MUTED, lw=0.7))
    axa.text(7.85, ly, "small off-take (dashed: gravity)", va="center", fontsize=FS1S)
    axa.text(17.2, ly, "Not to scale", ha="right", va="center", fontsize=FS1S, color=MUTED, style="italic")

    # (b) evidence hierarchy
    cols = [("Passports (official)", "geometry, depth limits,\ncapacities, gates, areas", BLUE, FILL["blue"]),
            ("Operating records", "daily discharge 2010–2019;\n2020 node balance;\n2021 plan; line diagram", GREEN, FILL["green"]),
            ("Field map (KMZ)", "chainage and\ntopology check", ORANGE, FILL["orange"]),
            ("Model inputs", "labelled observed /\nderived / assumed", INK, FILL["grey"])]
    x0, w, gap = 0.35, 3.9, 0.36
    for k, (t, sub, ec, fc) in enumerate(cols):
        x = x0 + k * (w + gap)
        box(axb, x, 0.62, w, 2.0, "", edge=ec, fill=fc, lw=1.0 if k < 3 else 1.2)
        axb.text(x + w / 2, 2.25, t, ha="center", va="center", fontsize=FS1, fontweight="bold")
        axb.text(x + w / 2, 1.3, sub, ha="center", va="center", fontsize=FS1S, color=INK, linespacing=1.25)
        if k < 3:
            arrow(axb, (x + w + 0.03, 1.62), (x + w + gap - 0.03, 1.62), lw=0.9, ms=7)
    axb.text(8.7, 0.25, "Precedence in a conflict: passport > operating records > map; conflicting values are kept only as sensitivity cases.",
             ha="center", va="center", fontsize=FS1S, color=MUTED, style="italic")
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}/Figure1.{ext}", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


# --------------------------------------------------------------------------- Figure 2
def polyarrow(ax, pts, color=INK, lw=0.9, ls="-", ms=7):
    """Polyline with an arrowhead on the last segment."""
    xs, ys = zip(*pts)
    ax.plot(xs[:-1] + (xs[-1],), ys[:-1] + (ys[-1],), color=color, lw=lw, ls=ls, alpha=0)  # for axis limits
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls)
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw,
                                 ls=ls, shrinkA=0, shrinkB=0))


def figure2():
    BOXES.clear()
    Wc, Hc = 17.4, 8.7
    fig = plt.figure(figsize=(W1_IN, Hc / Wc * W1_IN))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, Wc); ax.set_ylim(0, Hc); ax.axis("off")
    F = FS1S
    # IoT constraint legend
    ax.text(0.25, 8.35, "IoT constraints:", fontsize=FS1, va="center", fontweight="bold")
    for n, t, x in [(1, "sensor error", 2.75), (2, "quantisation, deadband", 5.35),
                    (3, "packet budget, packet loss", 8.95), (4, "node energy reserve", 13.0)]:
        tag(ax, x, 8.35, n); ax.text(x + 0.3, 8.35, t, fontsize=F, va="center")
    # zones
    for x, w, lab in ((0.2, 7.45, "Field: Kegeyli pool and Dustlik node"), (7.85, 2.15, "LoRaWAN"),
                      (10.2, 7.0, "Server")):
        ax.add_patch(Rectangle((x, 0.2), w, 7.55, fc="#FAFBFC", ec="#C9CED6", lw=0.6, ls=(0, (3, 2))))
        ax.text(x + w / 2, 7.45, lab, ha="center", va="center", fontsize=F, color=MUTED, fontweight="bold")
    # field
    box(ax, 0.45, 3.0, 2.85, 2.5, "Hydraulic plant\n(Saint–Venant pool,\nhead regulator,\nbarrier and\n5 regulators)",
        edge=BLUE, fill=FILL["blue"], fs=F)
    box(ax, 4.05, 5.5, 3.3, 1.3, "Level sensors\nEM500-SWL", edge=GREEN, fill=FILL["green"], fs=F)
    box(ax, 4.05, 3.35, 3.3, 1.75, "UC300 RTU, wired probe\nlow-level closure 1.30 m;\nbarrier relief 3.43/3.33 m", edge=INK, fill="white", fs=F)
    box(ax, 4.05, 1.55, 3.3, 1.3, "Gate actuators\n(grid-powered)", edge=VERM, fill=FILL["verm"], fs=F)
    box(ax, 0.45, 0.5, 2.85, 1.55, "IoT node supply:\n100 W panel,\n962 Wh battery", edge=ORANGE, fill=FILL["orange"], fs=F)
    # gateway
    box(ax, 8.35, 3.85, 1.45, 1.25, "UG67\ngateway", edge=INK, fill="white", fs=F)
    # server
    est = box(ax, 10.45, 5.5, 3.0, 1.45, "", edge=INK, fill=FILL["grey"])
    t1 = ax.text(11.95, 6.47, "State estimator", ha="center", va="center", fontsize=F)
    t2 = ax.text(11.95, 5.92, r"$\hat h_L,\ \hat V_j$", ha="center", va="center", fontsize=F + 0.5)
    BOXES[-1] = (est, [t1, t2])
    box(ax, 13.9, 5.5, 2.65, 1.45, "Daily three-stage\nlexicographic\nplan", edge=PURPLE, fill=FILL["purple"], fs=F)
    box(ax, 13.9, 3.35, 2.65, 1.75, "15-min execution\nprogram (ID model);\nfirst step executed", edge=PURPLE, fill=FILL["purple"], fs=F)
    box(ax, 10.45, 3.35, 3.0, 1.75, "Discharges →\ngate openings\n(Equation (6))", edge=INK, fill=FILL["grey"], fs=F)
    kb = box(ax, 10.45, 0.45, 6.5, 2.35, "", edge=MUTED, fill="white", ls=(0, (2, 1.5)))
    tk = ax.text(10.7, 1.6, "Morning dispatcher report: today's supply " + r"$S(t)$" + ".\n"
                 "Known in advance: decadal limit " + r"$S^{\mathrm{lim}}$" + ",\n"
                 "demand " + r"$D_j[p]$" + ", passport data.\nNot known: supply of later days.", fontsize=F, va="center", ha="left", linespacing=1.45)
    BOXES[-1] = (kb, [tk])
    # signal path
    arrow(ax, (3.3, 4.9), (4.05, 5.85))                       # plant -> sensors
    arrow(ax, (5.7, 5.5), (5.7, 5.1))                         # sensors -> RTU
    arrow(ax, (7.35, 4.75), (8.35, 4.75))                      # RTU -> gateway (uplink)
    ax.text(7.83, 4.85, "uplink", ha="center", va="bottom", fontsize=6.5, color=MUTED)
    polyarrow(ax, [(9.8, 4.75), (10.1, 4.75), (10.1, 6.2), (10.45, 6.2)])   # gateway -> estimator
    arrow(ax, (13.45, 6.22), (13.9, 6.22))                    # estimator -> plan
    arrow(ax, (15.22, 5.5), (15.22, 5.1))                     # plan -> execution
    arrow(ax, (13.9, 4.22), (13.45, 4.22))                    # execution -> openings
    polyarrow(ax, [(10.45, 3.75), (10.1, 3.75), (10.1, 4.15), (9.8, 4.15)])    # openings -> gateway
    arrow(ax, (8.35, 4.15), (7.35, 4.15))                      # gateway -> RTU (downlink)
    ax.text(7.83, 4.05, "downlink", ha="center", va="top", fontsize=6.5, color=MUTED)
    arrow(ax, (5.7, 3.35), (5.7, 2.85))                       # RTU -> actuators
    arrow(ax, (4.05, 2.2), (3.3, 3.2))                        # actuators -> plant
    polyarrow(ax, [(16.95, 2.8), (16.95, 6.22), (16.55, 6.22)], color=MUTED, lw=0.8, ls=(0, (2, 1.5)))  # report -> plan
    # node energy (dashed)
    polyarrow(ax, [(3.3, 1.45), (3.7, 1.45), (3.7, 4.0), (4.05, 4.0)], color=ORANGE, lw=0.9, ls=(0, (2, 1.5)))
    polyarrow(ax, [(3.3, 0.95), (9.07, 0.95), (9.07, 3.85)], color=ORANGE, lw=0.9, ls=(0, (2, 1.5)))
    tag(ax, 7.35, 6.8, 1); tag(ax, 7.35, 2.85, 2); tag(ax, 9.8, 5.1, 3); tag(ax, 3.3, 2.05, 4)
    bad = check_clearance(fig)
    print(f"Figure2: number of texts touching their box = {bad}")
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}/Figure2.{ext}", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


# --------------------------------------------------------------------------- Figure 3
def figure3():
    BOXES.clear()
    Wc, Hc = 17.4, 7.9
    fig = plt.figure(figsize=(W1_IN, Hc / Wc * W1_IN))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, Wc); ax.set_ylim(0, Hc); ax.axis("off")
    ax.text(0.05, 7.85, "(a)", fontsize=9, fontweight="bold", va="top")
    ax.text(9.05, 7.85, "(b)", fontsize=9, fontweight="bold", va="top")
    ax.plot([8.85, 8.85], [0.3, 7.7], color="#C9CED6", lw=0.6)
    # (a) chain of satisfaction levels (schematic)
    ax.text(0.55, 7.3, "Schematic; levels and ordering are illustrative, not data.", fontsize=F_IT, color=MUTED,
            style="italic", va="center")
    levels = [(r"$\lambda^{\mathrm{stat}}$", "static plan,\nno hydraulics", 6.0, MUTED, FILL["grey"], ""),
              (r"$\lambda^{\mathrm{phys}}$", "plant,\nideal devices", 5.15, BLUE, FILL["blue"], "physical\nprice\n" + REF_PHYSICAL_PRICE),
              (r"$\lambda^{\mathrm{IoT}}$", "plant, IoT\nconstraints,\nfeedback", 4.35, GREEN, FILL["green"], "IoT\nprice " + r"$\Pi_1$"),
              (r"$\lambda^{\mathrm{IoT,open}}$", "plant, IoT\nconstraints,\nno feedback", 3.6, VERM, FILL["verm"], "open-\nloop\nprice")]
    xs = [0.55, 2.6, 4.65, 6.7]; wbar = 1.55; base = 2.15
    for i, ((lab, sub, h, ec, fc, ptxt), x) in enumerate(zip(levels, xs)):
        ax.add_patch(Rectangle((x, base), wbar, h - base, fc=fc, ec=ec, lw=1.0, ls="-" if i else (0, (3, 2))))
        ax.text(x + wbar / 2, h + 0.1, lab, ha="center", va="bottom", fontsize=9)
        ax.text(x + wbar / 2, base - 0.12, sub, ha="center", va="top", fontsize=FS1S, linespacing=1.2)
        if i:
            ref = levels[i - 1][2] if i < 3 else levels[1][2]
            xa = x - 0.25
            ax.annotate("", xy=(xa, h), xytext=(xa, ref),
                        arrowprops=dict(arrowstyle="-|>", color=ec, lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=8))
            ax.text(x + wbar / 2, h - 0.15, ptxt, ha="center", va="top", fontsize=FS1S, color=ec, linespacing=1.15)
    ax.plot([2.1, 6.7], [5.15, 5.15], color=MUTED, lw=0.6, ls=":")
    ax.plot([0.35, 8.5], [base, base], color=INK, lw=0.6)

    # (b) Shapley attribution over the 16 subsets of N = {S, Q, C, E}
    from itertools import combinations
    N = "SQCE"
    rows = [[""]] + [["".join(c) for c in combinations(N, k)] for k in range(1, 5)]
    cx, dx, y0, dy, bw, bh = 13.3, 1.18, 1.95, 1.18, 0.98, 0.58
    pos = {}
    for k, row in enumerate(rows):
        for m, F in enumerate(row):
            pos[F] = (cx + (m - (len(row) - 1) / 2) * dx, y0 + k * dy)
    for F, (x, y) in pos.items():                              # Hasse diagram edges
        for e in N:
            if e not in F:
                G = "".join(c for c in N if c in F + e)
                x2, y2 = pos[G]
                hi = e == "Q"
                ax.plot([x, x2], [y + bh / 2, y2 - bh / 2], color=BLUE if hi else "#B8BEC7",
                        lw=1.1 if hi else 0.5, zorder=1)
    for F, (x, y) in pos.items():
        lab = "∅" if F == "" else ("N" if F == N else F)
        box(ax, x - bw / 2, y - bh / 2, bw, bh, lab, edge=INK, fill="white", fs=FS1S)
    ax.text(pos[""][0] + 0.65, pos[""][1], r"phys run: $v(\varnothing)=0$", fontsize=FS1S, va="center")
    ax.text(pos[N][0] + 0.65, pos[N][1], r"IoT run: $v(N)=\Pi_1$", fontsize=FS1S, va="center")
    ax.text(9.25, 7.35, r"$v(F)$: mean daily $\Pi_1$ with only the constraints in $F$ active", fontsize=FS1S, va="center")
    ax.plot([9.3, 9.75], [1.12, 1.12], color=BLUE, lw=1.1)
    ax.text(9.85, 1.12, r"adds $Q$: marginal contribution $v(F\cup\{Q\})-v(F)$, averaged into $\phi_Q$",
            fontsize=FS1S, va="center")
    ax.text(9.25, 0.42, r"$\phi_i=\sum_{F\subseteq N\setminus\{i\}}\dfrac{|F|!\,(3-|F|)!}{4!}\,[v(F\cup\{i\})-v(F)]$,"
            r"$\quad \sum_i\phi_i=\Pi_1$", fontsize=FS1S, va="center")
    bad = check_clearance(fig)
    print(f"Figure3: number of texts touching their box = {bad}")
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}/Figure3.{ext}", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


if __name__ == "__main__":
    figure1(); figure2(); figure3()
    print("Figure1–3 -> results/figures/")
