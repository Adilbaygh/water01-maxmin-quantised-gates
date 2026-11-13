"""Short checks of the rule variants (scripts/rules_variants.py) and of the inputs of scripts/run_sensitivity.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from water01.simulation.runner import run_closed_loop_period  # noqa: E402
from water01.simulation.scenarios import iot_scenario, load_config, load_demand  # noqa: E402

import rules  # noqa: E402
import rules_variants  # noqa: E402

DAYS = 3


def run(method, start="2010-04-01"):
    cfg = load_config(scenario="normal")
    rules_variants.register(); rules.LOG.clear()
    out = run_closed_loop_period(method, ROOT / "DATA/processed/rashod_2010_2019_daily.csv",
                                 ROOT / "DATA/processed/demand_decadal.csv", cfg, start, DAYS, tuned=True,
                                 iot=iot_scenario(cfg, ("quantisation",)), seed=cfg.seed + 2010)
    return out["result"], {p: {k: (v.copy() if hasattr(v, "copy") else v) for k, v in r.items()}
                           for p, r in rules.LOG.items()}


@pytest.fixture(scope="module")
def results():
    return {m: run(m) for m in ("LXB-T050", "LXB-T050S", "LXB-CO", "LXB-COS")}


def test_start_closure_changes_nothing_when_no_gate_is_open_at_the_day_break(results):
    for base, var in (("LXB-T050", "LXB-T050S"), ("LXB-CO", "LXB-COS")):
        a, _ = results[base]; b, log = results[var]
        closed = sum(int(np.sum(r.get("start_closed", 0))) for r in log.values())
        if closed == 0:
            assert np.allclose(a.delivered, b.delivered, rtol=0, atol=1e-9)


def test_minimal_equal_split_uses_no_more_open_steps_than_the_largest_split():
    res_m, log_m = run("LXB-ESM", "2010-05-01")
    res_e, log_e = run("LXB-ES", "2010-05-01")
    from water01.hydraulics.node import DustlikNode
    from water01.domain.passport import value
    node = DustlikNode(); amax = np.asarray(node.max_opening, float)[:5]
    g_hi = np.asarray(node.offtakes(value("H_max_m") - 0.2, value("gate_resolution_fraction") * amax)) * value("dt_s")
    checked = 0
    for p in range(DAYS):
        for j, mode in enumerate(log_m[p]["mode"]):
            if mode == "ES":
                assert abs(res_m.delivered_est[j, p] - res_m.targets[j, p]) <= g_hi[j] / 2 + 1e-6
                if log_e[p]["mode"][j] == "ES":
                    assert log_m[p]["m"][j] <= log_e[p]["m"][j]
                checked += 1
    assert checked > 0


def test_trimming_equal_split_keeps_half_a_step_with_few_open_steps():
    res, log = run("LXB-ESL", "2018-08-13")
    from water01.hydraulics.node import DustlikNode
    from water01.domain.passport import value
    node = DustlikNode(); amax = np.asarray(node.max_opening, float)[:5]
    g_hi = np.asarray(node.offtakes(value("H_max_m") - 0.2, value("gate_resolution_fraction") * amax)) * value("dt_s")
    checked = 0
    for p in range(DAYS):
        for j, mode in enumerate(log[p]["mode"]):
            if mode == "ES":
                assert abs(res.delivered_est[j, p] - res.targets[j, p]) <= g_hi[j] / 2 + 1e-6
                checked += 1
    assert checked > 0


def test_modified_demand_files_keep_units_and_change_only_their_rows(tmp_path, monkeypatch):
    import run_sensitivity as rs
    monkeypatch.setattr(rs, "ROOT", tmp_path)
    (tmp_path / "DATA/processed").mkdir(parents=True)
    src = ROOT / rs.rc.DEM
    (tmp_path / rs.rc.DEM).write_bytes(src.read_bytes())
    base = pd.read_csv(src)
    for scenario, check in (("r1_april_150", "r1"), ("demand_scale_120", "scale")):
        cfg = load_config(scenario=scenario)
        rel = rs.demand_file(cfg)
        new = pd.read_csv(tmp_path / rel)
        load_demand(tmp_path / rel, "A")                     # the unit check of the core passes
        ratio = new["D_mln_m3"] / base["D_mln_m3"]
        if check == "r1":
            sel = (base.j == 2) & (base.month == 4) & (base.decade == 1)
            assert np.allclose(ratio[sel], 1.5) and np.allclose(ratio[~sel], 1.0)
        else:
            assert np.allclose(ratio, 1.2)
    load_config(scenario="normal")
