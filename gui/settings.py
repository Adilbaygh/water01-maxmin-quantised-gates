"""Settings of the interface, kept in the home folder of the user (~/.water01_gui.json)."""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path.home() / ".water01_gui.json"
DEFAULTS = {
    "language": "en",
    "geometry": "",
    "workers": 1,
    "paper_out": "",
    "results": {},
    "theory": {},
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):          # known keys with the type of their default only
            data.update({k: v for k, v in stored.items() if k in DEFAULTS and type(v) is type(DEFAULTS[k])})
    except (OSError, ValueError):
        pass
    return data


def save(data: dict) -> None:
    try:
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
