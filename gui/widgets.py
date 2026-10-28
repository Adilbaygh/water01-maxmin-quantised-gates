"""Reusable widgets of the interface: console, table, plot panel, tooltips and helpers."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .i18n import tr  # noqa: E402

# categorical colours of the plots, assigned in this fixed order (adjacent pairs validated for colour-vision
# deficiencies); text stays in the text colours
PALETTE = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TEXT, TEXT2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
OK_COLOUR, WARN_COLOUR, BAD_COLOUR = "#1b7e3c", "#a35c00", "#c62828"
PAD = 6

# lines of the scripts shown as errors or successes in the console
_ERROR_LINE = re.compile(r"^(Traceback|ERROR|FAILED|FAIL:|\w*(Error|Exception):)|\b[1-9]\d* (failed|errors?)\b")
_OK_LINE = re.compile(r"^(DONE|OK\b|ok\b)|\b\d+ passed\b|checks passed")


def open_path(path: Path) -> None:
    """Opens a file or folder with the default application of the system."""
    path = Path(path)
    if not path.exists():
        messagebox.showwarning("Water-01", tr("Not found:") + f"\n{path}")
        return
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 (opens a file of the project)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as e:
        messagebox.showerror("Water-01", str(e))


def open_url(url: str) -> None:
    import webbrowser
    webbrowser.open(url)


class Tooltip:
    """A short explanation shown when the pointer rests on a widget."""

    def __init__(self, widget, text: str, delay: int = 600):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _):
        self._cancel()
        self.job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", background="#fffbe6", foreground="#222",
                 relief="solid", borderwidth=1, wraplength=420, padx=6, pady=4).pack()

    def _hide(self, _=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class Console(ttk.Frame):
    """Output of the scripts and messages of the interface."""

    def __init__(self, master, height=10):
        super().__init__(master)
        self.text = tk.Text(self, height=height, wrap="none", font=("Consolas", 9) if sys.platform == "win32"
                            else ("DejaVu Sans Mono", 9), background="#fbfbfb", relief="flat", undo=False)
        ys = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set, state="disabled")
        self.text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        for tag, colour in (("cmd", "#2a6fdb"), ("error", BAD_COLOUR), ("ok", OK_COLOUR), ("info", "#555555")):
            self.text.tag_configure(tag, foreground=colour)
        bold = tkfont.Font(font=self.text.cget("font"))
        bold.configure(weight="bold")
        self.text.tag_configure("title", font=bold)
        self._bold = bold

    def write(self, line: str, tag: str | None = None) -> None:
        if tag is None:
            if line.startswith("$ "):
                tag = "cmd"
            elif _ERROR_LINE.search(line):
                tag = "error"
            elif _OK_LINE.search(line):
                tag = "ok"
        at_end = self.text.yview()[1] > 0.98
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n", tag or ())
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > 20000:
            self.text.delete("1.0", f"{lines - 20000}.0")
        self.text.configure(state="disabled")
        if at_end:
            self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def save(self) -> None:
        f = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[(tr("Text"), "*.txt")])
        if f:
            Path(f).write_text(self.text.get("1.0", "end-1c"), encoding="utf-8")


class DataTable(ttk.Frame):
    """A table with sortable columns and an optional filter; Ctrl+C copies the selected rows."""

    def __init__(self, master, height=12, filter_box=True):
        super().__init__(master)
        self.df = None
        self.view = None
        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.info = ttk.Label(top, text="", foreground="#555")
        self.info.pack(side="right", padx=PAD)
        self.filter_var = tk.StringVar()
        if filter_box:
            ttk.Label(top, text=tr("Filter:")).pack(side="left")
            e = ttk.Entry(top, textvariable=self.filter_var, width=30)
            e.pack(side="left", padx=(4, 0), pady=(0, 4))
            self.filter_var.trace_add("write", lambda *_: self._fill())
        self.tree = ttk.Treeview(self, show="headings", height=height, selectmode="extended")
        ys = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        ys.grid(row=1, column=1, sticky="ns")
        xs.grid(row=2, column=0, sticky="ew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind("<Control-c>", self._copy)
        self.tree.bind("<Double-1>", self._details)
        self.tree.tag_configure("odd", background="#f5f7fa")
        self.sort_col, self.sort_desc = None, False
        self.formats = {}
        self.max_rows = 5000

    def set_dataframe(self, df, formats: dict | None = None, widths: dict | None = None, max_rows=5000):
        import pandas as pd
        self.df = df.reset_index(drop=True) if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
        self.df.columns = [str(c) for c in self.df.columns]
        self.formats = formats or {}
        self.max_rows = max_rows
        cols = list(self.df.columns)
        self.tree.configure(columns=cols)
        body, head = _table_fonts()
        for c in cols:
            self.tree.heading(c, text=c, command=lambda c=c: self._sort(c))
            w = (widths or {}).get(c)
            if w is None:
                cells = {self._cell(c, v) for v in self.df[c].head(300)}
                longest = sorted(cells, key=len, reverse=True)[:8]
                w = max([head.measure(c) + 22] + [body.measure(s) + 16 for s in longest])
                w = min(w, max(420, head.measure(c) + 22))
            self.tree.column(c, width=w, minwidth=40, stretch=False, anchor="w")
        self.sort_col, self.sort_desc = None, False
        self._fill()

    def _cell(self, col, v):
        import math
        if v is None:
            return ""
        if isinstance(v, float):
            if math.isnan(v):
                return ""
            fmt = self.formats.get(col)
            return format(v, fmt) if fmt else f"{v:.6g}"
        return str(v)

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        if self.df is None:
            return
        df = self.df
        q = self.filter_var.get().strip().lower()
        if q:
            mask = df.astype(str).apply(lambda col: col.str.lower().str.contains(q, regex=False)).any(axis=1)
            df = df[mask]
        if self.sort_col is not None:
            try:
                df = df.sort_values(self.sort_col, ascending=not self.sort_desc, kind="mergesort")
            except TypeError:                               # mixed types: sort by the shown text
                df = df.sort_values(self.sort_col, ascending=not self.sort_desc, kind="mergesort",
                                    key=lambda col: col.astype(str))
        self.view = df
        for i, (_, row) in enumerate(df.head(self.max_rows).iterrows()):
            self.tree.insert("", "end", values=[self._cell(c, row[c]) for c in df.columns],
                             tags=("odd",) if i % 2 else ())
        shown = min(len(df), self.max_rows)
        self.info.configure(text=f"{shown} / {len(self.df)} " + tr("rows"))

    def _sort(self, col):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = col, False
        for c in self.tree["columns"]:
            mark = (" ↓" if self.sort_desc else " ↑") if c == col else ""
            self.tree.heading(c, text=c + mark)
        self._fill()

    def _copy(self, _=None):
        rows = [self.tree.item(i, "values") for i in self.tree.selection()]
        if not rows:
            return
        cols = self.tree["columns"]
        text = "\t".join(cols) + "\n" + "\n".join("\t".join(map(str, r)) for r in rows)
        self.clipboard_clear()
        self.clipboard_append(text)

    def _details(self, event=None):
        """All values of a row, in full, in a separate window (double click)."""
        item = self.tree.identify_row(event.y) if event is not None else (self.tree.focus() or "")
        if not item:
            return
        values = self.tree.item(item, "values")
        win = tk.Toplevel(self)
        win.title(tr("Row"))
        text = tk.Text(win, width=100, height=min(30, len(values) + 1), wrap="word", relief="flat",
                       background="#fbfbfb", padx=8, pady=6)
        text.pack(fill="both", expand=True)
        text.tag_configure("key", font=_table_fonts()[1])
        for col, val in zip(self.tree["columns"], values):
            text.insert("end", f"{col}: ", "key")
            text.insert("end", f"{val}\n")
        text.configure(state="disabled")
        ttk.Button(win, text=tr("Close"), command=win.destroy).pack(pady=4)
        win.bind("<Escape>", lambda e: win.destroy())

    def export_csv(self):
        if self.view is None:
            return
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if f:
            self.view.to_csv(f, index=False)


class PlotPanel(ttk.Frame):
    """A matplotlib figure with the navigation toolbar (zoom, pan, save)."""

    def __init__(self, master, figsize=(8, 5), toolbar=True):
        super().__init__(master)
        self.figure = Figure(figsize=figsize, dpi=96, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        widget = self.canvas.get_tk_widget()
        widget.configure(background="white", highlightthickness=0)
        if toolbar:
            bar = ttk.Frame(self)
            bar.pack(side="bottom", fill="x")
            self.toolbar = NavigationToolbar2Tk(self.canvas, bar, pack_toolbar=False)
            self.toolbar.update()
            self.toolbar.pack(side="left", fill="x")
        widget.pack(side="top", fill="both", expand=True)

    def clear(self):
        self.figure.clear()

    def draw(self):
        self.canvas.draw_idle()

    def message(self, text: str):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color="#555", wrap=True,
                transform=ax.transAxes)
        self.draw()


def style_axes(ax, xlabel=None, ylabel=None, title=None):
    """Recessive grid and axes, labels in text colour."""
    ax.grid(True, color="#e3e3e3", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#9a9a9a")
    ax.tick_params(colors="#444", labelsize=9)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color="#333")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color="#333")
    if title:
        ax.set_title(title, fontsize=10, color="#222", loc="left")


def labelled(master, text, widget_factory, row, column=0, tooltip=None, **grid):
    """A label and a widget on one row of a grid; returns the widget."""
    lab = ttk.Label(master, text=text)
    lab.grid(row=row, column=column, sticky="w", padx=(0, PAD), pady=3)
    w = widget_factory(master)
    w.grid(row=row, column=column + 1, sticky="ew", pady=3, **grid)
    if tooltip:
        Tooltip(lab, tooltip)
        Tooltip(w, tooltip)
    return w


def _table_fonts():
    """Fonts of the rows and of the headings of the tables, for the widths of the columns."""
    body = tkfont.nametofont("TkDefaultFont")
    head = tkfont.Font(font=body)
    head.configure(weight="bold")
    return body, head


_SCROLL_FRAMES: list = []
_WHEEL_BOUND = False


def _wheel(event):
    """Mouse wheel over a scrollable frame (one binding for all of them)."""
    for sf in list(_SCROLL_FRAMES):
        try:
            if not sf.winfo_exists():
                _SCROLL_FRAMES.remove(sf)
                continue
            w = sf.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, KeyError):
            continue
        while w is not None:
            if w is sf:
                sf.scroll(event)
                return
            w = getattr(w, "master", None)


class ScrollFrame(ttk.Frame):
    """A vertically scrollable frame for long forms; as wide as its content."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        global _WHEEL_BOUND
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, yscrollincrement=20)
        self.ys = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", self._inner_changed)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.ys.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.ys.pack(side="right", fill="y")
        if not _WHEEL_BOUND:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.bind_all(seq, _wheel, add="+")
            _WHEEL_BOUND = True
        _SCROLL_FRAMES.append(self)

    def _inner_changed(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"), width=self.inner.winfo_reqwidth())

    def scroll(self, event):
        if self.canvas.yview() == (0.0, 1.0):
            return
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-3, "units")
        else:
            self.canvas.yview_scroll(3, "units")
