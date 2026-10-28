"""Background processes: the scripts of the project run in separate Python processes, so that the interface stays
responsive and a run can be stopped. Output lines are collected in a queue that the interface polls."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Group:
    """Commands submitted together: run one after another, or all at once (parallel workers)."""
    name: str
    commands: list[list[str]]
    parallel: bool = False
    on_line: object = None          # callable(worker, text) called in the interface thread
    on_finish: object = None        # callable(returncodes, stopped) called in the interface thread
    started: float = 0.0
    procs: list = field(default_factory=list)
    returncodes: dict = field(default_factory=dict)
    next_index: int = 0
    stopped: bool = False


class TaskRunner:
    """Runs one group of commands at a time; further groups wait in a queue. poll() must be called periodically from
    the interface thread; it returns the events since the previous call."""

    def __init__(self, cwd: Path):
        self.cwd = Path(cwd)
        self.lines: queue.Queue = queue.Queue()
        self.pending: list[Group] = []
        self.current: Group | None = None

    # ---------------------------------------------------------------- public
    def submit(self, name, commands, parallel=False, on_line=None, on_finish=None) -> Group:
        g = Group(name, [list(map(str, c)) for c in commands], parallel, on_line, on_finish)
        self.pending.append(g)
        return g

    def busy(self) -> bool:
        return self.current is not None or bool(self.pending)

    def stop(self) -> None:
        """Stops the running group and removes the waiting ones."""
        self.pending.clear()
        g = self.current
        if g is None:
            return
        g.stopped = True
        g.next_index = len(g.commands)
        for p in g.procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except OSError:
                    pass

    def elapsed(self) -> float:
        return time.time() - self.current.started if self.current else 0.0

    def poll(self) -> list[tuple]:
        """Events: ('start', group), ('line', group, worker, text), ('finish', group)."""
        events = []
        if self.current is None and self.pending:
            self.current = self.pending.pop(0)
            self.current.started = time.time()
            events.append(("start", self.current))
            self._launch_next()
        while True:
            try:
                kind, gid, worker, payload = self.lines.get_nowait()
            except queue.Empty:
                break
            g = self.current
            if g is None or id(g) != gid:
                continue
            if kind == "line":
                events.append(("line", g, worker, payload))
            elif kind == "exit":
                g.returncodes[worker] = payload
                if not g.parallel and not g.stopped:
                    if payload != 0 and g.next_index < len(g.commands):
                        g.next_index = len(g.commands)       # a later command needs the output of this one
                        events.append(("line", g, worker, "The remaining commands were not run after this error."))
                    self._launch_next()
        g = self.current
        if g is not None and g.next_index >= len(g.commands) and all(p.poll() is not None for p in g.procs) \
                and len(g.returncodes) == len(g.procs):
            events.append(("finish", g))
            self.current = None
        return events

    # ---------------------------------------------------------------- internal
    def _launch_next(self):
        g = self.current
        if g.parallel:
            while g.next_index < len(g.commands):
                self._spawn(g, g.next_index)
                g.next_index += 1
        elif g.next_index < len(g.commands):
            self._spawn(g, g.next_index)
            g.next_index += 1

    def _spawn(self, g: Group, worker: int):
        env = dict(os.environ)
        env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        cmd = g.commands[worker]
        self.lines.put(("line", id(g), worker, "$ " + " ".join(_quote(c) for c in cmd)))
        try:
            p = subprocess.Popen(cmd, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
                                 env=env, creationflags=flags)
        except OSError as e:
            self.lines.put(("line", id(g), worker, f"ERROR: {e}"))
            g.procs.append(_Finished())
            self.lines.put(("exit", id(g), worker, -1))
            return
        g.procs.append(p)
        threading.Thread(target=self._read, args=(g, worker, p), daemon=True).start()

    def _read(self, g: Group, worker: int, p: subprocess.Popen):
        try:
            for line in p.stdout:
                self.lines.put(("line", id(g), worker, line.rstrip("\r\n")))
        except (OSError, ValueError):
            pass
        rc = p.wait()
        self.lines.put(("exit", id(g), worker, rc))


class _Finished:
    """Placeholder for a command that could not be started."""

    def poll(self):
        return -1

    def terminate(self):
        pass


def _quote(s: str) -> str:
    return f'"{s}"' if " " in s else s


PYTHON_FLAGS = ("-u",)      # unbuffered output, so that progress lines arrive at once


def python_command(script: Path, *args) -> list[str]:
    """A command that runs a script of the project with the interpreter of the interface, as it is run by hand from the
    project folder (the scripts add src/ and scripts/ to the import path themselves)."""
    return [_interpreter(), *PYTHON_FLAGS, str(script), *map(str, args)]


def python_module(module: str, *args) -> list[str]:
    return [_interpreter(), *PYTHON_FLAGS, "-m", module, *map(str, args)]


def _interpreter() -> str:
    """The console interpreter: pythonw.exe (no console) cannot show the output of the scripts on all systems."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return str(exe)
