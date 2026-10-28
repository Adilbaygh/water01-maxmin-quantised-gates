"""Water-01: max-min water delivery through quantised gates at the Dustlik node of the Kegeyli canal.

Graphical interface of the project:

    python main.py               start the interface
    python main.py --lang uz     start it in Uzbek (the choice is remembered)
    python main.py --check       check the environment, the simulation core and the stored results in the terminal

The interface needs the packages of requirements.txt and Tkinter, which is part of the standard Python installers
for Windows and macOS (on Linux: the package python3-tk).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = ("numpy", "scipy", "pandas", "yaml", "matplotlib")


def missing_modules() -> list[str]:
    import importlib.util
    return [m for m in REQUIRED + ("tkinter",) if importlib.util.find_spec(m) is None]


def check() -> int:
    """Environment, simulation core and stored results, printed in the terminal."""
    sys.path.insert(0, str(ROOT))
    from gui.project import citation, environment, inventory, verify_core_manifest
    info = citation()
    print(f"{info.get('title', 'Water-01')} {info.get('version', '')}")
    print(f"Project folder: {ROOT}\n")
    status = 0
    words = {"ok": "ok", "different": "other version", "old": "too old", "missing": "missing",
             "optional": "not installed (optional)"}
    for name, have, need, state in environment():
        print(f"  {words[state]:24s} {name:12s} {have:12s} expected {need}")
        status |= state in ("old", "missing")
    n, bad = verify_core_manifest()
    differences = f"{len(bad)} differ: " + ", ".join(bad) if bad else "no differences"
    print(f"\nSimulation core: {n} files, {differences}")
    status |= bool(bad)
    jobs = inventory()
    states = {}
    for j in jobs:
        states[j.state] = states.get(j.state, 0) + 1
    print("Stored seasons: " + ", ".join(f"{k} {v}" for k, v in sorted(states.items())) + f" (of {len(jobs)})")
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Graphical interface of the Water-01 project.")
    ap.add_argument("--check", action="store_true",
                    help="check the environment and the stored results, without the interface")
    ap.add_argument("--lang", choices=("en", "uz"), help="language of the interface (remembered)")
    args = ap.parse_args()

    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is needed (the results were computed with Python 3.13).")
        return 1
    missing = missing_modules()
    if args.check:
        if set(missing) - {"tkinter"}:
            print("Missing packages: " + ", ".join(sorted(set(missing) - {"tkinter"})))
            print("Install them with:  python -m pip install -r requirements.txt")
            return 1
        return check()
    if missing:
        print("The interface cannot start. Missing: " + ", ".join(missing))
        if "tkinter" in missing:
            print("Tkinter is part of the standard installers of Python for Windows and macOS (option 'tcl/tk and "
                  "IDLE'); on Linux install the package python3-tk.")
        if set(missing) - {"tkinter"}:
            print("Install the packages with:  python -m pip install -r requirements.txt")
        return 1

    if sys.platform == "win32":
        try:                                              # sharp text on high-resolution screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    sys.path.insert(0, str(ROOT))
    if args.lang:
        from gui import settings
        data = settings.load()
        data["language"] = args.lang
        settings.save(data)
    from gui.app import main as start
    start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
