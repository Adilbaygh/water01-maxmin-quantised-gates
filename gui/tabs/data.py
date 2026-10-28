"""Data: parameters of the configuration and the recorded supply with the plan-derived demand of each season."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pandas as pd

from .. import datasets as ds
from ..i18n import tr
from ..project import CONFIGS, DATA, YEARS
from ..widgets import PAD, PALETTE, DataTable, PlotPanel, Tooltip, open_path, style_axes

STATUSES = ("observed", "derived", "assumed", "setting")


class DataTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.loaded = False
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # ------------------------------------------------ parameters
        par = ttk.Frame(nb, padding=PAD)
        nb.add(par, text=tr("Parameters"))
        top = ttk.Frame(par)
        top.pack(fill="x", pady=(0, PAD))
        ttk.Label(top, text=tr("Scenario:")).pack(side="left")
        self.scen = ds.scenarios()
        self.scen_var = tk.StringVar(value="normal")
        box = ttk.Combobox(top, textvariable=self.scen_var, values=[s for s, _ in self.scen], state="readonly",
                           width=22)
        box.pack(side="left", padx=PAD)
        box.bind("<<ComboboxSelected>>", lambda e: self.show_parameters())
        self.scen_desc = ttk.Label(top, text="", style="Sub.TLabel")
        self.scen_desc.pack(side="left", padx=PAD)
        ttk.Label(top, text=tr("Status:")).pack(side="left", padx=(PAD * 2, 0))
        self.status_var = tk.StringVar(value=tr("all"))
        sbox = ttk.Combobox(top, textvariable=self.status_var, state="readonly", width=14,
                            values=[tr("all")] + [tr(s) for s in STATUSES])
        sbox.pack(side="left", padx=PAD)
        sbox.bind("<<ComboboxSelected>>", lambda e: self.show_parameters())
        ttk.Button(top, text=tr("Open the configuration"),
                   command=lambda: open_path(CONFIGS / "kegeyli_reference.yaml")).pack(side="right")
        self.params = DataTable(par, height=18)
        self.params.pack(fill="both", expand=True)
        ttk.Label(par, text=tr("observed: passport, datasheet or record; derived: computed from observed values; "
                               "assumed: an assumption, covered by the robustness cases; setting: a numerical or "
                               "experimental setting. Rows changed by the scenario are marked."),
                  style="Muted.TLabel", wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0),
                                                                              before=self.params)

        # ------------------------------------------------ supply and demand
        sd = ttk.Frame(nb, padding=PAD)
        nb.add(sd, text=tr("Supply and demand"))
        top = ttk.Frame(sd)
        top.pack(fill="x", pady=(0, PAD))
        ttk.Label(top, text=tr("Season:")).pack(side="left")
        self.year_var = tk.StringVar(value="2010")
        ybox = ttk.Combobox(top, textvariable=self.year_var, values=[str(y) for y in YEARS], state="readonly", width=8)
        ybox.pack(side="left", padx=PAD)
        ybox.bind("<<ComboboxSelected>>", lambda e: self.show_season())
        self.season_info = ttk.Label(top, text="", style="Sub.TLabel")
        self.season_info.pack(side="left", padx=PAD)
        b = ttk.Button(top, text=tr("Open the data folder"), command=lambda: open_path(DATA))
        b.pack(side="right")
        Tooltip(b, "DATA/processed")
        body = ttk.Panedwindow(sd, orient="horizontal")
        body.pack(fill="both", expand=True)
        self.plot = PlotPanel(body, figsize=(9, 6))
        body.add(self.plot, weight=3)
        right = ttk.Frame(body)
        body.add(right, weight=1)
        ttk.Label(right, text=tr("Demand of the outlets"), style="Bold.TLabel").pack(anchor="w")
        self.demand = DataTable(right, height=8, filter_box=False)
        self.demand.pack(fill="both", expand=True)
        ttk.Label(right, text=tr("The demand is derived from the 2021 plan of the Kegeyli system (Equation (1) of the "
                                 "article); the same profile is used in every season. Blank records are treated as "
                                 "days without supply."), style="Muted.TLabel", wraplength=320,
                  justify="left").pack(side="bottom", anchor="w", pady=(PAD, 0), before=self.demand)

    def on_show(self):
        if not self.loaded:
            self.loaded = True
            self.show_parameters()
            self.show_season()

    def refresh(self):
        self.show_parameters()
        self.show_season()

    def show_parameters(self):
        scen = self.scen_var.get()
        desc = dict(self.scen).get(scen, "")
        self.scen_desc.configure(text=desc)
        df = ds.config_rows(scen)
        status = next((s for s in STATUSES if tr(s) == self.status_var.get()), None)
        if status:
            df = df[df["status"] == status]
        df = df.assign(status=df["status"].map(lambda v: tr(v) if v in STATUSES else v),
                       scenario=df["scenario"].map(lambda v: tr("yes") if v else ""))
        df = df.rename(columns={"section": tr("Section"), "parameter": tr("Parameter"), "value": tr("Value"),
                                "status": tr("Status"), "source": tr("Source"), "scenario": tr("Changed")})
        self.params.set_dataframe(df, widths={tr("Source"): 600, tr("Value"): 160})

    def show_season(self):
        year = int(self.year_var.get())
        self.plot.message(tr("Loading…"))

        def load():
            return ds.supply_season(year), ds.node_season(year)
        self.app.background(load, lambda res: self._draw_season(year, *res), busy_text=tr("Loading the season…"))

    def _draw_season(self, year, sup, node):
        fig = self.plot.figure
        fig.clear()
        axes = fig.subplots(3, 1, sharex=True)
        ax = axes[0]
        ax.plot(sup["date"], sup["kegeyli_Q"], color=PALETTE[0], linewidth=1.4, label=tr("recorded"))
        blank = sup[sup["blank"]]
        if len(blank):
            for d in blank["date"]:
                ax.axvspan(d - pd.Timedelta(hours=12), d + pd.Timedelta(hours=12), color="#e6e6e6", linewidth=0)
            ax.plot([], [], color="#d0d0d0", linewidth=6, label=tr("blank record (no supply)"))
            ax.legend(loc="upper right", fontsize=8, frameon=False)
        style_axes(ax, ylabel=tr("Head discharge S, m³/s"), title=f"{tr('Season')} {year}")
        ax = axes[1]
        ax.plot(node["date"], node["W_m3"] / 1e6, color=PALETTE[0], linewidth=1.4, label=tr("available at the node, W"))
        ax.plot(node["date"], node["D_total_m3"] / 1e6, color=PALETTE[1], linewidth=1.4,
                label=tr("demand of the six outlets"))
        ax.legend(loc="upper right", fontsize=8, frameon=False)
        style_axes(ax, ylabel=tr("million m³ per day"))
        ax = axes[2]
        ax.plot(node["date"], node["lambda_star"], color=PALETTE[2], linewidth=1.4)
        ax.set_ylim(-0.03, 1.05)
        style_axes(ax, ylabel="λ* = min{1, W / ΣD}")
        fig.autofmt_xdate()
        self.plot.draw()
        deficit = int((node["lambda_star"] < 1).sum())
        self.season_info.configure(text=f"{tr('blank records')}: {int(sup['blank'].sum())} · "
                                        f"{tr('deficit days')}: {deficit} · "
                                        f"{tr('mean')} λ* = {node['lambda_star'].mean():.3f}")
        rows = []
        season, april = tr("Season, million m³"), tr("1–10 April, m³ per day")
        for u in ds.USERS:
            col = node[f"D_{u}"]
            rows.append({tr("Outlet"): u, season: col.sum() / 1e6, april: col.iloc[:10].mean()})
        rows.append({tr("Outlet"): tr("All"), season: node["D_total_m3"].sum() / 1e6,
                     april: node["D_total_m3"].iloc[:10].mean()})
        self.demand.set_dataframe(pd.DataFrame(rows), formats={season: ".3f", april: ",.1f"})
