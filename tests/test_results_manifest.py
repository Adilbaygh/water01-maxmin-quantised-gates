"""Result validator (scripts/check_results.py): every check works on a synthetic folder, and the stored results, if
present, are complete and match the manifest."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_results as C  # noqa: E402


def write_run(folder, run, inputs, rows=183, energy=None, code="c0"):
    m, y, t, i = run
    dates = pd.date_range(f"{y}-04-01", periods=rows, freq="D").date
    energy = C.has_energy(i) if energy is None else energy
    df = pd.DataFrame({"method": m, "year": y, "tuned": t, "iot": i, "date": dates, "lambda": 0.8,
                       "battery_min_wh": 900.0 if energy else np.nan, "radio_off_steps": 0})
    path = folder / C.name_of(run)
    df.to_csv(path, index=False)
    path.with_name(path.name + ".meta.json").write_text(json.dumps({"inputs": inputs, "code_sha256": code}),
                                                        encoding="utf-8")


RUNS = [("LXB", 2010, "tuned", "phys"), ("LXB", 2010, "tuned", "iot"), ("LXB", 2010, "tuned", "SQ")]
INPUTS = {"configs/kegeyli_reference.yaml": "aaa", "requirements/hypotheses.md": "bbb", "DATA/processed/s.csv": "s"}
PREREG = {"configs\\kegeyli_reference.yaml": "old", "hypotheses.md": "bbb"}


def test_expected_run_count_is_390():
    assert len(C.expected_runs()) == 390 and len(set(C.expected_runs())) == 390


def test_case_folders_cover_every_case():
    runs = C.case_runs()
    assert any(k.startswith("results/sensitivity/") for k in runs)
    assert "results/exploratory/untuned_reverse" in runs and all(runs.values())


def test_complete_folder_passes_and_config_edits_are_not_errors(tmp_path):
    for r in RUNS:
        write_run(tmp_path, r, INPUTS)
    seen = {}
    errors, hashes = C.validate(tmp_path, RUNS, PREREG, seen)
    assert errors == [] and C.consistency(seen) == [] and len(hashes) == 6       # result files and .meta.json


def test_missing_extra_error_and_short_files_are_reported(tmp_path):
    write_run(tmp_path, RUNS[0], INPUTS)
    write_run(tmp_path, RUNS[1], INPUTS, rows=180)
    write_run(tmp_path, ("B0", 2010, "tuned", "phys"), INPUTS)            # unexpected
    (tmp_path / "LXB_2010_tuned_SQ.error.txt").write_text("ValueError")
    errors, _ = C.validate(tmp_path, RUNS, PREREG)
    text = "\n".join(errors)
    assert "missing LXB_2010_tuned_SQ.csv" in text and "unexpected file B0_2010_tuned_phys.csv" in text
    assert "error file" in text and "180 rows" in text


def test_energy_columns_inputs_code_and_protocol_are_checked(tmp_path):
    write_run(tmp_path, RUNS[0], INPUTS, energy=True)                       # no energy factor under phys
    write_run(tmp_path, RUNS[1], {**INPUTS, "DATA/processed/s.csv": "t"})
    write_run(tmp_path, RUNS[2], {**INPUTS, "requirements/hypotheses.md": "changed"}, code="c1")
    seen = {}
    errors, _ = C.validate(tmp_path, RUNS, PREREG, seen)
    text = "\n".join(errors + C.consistency(seen))
    assert "energy factor inactive but battery_min_wh filled" in text
    assert "DATA/processed/s.csv differs between runs" in text and "code_sha256 differs between runs" in text
    assert "different code versions" in text
    assert "differs from the frozen protocol" in text


def test_listed_code_versions_are_accepted_across_folders(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    write_run(a, RUNS[0], INPUTS, code="c0"); write_run(b, RUNS[0], INPUTS, code="c1")
    seen = {}
    assert C.validate(a, RUNS[:1], PREREG, seen)[0] == [] and C.validate(b, RUNS[:1], PREREG, seen)[0] == []
    monkeypatch.setattr(C, "versions", lambda: {})
    assert any("code_sha256 differs" in e for e in C.consistency(seen))
    monkeypatch.setattr(C, "versions", lambda: {"code_sha256": {"c0": "1.0", "c1": "1.1"}})
    assert C.consistency(seen) == []


def test_stored_results_match_manifest():
    man = ROOT / "results/experiment/MANIFEST_all.json"
    if not (ROOT / "results/experiment/normal").exists() or not man.exists():
        pytest.skip("no stored results in this copy")
    reg = json.loads((ROOT / "results/experiment/PREREGISTRATION.json").read_text(encoding="utf-8"))["sha256"]
    errors, hashes = C.validate(ROOT / "results/experiment/normal", C.expected_runs(), reg)
    prefix = "results/experiment/normal/"
    files = {k[len(prefix):]: v for k, v in json.loads(man.read_text(encoding="utf-8"))["files"].items()
             if k.startswith(prefix)}
    assert errors == []
    assert {n for n in hashes if n.endswith(".csv")} == {n for n in files if n.endswith(".csv")}
    assert all(hashes[n] == h for n, h in files.items())
