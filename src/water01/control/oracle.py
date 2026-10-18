"""Section 2.8, Oracle: the LXB formulation with future supply and state known in advance (upper bound).

In closed loop (OracleController) the plan and execution are the same as in LXB, but perfect_information = True:
the loop provides the true level and the true delivered volume (no measurement or reconstruction error), and the
true future supply and next-day inflow instead of a forecast. The plant and gates are the same as for the other
controllers, so the Oracle gap measures information and execution constraints, not the hydraulic model.
"""
from ..optimization.lexlp import solve_lexicographic
from .lxb import LXBController


def oracle(D, A_actual, U=None, weights=None, epsilon_1=None, epsilon_2=None):
    """Static variant: a single LP for the whole period (code checks only)."""
    return solve_lexicographic(D, A_actual, U, weights, None, epsilon_1, epsilon_2)["x"]


class OracleController(LXBController):
    name = "Oracle"
    perfect_information = True
