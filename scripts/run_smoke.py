"""Water-01 static smoke test: first decade of July 2018, B3 / LXB / Oracle, daily allocation without hydraulics.
A code check only, not a result. Hydraulic results: scripts/run_closed_loop.py."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from water01.simulation.runner import run_smoke  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402


def main():
    cfg = load_config()
    out = run_smoke(ROOT / "DATA/processed/rashod_2010_2019_daily.csv", ROOT / "DATA/processed/demand_decadal.csv",
                    variant=cfg.demand_variant, horizon_days=cfg.horizon_days,
                    epsilon_1=cfg.epsilon_1, epsilon_2=cfg.epsilon_2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
