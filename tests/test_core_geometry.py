"""§2.10 (2): consistency with the canal passport and Q_c."""
import numpy as np
from water01.domain.geometry import area, critical_supply, manning_discharge


def test_area_actual_normal_depth():
    assert np.isclose(area(3.0), 126.0)


def test_passport_capacity_at_filling_depth():
    # the passport capacity of 160 m3/s is reproduced at H_max = 3.43 m with n = 0.0185 (±0.5%)
    assert abs(manning_discharge(3.43) - 160.0) / 160.0 < 0.005


def test_passport_velocity_at_normal_depth():
    v = manning_discharge(3.0) / area(3.0)
    assert abs(v - 1.02) <= 0.015  # passport 1.02 m/s; model 1.01


def test_design_geometry_consistency():
    q = manning_discharge(4.00, roughness=0.0193, bottom_width=28.0)
    v = manning_discharge(3.78, roughness=0.0193, bottom_width=28.0) / area(3.78, bottom_width=28.0)
    assert abs(q - 160.0) / 160.0 < 0.005 and abs(v - 1.08) <= 0.01


def test_critical_supply_matches_data_analysis():
    assert abs(critical_supply() - 86.7) < 0.2  # critical supply at the node
