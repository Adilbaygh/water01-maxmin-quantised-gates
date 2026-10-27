"""Reproducibility: environment record, pinned versions and numerical sensitivity of the closed loop."""
import json
from pathlib import Path

import pytest

from water01.optimization.lexlp import lp_options
from water01.simulation.provenance import environment_info, read_pins, write_metadata
from water01.simulation.runner import run_closed_loop_period
from water01.simulation.scenarios import load_config
from _inputs import DEM, SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_environment_and_pins(tmp_path):
    env = environment_info()
    assert {"python", "numpy", "scipy", "pandas", "highs", "platform", "water01"} <= set(env)
    pins = read_pins(ROOT / "requirements.txt")
    assert {"numpy", "scipy", "pandas", "PyYAML"} <= set(pins)
    out = tmp_path / "r.csv"; out.write_text("a\n1\n")
    meta = json.loads(write_metadata(out, ROOT, ("configs/kegeyli_reference.yaml",), {"x": 1}).read_text())
    assert len(meta["inputs"]["configs/kegeyli_reference.yaml"]) == 64 and meta["params"] == {"x": 1}


def test_lp_tolerances_are_tight():
    assert lp_options()["dual_feasibility_tolerance"] <= 1e-9 and lp_options()["primal_feasibility_tolerance"] <= 1e-9


@pytest.mark.parametrize("method", ["LXB", "B2"])
def test_closed_loop_is_not_sensitive_to_round_off(method):
    """Perturbing the initial level by 10⁻⁷ m (round-off level) changes λ in the untuned case by less than 10⁻⁴.
    Tied optima and end-of-day "borrowing from storage" can amplify such perturbations up to about 10⁻³."""
    cfg = load_config()
    args = (method, SUP, DEM,
            cfg, "2018-07-01", 2)
    a = run_closed_loop_period(*args, tuned=False)["lambda"]
    b = run_closed_loop_period(*args, tuned=False, h_init=3.0 + 1e-7)["lambda"]
    assert abs(a - b) < 1e-4
