"""Simulation: the seasons of the ten cases (scripts/run_cases.py), their state, and runs of the missing seasons."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from ..i18n import tr
from ..project import CASE_LABELS, RULE_LABELS, RUNS, cases, inventory, release_claim, result_path
from ..tasks import python_module
from ..widgets import PAD, Tooltip, open_path

STATE_TAGS = {"done": "#1b7e3c", "missing": "#8a8984", "claimed": "#b26a00", "error": "#c62828", "partial": "#b26a00",
              "running": "#2a78d6"}


class SimulationTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.loaded = False
        self.jobs = {}
        self.running = {}            # worker -> job spec started and not finished
        self.total = 0
        self.finished = set()        # specs finished in this run (several workers report the same list)

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, PAD))
        ttk.Button(top, text=tr("Refresh"), command=self.refresh).pack(side="left")
        ttk.Button(top, text=tr("Select missing"), command=self.select_missing).pack(side="left", padx=PAD)
        self.run_btn = ttk.Button(top, text=tr("Run selected"), style="Accent.TButton", command=self.run_selected)
        self.run_btn.pack(side="left")
        Tooltip(self.run_btn, tr("Computes the selected seasons that are not complete. A complete season is never "
                                 "recomputed; to repeat one, delete its result files first."))
        phases = ttk.Menubutton(top, text=tr("Run a phase"))
        menu = tk.Menu(phases, tearoff=False)
        for ph, case_list in cases()["phases"].items():
            menu.add_command(label=f"{ph}: " + ", ".join(case_list), command=lambda c=case_list: self.run_cases(c))
        phases["menu"] = menu
        phases.pack(side="left", padx=PAD)
        ttk.Label(top, text=tr("Parallel workers:")).pack(side="left", padx=(PAD * 2, 2))
        self.workers = tk.IntVar(value=max(1, min(app.settings.get("workers", 1), os.cpu_count() or 1)))
        sp = ttk.Spinbox(top, from_=1, to=max(1, os.cpu_count() or 1), textvariable=self.workers, width=4)
        sp.pack(side="left")
        Tooltip(sp, tr("Several seasons can be computed at once; each worker uses one processor core."))

        prog = ttk.Frame(self)
        prog.pack(fill="x", pady=(0, PAD))
        self.bar = ttk.Progressbar(prog, mode="determinate", length=240)
        self.bar.pack(side="left")
        self.prog_label = ttk.Label(prog, text="", style="Sub.TLabel")
        self.prog_label.pack(side="left", padx=PAD)
        ttk.Button(prog, text=tr("Open the results folder"), command=lambda: open_path(RUNS)).pack(side="right")
        ttk.Button(prog, text=tr("Show the error"), command=self.show_error).pack(side="right", padx=PAD)
        b = ttk.Button(prog, text=tr("Release claims"), command=self.release)
        b.pack(side="right")
        Tooltip(b, tr("Removes the claim of selected seasons left by an interrupted or failed run, so that they can "
                      "be computed again. Do not use it while another program computes them."))

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        cols = ("description", "state", "minutes", "created")
        self.tree = ttk.Treeview(frame, columns=cols, selectmode="extended")
        self.tree.heading("#0", text=tr("Case / rule / season"))
        self.tree.heading("description", text=tr("Description"))
        self.tree.heading("state", text=tr("State"))
        self.tree.heading("minutes", text=tr("Minutes"))
        self.tree.heading("created", text=tr("Computed (UTC)"))
        self.tree.column("#0", width=230)
        self.tree.column("description", width=360)
        self.tree.column("state", width=140)
        self.tree.column("minutes", width=80, anchor="e")
        self.tree.column("created", width=200)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        for state, colour in STATE_TAGS.items():
            self.tree.tag_configure(state, foreground=colour)
        ttk.Label(self, text=tr("Each season is one run of the closed loop over 183 days (about 3 min on one core). "
                                "Results are written to results/runs/<case>/<rule>_<season>.csv with a .meta.json file "
                                "(checksums of the code and inputs, environment)."),
                  style="Muted.TLabel", wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(PAD, 0),
                                                                              before=frame)

    # ---------------------------------------------------------------- tree
    def on_show(self):
        if not self.loaded:
            self.refresh()

    def save_state(self, settings):
        try:
            settings["workers"] = max(1, int(self.workers.get()))
        except (tk.TclError, ValueError):
            pass

    def refresh(self):
        self.loaded = True
        self.app.background(inventory, self._fill)

    def _fill(self, jobs):
        open_items = {i for i in self._all_items() if self.tree.item(i, "open")}
        self.tree.delete(*self.tree.get_children())
        self.jobs = {j.spec: j for j in jobs}
        info = cases()["cases"]
        for case, (scenario, chain, methods) in info.items():
            cj = [j for j in jobs if j.case == case]
            done = sum(j.state == "done" for j in cj)
            cid = self.tree.insert("", "end", iid=f"case:{case}", text=case, open=f"case:{case}" in open_items,
                                   values=(f"{tr(CASE_LABELS.get(case, case))} · {scenario} · {chain}",
                                           f"{done} / {len(cj)}", "", ""),
                                   tags=("done" if done == len(cj) else "missing",))
            for m in methods:
                mj = [j for j in cj if j.method == m]
                mdone = sum(j.state == "done" for j in mj)
                mid = self.tree.insert(cid, "end", iid=f"method:{case}:{m}", text=m,
                                       open=f"method:{case}:{m}" in open_items,
                                       values=(tr(RULE_LABELS.get(m, m)), f"{mdone} / {len(mj)}", "", ""),
                                       tags=("done" if mdone == len(mj) else "missing",))
                for j in mj:
                    self.tree.insert(mid, "end", iid=j.spec, text=str(j.year),
                                     values=("", tr(j.state), f"{j.minutes:.1f}" if j.minutes else "", j.created or ""),
                                     tags=(j.state,))
        self._update_progress()

    def _all_items(self, parent=""):
        for i in self.tree.get_children(parent):
            yield i
            yield from self._all_items(i)

    def _leaves(self, items):
        out = []
        for i in items:
            children = self.tree.get_children(i)
            if children:
                out += self._leaves(children)
            elif i in self.jobs:
                out.append(i)
        return list(dict.fromkeys(out))

    def select_missing(self):
        missing = [s for s, j in self.jobs.items() if j.state != "done"]
        self.tree.selection_set(missing)
        if missing:
            self.tree.see(missing[0])
        else:
            messagebox.showinfo("Water-01", tr("All seasons are complete."))

    # ---------------------------------------------------------------- runs
    def run_selected(self):
        specs = [s for s in self._leaves(self.tree.selection()) if self.jobs[s].state != "done"]
        self._run(specs)

    def run_cases(self, case_list):
        specs = [s for s, j in self.jobs.items() if j.case in case_list and j.state != "done"]
        self._run(specs)

    def _run(self, specs):
        if not specs:
            messagebox.showinfo("Water-01", tr("The selected seasons are complete; nothing to compute."))
            return
        claimed = [s for s in specs if result_path(*self._parts(s)).with_suffix(".claim").exists()]
        if claimed:
            answer = messagebox.askyesnocancel("Water-01", tr(
                "{n} of the selected seasons are claimed by an earlier run that was interrupted or failed, or by "
                "another program that is computing them now. Release these claims and compute the seasons again?\n\n"
                "Yes: release and compute. No: compute only the other seasons.").format(n=len(claimed)))
            if answer is None:
                return
            if answer:
                for spec in claimed:
                    release_claim(*self._parts(spec))
            else:
                specs = [s for s in specs if s not in claimed]
                if not specs:
                    return
        try:
            workers = max(1, min(int(self.workers.get() or 1), len(specs)))
        except (tk.TclError, ValueError):
            workers = 1
        minutes = 3 * len(specs) / workers
        if not messagebox.askyesno("Water-01", tr("Seasons to compute: {n}; parallel workers: {w}. This takes about "
                                                  "{m:.0f} min. Continue?").format(n=len(specs), w=workers, m=minutes)):
            return
        self.total, self.finished = len(specs), set()
        self.running = {}
        cmd = python_module("gui.jobrunner", *specs)
        self.app.run_commands(tr("Simulation") + f" ({len(specs)})", [cmd] * workers, parallel=workers > 1,
                              on_line=self._on_line, on_finish=self._on_finish)
        if self.tree.exists(specs[0]):
            self.tree.see(specs[0])                     # opens the case and the rule of the first season
        self._update_progress()

    @staticmethod
    def _parts(spec):
        case, method, year = spec.split(":")
        return case, method, int(year)

    def _on_line(self, worker, text):
        word, _, rest = text.partition(" ")
        if word not in ("START", "DONE", "FAILED", "SKIP"):
            return
        spec = rest.split(" ")[0].rstrip(":").replace("/", ":")
        if word == "START":
            self.running[worker] = spec
            self._set_state(spec, "running")
        elif word in ("DONE", "FAILED"):
            self.running.pop(worker, None)
            self.finished.add(spec)
            self._set_state(spec, "done" if word == "DONE" else "error")
        elif "(complete)" in rest:
            self.finished.add(spec)
        self._update_progress()

    def _set_state(self, spec, state):
        if self.tree.exists(spec):
            values = list(self.tree.item(spec, "values"))
            values[1] = tr(state)
            self.tree.item(spec, values=values, tags=(state,))

    def _on_finish(self, codes, stopped):
        if stopped and self.running:
            names = ", ".join(self.running.values())
            for spec in self.running.values():
                release_claim(*self._parts(spec))
            self.app.console.write(tr("Interrupted seasons released") + f": {names}", "info")
        self.running = {}
        self.refresh()

    def _update_progress(self):
        done = sum(j.state == "done" for j in self.jobs.values())
        text = f"{tr('Complete')}: {done} / {len(self.jobs)}"
        if self.total:
            text += f"   ·   {tr('this run')}: {len(self.finished)} / {self.total}"
            self.bar.configure(maximum=self.total, value=len(self.finished))
        else:
            self.bar.configure(maximum=max(1, len(self.jobs)), value=done)
        self.prog_label.configure(text=text)

    # ---------------------------------------------------------------- claims and errors
    def release(self):
        specs = [s for s in self._leaves(self.tree.selection())
                 if self.jobs[s].state in ("claimed", "partial", "error")]
        if not specs:
            messagebox.showinfo("Water-01", tr("No claimed, failed or partial season is selected."))
            return
        if self.app.runner.busy():
            messagebox.showwarning("Water-01", tr("Wait until the running script finishes."))
            return
        question = tr("Release {n} season(s)? Do this only if no other program is computing them.")
        if messagebox.askyesno("Water-01", question.format(n=len(specs))):
            for s in specs:
                release_claim(*self._parts(s))
            self.refresh()

    def show_error(self):
        specs = [s for s in self._leaves(self.tree.selection()) if self.jobs[s].state == "error"]
        if not specs:
            messagebox.showinfo("Water-01", tr("Select a season whose state is error."))
            return
        case, method, year = self._parts(specs[0])
        f = result_path(case, method, year).with_suffix(".error.txt")
        win = tk.Toplevel(self)
        win.title(f"{case}/{method}/{year}")
        txt = tk.Text(win, width=110, height=30, wrap="none")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", f.read_text(encoding="utf-8") if f.exists() else "")
        txt.configure(state="disabled")
