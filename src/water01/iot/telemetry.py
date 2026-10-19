"""Section 2.4, Equation (7): measurement model z = h + ν and state estimation (physical filter + prediction).

The estimator is described as a pluggable interface; it has not been calibrated in the field.
"""
import numpy as np

from ..domain.passport import value


def measure(true_level, accuracy_m, rng=None, available=True, resolution_m=None, unit_noise=None, bias_m=0.0):
    """(7): z = h + ν with ν ~ U(−a, +a) (assumed; a is the datasheet accuracy class).

    unit_noise ∈ [−1, 1] is a pre-drawn innovation (ν = a·unit_noise), used by the closed loop so that every
    coalition of IoT constraints sees the same sensor innovation at the same step; otherwise ν is drawn from rng.
    With resolution_m the reading is rounded to the sensor step; bias_m is a persistent offset (calibration error,
    sensitivity case; 0 in the base case). Returns None when no sample is available."""
    if not available:
        return None
    if accuracy_m is None:
        raise ValueError("Sensor accuracy is not given (datasheet value required)")
    u = rng.uniform(-1.0, 1.0) if unit_noise is None else float(unit_noise)
    z = float(true_level + bias_m + accuracy_m * u)
    if resolution_m:
        z = round(z / resolution_m) * resolution_m
    return float(z)


def update(measured_level, previous_estimate, h_lo, h_hi, prediction=None, blend=None):
    """1) last valid measurement; 2) measurements outside the physical bounds are rejected; 3) blended with the
    prediction. blend: weight of the measurement (assumed)."""
    blend = value("estimator_blend") if blend is None else blend
    if not 0.0 <= blend <= 1.0:
        raise ValueError("blend must lie in [0, 1]")
    valid = measured_level is not None and h_lo <= measured_level <= h_hi
    if not valid:
        return float(previous_estimate if prediction is None else prediction)
    if prediction is None:
        return float(measured_level)
    return float(blend * measured_level + (1.0 - blend) * prediction)


def default_rng(seed):
    return np.random.default_rng(seed)
