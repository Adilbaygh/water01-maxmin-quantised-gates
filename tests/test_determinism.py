"""§2.10 (9): identical inputs give identical results."""
from pathlib import Path
from water01.simulation.runner import run_smoke
from _inputs import DEM, SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_smoke_is_deterministic():
    a = run_smoke(SUP, DEM)
    b = run_smoke(SUP, DEM)
    assert a == b
