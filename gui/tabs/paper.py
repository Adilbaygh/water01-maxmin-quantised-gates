"""Article: builds the manuscript and the Supplementary Materials from paper/src with the MDPI template, checks them
against the results, and counts the words of the sections. The sources of the article are kept locally and are not
part of the public repository."""
from __future__ import annotations

import re
import time
import tkinter as tk
from tkinter import filedialog, ttk

import pandas as pd

from ..i18n import tr
from ..project import PAPER, PAPER_SRC, PAPER_TOOLS
from ..tasks import python_command
from ..widgets import PAD, DataTable, Tooltip, open_path

SECTIONS = (("abstract.md", "Abstract"), ("introduction.md", "1. Introduction"),
            ("methods.md", "2. Materials and Methods"), ("results.md", "3. Results"),
            ("discussion.md", "4. Discussion"), ("conclusions.md", "5. Conclusions"), ("appendix.md", "Appendix A"))


def count_words(text: str) -> int:
    """Words of a section without the lines that include tables and figures ([[...]])."""
    lines = [line for line in text.splitlines() if not line.strip().startswith("[[")]
    return len(re.sub(r"\^", "", "\n".join(lines)).split())


class PaperTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD * 2)
        self.app = app
        self.loaded = False
        self.available = (PAPER_TOOLS / "build_paper.py").exists()
        if not self.available:
            ttk.Label(self, text=tr("The sources of the article (paper/src and paper/tools) are not in this folder."),
                      style="Bold.TLabel").pack(anchor="w")
            ttk.Label(self, text=tr("They are kept locally by the authors and are not part of the public repository."),
                      style="Sub.TLabel").pack(anchor="w", pady=PAD)
            return
        default = app.settings.get("paper_out") or str(PAPER / "build")
        self.out_var = tk.StringVar(value=default)
        top = ttk.Labelframe(self, text=tr("Build"), padding=PAD * 2)
        top.pack(fill="x")
        row = ttk.Frame(top)
        row.pack(fill="x")
        ttk.Label(row, text=tr("Output folder:")).pack(side="left")
        ttk.Entry(row, textvariable=self.out_var, width=70).pack(side="left", padx=PAD, fill="x", expand=True)
        ttk.Button(row, text=tr("Browse…"), command=self.browse).pack(side="left")
        row = ttk.Frame(top)
        row.pack(fill="x", pady=(PAD, 0))
        b = ttk.Button(row, text=tr("Build and check"), style="Accent.TButton", command=self.build_all)
        b.pack(side="left")
        Tooltip(b, tr("Generates the tables from results/analysis, builds manuscript.docx and supplementary.docx and "
                      "checks every number of the text against the results."))
        ttk.Button(row, text=tr("Generate the tables"), command=self.tables).pack(side="left", padx=PAD)
        ttk.Button(row, text=tr("Build the documents"), command=self.build).pack(side="left")
        ttk.Button(row, text=tr("Check the documents"), command=self.verify).pack(side="left", padx=PAD)
        ttk.Separator(row, orient="vertical").pack(side="left", fill="y", padx=PAD)
        ttk.Button(row, text=tr("Open the manuscript"), command=lambda: self._open("manuscript.docx")).pack(side="left")
        ttk.Button(row, text=tr("Open the supplement"), command=lambda: self._open("supplementary.docx")).pack(
            side="left", padx=PAD)
        ttk.Button(row, text=tr("Open the folder"), command=lambda: open_path(self._out())).pack(side="left")
        self.check_label = ttk.Label(top, text="", style="Sub.TLabel")
        self.check_label.pack(anchor="w", pady=(PAD, 0))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(PAD, 0))
        body.columnconfigure((0, 1), weight=1)
        body.rowconfigure(0, weight=1)
        words = ttk.Labelframe(body, text=tr("Words of the main text"), padding=PAD)
        words.grid(row=0, column=0, sticky="nsew", padx=(0, PAD))
        self.words = DataTable(words, height=9, filter_box=False)
        self.words.pack(fill="both", expand=True)
        self.words_note = ttk.Label(words, text="", style="Sub.TLabel", wraplength=520, justify="left")
        self.words_note.pack(side="bottom", anchor="w", pady=(4, 0), before=self.words)
        src = ttk.Labelframe(body, text=tr("Sources (paper/src)"), padding=PAD)
        src.grid(row=0, column=1, sticky="nsew")
        self.sources = DataTable(src, height=9, filter_box=False)
        self.sources.pack(fill="both", expand=True)
        row = ttk.Frame(src)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text=tr("Refresh"), command=self.refresh).pack(side="left")
        ttk.Button(row, text=tr("Open the sources"), command=lambda: open_path(PAPER_SRC)).pack(side="left", padx=PAD)

    # ---------------------------------------------------------------- state
    def on_show(self):
        if self.available and not self.loaded:
            self.refresh()

    def save_state(self, settings):
        if self.available:                  # the default folder is not stored, so that it follows the project folder
            out = self.out_var.get().strip()
            settings["paper_out"] = "" if out == str(PAPER / "build") else out

    def _out(self):
        from pathlib import Path
        p = Path(self.out_var.get()).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get() or str(PAPER))
        if d:
            self.out_var.set(d)

    def _open(self, name):
        open_path(self._out() / name)

    def refresh(self):
        if not self.available:
            return
        self.loaded = True
        rows, total = [], 0
        for f, label in SECTIONS:
            p = PAPER_SRC / f
            n = count_words(p.read_text(encoding="utf-8")) if p.exists() else 0
            total += n
            rows.append({tr("Section"): tr(label), tr("Words"): n})
        rows.append({tr("Section"): tr("Total"), tr("Words"): total})
        self.words.set_dataframe(pd.DataFrame(rows))
        abstract = rows[0][tr("Words")]
        self.words_note.configure(
            text=f"{tr('Abstract')}: {abstract} / 200 " + ("✓" if abstract <= 200 else "✗") + "   ·   " +
            tr("Text only: tables, figures and the reference list are not counted."),
            style="Ok.TLabel" if abstract <= 200 else "Bad.TLabel")
        files = sorted(PAPER_SRC.rglob("*")) if PAPER_SRC.is_dir() else []
        src = [{tr("File"): f.relative_to(PAPER_SRC).as_posix(),
                tr("Modified"): time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
                tr("Size, KB"): f.stat().st_size / 1024}
               for f in files if f.is_file() and "__pycache__" not in f.parts]
        self.sources.set_dataframe(pd.DataFrame(src), formats={tr("Size, KB"): ".1f"})

    # ---------------------------------------------------------------- commands
    def _commands(self, which):
        out = self._out()
        cmds = {"tables": python_command(PAPER_TOOLS / "make_tables.py"),
                "build": python_command(PAPER_TOOLS / "build_paper.py", out),
                "verify": python_command(PAPER_TOOLS / "verify_paper.py", out / "manuscript.docx",
                                         out / "supplementary.docx")}
        return [cmds[w] for w in which]

    def _run(self, name, which):
        self.check_label.configure(text="", style="Sub.TLabel")
        self.app.run_commands(name, self._commands(which), on_line=self._on_line,
                              on_finish=lambda codes, stopped: self.refresh())

    def _on_line(self, worker, text):
        m = re.search(r"(\d+)/(\d+) checks passed", text)
        if m:
            ok = m.group(1) == m.group(2)
            self.check_label.configure(text=tr("Check of the documents") + f": {m.group(0)}",
                                       style="Ok.TLabel" if ok else "Bad.TLabel")
        elif text.startswith("FAIL:"):
            self.check_label.configure(style="Bad.TLabel")

    def tables(self):
        self._run(tr("Generate the tables"), ["tables"])

    def build(self):
        self._run(tr("Build the documents"), ["build"])

    def verify(self):
        self._run(tr("Check the documents"), ["verify"])

    def build_all(self):
        self._run(tr("Build and check"), ["tables", "build", "verify"])
