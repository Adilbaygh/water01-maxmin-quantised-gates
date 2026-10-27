"""Inversion of the barrier relation when the commanded discharge equals the full-open discharge (node.openings_for).

The barrier relation is implicit (its tail water depends on the discharge) and is solved by a warm-started Newton
iteration, so two evaluations at the same level and opening can differ in the last digits. A command that equals the
full-open discharge to within this tolerance must open the barrier fully instead of stopping the run."""
import numpy as np

from water01.hydraulics.node import DustlikNode


def test_command_at_the_full_open_discharge_opens_the_barrier_fully(monkeypatch):
    node = DustlikNode()
    h = 2.585
    q_full = DustlikNode().barrier(h, node.bar_max)
    calls = {"n": 0}
    exact = DustlikNode.barrier

    def jittered(self, h_up, opening, cd=None):        # first evaluation slightly above, later ones slightly below
        q = exact(self, h_up, opening, cd)
        if opening >= self.bar_max:
            calls["n"] += 1
            q += 1e-11 if calls["n"] == 1 else -1e-11
        return q
    monkeypatch.setattr(DustlikNode, "barrier", jittered)
    a, lost = node.openings_for(np.r_[np.zeros(5), q_full], h)
    assert a[5] == node.bar_max and not lost[5]


def test_command_below_the_full_open_discharge_is_inverted():
    node = DustlikNode()
    h = 3.0
    q = 0.5 * node.barrier(h, node.bar_max)
    a, lost = node.openings_for(np.r_[np.zeros(5), q], h)
    assert 0 < a[5] < node.bar_max and not lost[5]
    assert abs(node.barrier(h, a[5]) - q) < 1e-6
