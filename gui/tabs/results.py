"""Results: the stored daily results of the closed loop, plotted and summarised by case, rule, season and outlet."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd

from .. import datasets as ds
from ..i18n import tr
from ..project import CASE_LABELS, RULE_LABELS, available_cases, available_methods, available_years
from ..widgets import PAD, PALETTE, MUTED, DataTable, PlotPanel, style_axes

QUANTITIES = (
    ("lambda", "Daily satisfaction of the worst-served user λ"),
    ("r", "Satisfaction of the outlet r"),
    ("volume", "Plan and delivery of the outlet"),
    ("error", "Daily error of the outlet: delivery − target"),
    ("dekad", "Error of the outlet over calendar dekads"),
    ("level", "Node level"),
    ("gate", "Open steps and pulses of the outlet"),
    ("season", "Mean λ by season"),
)
ALL = "All seasons"


class ResultsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.loaded = False
        self.data = {}
        self.plotted = None
        self._job = None
        state = app.settings.get("results", {}) or {}

        left = ttk.Frame(self, padding=(0, 0, PAD * 2, 0))
        left.pack(side="left", fill="y")
        ttk.Label(left, text=tr("Case")).pack(anchor="w")
        self.case_var = tk.StringVar()
        self.case_box = ttk.Combobox(left, textvariable=self.case_var, state="readonly", width=38)
        self.case_box.pack(fill="x", pady=(0, PAD))
        self.case_box.bind("<<ComboboxSelected>>", lambda e: self._case_changed())
        ttk.Label(left, text=tr("Rules (select one or more)")).pack(anchor="w")
        lb_frame = ttk.Frame(left)
        lb_frame.pack(fill="x", pady=(0, PAD))
        self.rules = tk.Listbox(lb_frame, selectmode="extended", exportselection=False, height=7, activestyle="none")
        self.rules.pack(side="left", fill="x", expand=True)
        self.rules.bind("<<ListboxSelect>>", lambda e: self.schedule())
        self.ref_var = tk.BooleanVar(value=bool(state.get("reference", True)))
        ttk.Checkbutton(left, text=tr("Show ideal execution as reference"), variable=self.ref_var,
                        command=self.schedule).pack(anchor="w", pady=(0, PAD))
        ttk.Label(left, text=tr("Season")).pack(anchor="w")
        self.year_var = tk.StringVar(value=state.get("season", "2010"))
        self.year_box = ttk.Combobox(left, textvariable=self.year_var, state="readonly", width=38)
        self.year_box.pack(fill="x", pady=(0, PAD))
        self.year_box.bind("<<ComboboxSelected>>", lambda e: self.schedule())
        ttk.Label(left, text=tr("Outlet")).pack(anchor="w")
        self.user_var = tk.StringVar(value=state.get("user", "R-1"))
        ub = ttk.Combobox(left, textvariable=self.user_var, values=list(ds.USERS), state="readonly", width=38)
        ub.pack(fill="x", pady=(0, PAD))
        ub.bind("<<ComboboxSelected>>", lambda e: self.schedule())
        ttk.Label(left, text=tr("Quantity")).pack(anchor="w")
        self.q_var = tk.StringVar(value=tr(dict(QUANTITIES).get(state.get("quantity", "lambda"), QUANTITIES[0][1])))
        qb = ttk.Combobox(left, textvariable=self.q_var, values=[tr(t) for _, t in QUANTITIES], state="readonly",
                          width=38)
        qb.pack(fill="x", pady=(0, PAD))
        qb.bind("<<ComboboxSelected>>", lambda e: self.schedule())
        ttk.Button(left, text=tr("Export the plotted data (CSV)"), command=self.export).pack(fill="x", pady=(PAD, 2))
        self.note = ttk.Label(left, text="", style="Muted.TLabel", wraplength=300, justify="left")
        self.note.pack(anchor="w", pady=(PAD, 0))

        right = ttk.Panedwindow(self, orient="vertical")
        right.pack(side="left", fill="both", expand=True)
        self.plot = PlotPanel(right, figsize=(9, 5))
        right.add(self.plot, weight=3)
        box = ttk.Frame(right)
        right.add(box, weight=1)
        ttk.Label(box, text=tr("Summary of the selection"), style="Bold.TLabel").pack(anchor="w")
        self.table = DataTable(box, height=8, filter_box=False)
        self.table.pack(fill="both", expand=True)
        self._state = state

    # ---------------------------------------------------------------- selections
    def on_show(self):
        if not self.loaded:
            self.loaded = True
            self._fill_cases()

    def refresh(self):
        ds._cache.clear()
        self._fill_cases()

    def save_state(self, settings):
        if not self.loaded:                 # the tab was not opened: keep the stored selection
            return
        settings["results"] = {"case": self._case(), "rules": self._rules(), "season": self.year_var.get(),
                               "user": self.user_var.get(), "quantity": self._quantity(),
                               "reference": bool(self.ref_var.get())}

    def _fill_cases(self):
        self.case_ids = available_cases()
        labels = [f"{c} — {tr(CASE_LABELS.get(c, c))}" for c in self.case_ids]
        self.case_box.configure(values=labels)
        if not labels:
            self.plot.message(tr("No stored results in results/runs."))
            return
        want = self._state.get("case", "q_main")
        idx = self.case_ids.index(want) if want in self.case_ids else 0
        self.case_box.current(idx)
        self._case_changed(initial=True)

    def _case(self):
        i = self.case_box.current()
        return self.case_ids[i] if i >= 0 else None

    def _case_changed(self, initial=False):
        case = self._case()
        self.methods = available_methods(case)
        self.rules.delete(0, "end")
        for m in self.methods:
            self.rules.insert("end", f"{m} — {tr(RULE_LABELS.get(m, m))}")
        wanted = self._state.get("rules", []) if initial else []
        sel = [i for i, m in enumerate(self.methods) if m in wanted] or list(range(min(len(self.methods), 3)))
        for i in sel:
            self.rules.selection_set(i)
        years = sorted({y for m in self.methods for y in available_years(case, m)})
        self.year_box.configure(values=[tr(ALL)] + [str(y) for y in years])
        if self.year_var.get() not in [tr(ALL)] + [str(y) for y in years]:
            self.year_var.set(str(years[0]) if years else tr(ALL))
        self.schedule()

    def _rules(self):
        return [self.methods[i] for i in self.rules.curselection()]

    def _quantity(self):
        label = self.q_var.get()
        return next((k for k, t in QUANTITIES if tr(t) == label), "lambda")

    def _years(self):
        y = self.year_var.get()
        return None if y in (tr(ALL), ALL, "") else [int(y)]

    def schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(120, self.load_and_plot)

    # ---------------------------------------------------------------- data and plots
    def load_and_plot(self):
        self._job = None
        case, rules, years = self._case(), self._rules(), self._years()
        if not case or not rules:
            self.plot.message(tr("Select at least one rule."))
            return
        ref = bool(self.ref_var.get()) and case != "phys" and "LXB" in available_methods("phys")

        def load():
            data = {m: ds.load_runs(case, m, years) for m in rules}
            if ref:
                data["__ref__"] = ds.load_runs("phys", "LXB", years)
            return data
        self.app.background(load, self._plot, busy_text=tr("Loading results…"))

    def _plot(self, data):
        self.data = data
        quantity, user = self._quantity(), self.user_var.get()
        series = {m: df for m, df in data.items() if m != "__ref__" and not df.empty}
        ref = data.get("__ref__")
        fig = self.plot.figure
        fig.clear()
        self.plotted = None
        if not series:
            self.plot.message(tr("No stored results for this selection."))
            return
        title_case = f"{self._case()} · {self.year_var.get()}"
        notes = ""
        if quantity == "season":
            ax = fig.add_subplot(111)
            frames = []
            names = list(series)
            width = 0.8 / max(1, len(names))
            for i, (m, df) in enumerate(series.items()):
                s = df.groupby("year")["lambda"].mean()
                ax.bar(s.index + (i - (len(names) - 1) / 2) * width, s.values, width=width * 0.92,
                       color=PALETTE[i % len(PALETTE)], label=m)
                frames.append(s.rename(m))
            if ref is not None and not ref.empty:
                s = ref.groupby("year")["lambda"].mean()
                ax.plot(s.index, s.values, color=MUTED, marker="_", markersize=18, linestyle="none",
                        label=tr("ideal execution"))
                frames.append(s.rename("ideal"))
            ax.legend(fontsize=8, frameon=False, ncols=min(4, len(names) + 1))
            style_axes(ax, xlabel=tr("Season"), ylabel=tr("Mean daily λ"), title=title_case)
            self.plotted = pd.concat(frames, axis=1).reset_index()
        elif quantity == "dekad":
            ax = fig.add_subplot(111)
            frames = []
            names = list(series)
            width = 0.8 / max(1, len(names))
            single = self._years() is not None
            for i, (m, df) in enumerate(series.items()):
                dk = ds.dekad_errors(df, user)
                if single:
                    x = np.arange(len(dk))
                    labels = [d.strftime("%d.%m") for d in dk["start"]]
                    y = dk["error"].to_numpy()
                else:
                    dk["index"] = dk.groupby(dk["dekad"] // 1000).cumcount()
                    agg = dk.groupby("index")["error"].mean()
                    x, y = agg.index.to_numpy(), agg.to_numpy()
                    labels = [str(i + 1) for i in x]
                ax.bar(x + (i - (len(names) - 1) / 2) * width, y, width=width * 0.92, color=PALETTE[i % len(PALETTE)],
                       label=m)
                frames.append(pd.DataFrame({"dekad": labels, m: y}).set_index("dekad"))
            ax.set_xticks(np.arange(len(labels)))
            ax.set_xticklabels(labels, rotation=60 if single else 0, fontsize=8)
            ax.legend(fontsize=8, frameon=False)
            style_axes(ax, xlabel=tr("Calendar dekad") if single else tr("Dekad of the season (mean over the seasons)"),
                       ylabel="|ΣV − Σx| / ΣD", title=f"{user} · {title_case}")
            self.plotted = pd.concat(frames, axis=1).reset_index()
            notes = tr("Unweighted errors; the early-April dekads, with daily demands below one quantum, dominate "
                       "the mean of R-1.")
        else:
            ax = fig.add_subplot(111)
            frames = []
            for i, (m, df) in enumerate(series.items()):
                colour = PALETTE[i % len(PALETTE)]
                d = df["date"]
                if quantity == "lambda":
                    _line(ax, d, df["lambda"], colour, m)
                    frames.append(df[["date"]].assign(**{m: df["lambda"]}))
                elif quantity == "r":
                    _line(ax, d, df[f"r_{user}"], colour, m)
                    frames.append(df[["date"]].assign(**{m: df[f"r_{user}"]}))
                elif quantity == "volume":
                    _line(ax, d, df[f"V_{user}"], colour, f"{m}: V")
                    if i == 0:
                        _line(ax, d, df[f"x_{user}"], MUTED, tr("plan x"), dashed=True)
                    if m == "LXB-CO":
                        _line(ax, d, df[f"xt_{user}"], colour, f"{m}: " + r"$\tilde{x}$", dashed=True, width=1.0)
                    frames.append(df[["date"]].assign(**{f"{m}_V": df[f"V_{user}"], f"{m}_x": df[f"x_{user}"],
                                                         f"{m}_xt": df[f"xt_{user}"]}))
                elif quantity == "error":
                    e = df[f"V_{user}"] - df[f"xt_{user}"]
                    _line(ax, d, e, colour, m, marker=True)
                    frames.append(df[["date"]].assign(**{m: e}))
                elif quantity == "level":
                    _band(ax, d, df["h_min"], df["h_max"], colour, m)
                    frames.append(df[["date"]].assign(**{f"{m}_h_min": df["h_min"], f"{m}_h_max": df["h_max"]}))
                elif quantity == "gate":
                    _line(ax, d, df[f"open_{user}"], colour, f"{m}: " + tr("open steps"))
                    if f"pulses_{user}" in df and df[f"pulses_{user}"].any():
                        _line(ax, d, df[f"pulses_{user}"], colour, f"{m}: " + tr("pulses"), dashed=True, width=1.0)
                    frames.append(df[["date"]].assign(**{f"{m}_open": df[f"open_{user}"],
                                                         f"{m}_pulses": df.get(f"pulses_{user}")}))
            if ref is not None and not ref.empty and quantity in ("lambda", "r", "volume"):
                col = {"lambda": "lambda", "r": f"r_{user}", "volume": f"V_{user}"}[quantity]
                _line(ax, ref["date"], ref[col], "#9a9a9a", tr("ideal execution"), dashed=True, width=1.0)
            labels = {"lambda": "λ = min_j r_j", "r": f"r = min{{1, V/D}} · {user}",
                      "volume": tr("Volume, m³ per day") + f" · {user}", "error": r"$V - \tilde{x}$, m³ · " + user,
                      "level": tr("Node level, m (daily minimum to maximum)"),
                      "gate": tr("Steps per day") + f" · {user}"}
            if quantity in ("lambda", "r"):
                ax.set_ylim(-0.03, 1.05)
            if quantity == "error":
                ax.axhline(0, color="#9a9a9a", linewidth=0.8)
            ax.legend(fontsize=8, frameon=False, loc="best")
            style_axes(ax, ylabel=labels[quantity], title=title_case)
            fig.autofmt_xdate()
            self.plotted = pd.concat([f.set_index("date") for f in frames], axis=1).reset_index()
        self.plot.draw()
        self.note.configure(text=notes)
        self._summary(series, user)

    def _summary(self, series, user):
        rows = {key: [] for key, _, _ in ds.SUMMARY_LABELS}
        cols = []
        for m, df in series.items():
            s = ds.summary(df, user)
            cols.append(m)
            for key, _, _ in ds.SUMMARY_LABELS:
                rows[key].append(s.get(key))
        out = []
        for key, label, fmt in ds.SUMMARY_LABELS:
            values = rows[key]
            if all(v is None for v in values):
                continue
            out.append([tr(label) + (f" ({user})" if key not in ("seasons", "days", "mean_lambda", "min_lambda",
                                                                   "days_lambda_zero") else "")] +
                       [("" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)) for v in values])
        self.table.set_dataframe(pd.DataFrame(out, columns=[tr("Quantity")] + cols),
                                 widths={tr("Quantity"): 320})

    def export(self):
        if self.plotted is None or self.plotted.empty:
            messagebox.showinfo("Water-01", tr("Nothing is plotted."))
            return
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                         initialfile=f"{self._case()}_{self._quantity()}_{self.user_var.get()}.csv")
        if f:
            self.plotted.to_csv(f, index=False)


def _season_segments(dates, values):
    """Splits a daily series into seasons so that lines do not join 30 September to 1 April."""
    d = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    v = pd.Series(values).reset_index(drop=True)
    breaks = np.flatnonzero(d.diff().dt.days.fillna(1).to_numpy() > 1)
    start = 0
    for b in list(breaks) + [len(d)]:
        yield d.iloc[start:b], v.iloc[start:b]
        start = b


def _line(ax, dates, values, colour, label, dashed=False, width=1.4, marker=False):
    first = True
    for d, v in _season_segments(dates, values):
        ax.plot(d, v, color=colour, linewidth=width, linestyle="--" if dashed else "-",
                marker="o" if marker else None, markersize=2.5, label=label if first else None)
        first = False


def _band(ax, dates, low, high, colour, label):
    first = True
    for (d, lo), (_, hi) in zip(_season_segments(dates, low), _season_segments(dates, high)):
        ax.fill_between(d, lo, hi, color=colour, alpha=0.25, linewidth=0, label=label if first else None)
        ax.plot(d, hi, color=colour, linewidth=0.8)
        first = False
