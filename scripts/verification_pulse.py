"""Convergence of the delivered volume of a short gate pulse with respect to the hydraulic step (Table S2b).

Test case: steady state at 86.7 m3/s and H_norm with fixed openings of the other gates. The R-1 regulator is closed,
opened by the smallest executable opening (the deadband, 0.5% of the travel, 7.5 mm) for one control step of 900 s,
and closed again. The control (command) step is fixed at 900 s; the plant integrates it with 1, 2, 4, 8 or 16 equal
hydraulic steps, with the gate change either theta-weighted over the first hydraulic step (first code versions) or
applied at the start of the step (gate_change_at_step_start). Recorded: the R-1 volume credited to the control step with the open gate and to the following
step, their sum, and the node level after the pulse. The exact volume of a pulse at a constant level is
q(H_norm, 7.5 mm) x 900 s.
Usage: python scripts/verification_pulse.py  ->  results/verification/pulse.csv and .md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.geometry import Reach  # noqa: E402
from water01.domain.passport import value  # noqa: E402
from water01.hydraulics.node import DustlikNode  # noqa: E402
from water01.simulation.plant_loop import CanalPlant  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402

Q_C, DT = 86.7, 900.0
REG = np.array([0.5, 0.0, 0.2, 0.3, 0.2])


def run(substeps, jump):
    cfg = load_config()
    node = DustlikNode()
    plant = CanalPlant(Reach(), node, np.full(3, Q_C), cfg.eta, cfg.H_norm_m, DT, 96, cfg.preissmann_theta,
                       np.random.default_rng(0))
    plant.solver.base_substeps = substeps
    plant.gate_jump = jump
    a = np.r_[REG, 0.0]
    plant.initialise_gates(a)
    a = plant.openings.copy()
    for _ in range(8):                                      # settle with R-1 closed (2 h)
        plant.advance(a, DT)
    a_open = a.copy(); a_open[1] = value("gate_deadband_fraction") * node.max_opening[1]
    v0 = plant.delivered.volume[1].sum()
    plant.advance(a_open, DT); v1 = plant.delivered.volume[1].sum()
    plant.advance(a, DT); v2 = plant.delivered.volume[1].sum()
    for _ in range(4):
        plant.advance(a, DT)
    v3 = plant.delivered.volume[1].sum()
    exact = float(node.flows(cfg.H_norm_m, a_open)[1]) * DT
    return dict(gate_change="at step start" if jump else "theta-weighted", hydraulic_steps=substeps, dt_hydraulic_s=DT / substeps, opening_mm=a_open[1] * 1000,
                vol_open_step_m3=v1 - v0, vol_next_step_m3=v2 - v1, vol_total_m3=v3 - v0,
                share_in_open_step=(v1 - v0) / (v3 - v0), pulse_at_Hnorm_m3=exact)


def main():
    t = pd.DataFrame([run(k, j) for j in (False, True) for k in (1, 2, 4, 8, 16)])
    out = ROOT / "results/verification"; out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / "pulse.csv", index=False)
    lines = ["| Gate change | Hydraulic steps per 15 min | Δt, s | Volume in the open step, m³ | Volume in the next step, m³ | "
             "Total, m³ | Share in the open step |", "|" + "---|" * 7]
    for r in t.itertuples():
        lines.append(f"| {r.gate_change} | {r.hydraulic_steps} | {r.dt_hydraulic_s:.1f} | {r.vol_open_step_m3:.2f} | "
                     f"{r.vol_next_step_m3:.2f} | {r.vol_total_m3:.2f} | {r.share_in_open_step:.1%} |")
    (out / "pulse.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines)); print(f"pulse volume at H_norm: {t.pulse_at_Hnorm_m3.iloc[0]:.2f} m3")


if __name__ == "__main__":
    main()
