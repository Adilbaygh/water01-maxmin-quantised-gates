"""domain.state: state objects."""
import numpy as np
import pytest

from water01.domain.state import CanalState, DeliveryLedger, NodeGates
from water01.hydraulics.node import DustlikNode


def test_ledger_accumulates_and_fixes_previous_day():
    led = DeliveryLedger(users=6, days=2)
    for _ in range(96):
        led.add(0, [1.0, 0.1, 0.0, 0.5, 0.2, 40.0], 900.0)
    assert np.isclose(led.volume[0, 0], 86_400.0) and led.fixed(0)[(5, 0)] == pytest.approx(40.0 * 86_400)
    with pytest.raises(ValueError):
        led.add(1, [-1, 0, 0, 0, 0, 0], 900.0)


def test_node_gates_and_canal_state():
    g = NodeGates((0.5, 0.2, 0.2, 0.3, 0.2), 0.5)
    q = DustlikNode().outflow_for(g)(3.0)
    assert q == pytest.approx(DustlikNode().outflow(3.0, g.regulators, g.barrier))
    with pytest.raises(ValueError):
        NodeGates((0.1, 0.1), 0.0)
    s = CanalState(0.0, np.array([2.5, 3.0]), np.array([80.0, 70.0]))
    c = s.copy(); c.h[0] = 0.0
    assert s.h[0] == 2.5 and s.level_downstream == 3.0 and s.inflow == 80.0 and s.outflow == 70.0
