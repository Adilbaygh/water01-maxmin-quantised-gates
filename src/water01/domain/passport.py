"""Sections 2.1-2.2, Tables 1-2: parameter registry.

Values live in the configuration, not in the code: configs/kegeyli_reference.yaml (+ scenario). This module
gives convenient access to the active configuration: value(name), PARAMETERS[name] (Parameter: value, status,
source), USERS.
"""
from .config import STATUSES, Parameter, active, optional, value  # noqa: F401


class _Registry:
    """Parameters of the active configuration (read from the current configuration on every access)."""

    def __getitem__(self, name):
        return active().params[name]

    def __contains__(self, name):
        return name in active().params

    def __iter__(self):
        return iter(active().params)

    def __len__(self):
        return len(active().params)

    def items(self):
        return active().params.items()

    def values(self):
        return active().params.values()

    def keys(self):
        return active().params.keys()


PARAMETERS = _Registry()


def users():
    return tuple(value("users"))


USERS = users()          # user order (not changed by scenarios; used as result column names)
