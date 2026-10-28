"""Main window of the interface: tabs, console of the running scripts, menus and status bar."""
from __future__ import annotations

import platform
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import APP_NAME, __version__, settings
from .i18n import LANGUAGES, language, set_language, tr
from .project import DOCS, RESULTS, ROOT, citation, git_state
from .tasks import TaskRunner
from .widgets import BAD_COLOUR, OK_COLOUR, PAD, WARN_COLOUR, Console, open_path, open_url


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = settings.load()
        set_language(self.settings.get("language", "en"))
        self.runner = TaskRunner(ROOT)
        self.bg = queue.Queue()
        self._busy = 0                      # background computations that show a busy text
        self.tabs = {}
        self._console_text = ""
        self._setup_style()
        geometry = self.settings.get("geometry") or ""
        if geometry:
            try:
                root.geometry(geometry)
            except tk.TclError:
                geometry = ""
        if not geometry:
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            w, h = min(int(sw * 0.92), 1760), min(int(sh * 0.86), 1080)
            root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        root.minsize(1000, 640)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build()
        self._poll()

    # ---------------------------------------------------------------- layout
    def _setup_style(self):
        style = ttk.Style(self.root)
        names = style.theme_names()
        for theme in (("vista", "xpnative") if sys.platform == "win32" else ()) + ("clam",):
            if theme in names:
                style.theme_use(theme)
                break
        base = tkfont.nametofont("TkDefaultFont")
        if sys.platform == "win32":
            base.configure(family="Segoe UI", size=10)
        else:
            base.configure(size=10)
        for name in ("TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=base.cget("family"), size=base.cget("size"))
            except tk.TclError:
                pass
        family = base.cget("family")
        style.configure("Title.TLabel", font=(family, 15, "bold"), foreground="#0b0b0b")
        style.configure("Sub.TLabel", foreground="#52514e")
        style.configure("Muted.TLabel", foreground="#8a8984")
        style.configure("Big.TLabel", font=(family, 20, "bold"), foreground="#0b0b0b")
        style.configure("Bold.TLabel", font=(family, 10, "bold"))
        style.configure("Ok.TLabel", foreground=OK_COLOUR)
        style.configure("Warn.TLabel", foreground=WARN_COLOUR)
        style.configure("Bad.TLabel", foreground=BAD_COLOUR)
        style.configure("Accent.TButton", font=(family, 10, "bold"))
        style.configure("Treeview", rowheight=int(base.metrics("linespace") * 1.45))
        style.configure("Treeview.Heading", font=(family, 10, "bold"))
        style.configure("TNotebook.Tab", padding=(12, 5))

    def build(self):
        """Creates (or, after a change of language, recreates) the menus and the tabs."""
        if hasattr(self, "console"):
            self._console_text = self.console.text.get("1.0", "end-1c")
        for child in self.root.winfo_children():
            child.destroy()
        self.tabs = {}
        info = citation()
        version = info.get("version", "")
        self.root.title(f"{APP_NAME} {version} — " + tr("Max–min water delivery through quantised gates"))
        self._menus()

        header = ttk.Frame(self.root, padding=(PAD * 2, PAD, PAD * 2, 0))
        header.pack(fill="x")
        lang = ttk.Frame(header)                       # packed first: stays visible in a narrow window
        lang.pack(side="right")
        ttk.Label(lang, text=tr("Language:"), style="Sub.TLabel").pack(side="left")
        self.lang_var = tk.StringVar(value=LANGUAGES[language()])
        box = ttk.Combobox(lang, textvariable=self.lang_var, values=list(LANGUAGES.values()), width=10,
                           state="readonly")
        box.pack(side="left", padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.set_language(
            next(k for k, v in LANGUAGES.items() if v == self.lang_var.get())))
        ttk.Label(header, text=info.get("title") or APP_NAME, style="Title.TLabel").pack(side="left")
        g = git_state()
        tag = g.get("tag") or ""
        bits = [f"v{version}" if version else "", "" if tag == f"v{version}" else tag, (g.get("commit") or "")[:7]]
        ttk.Label(header, text="  ".join(b for b in bits if b), style="Muted.TLabel").pack(side="left", padx=PAD * 2)

        # the status bar is packed before the panes, so that it keeps its place in a small window
        status = ttk.Frame(self.root, padding=(PAD * 2, 0, PAD * 2, 4))
        status.pack(fill="x", side="bottom")
        ttk.Label(status, text=f"{tr('Project folder')}: {ROOT}", style="Muted.TLabel").pack(side="left")
        ttk.Label(status, text=f"Python {platform.python_version()} · {APP_NAME} GUI {__version__}",
                  style="Muted.TLabel").pack(side="right")

        paned = ttk.Panedwindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=PAD, pady=PAD)
        self.notebook = ttk.Notebook(paned)
        from .tabs import TABS
        for key, label, cls in TABS:
            frame = cls(self.notebook, self)
            self.tabs[key] = frame
            self.notebook.add(frame, text=tr(label))
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        paned.add(self.notebook, weight=5)

        bottom = ttk.Frame(paned)
        bar = ttk.Frame(bottom)
        bar.pack(fill="x")
        ttk.Label(bar, text=tr("Console"), style="Bold.TLabel").pack(side="left")
        self.status_var = tk.StringVar(value=tr("Ready"))
        ttk.Label(bar, textvariable=self.status_var, style="Sub.TLabel").pack(side="left", padx=PAD * 2)
        self.progress = ttk.Progressbar(bar, length=160, mode="indeterminate")
        self.progress.pack(side="left")
        ttk.Button(bar, text=tr("Save log"), command=lambda: self.console.save()).pack(side="right")
        ttk.Button(bar, text=tr("Clear"), command=lambda: self.console.clear()).pack(side="right", padx=4)
        self.stop_button = ttk.Button(bar, text=tr("Stop"), command=self.stop_tasks, state="disabled")
        self.stop_button.pack(side="right", padx=4)
        self.console = Console(bottom, height=6)
        self.console.pack(fill="both", expand=True, pady=(4, 0))
        for line in self._console_text.splitlines():
            self.console.write(line)
        paned.add(bottom, weight=1)

        self.root.after(50, self._tab_changed)

    def _menus(self):
        menu = tk.Menu(self.root)
        f = tk.Menu(menu, tearoff=False)
        f.add_command(label=tr("Open project folder"), command=lambda: open_path(ROOT))
        f.add_command(label=tr("Open results folder"), command=lambda: open_path(RESULTS))
        f.add_separator()
        f.add_command(label=tr("Exit"), command=self.on_close)
        menu.add_cascade(label=tr("File"), menu=f)
        v = tk.Menu(menu, tearoff=False)
        self._lang_menu_var = tk.StringVar(value=language())
        for code, name in LANGUAGES.items():
            v.add_radiobutton(label=name, value=code, variable=self._lang_menu_var,
                              command=lambda c=code: self.set_language(c))
        v.add_separator()
        v.add_command(label=tr("Refresh the current tab"), command=self.refresh_current, accelerator="F5")
        menu.add_cascade(label=tr("View"), menu=v)
        h = tk.Menu(menu, tearoff=False)
        h.add_command(label="README", command=lambda: open_path(ROOT / "README.md"))
        h.add_command(label=tr("Design of the experiment"), command=lambda: open_path(DOCS / "EXPERIMENT.md"))
        h.add_command(label=tr("Hypotheses of the experiment (in Uzbek)"),
                      command=lambda: open_path(DOCS / "EXPECTED_OUTCOMES_uz.md"))
        repo = citation().get("repository-code")
        if repo:
            h.add_command(label=tr("Repository on GitHub"), command=lambda: open_url(repo))
        doi = citation().get("doi")
        if doi:
            h.add_command(label=tr("Archived version (Zenodo)") + f": {doi}",
                          command=lambda: open_url(f"https://doi.org/{doi}"))
        h.add_separator()
        h.add_command(label=tr("About"), command=self.about)
        menu.add_cascade(label=tr("Help"), menu=h)
        self.root.configure(menu=menu)
        self.root.bind("<F5>", lambda e: self.refresh_current())

    def _tab_changed(self, _=None):
        try:
            frame = self.root.nametowidget(self.notebook.select())
        except (KeyError, tk.TclError):
            return
        if hasattr(frame, "on_show"):
            try:
                frame.on_show()
            except Exception:  # noqa: BLE001 (report and keep the interface running)
                self.report_error(tr("The tab could not be shown"))

    def refresh_current(self):
        try:
            frame = self.root.nametowidget(self.notebook.select())
        except (KeyError, tk.TclError):
            return
        if hasattr(frame, "refresh"):
            frame.refresh()

    def set_language(self, code: str):
        if code == language():
            return
        if self.runner.busy():
            messagebox.showinfo(APP_NAME, tr("The language can be changed when no script is running."))
            self.lang_var.set(LANGUAGES[language()])
            self._lang_menu_var.set(language())
            return
        for tab in self.tabs.values():
            if hasattr(tab, "save_state"):
                try:
                    tab.save_state(self.settings)
                except Exception:  # noqa: BLE001 (the state of a tab is optional)
                    pass
        set_language(code)
        self.settings["language"] = code
        settings.save(self.settings)
        current = self.notebook.index(self.notebook.select()) if hasattr(self, "notebook") else 0
        self.build()
        self.notebook.select(current)

    def about(self):
        info = citation()
        authors = ", ".join(f"{a.get('given-names', '')} {a.get('family-names', '')}".strip()
                            for a in info.get("authors", []) if isinstance(a, dict))
        doi = f"\nDOI: {info['doi']}" if info.get("doi") else ""
        messagebox.showinfo(
            tr("About"),
            f"{info.get('title', APP_NAME)}\n{tr('Version')} {info.get('version', '')}{doi}\n\n{authors}\n\n"
            f"{tr('Graphical interface')} {__version__}\n{tr('Code: MIT licence; data and results: CC BY 4.0.')}")

    # ---------------------------------------------------------------- background work
    def background(self, func, on_done=None, on_error=None, busy_text=None):
        """Runs func() in a worker thread; on_done(result) or on_error(exception) run in the interface thread."""
        if busy_text:
            self._busy += 1
            self.status_var.set(busy_text)
            self.root.configure(cursor="watch")

        def work():
            try:
                self.bg.put((on_done, func(), None, busy_text))
            except Exception as e:  # noqa: BLE001
                self.bg.put((on_error, None, (e, traceback.format_exc()), busy_text))
        threading.Thread(target=work, daemon=True).start()

    def run_commands(self, name, commands, parallel=False, on_line=None, on_finish=None):
        """Runs commands (lists of arguments) in separate processes; the output goes to the console."""
        if self.runner.busy():
            self.console.write(f"… {tr('queued')}: {name}", "info")
        return self.runner.submit(name, commands, parallel, on_line, on_finish)

    def stop_tasks(self):
        if self.runner.busy() and messagebox.askyesno(APP_NAME, tr("Stop the running script?")):
            self.runner.stop()
            self.console.write(tr("Stopped by the user."), "error")

    def report_error(self, title, exc_info=None):
        text = exc_info if isinstance(exc_info, str) else traceback.format_exc()
        self.console.write(f"{title}:", "error")
        for line in text.rstrip().splitlines():
            self.console.write(line, "error")
        last = text.strip().splitlines()[-1] if text.strip() else ""
        messagebox.showerror(APP_NAME, f"{title}\n\n{last}")

    def _poll(self):
        try:
            for ev in self.runner.poll():
                kind, g = ev[0], ev[1]
                if kind == "start":
                    self.console.write(f"== {g.name} ==", "title")
                    self.progress.start(12)
                    self.stop_button.configure(state="normal")
                elif kind == "line":
                    worker, text = ev[2], ev[3]
                    several = g.parallel and len(g.commands) > 1 and not text.startswith("$")
                    prefix = f"[{worker + 1}] " if several else ""
                    self.console.write(prefix + text)
                    if g.on_line:
                        self._callback(g.on_line, worker, text)
                elif kind == "finish":
                    codes = list(g.returncodes.values())
                    ok = not g.stopped and all(c == 0 for c in codes)
                    secs = time.time() - g.started
                    msg = (tr("finished") if ok else (tr("stopped") if g.stopped else tr("finished with errors")))
                    self.console.write(f"== {g.name}: {msg} ({_duration(secs)}) ==", "ok" if ok else "error")
                    if g.on_finish:
                        self._callback(g.on_finish, codes, g.stopped)
            if self.runner.current is not None:
                self.status_var.set(f"{self.runner.current.name} · {_duration(self.runner.elapsed())}")
            elif not self.runner.busy():
                self.progress.stop()
                self.stop_button.configure(state="disabled")
            while True:
                try:
                    cb, res, err, busy_text = self.bg.get_nowait()
                except queue.Empty:
                    break
                if busy_text:
                    self._busy = max(0, self._busy - 1)
                    if not self._busy:
                        self.root.configure(cursor="")
                if err is not None:
                    if cb:
                        self._callback(cb, err[0])
                    else:
                        self.report_error(tr("Error"), err[1])
                elif cb:
                    self._callback(cb, res)
            if self.runner.current is None and not self._busy and self.status_var.get() != tr("Ready"):
                self.status_var.set(tr("Ready"))
        except tk.TclError:
            pass
        self.root.after(100, self._poll)

    def _callback(self, func, *args):
        """Calls a function of a tab; a tab replaced after a change of language is ignored."""
        try:
            func(*args)
        except tk.TclError:
            pass
        except Exception:  # noqa: BLE001 (report and keep the interface running)
            self.report_error(tr("Error"))

    def on_close(self):
        if self.runner.busy():
            if not messagebox.askyesno(APP_NAME, tr("A script is still running. Stop it and exit?")):
                return
            self.runner.stop()
        self.settings["geometry"] = self.root.geometry()
        self.settings["language"] = language()
        for tab in self.tabs.values():
            if hasattr(tab, "save_state"):
                try:
                    tab.save_state(self.settings)
                except Exception:  # noqa: BLE001
                    pass
        settings.save(self.settings)
        self.root.destroy()


def _duration(seconds: float) -> str:
    seconds = int(seconds)
    s, m, h = tr("s"), tr("min"), tr("h")
    if seconds < 60:
        return f"{seconds} {s}"
    if seconds < 3600:
        return f"{seconds // 60} {m} {seconds % 60:02d} {s}"
    return f"{seconds // 3600} {h} {seconds % 3600 // 60:02d} {m}"


def main():
    root = tk.Tk()
    try:
        root.tk.call("tk", "appname", APP_NAME)
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
