"""Descriptive sensitivity cases: scenario files, the intraday supply ramp, and the source of the supply forecast."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from water01.domain.config import CONFIG_DIR, load  # noqa: E402
from water01.domain.geometry import Reach  # noqa: E402
from water01.hydraulics.node import DustlikNode  # noqa: E402
from water01.simulation.plant_loop import CanalPlant  # noqa: E402
from water01.simulation.runner import select_limit  # noqa: E402
from water01.simulation.scenarios import load_config, load_supply  # noqa: E402
from _inputs import SUP, requires_records  # noqa: E402


def test_every_sensitivity_case_has_a_scenario_file():
    from run_experiment import SENSITIVITY
    for case, iots in SENSITIVITY.items():
        assert (CONFIG_DIR / "scenarios" / f"{case}.yaml").exists(), case
        assert set(iots) <= {"phys", "iot"} and iots
        assert load(scenario=case).scenario == case


def _plant(S):
    return CanalPlant(Reach(), DustlikNode(), S, 0.82, 3.0, 900.0, 96, 0.6, np.random.default_rng(0))


def test_ramp_zero_keeps_step_change_and_ramp_is_linear():
    load_config()                                                   # baseline: supply_ramp_hours = 0
    S = np.array([40.0, 80.0])
    p = _plant(S)
    assert p.inflow(86400.0 + 900.0) == 80.0 and p.inflow(3600.0) == 40.0
    load_config(scenario="supply_ramp")                             # 6 h
    p = _plant(S)
    assert p.inflow(86400.0 + 3 * 3600.0) == pytest.approx(60.0)
    assert p.inflow(86400.0 + 6 * 3600.0) == pytest.approx(80.0) and p.inflow(86400.0 + 12 * 3600.0) == 80.0
    assert p.inflow(3600.0) == 40.0                                 # first day: no previous day
    load_config()


@requires_records
def test_limit_source_switches_forecast():
    sup = load_supply(SUP)
    load_config()
    base = select_limit(sup)
    load_config(scenario="limit_2021")
    alt = select_limit(sup)
    load_config()
    assert len(base) == len(alt) == 18
    assert alt.set_index(["month", "decade"]).S_lim_m3s.loc[(4, 1)] == 35.0
    assert not np.allclose(base.S_lim_m3s.to_numpy(), alt.S_lim_m3s.to_numpy())


@pytest.mark.parametrize("path", sorted((CONFIG_DIR / "scenarios").glob("*.yaml")), ids=lambda p: p.stem)
def test_scenario_levels_are_consistent(path):
    """Level order in every scenario: H_min <= H_norm < relief release < relief opening <= H_max."""
    cfg = load(scenario=path.stem)
    v = cfg.value
    assert v("H_min_m") <= v("H_norm_m") < v("relief_release_level_m") < v("relief_open_level_m") <= v("H_max_m")
    assert v("rtu_low_level_interlock_m") < v("H_min_m")
