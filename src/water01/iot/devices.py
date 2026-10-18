"""Section 2.6, Table 3, Equation (14): IoT devices and gate actuator (quantisation, deadband).

Values that are absent from the datasheet or not yet confirmed are stored as None together with their status;
they are never invented. Gate opening is expressed as a fraction in [0, 1] of the actuator stroke.
"""
from dataclasses import dataclass

from ..domain.passport import value


@dataclass(frozen=True)
class Device:
    name: str
    role: str
    source: str
    status: str                 # observed (datasheet) | assumed | pending (datasheet URL not confirmed)
    power_supply: str
    accuracy_m: float = None    # level sensor error (accuracy class), m, from the datasheet
    resolution_m: float = None  # measurement step, m, from the datasheet
    note: str = ""


def devices():
    """Device registry: datasheet values are kept in the configuration (iot.devices), not here."""
    out = {}
    for key, d in value("devices").items():
        out[key] = Device(d.get("name", key), d.get("role", ""), d.get("source", ""), d.get("status", "observed"),
                          d.get("power_supply", "IoT node kit"), d.get("accuracy_m"), d.get("resolution_m"),
                          d.get("note", ""))
    return out


def quantize(command, resolution, previous=None, deadband=0.0):
    """(14): the command (share of the gate travel) is rounded to the actuator step. A command that rounds to the
    closed position is a full closure and travels to the end stop. Otherwise, if the change from the previous
    position is smaller than the deadband, the previous position is kept. Positions and the deadband are compared
    in whole actuator steps, so that a change of exactly the deadband is always executed."""
    if resolution <= 0:
        raise ValueError("resolution must be > 0")
    c = min(max(float(command), 0.0), 1.0)
    n = int(round(c / resolution))
    if n == 0:
        return 0.0                         # full closure: travel to the limit switch, not subject to the deadband
    if previous is not None:
        n_prev = int(round(float(previous) / resolution))
        if abs(n - n_prev) < deadband / resolution - 1e-9:
            return float(previous)
    return float(min(n * resolution, 1.0))
