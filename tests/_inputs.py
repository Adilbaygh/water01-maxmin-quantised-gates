"""Input files of the tests.

The tests use the processed operating records (DATA/processed) when they are present. These records are third-party
data and are not part of the public repository; without them, the tests use the synthetic files of DATA/synthetic
(scripts/make_synthetic_inputs.py), and the tests that check properties of the records themselves are skipped.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_RECORDS_SUP = ROOT / "DATA/processed/rashod_2010_2019_daily.csv"
_RECORDS_DEM = ROOT / "DATA/processed/demand_decadal.csv"
RECORDS = _RECORDS_SUP.exists() and _RECORDS_DEM.exists()
SUP = _RECORDS_SUP if RECORDS else ROOT / "DATA/synthetic/supply_daily.csv"
DEM = _RECORDS_DEM if RECORDS else ROOT / "DATA/synthetic/demand_decadal.csv"

requires_records = pytest.mark.skipif(not RECORDS, reason="needs the operating records (DATA/processed), "
                                                         "which are available to reviewers on request")
