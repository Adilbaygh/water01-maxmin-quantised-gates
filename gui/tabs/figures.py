"""Figures: the figures in results/figures (Figures 1-5 of the article and two separate panels of Figure 5),
shown scaled to the window."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..i18n import tr
from ..project import FIGURES, SCRIPTS
from ..tasks import python_command
from ..widgets import PAD, open_path

# the figures of the article, in their order, with the first sentences of their captions
ARTICLE = ("fig_schematic", "fig_exclusion", "fig_theta", "fig_equal_split", "fig_carryover")
CAPTIONS = {
    "fig_schematic": "Quantised gate and execution rules (abstract actuator, constant level, k = 5): (a) one step "
                     "from a closed gate; (b) one day of N = 96 steps.",
    "fig_exclusion": "Daily plan of each regulator in units of its quantum at the lowest level of the day under "
                     "direct execution, 2010–2019: deadband 0.5% (k = 5), 0.25% (k = 3) and 1% (k = 10).",
    "fig_theta": "Error of the pulse rule on the regulator-days operated by pulses only, for θ = 0, 0.25, 0.5 and "
                 "0.75, with the bounds of Theorem 3.",
    "fig_equal_split": "Daily error of the equal split and of the pulse rule with θ = 0.5 on the same regulator-days, "
                       "with the bound of Theorem 1(b).",
    "fig_carryover": "Carry-over and accounting periods at R-1: (a) daily satisfaction in 1–12 April 2010; (b) error "
                     "of the delivery over accounting periods of T days.",
    "fig_april": "Not in the article: panel (a) of Figure 5 as a separate figure (satisfaction of R-1 in 1–12 April "
                 "2010).",
    "fig_periods": "Not in the article: panel (b) of Figure 5 as a separate figure (error over accounting periods at "
                   "R-1); the colours of the rules differ from Figure 5.",
}


class FiguresTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD)
        self.app = app
        self.loaded = False
        self.image = None
        self.photo = None
        self.files = []

        left = ttk.Frame(self, padding=(0, 0, PAD * 2, 0))
        left.pack(side="left", fill="y")
        ttk.Label(left, text=tr("Figures"), style="Bold.TLabel").pack(anchor="w")
        self.listbox = tk.Listbox(left, width=30, height=14, exportselection=False, activestyle="none")
        self.listbox.pack(fill="y", expand=True, pady=(4, PAD))
        self.listbox.bind("<<ListboxSelect>>", lambda e: self.show())
        ttk.Button(left, text=tr("Open"), command=self.open_current).pack(fill="x", pady=2)
        ttk.Button(left, text=tr("Open the folder"), command=lambda: open_path(FIGURES)).pack(fill="x", pady=2)
        ttk.Button(left, text=tr("Recreate the figures"), command=self.recreate).pack(fill="x", pady=(PAD, 2))

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        self.caption = ttk.Label(right, text="", style="Sub.TLabel", wraplength=900, justify="left")
        self.caption.pack(anchor="w", pady=(0, PAD))
        self.canvas = tk.Canvas(right, background="white", highlightthickness=1, highlightbackground="#dddddd")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._render())

    def on_show(self):
        if not self.loaded:
            self.refresh()

    def refresh(self):
        self.loaded = True
        self.files = sorted(FIGURES.glob("*.png")) if FIGURES.is_dir() else []
        current = self.listbox.curselection()
        self.listbox.delete(0, "end")
        order = list(CAPTIONS)
        self.files.sort(key=lambda f: (order.index(f.stem) if f.stem in order else 99, f.name))
        for f in self.files:
            self.listbox.insert("end", self._title(f.stem))
        if self.files:
            self.listbox.selection_set(current[0] if current and current[0] < len(self.files) else 0)
            self.show()
        else:
            self.caption.configure(text=tr("No figures in results/figures; recreate them first."))

    @staticmethod
    def _title(stem):
        if stem in ARTICLE:
            return tr("Figure {n}").format(n=ARTICLE.index(stem) + 1) + f" — {stem}"
        return tr("Extra") + f" — {stem}"

    def _current(self):
        sel = self.listbox.curselection()
        return self.files[sel[0]] if sel else None

    def show(self):
        f = self._current()
        if f is None:
            return
        from PIL import Image
        self.image = Image.open(f)
        self.image.load()
        size = f"   ({self.image.width} × {self.image.height} px)"
        head = tr("Figure {n}").format(n=ARTICLE.index(f.stem) + 1) + ". " if f.stem in ARTICLE else ""
        self.caption.configure(text=head + tr(CAPTIONS.get(f.stem, f.name)) + size)
        self._render()

    def _render(self):
        if self.image is None:
            return
        from PIL import Image, ImageTk
        w, h = max(self.canvas.winfo_width() - 8, 50), max(self.canvas.winfo_height() - 8, 50)
        scale = min(w / self.image.width, h / self.image.height, 1.0)
        size = (max(1, int(self.image.width * scale)), max(1, int(self.image.height * scale)))
        self.photo = ImageTk.PhotoImage(self.image.resize(size, Image.LANCZOS))
        self.canvas.delete("all")
        self.canvas.create_image(w // 2 + 4, h // 2 + 4, image=self.photo, anchor="center")

    def open_current(self):
        f = self._current()
        if f is not None:
            open_path(f)

    def recreate(self):
        self.app.run_commands(tr("Recreate the figures"), [python_command(SCRIPTS / "make_figures.py")],
                              on_finish=lambda *a: self.refresh())
