"""§2.4, (9): the chord constraint is conservative, the tangent constraint is not."""
import numpy as np
from water01.optimization.constraints import command_is_conservative


def f(h):
    return np.sqrt(np.maximum(np.asarray(h) - 1.0, 0.0))


def test_secant_is_conservative():
    xp = np.linspace(1.5, 3.5, 6)
    assert command_is_conservative(xp, f(xp), f)


def test_tangents_would_overestimate():
    h0 = 2.5; slope = 0.5 / np.sqrt(h0 - 1.0)
    xs = np.linspace(1.5, 3.5, 50)
    assert np.any(f(h0) + slope * (xs - h0) > f(xs) + 1e-9)
