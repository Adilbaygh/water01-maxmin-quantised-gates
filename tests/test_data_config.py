"""§2.1 and §2.10: data loading, units, manifest."""
from pathlib import Path
from water01.domain.passport import PARAMETERS
from water01.simulation.scenarios import derive_limit, load_config, load_demand, load_supply
from _inputs import DEM, SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_supply_vegetation_rows():
    s = load_supply(SUP)
    assert len(s) == 1830 and (s.S_m3s >= 0).all()
    assert len(derive_limit(s)) == 18


def test_demand_units_consistent():
    for v in "ABC":
        assert len(load_demand(DEM, v)) == 108


def test_manifest_nested_and_lists():
    c = load_config()
    assert c.years[0] == 2010 and c.nasa_power_latitude == 42.649 and c.preissmann_theta == 0.6


def test_every_parameter_has_status():
    assert all(p.status in {"observed", "derived", "assumed", "setting"} for p in PARAMETERS.values())
