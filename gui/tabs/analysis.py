"""Analysis: the scripts that recompute the checks of the theorems, the figures and the verification of the plant, and
a viewer of the tables they write."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import datasets as ds
from ..i18n import tr
from ..project import ANALYSIS, INPUTS, ROOT, SCRIPTS, TESTS, VERIFICATION, describe_table, verify_core_manifest
from ..tasks import python_command, python_module
from ..widgets import PAD, DataTable, Tooltip, open_path

# columns that identify the rows of a table, shown first
LEAD_COLUMNS = ("case", "rule", "method", "chain", "scenario", "theta", "year", "season", "regulator", "user", "outlet")

# (title, command arguments, duration, explanation)
SCRIPTS_LIST = (
    ("Checks of Theorems 1–4", ("analyse_theorems.py",), "≈ 3 min",
     "All tables of results/analysis from the stored seasons: exclusion, equal split, price of indivisibility and "
     "whole steps, pulse rule, carry-over, outcome of the rules, device chain, records."),
    ("Figures of the article", ("make_figures.py",), "≈ 20 s", "The five figures of the article and two separate panels of Figure 5 (results/figures)."),
    ("Derived inputs", ("derive_inputs.py",), "< 1 min",
     "Delivery factor, monthly shares of Abad-Yarmish, node balance and checks of the records "
     "(results/inputs/derived_inputs.json)."),
    ("Plant: grid and time step", ("verification_convergence.py", "--eta", "0.81"), "several min",
     "Convergence of the Saint–Venant plant with the conveyance loss of the baseline (Table S2a)."),
    ("Plant: volume of one quantum", ("verification_pulse.py",), "< 1 min",
     "The smallest opening of R-1 for one control step at 1–16 hydraulic steps (Table S2b)."),
    ("Plant: comparison with EPA SWMM", ("check_swmm_benchmark.py",), "several min",
     "Three transients replayed in EPA SWMM 5 (needs the package swmm-toolkit; Table S2c)."),
    ("Gate movements: summary", ("gate_activity.py", "--summary"), "< 1 min",
     "Summary of the stored re-runs of the quantised-actuator case."),
    ("Gate movements: re-run", ("gate_activity.py",), "≈ 3 h",
     "Re-runs the 50 seasons of q_main, counts the gate movements and checks that the stored volumes are reproduced."),
    ("Requests of direct execution: summary", ("check_residual_cap.py", "--summary"), "< 1 min",
     "Summary of the stored re-runs of the seven direct-execution cases."),
    ("Requests of direct execution: re-run", ("check_residual_cap.py",), "≈ 5 h",
     "Re-runs the 70 direct-execution seasons and checks every request against the remainder of the plan."),
)


class AnalysisTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.loaded = False
        pw = ttk.Panedwindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)

        left = ttk.Labelframe(pw, text=tr("Scripts"), padding=PAD)
        pw.add(left, weight=2)
        canvas_rows = ttk.Frame(left)
        canvas_rows.pack(fill="both", expand=True)
        canvas_rows.columnconfigure(1, weight=1)
        run_width = max(6, len(tr("Run")) + 2)
        for i, (title, args, duration, tip) in enumerate(SCRIPTS_LIST):
            b = ttk.Button(canvas_rows, text=tr("Run"), width=run_width,
                           command=lambda t=title, a=args: app.run_commands(
                               tr(t), [python_command(SCRIPTS / a[0], *a[1:])], on_finish=lambda *x: self.refresh()))
            b.grid(row=i, column=0, sticky="w", pady=2)
            lab = ttk.Label(canvas_rows, text=tr(title))
            lab.grid(row=i, column=1, sticky="w", padx=PAD)
            ttk.Label(canvas_rows, text=tr(duration), style="Muted.TLabel").grid(row=i, column=2, sticky="e")
            for w in (b, lab):
                Tooltip(w, f"scripts/{' '.join(args)}\n\n{tr(tip)}")
        n = len(SCRIPTS_LIST)
        ttk.Separator(canvas_rows).grid(row=n, column=0, columnspan=3, sticky="ew", pady=PAD)
        b = ttk.Button(canvas_rows, text=tr("Run"), width=run_width, command=self.run_tests)
        b.grid(row=n + 1, column=0, sticky="w", pady=2)
        ttk.Label(canvas_rows, text=tr("Test suite (pytest)")).grid(row=n + 1, column=1, sticky="w", padx=PAD)
        ttk.Label(canvas_rows, text=tr("≈ 2 min"), style="Muted.TLabel").grid(row=n + 1, column=2, sticky="e")
        Tooltip(b, tr("Randomised checks of Theorems 1–4 on the abstract actuator, short closed-loop checks of the "
                      "rules and the tests of the simulation core."))
        b = ttk.Button(canvas_rows, text=tr("Run"), width=run_width, command=self.check_core)
        b.grid(row=n + 2, column=0, sticky="w", pady=2)
        ttk.Label(canvas_rows, text=tr("Checksums of the simulation core")).grid(row=n + 2, column=1, sticky="w",
                                                                                 padx=PAD)
        ttk.Label(canvas_rows, text=tr("< 1 s"), style="Muted.TLabel").grid(row=n + 2, column=2, sticky="e")
        ttk.Label(left, text=tr("The scripts run in separate processes; their output appears in the console below. "
                                "Stored seasons are read, not recomputed, except by the re-run scripts."),
                  style="Muted.TLabel", wraplength=380, justify="left").pack(side="bottom", anchor="w", pady=(PAD, 0),
                                                                             before=canvas_rows)

        right = ttk.Labelframe(pw, text=tr("Tables"), padding=PAD)
        pw.add(right, weight=5)
        top = ttk.Frame(right)
        top.pack(fill="x")
        ttk.Label(top, text=tr("Table:")).pack(side="left")
        self.file_var = tk.StringVar()
        self.file_box = ttk.Combobox(top, textvariable=self.file_var, state="readonly", width=40)
        self.file_box.pack(side="left", padx=PAD)
        self.file_box.bind("<<ComboboxSelected>>", lambda e: self.show_table())
        ttk.Button(top, text=tr("Open"), command=self.open_file).pack(side="left")
        ttk.Button(top, text=tr("Export (CSV)"), command=lambda: self.table.export_csv()).pack(side="left", padx=PAD)
        self.title = ttk.Label(right, text="", style="Sub.TLabel", wraplength=900, justify="left")
        self.title.pack(anchor="w", pady=PAD)
        self.table = DataTable(right, height=20)
        self.table.pack(fill="both", expand=True)
        self.files = []

    def on_show(self):
        if not self.loaded:
            self.refresh()

    def refresh(self):
        self.loaded = True
        files = []
        for folder in (ANALYSIS, VERIFICATION, INPUTS):
            if folder.is_dir():
                files += sorted(folder.glob("*.csv")) + sorted(folder.glob("*.json"))
        self.files = files
        names = [f.relative_to(ROOT).as_posix() for f in files]
        current = self.file_var.get()
        self.file_box.configure(values=names)
        if current in names:
            self.show_table()
        elif names:
            main = "results/analysis/rules_outcome.csv"
            idx = names.index(main) if main in names else 0
            self.file_box.current(idx)
            self.show_table()

    def _path(self):
        i = self.file_box.current()
        return self.files[i] if 0 <= i < len(self.files) else None

    def show_table(self):
        p = self._path()
        if p is None:
            return
        try:
            df = ds.table_file(p)
        except Exception as e:  # noqa: BLE001
            self.title.configure(text=f"{p.name}: {e}")
            return
        title = describe_table(p)
        self.title.configure(text=(title + "  ·  " if title else "") + f"{len(df)} × {len(df.columns)}")
        lead = [c for c in LEAD_COLUMNS if c in df.columns]
        self.table.set_dataframe(df[lead + [c for c in df.columns if c not in lead]])

    def open_file(self):
        p = self._path()
        if p is not None:
            md = p.with_suffix(".md")
            open_path(md if md.exists() else p)

    def run_tests(self):
        self.app.run_commands(tr("Test suite (pytest)"),
                              [python_module("pytest", "-q", "-p", "no:cacheprovider", str(TESTS))])

    def check_core(self):
        def done(res):
            n, bad = res
            if bad:
                self.app.console.write(f"{tr('Checksums of the simulation core')}: {len(bad)} {tr('files differ')}: "
                                       + ", ".join(bad), "error")
            else:
                self.app.console.write(f"{tr('Checksums of the simulation core')}: {n} {tr('files, no differences')}",
                                       "ok")
        self.app.background(verify_core_manifest, done)
