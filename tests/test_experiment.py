"""Experiment pipeline: IoT scenarios and a single job (method × year × tuned × iot)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from water01.simulation.scenarios import AVAILABLE_FACTORS, iot_scenario, load_config
from _inputs import DEM, SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config()


def test_iot_scenarios_from_datasheet_and_manifest():
    phys = iot_scenario(CFG, ())
    assert phys.ideal
    full = iot_scenario(CFG, AVAILABLE_FACTORS)
    assert full.sensor_accuracy_m == pytest.approx(0.025) and full.sensor_resolution_m == 0.01   # EM500-SWL L005
    assert full.message_budget == CFG.message_budget_per_window and full.gate_resolution == CFG.gate_resolution_fraction
    assert full.energy and iot_scenario(CFG, ("energy",)).energy and not phys.energy   # (16) with NASA POWER
    assert set(AVAILABLE_FACTORS) == {"sensor", "quantisation", "communication", "energy"}


def test_single_experiment_job(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("run_experiment", ROOT / "scripts/run_experiment.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "OUT", tmp_path)
    monkeypatch.setattr(mod, "SUP", SUP); monkeypatch.setattr(mod, "DEM", DEM)
    monkeypatch.setattr(mod, "DATA", ("requirements/hypotheses.md", SUP.relative_to(ROOT).as_posix(),
                                      DEM.relative_to(ROOT).as_posix()))
    name, lam, _ = mod.run_job("B3", 2018, "untuned", "iot", start="2018-07-01", days=1)
    df = pd.read_csv(tmp_path / name)
    assert len(df) == 1 and abs(df["lambda"].iloc[0] - lam) < 1e-12
    assert {"r_Abad-Yarmish", "lost_K-2", "storage_change_share_season", "mass_error"} <= set(df.columns)
    assert (tmp_path / (name + ".meta.json")).exists()
    assert df.messages.iloc[0] >= 0 and df.battery_min_wh.iloc[0] > 0          # iot: the energy layer is active
