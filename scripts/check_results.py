"""Validator and manifest of the stored results.

Checks (every violation is listed):
  1. every expected run exists: 6 methods x 10 seasons x tuned/untuned x phys/iot (240), the 14 Shapley coalitions
     of LXB, tuned (140), and LXB-noS3, tuned, phys (10), i.e. 390 runs in results/experiment/normal; with --all,
     also the sensitivity and exploratory cases; no unexpected CSV, no *.error.txt, no CSV without .meta.json;
  2. every file has 183 rows with consecutive dates from 1 April to 30 September and unique (year, date); the method,
     year, tuned and iot columns match the file name;
  3. energy columns: battery_min_wh is filled when factor E is active and empty otherwise; radio_off_steps >= 0;
  4. every run used the same input files (checksums in .meta.json); the runs of one folder used the same source
     code, and every code version is listed in results/versions.json, which also lists accepted revisions of the
     reference configuration (a later version must reproduce the stored runs of an earlier one, see
     results/verification/); the protocol checksum of requirements/hypotheses.md
     equals the frozen value in PREREGISTRATION.json;
  5. --write records MANIFEST_<scenario>.json with the checksum of every result file and its .meta.json; without --write the manifest must
     exist and every file must still match it.
Usage:
    python scripts/check_results.py            # check against the manifest
    python scripts/check_results.py --all      # also the sensitivity and exploratory folders
    python scripts/check_results.py --write    # check and write the manifest
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from water01.simulation.provenance import sha256  # noqa: E402

METHODS = ("B0", "B1", "B2", "B3", "LXB", "Oracle")
SUBSETS = ("S", "Q", "C", "E", "SQ", "SC", "SE", "QC", "QE", "CE", "SQC", "SQE", "SCE", "QCE")
YEARS = tuple(range(2010, 2020))
SEASON_DAYS = 183
PROTOCOL = "requirements/hypotheses.md"


def expected_runs(years=YEARS):
    runs = [(m, y, t, i) for y in years for t in ("tuned", "untuned") for i in ("phys", "iot") for m in METHODS]
    runs += [("LXB", y, "tuned", c) for y in years for c in SUBSETS]
    runs += [("LXB-noS3", y, "tuned", "phys") for y in years]
    return runs


def case_runs(years=YEARS):
    """{folder: expected runs} for the sensitivity and exploratory cases (tables in run_experiment.py)."""
    from run_experiment import EXPLORATORY, SENS_METHODS, SENSITIVITY, groups
    out = {f"results/sensitivity/{c}": [(m, y, "tuned", i) for y in years for i in iots for m in SENS_METHODS]
           for c, iots in SENSITIVITY.items()}
    out.update({f"results/exploratory/{c}": [(m, y, t, i) for (ms, tu, io) in groups(c) for y in years for t in tu
                                             for i in io for m in ms]
                for c in EXPLORATORY})
    return out


def name_of(run):
    return "{}_{}_{}_{}.csv".format(*run)


def has_energy(iot):
    return iot == "iot" or "E" in iot


def _norm(key):
    key = key.replace("\\", "/")                             # platform-independent keys
    return PROTOCOL if key == "hypotheses.md" else key


def check_file(path, run, errors):
    m, y, t, i = run
    df = pd.read_csv(path)
    if len(df) != SEASON_DAYS:
        errors.append(f"{path.name}: {len(df)} rows (expected {SEASON_DAYS})")
    dates = pd.to_datetime(df.date)
    want = pd.date_range(f"{y}-04-01", periods=SEASON_DAYS, freq="D")
    if len(dates) == SEASON_DAYS and not (dates.reset_index(drop=True) == pd.Series(want)).all():
        errors.append(f"{path.name}: dates are not 1 April to 30 September")
    if df.duplicated(["year", "date"]).any():
        errors.append(f"{path.name}: duplicate (year, date)")
    for col, val in (("method", m), ("year", y), ("tuned", t), ("iot", i)):
        if col not in df or set(df[col].astype(str)) != {str(val)}:
            errors.append(f"{path.name}: column {col} does not match the file name")
    if "battery_min_wh" in df:
        filled = df.battery_min_wh.notna().all()
        if has_energy(i) and not filled:
            errors.append(f"{path.name}: energy factor active but battery_min_wh empty")
        if not has_energy(i) and df.battery_min_wh.notna().any():
            errors.append(f"{path.name}: energy factor inactive but battery_min_wh filled")
    if "radio_off_steps" in df and (df.radio_off_steps.fillna(0) < 0).any():
        errors.append(f"{path.name}: negative radio_off_steps")


def validate(folder, runs, prereg=None, seen=None):
    """Returns (errors, {file: sha256}). seen collects input and code checksums across folders."""
    folder = Path(folder); errors = []; hashes = {}; codes = set()
    seen = {} if seen is None else seen
    expected = {name_of(r): r for r in runs}
    present = {p.name for p in folder.glob("*.csv")}
    rel = folder.relative_to(ROOT).as_posix() if folder.is_relative_to(ROOT) else str(folder)
    for n in sorted(set(expected) - present):
        errors.append(f"{rel}: missing {n}")
    for n in sorted(present - set(expected)):
        errors.append(f"{rel}: unexpected file {n}")
    for p in sorted(folder.glob("*.error.txt")):
        errors.append(f"{rel}: error file {p.name}")
    for n in sorted(set(expected) & present):
        path = folder / n
        check_file(path, expected[n], errors)
        hashes[n] = sha256(path)
        meta = path.with_name(n + ".meta.json")
        if not meta.exists():
            errors.append(f"{rel}/{n}: .meta.json missing"); continue
        hashes[n + ".meta.json"] = sha256(meta)
        m = json.loads(meta.read_text(encoding="utf-8"))
        items = {_norm(k): v for k, v in m.get("inputs", {}).items() if not _norm(k).startswith("configs/scenarios/")}
        for k, v in items.items():
            seen.setdefault(k, {}).setdefault(v, []).append(f"{rel}/{n}")
        code = m.get("code_sha256", "not recorded")
        seen.setdefault("code_sha256", {}).setdefault(code, []).append(f"{rel}/{n}")
        codes.add(code)
    if len(codes) > 1:
        errors.append(f"{rel}: runs computed with different code versions ({', '.join(c[:12] for c in codes)})")
    if prereg:
        frozen = {_norm(k): v for k, v in prereg.items()}.get(PROTOCOL)
        if frozen is not None and PROTOCOL in seen and set(seen[PROTOCOL]) != {frozen}:
            errors.append(f"{PROTOCOL}: checksum differs from the frozen protocol")
    return errors, hashes


def versions():
    """{"code_sha256" or input path: {checksum: description}}: accepted versions of the code and of the reference
    configuration (results/versions.json)."""
    p = ROOT / "results/versions.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def consistency(seen):
    """Every run must have used the same inputs and code; several versions of an input or of the code are accepted
    only when each of them is listed in results/versions.json."""
    known, errors = versions(), []
    for k, by_hash in seen.items():
        if len(by_hash) < 2:
            continue
        listed = known.get(k, {})
        if all(h in listed for h in by_hash):
            continue
        errors.append(f"{k} differs between runs: " + ", ".join(
            f"{h[:8]} ({len(f)} files{'' if h in listed else ', not in results/versions.json'})"
            for h, f in by_hash.items()))
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="normal")
    ap.add_argument("--all", action="store_true", help="also check the sensitivity and exploratory folders")
    ap.add_argument("--write", action="store_true", help="write the manifest if every check passes")
    a = ap.parse_args()
    exp = ROOT / "results/experiment"
    reg = exp / "PREREGISTRATION.json"
    if not reg.exists():
        sys.exit("results/experiment/PREREGISTRATION.json not found")
    prereg = json.loads(reg.read_text(encoding="utf-8"))["sha256"]
    folders = {f"results/experiment/{a.scenario}": expected_runs()}
    if a.all:
        folders.update(case_runs())
    errors, hashes, seen = [], {}, {}
    for rel, runs in folders.items():
        e, h = validate(ROOT / rel, runs, prereg, seen)
        errors += e
        hashes.update({f"{rel}/{n}": v for n, v in h.items()})
    errors += consistency(seen)
    man_path = exp / (f"MANIFEST_{a.scenario}.json" if not a.all else "MANIFEST_all.json")
    if not a.write:
        if not man_path.exists():
            errors.append(f"{man_path.relative_to(ROOT).as_posix()} not found (write it with --write)")
        else:
            man = json.loads(man_path.read_text(encoding="utf-8"))["files"]
            man = {(k if "/" in k else f"results/experiment/{a.scenario}/{k}"): v for k, v in man.items()}
            for n, h in hashes.items():
                if man.get(n) != h:
                    errors.append(f"{n}: " + ("not in the manifest" if n not in man else "changed after the manifest"))
            for n in sorted(set(man) - set(hashes)):
                errors.append(f"{n}: listed in the manifest but missing")
    if errors:
        print(f"{len(errors)} problem(s):"); print("\n".join("  " + e for e in errors[:50]))
        sys.exit(1)
    codes = {h: len(f) for h, f in seen.get("code_sha256", {"n/a": []}).items()}
    code = next(iter(codes)) if len(codes) == 1 else sorted(codes)
    print(f"OK: {len(hashes)} runs in {len(folders)} folder(s), complete, with identical inputs; code_sha256 "
          + ", ".join(f"{h[:12]} ({n} runs)" for h, n in codes.items()) + ".")
    if a.write:
        man = {"folders": sorted(folders), "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "expected_files": sum(len(r) for r in folders.values()), "code_sha256": code,
               "protocol_sha256": {_norm(k): v for k, v in prereg.items()}.get(PROTOCOL), "files": hashes}
        man_path.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"-> {man_path.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
