"""Section 2.8: compared controllers with a single interface (control.interface):

    command = controller.step(state=state, demand=demand, supply=supply, constraints=constraints, horizon=horizon)

CONTROLLERS -- classes operating in closed loop with the Saint-Venant plant (simulation.plant_loop):
    B0       -- current practice: area-proportional regulators + PI level control at the check structure;
    B1       -- simple fairness: lexicographic plan at the start of the period, no feedback;
    B2       -- fairness + hydraulic feasibility: weighted-sum MPC (same model and constraints as LXB);
    B3       -- existing constrained method: proportional rationing, gates driven by measured levels;
    LXB      -- proposed method: three-stage lexicographic plan + ID/(9) execution LP;
    Oracle   -- LXB with known future and true state (upper bound);
    LXB-noS3 -- H3 ablation: LXB without Stage 3;
    B3V      -- B3 + feedback on daily volume (control variant);
    LXB-DA   -- LXB aware of the actuation deadband (pulse rule; sensitivity variant);
    LXB-F    -- LXB whose execution LP maximises the final daily share of the plan (exploratory);
    B3V-DA   -- B3V with the pulse rule of LXB-DA (exploratory);
    ROT      -- rotation of the small regulators with proportional targets and PI level control (current practice
                at small outlets; comparator).
Static functions (b3_proportional, lxb_receding, oracle) are hydraulics-free versions for code checks.
"""
from .b0 import B0Controller
from .b1 import B1Controller
from .b2 import B2Controller
from .b3 import B3Controller, B3VController, B3VDeadbandAwareController, b3_proportional
from .interface import Command, ControlState, Controller, Demand, Horizon, Supply
from .lxb import (LXBController, LXBDeadbandAwareController, LXBFinalShareController, LXBNoStage3Controller,
                  lxb_receding)
from .oracle import OracleController, oracle
from .rotation import RotationController

CONTROLLERS = {"B0": B0Controller, "B1": B1Controller, "B2": B2Controller, "B3": B3Controller,
               "LXB": LXBController, "Oracle": OracleController, "LXB-noS3": LXBNoStage3Controller,
               # control variants: descriptive only, not part of the hypothesis tests
               "B3V": B3VController, "LXB-DA": LXBDeadbandAwareController,
               "LXB-F": LXBFinalShareController, "B3V-DA": B3VDeadbandAwareController, "ROT": RotationController}
STATIC = {"B3": b3_proportional, "LXB": lxb_receding, "Oracle": oracle}
