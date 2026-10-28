"""Gate and rules: step volumes of a regulator and the execution rules of Section 2.4 on one day and over several days
(Theorems 1, 3 and 4 at a constant level)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np

from .. import theory as th
from ..i18n import tr
from ..datasets import REGULATORS
from ..widgets import MUTED, PAD, PALETTE, PlotPanel, ScrollFrame, Tooltip, style_axes

SCEN_LABELS = {"normal": "Baseline (deadband 0.5%, k = 5)", "deadband_low": "Deadband 0.25% (k = 3)",
               "deadband_high": "Deadband 1% (k = 10)", "gate_cd_low": "Gate coefficient -20%",
               "gate_cd_high": "Gate coefficient +20%"}


def _number(value, default, low, high):
    """A stored setting as a number within [low, high], or the default."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return min(high, max(low, v))


class TheoryTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.loaded = False
        self.sv = None
        self._job = None
        state = app.settings.get("theory", {}) or {}

        scroll = ScrollFrame(self)
        scroll.pack(side="left", fill="y", padx=(0, PAD))
        left = ttk.Frame(scroll.inner, padding=(0, 0, PAD, 0))
        left.pack(fill="both", expand=True)
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        form = ttk.Labelframe(left, text=tr("Gate"), padding=PAD * 2)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text=tr("Scenario")).grid(row=0, column=0, sticky="w", pady=3)
        self.scen_var = tk.StringVar(value=tr(SCEN_LABELS.get(state.get("scenario"), SCEN_LABELS["normal"])))
        box = ttk.Combobox(form, textvariable=self.scen_var, state="readonly", width=30,
                           values=[tr(SCEN_LABELS[s]) for s in th.SCENARIOS])
        box.grid(row=0, column=1, sticky="ew", pady=3)
        box.bind("<<ComboboxSelected>>", lambda e: self.recompute_volumes())
        ttk.Label(form, text=tr("Regulator")).grid(row=1, column=0, sticky="w", pady=3)
        self.user_var = tk.StringVar(value=state.get("user") if state.get("user") in REGULATORS else "R-1")
        ubox = ttk.Combobox(form, textvariable=self.user_var, state="readonly", width=30, values=list(REGULATORS))
        ubox.grid(row=1, column=1, sticky="ew", pady=3)
        ubox.bind("<<ComboboxSelected>>", lambda e: self.schedule())
        ttk.Label(form, text=tr("Level h, m")).grid(row=2, column=0, sticky="w", pady=3)
        self.h_var = tk.DoubleVar(value=_number(state.get("h"), 3.00, 2.40, 3.23))
        hrow = ttk.Frame(form)
        hrow.grid(row=2, column=1, sticky="ew")
        ttk.Scale(hrow, from_=2.40, to=3.23, variable=self.h_var, command=lambda v: self._h_moved()).pack(
            side="left", fill="x", expand=True)
        self.h_label = ttk.Label(hrow, text="", width=6)
        self.h_label.pack(side="left", padx=(PAD, 0))
        Tooltip(hrow, tr("Operating range of the node level: 2.40 m (passport minimum) to 3.23 m (relief level less "
                         "the freeboard)."))

        rule = ttk.Labelframe(left, text=tr("Plan and rule"), padding=PAD * 2)
        rule.pack(fill="x", pady=(PAD, 0))
        rule.columnconfigure(1, weight=1)
        ttk.Label(rule, text=tr("Daily plan x, m³")).grid(row=0, column=0, sticky="w", pady=3)
        self.x_var = tk.StringVar(value=str(state.get("x", 21.7)))
        e = ttk.Entry(rule, textvariable=self.x_var, width=12)
        e.grid(row=0, column=1, sticky="w", pady=3)
        e.bind("<Return>", lambda ev: self.schedule())
        e.bind("<FocusOut>", lambda ev: self.schedule())
        self.x_units = ttk.Label(rule, text="", style="Sub.TLabel")
        self.x_units.grid(row=1, column=1, sticky="w")
        quick = ttk.Frame(rule)
        quick.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 4))
        for label, value in (("21.7", 21.7), ("0.5 q", "0.5q"), ("1 q", "1q"), ("2.3 q", "2.3q"), ("10 q", "10q")):
            ttk.Button(quick, text=label, width=6, command=lambda v=value: self.set_plan(v)).pack(side="left", padx=1)
        ttk.Label(rule, text=tr("Threshold θ")).grid(row=3, column=0, sticky="w", pady=3)
        self.theta_var = tk.DoubleVar(value=_number(state.get("theta"), 0.5, 0.0, 1.0))
        trow = ttk.Frame(rule)
        trow.grid(row=3, column=1, sticky="ew")
        ttk.Scale(trow, from_=0.0, to=1.0, variable=self.theta_var, command=lambda v: self._theta_moved()).pack(
            side="left", fill="x", expand=True)
        self.theta_label = ttk.Label(trow, text="", width=5)
        self.theta_label.pack(side="left", padx=(PAD, 0))
        ttk.Label(rule, text=tr("Days (carry-over)")).grid(row=4, column=0, sticky="w", pady=3)
        self.days_var = tk.IntVar(value=int(_number(state.get("days"), 30, 5, 120)))
        sp = ttk.Spinbox(rule, from_=5, to=120, textvariable=self.days_var, width=6, command=self.schedule)
        sp.grid(row=4, column=1, sticky="w", pady=3)
        sp.bind("<Return>", lambda ev: self.schedule())

        res = ttk.Labelframe(left, text=tr("Outcome"), padding=PAD * 2)
        res.pack(fill="x", pady=(PAD, 0))
        self.out = ttk.Frame(res)
        self.out.pack(fill="both", expand=True)

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self.plot_day = PlotPanel(self.nb, figsize=(8, 5))
        self.nb.add(self.plot_day, text=tr("One day: delivery against plan"))
        self.plot_days = PlotPanel(self.nb, figsize=(8, 5))
        self.nb.add(self.plot_days, text=tr("Several days: carry-over"))
        self._h_moved(schedule=False)
        self._theta_moved(schedule=False)

    # ---------------------------------------------------------------- state
    def on_show(self):
        if not self.loaded:
            self.loaded = True
            self.recompute_volumes()

    def refresh(self):
        self.recompute_volumes()

    def save_state(self, settings):
        settings["theory"] = {"scenario": self._scenario(), "user": self.user_var.get(),
                              "h": round(self.h_var.get(), 2), "x": self.x_var.get(),
                              "theta": round(self.theta_var.get(), 2), "days": self.days_var.get()}

    def _scenario(self):
        label = self.scen_var.get()
        return next((s for s in th.SCENARIOS if tr(SCEN_LABELS[s]) == label), "normal")

    def _h_moved(self, schedule=True):
        h = round(self.h_var.get(), 2)
        self.h_label.configure(text=f"{h:.2f}")
        if schedule:
            self._schedule_volumes()

    def _theta_moved(self, schedule=True):
        t = round(self.theta_var.get() * 20) / 20
        self.theta_label.configure(text=f"{t:.2f}")
        if schedule:
            self.schedule()

    def _schedule_volumes(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.recompute_volumes)

    def schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(150, self.compute)

    def set_plan(self, value):
        if isinstance(value, str) and value.endswith("q") and self.sv is not None:
            j = self._user_index()
            value = round(float(value[:-1]) * float(self.sv["q"][j]), 1)
        self.x_var.set(str(value))
        self.schedule()

    def _user_index(self):
        return list(REGULATORS).index(self.user_var.get())

    # ---------------------------------------------------------------- computation
    def recompute_volumes(self):
        scen, h = self._scenario(), round(self.h_var.get(), 2)
        self.app.background(lambda: th.step_volumes(scen, h), self._volumes_ready, busy_text=tr("Computing…"))

    def _volumes_ready(self, sv):
        self.sv = sv
        self.compute()

    def compute(self):
        self._job = None
        if self.sv is None:
            return
        try:
            x = float(self.x_var.get().replace(",", "."))
            if x < 0:
                raise ValueError
        except ValueError:
            self.x_units.configure(text=tr("Enter a non-negative number"), style="Bad.TLabel")
            return
        sv, j = self.sv, self._user_index()
        v, q, p, C = float(sv["v"][j]), float(sv["q"][j]), float(sv["p"][j]), float(sv["C"][j])
        k, N = int(sv["k"]), int(sv["N"])
        theta = round(self.theta_var.get() * 20) / 20
        try:
            days = max(5, min(120, int(self.days_var.get() or 30)))
        except (tk.TclError, ValueError):
            days = 30
        self.x_units.configure(text=f"= {x / q:.3f} q = {x / p:.3f} p", style="Sub.TLabel")
        r = th.day_rules(x, v, k, theta, N, C)
        self._show_outcome(r, sv, j)
        curves = th.delivery_curves(v, k, theta, N, C, max(3.0 * q, 1.25 * x))
        self._draw_day(r, curves)
        co = th.carry_over_days([x] * days, v, k, theta, N)
        self._draw_days(co, x)

    def _show_outcome(self, r, sv, j):
        for w in self.out.winfo_children():
            w.destroy()
        m3 = tr("m³")
        rows = [
            (tr("Deadband"), f"k = {r['k']} {tr('resolution steps')}"),
            (tr("One resolution step v"), f"{r['v']:.2f} {m3}"),
            (tr("Quantum q = k v"), f"{r['q']:.2f} {m3}"),
            (tr("Pulse p = (k+1) v"), f"{r['p']:.2f} {m3}"),
            (tr("One full step C"), f"{r['C']:,.0f} {m3}"),
            (tr("Exclusion threshold (1 − 1/(2k)) q"), f"{r['threshold']:.2f} {m3}"),
            (tr("Daily pulse capacity N p"), f"{r['pulse_capacity']:,.0f} {m3}"),
        ]
        line = 0
        for k, v in rows:
            ttk.Label(self.out, text=k, style="Sub.TLabel").grid(row=line, column=0, sticky="w")
            ttk.Label(self.out, text=v).grid(row=line, column=1, sticky="e", padx=(PAD, 0))
            line += 1
        ttk.Separator(self.out).grid(row=line, column=0, columnspan=2, sticky="ew", pady=PAD)
        line += 1
        x = r["x"]

        def put(label, value, ok=None, note=""):
            nonlocal line
            ttk.Label(self.out, text=label, style="Bold.TLabel").grid(row=line, column=0, sticky="w")
            style = "TLabel" if ok is None else ("Ok.TLabel" if ok else "Bad.TLabel")
            ttk.Label(self.out, text=value, style=style).grid(row=line, column=1, sticky="e", padx=(PAD, 0))
            line += 1
            if note:
                ttk.Label(self.out, text=note, style="Muted.TLabel", wraplength=340, justify="left").grid(
                    row=line, column=0, columnspan=2, sticky="w")
                line += 1

        excluded = x > 0 and r["direct"] <= 1e-9
        put(tr("Direct execution"), f"V = {r['direct']:.1f} {m3}", ok=not excluded,
            note=(tr("Excluded: the plan is below the threshold of Theorem 1(a).") if r["excluded_predicted"]
                  else (tr("No water although the plan is above the threshold (the condition is sufficient only).")
                        if excluded else "")))
        if r["pulse"] is not None:
            put(tr("Pulse rule") + f", θ = {r['theta']:.2f}",
                f"V = {r['pulse']:.1f} {m3} · " + tr("pulses") + f": {r['pulses']}",
                ok=bool(r["pulse_ok"]),
                note=f"{tr('Bounds (14)')}: {r['pulse_lower']:.1f} ≤ V < {r['pulse_upper']:.1f}")
        else:
            put(tr("Pulse rule"), tr("not in the pulse regime"),
                note=tr("The plan is at least the daily pulse capacity."))
        if r["equal"] is not None:
            put(tr("Equal split") + f", m = {r['m']}", f"V = {r['equal']:.1f} {m3}", ok=bool(r["equal_ok"]),
                note=f"|V − x| = {abs(r['equal'] - x):.2f} ≤ v/2 = {r['v'] / 2:.2f}")
        else:
            put(tr("Equal split"), tr("not applicable"),
                note=tr("Theorem 1(b) needs q ≤ x ≤ ⌈N/2⌉ (C − v) and C ≥ 2q + 3v; smaller plans are served by "
                        "pulses."))

    def _draw_day(self, r, c):
        fig = self.plot_day.figure
        fig.clear()
        ax = fig.add_subplot(111)
        q = r["q"]
        xs = c["x"] / q
        ax.plot(xs, xs, color=MUTED, linewidth=1, linestyle="--", label=tr("plan, V = x"))
        ax.plot(xs, c["direct"] / q, color=PALETTE[0], linewidth=1.8, label=tr("direct execution"))
        ax.plot(xs, c["pulse"] / q, color=PALETTE[1], linewidth=1.8, label=tr("pulse rule") + f", θ = {r['theta']:.2f}")
        ax.plot(xs, c["equal"] / q, color=PALETTE[2], linewidth=1.8, label=tr("equal split"))
        thr = r["threshold"] / q
        ax.axvline(thr, color=MUTED, linewidth=1, linestyle=":")
        ax.annotate("1 − 1/(2k)", (thr, ax.get_ylim()[1] * 0.92), fontsize=8, color="#52514e", ha="right",
                    xytext=(-4, 0), textcoords="offset points")
        x = r["x"] / q
        for value, colour in ((r["direct"], PALETTE[0]), (r["pulse"], PALETTE[1]), (r["equal"], PALETTE[2])):
            if value is not None:
                ax.plot([x], [value / q], marker="o", markersize=8, color=colour, markeredgecolor="white",
                        markeredgewidth=1.5, zorder=5)
        ax.legend(loc="lower right", fontsize=9, frameon=False)
        style_axes(ax, xlabel=tr("Daily plan x / q"), ylabel=tr("Delivered volume V / q"),
                   title=tr("One day at a constant level") + f" (N = {r['N']}, k = {r['k']})")
        self.plot_day.draw()

    def _draw_days(self, co, x):
        fig = self.plot_days.figure
        fig.clear()
        a1, a2 = fig.subplots(2, 1, sharex=True)
        days = np.arange(1, len(co["plan"]) + 1)
        w = 0.4
        a1.bar(days - w / 2, co["V_pulse"], width=w, color=PALETTE[1], label=tr("pulse rule"))
        a1.bar(days + w / 2, co["V_carry"], width=w, color=PALETTE[0], label=tr("carry-over"))
        a1.axhline(x, color=MUTED, linestyle="--", linewidth=1, label=tr("plan x"))
        top = max(float(np.nanmax(co["V_pulse"])), float(np.nanmax(co["V_carry"])), x, 1e-9)
        a1.set_ylim(0, top * 1.4)                       # room for the legend above the bars
        a1.legend(loc="upper right", fontsize=8, frameon=False, ncols=3)
        style_axes(a1, ylabel=tr("Delivered volume, m³"), title=tr("Pulse rule with and without carry-over"))
        cum_pulse = np.cumsum(co["plan"] - co["V_pulse"])
        a2.plot(days, co["debt"], color=PALETTE[0], marker="o", markersize=4, linewidth=1.6,
                label=tr("debt e(s), carry-over"))
        a2.plot(days, cum_pulse, color=PALETTE[1], linewidth=1.4, label=tr("cumulative error, pulse rule"))
        a2.axhline(co["upper"], color=MUTED, linestyle="--", linewidth=1)
        a2.axhline(co["lower"], color=MUTED, linestyle="--", linewidth=1)
        a2.annotate("θ p", (days[-1], co["upper"]), fontsize=8, color="#52514e", xytext=(4, 0),
                    textcoords="offset points", va="center")
        a2.annotate("−p", (days[-1], co["lower"]), fontsize=8, color="#52514e", xytext=(4, 0),
                    textcoords="offset points", va="center")
        a2.legend(loc="lower left", fontsize=8, frameon=False)
        style_axes(a2, xlabel=tr("Day"), ylabel=tr("Plan − delivery, m³"))
        self.plot_days.draw()
