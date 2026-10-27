"""Configuration (configs/*.yaml): all parameters are in YAML, scenarios change only known parameters,
and a change reaches every module."""
import ast
from pathlib import Path

import pytest

from water01.domain.config import CONFIG_DIR, STATUSES, activate, load
from water01.domain.geometry import Reach
from water01.hydraulics.node import DustlikNode
from water01.simulation.scenarios import AVAILABLE_FACTORS, iot_scenario, load_config

ROOT = Path(__file__).resolve().parents[1]
# Required: geometry, dt/horizon, θ, gate limits, deadband/quantisation, energy, fairness tolerances, hypothesis tests.
REQUIRED = {
    "L_m", "b_actual_m", "side_slope", "S0", "n_manning", "H_max_m", "H_norm_m", "H_min_m",
    "dt_s", "steps_per_day", "horizon_days", "season_days", "preissmann_theta", "preissmann_nodes",
    "outlet_capacity_m3s", "regulator_gate_height_m", "barrier_gate_height_m", "gate_rate_fraction_per_step",
    "gate_resolution_fraction", "gate_deadband_fraction", "battery_capacity_wh", "battery_eta_ch",
    "battery_eta_dis", "epsilon_1", "epsilon_2", "epsilon_lambda", "alpha", "min_sign_share", "holm_families"}


def teardown_function():
    activate(load())


def test_reference_has_all_required_parameters_with_status():
    cfg = load()
    assert REQUIRED <= set(cfg.params)
    assert all(p.status in STATUSES for p in cfg.params.values())


@pytest.mark.parametrize("path", sorted((CONFIG_DIR / "scenarios").glob("*.yaml")), ids=lambda p: p.stem)
def test_every_scenario_loads(path):
    cfg = load(scenario=path.stem)
    assert cfg.scenario == path.stem


def test_unknown_override_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"; bad.write_text("overrides:\n  no_such_parameter: 1\n")
    with pytest.raises(KeyError):
        load(scenario=str(bad))


def test_scenario_reaches_every_module():
    load_config(scenario="design_geometry")
    assert Reach().b == 28.0 and Reach().n == 0.0193
    cfg = load_config(scenario="communication_loss")
    io = iot_scenario(cfg, AVAILABLE_FACTORS)
    assert io.loss_probability == 0.10 and io.message_budget == 4
    cfg = load_config(scenario="sensor_udl")
    assert iot_scenario(cfg, ("sensor",)).sensor_resolution_m == 0.001
    load_config()
    assert Reach().b == 36.0 and DustlikNode().cd == 0.62


def test_no_physical_constants_in_module_defaults():
    """Function and dataclass defaults contain no physical parameters (e.g. 36.0, 0.0185, 11440, 0.62)."""
    forbidden = {36.0, 0.0185, 11440.0, 11_440.0, 0.62, 0.82, 3.43, 2.4, 3.0, 900.0, 0.6, 1e-4, 1e-6, 0.005, 0.001}
    bad = []
    for f in (ROOT / "src/water01").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in n.args.defaults + n.args.kw_defaults:
                    if isinstance(d, ast.Constant) and isinstance(d.value, float) and d.value in forbidden:
                        bad.append(f"{f.name}:{n.name}={d.value}")
            if isinstance(n, ast.AnnAssign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, float) \
                    and n.value.value in forbidden:
                bad.append(f"{f.name}:{ast.unparse(n.target)}={n.value.value}")
    assert not bad, bad
