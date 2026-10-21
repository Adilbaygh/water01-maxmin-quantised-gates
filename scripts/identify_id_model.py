"""Section 2.4: identification of the ID model (8) parameters from the reference Saint–Venant plant (Schuurmans, 1997).

Protocol: steady profile at Q_C = 86.7 m³/s with node level h_L = H and the conveyance losses of the plant (η);
at the start of the first step the inflow steps by ±1 m³/s while the node outflow is held constant; 6 h,
Δt = 15 min; straight-line fit to the last 3 h (optimization.constraints.identify_from_step). The ID model (8)
receives η·Q_in at the node, so the fit uses the step η·dQ.
Output: results/id_identification.csv (A_s, τ, d and A_s / (T·L)); with --scenario design_geometry,
results/id_identification_design_geometry.csv.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from water01.domain.geometry import Reach   # noqa: E402
from water01.domain.passport import PARAMETERS   # noqa: E402
from water01.optimization.constraints import delay_steps, identify_from_step   # noqa: E402
from water01.simulation.plant_loop import step_response   # noqa: E402
from water01.simulation.provenance import config_inputs, write_metadata   # noqa: E402
from water01.simulation.scenarios import load_config   # noqa: E402



def identify(hold, dq):
    Q_C, DT = PARAMETERS["Q_c_m3s"].value, PARAMETERS["dt_s"].value
    r = Reach()
    eta = PARAMETERS["eta"].value
    run = step_response(r, Q_C, hold, dq, PARAMETERS["id_duration_h"].value * 3600, DT, eta=eta)
    return identify_from_step(run["t"], run["h_L"], eta * dq), r.top(hold) * r.L


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", default="normal")
    a = ap.parse_args()
    cfg = load_config(scenario=a.scenario)
    rows = []
    for name in ("H_min_m", "H_norm_m", "H_max_m"):
        hold = PARAMETERS[name].value
        dQ = PARAMETERS["id_step_dq_m3s"].value
        for dq in (dQ, -dQ):
            (A_s, tau), TL = identify(hold, dq)
            rows.append({"level": name, "h_L_m": hold, "dQ_m3s": dq, "A_s_m2": round(A_s), "tau_s": round(tau),
                         "d_steps": delay_steps(tau, PARAMETERS["dt_s"].value), "A_s_over_TL": round(A_s / TL, 3)})
    df = pd.DataFrame(rows)
    out = ROOT / "results" / ("id_identification.csv" if a.scenario == "normal" else f"id_identification_{a.scenario}.csv")
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    write_metadata(out, ROOT, config_inputs(cfg, ROOT), {}, cfg)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
