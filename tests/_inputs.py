"""Input files of the tests: the processed operating records of DATA/processed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "DATA/processed/rashod_2010_2019_daily.csv"
DEM = ROOT / "DATA/processed/demand_decadal.csv"
