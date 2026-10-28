"""Overview: the project, the stored results, the environment and the main outcome of the execution rules."""
from __future__ import annotations

from tkinter import ttk

import pandas as pd

from ..i18n import tr
from ..project import (ANALYSIS, CASE_LABELS, FIGURES, ROOT, RULE_LABELS, SCRIPTS, TESTS, citation, environment,
                       git_state, inventory, verify_core_manifest)
from ..tasks import python_command, python_module
from ..widgets import PAD, DataTable, Tooltip, open_path


class OverviewTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD * 2)
        self.app = app
        self.loaded = False
        self.columnconfigure((0, 1, 2), weight=1, uniform="cards")
        self.rowconfigure(2, weight=1)

        # project card
        card = ttk.Labelframe(self, text=tr("Project"), padding=PAD * 2)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, PAD), pady=(0, PAD))
        info = citation()
        g = git_state()
        rows = [(tr("Version"), info.get("version", "—")), (tr("Released"), str(info.get("date-released", "—"))),
                ("DOI", info.get("doi") or "—"), (tr("Git tag"), g.get("tag") or "—"),
                (tr("Commit"), (g.get("commit") or "—")[:12]), (tr("Branch"), g.get("branch") or "—")]
        for i, (k, v) in enumerate(rows):
            ttk.Label(card, text=k + ":", style="Sub.TLabel").grid(row=i, column=0, sticky="w")
            ttk.Label(card, text=v).grid(row=i, column=1, sticky="w", padx=PAD)
        ttk.Button(card, text=tr("Open folder"), command=lambda: open_path(ROOT)).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(PAD, 0))

        # results card
        card = ttk.Labelframe(self, text=tr("Stored simulation seasons"), padding=PAD * 2)
        card.grid(row=0, column=1, sticky="nsew", padx=PAD, pady=(0, PAD))
        self.runs_big = ttk.Label(card, text="…", style="Big.TLabel")
        self.runs_big.pack(anchor="w")
        self.runs_text = ttk.Label(card, text="", style="Sub.TLabel", justify="left")
        self.runs_text.pack(anchor="w")
        ttk.Button(card, text=tr("Simulation tab"), command=lambda: app.notebook.select(app.tabs["simulation"])).pack(
            anchor="w", pady=(PAD, 0))

        # environment card
        card = ttk.Labelframe(self, text=tr("Environment"), padding=PAD * 2)
        card.grid(row=0, column=2, sticky="nsew", padx=(PAD, 0), pady=(0, PAD))
        self.env_frame = ttk.Frame(card)
        self.env_frame.pack(anchor="w", fill="x")
        line = ttk.Frame(card)
        line.pack(anchor="w", pady=(PAD, 0), fill="x")
        b = ttk.Button(line, text=tr("Check the core"), command=self.check_core)
        b.pack(side="left")
        Tooltip(b, tr("Compares the files of the simulation core (src/water01) with docs/CORE_MANIFEST.sha256."))
        self.core_label = ttk.Label(line, text="", style="Sub.TLabel")
        self.core_label.pack(side="left", padx=PAD)

        # quick actions
        actions = ttk.Labelframe(self, text=tr("Quick actions"), padding=PAD)
        actions.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, PAD))
        theorems = tr("Checks of Theorems 1–4")
        figures = tr("Recreate the figures")
        tests = tr("Run the tests")
        for text, tip, cmd in (
                (theorems, tr("scripts/analyse_theorems.py: all tables of results/analysis from the stored seasons "
                              "(about 3 min)."),
                 lambda: app.run_commands(theorems, [python_command(SCRIPTS / "analyse_theorems.py")],
                                          on_finish=lambda *a: self.refresh())),
                (figures, tr("scripts/make_figures.py: the figures of the article in results/figures (about 20 s)."),
                 lambda: app.run_commands(figures, [python_command(SCRIPTS / "make_figures.py")])),
                (tests, tr("pytest: randomised checks of Theorems 1–4 and tests of the simulation core (about 2 min)."),
                 lambda: app.run_commands(tests, [python_module("pytest", "-q", "-p", "no:cacheprovider",
                                                                 str(TESTS))])),
                (tr("Open the analysis tables"), "results/analysis", lambda: open_path(ANALYSIS)),
                (tr("Open the figures"), "results/figures", lambda: open_path(FIGURES))):
            btn = ttk.Button(actions, text=text, command=cmd)
            btn.pack(side="left", padx=PAD // 2, pady=2)
            Tooltip(btn, tip)

        # main outcome
        box = ttk.Labelframe(self, text=tr("Outcome of the execution rules (Table 4 of the article)"), padding=PAD)
        box.grid(row=2, column=0, columnspan=3, sticky="nsew")
        self.table = DataTable(box, height=10, filter_box=False)
        self.table.pack(fill="both", expand=True)
        self.note = ttk.Label(box, text=tr("From results/analysis/rules_outcome.csv. λ: daily satisfaction of the "
                                           "worst-served user; dekad error: unweighted mean of |ΣV − Σx| / ΣD of R-1 "
                                           "over the calendar dekads."),
                              style="Muted.TLabel", wraplength=1100, justify="left")
        self.note.pack(side="bottom", anchor="w", pady=(4, 0), before=self.table)

    def on_show(self):
        if not self.loaded:
            self.refresh()

    def refresh(self):
        self.loaded = True
        self._fill_environment()
        self.app.background(inventory, self._show_inventory)
        self._fill_outcome()

    def _fill_environment(self):
        for w in self.env_frame.winfo_children():
            w.destroy()
        styles = {"ok": "Ok.TLabel", "different": "Warn.TLabel", "old": "Bad.TLabel", "missing": "Bad.TLabel",
                  "optional": "Muted.TLabel"}
        words = {"ok": tr("matches"), "different": tr("other version"), "old": tr("too old"),
                 "missing": tr("not installed"), "optional": tr("not installed (optional)")}
        note = tr("Other versions can change the last digits of recomputed results.")
        for i, (name, have, need, state) in enumerate(environment()):
            labels = (ttk.Label(self.env_frame, text=name, style=styles[state]),
                      ttk.Label(self.env_frame, text=have),
                      ttk.Label(self.env_frame, text=f"{need}  {words[state]}", style="Muted.TLabel"))
            for column, lab in enumerate(labels):
                lab.grid(row=i, column=column, sticky="w", padx=(PAD, 0) if column else 0)
                if state == "different":
                    Tooltip(lab, note)

    def _show_inventory(self, jobs):
        done = sum(j.state == "done" for j in jobs)
        self.runs_big.configure(text=f"{done} / {len(jobs)}")
        counts = {}
        for j in jobs:
            counts.setdefault(j.state, 0)
            counts[j.state] += 1
        minutes = sum(j.minutes or 0 for j in jobs if j.state == "done")
        parts = [f"{tr(s)}: {n}" for s, n in sorted(counts.items()) if s != "done"]
        text = tr("seasons complete") + (" · " + ", ".join(parts) if parts else "")
        text += "\n" + tr("Computing time of the stored seasons") + f": {minutes / 60:.1f} " + tr("h")
        self.runs_text.configure(text=text)

    def _fill_outcome(self):
        f = ANALYSIS / "rules_outcome.csv"
        if not f.exists():
            message = tr("results/analysis/rules_outcome.csv not found")
            self.table.set_dataframe(pd.DataFrame({tr("Message"): [message]}))
            return
        r = pd.read_csv(f)
        moves = {}
        g = ANALYSIS / "gate_activity.csv"
        if g.exists():
            ga = pd.read_csv(g)
            if "moves_R-1" in ga:
                moves = dict(zip(ga["method"], ga["moves_R-1"]))
        out = pd.DataFrame({
            tr("Case"): [tr(CASE_LABELS.get(c, c)) for c in r["case"]],
            tr("Rule"): [tr(RULE_LABELS.get(m, m)) for m in r["rule"]],
            tr("Mean daily λ"): r["mean_daily_lambda"],
            tr("Days with λ = 0"): r["days_lambda_zero"],
            tr("Shortfall, %"): 100 * r["shortfall_share"],
            tr("Over-delivery, %"): 100 * r["overdelivery_share"],
            tr("Delivery ratio of R-1"): r["season_satisfaction_R1_mean"],
            tr("Dekad error of R-1"): r["R1_dekad_err_mean"],
            tr("Gate moves of R-1 per day"): [moves.get(m) if c == "q_main" else None
                                              for c, m in zip(r["case"], r["rule"])],
        })
        self.table.set_dataframe(out, formats={tr("Mean daily λ"): ".4f", tr("Shortfall, %"): ".3f",
                                               tr("Over-delivery, %"): ".3f", tr("Delivery ratio of R-1"): ".3f",
                                               tr("Dekad error of R-1"): ".4f", tr("Gate moves of R-1 per day"): ".1f"})

    def check_core(self):
        def done(res):
            n, bad = res
            if bad:
                self.core_label.configure(text=f"{len(bad)} " + tr("files differ") + ": " + ", ".join(bad[:3]),
                                          style="Bad.TLabel")
            else:
                self.core_label.configure(text=f"{n} " + tr("files, no differences"), style="Ok.TLabel")
        self.app.background(verify_core_manifest, done)
