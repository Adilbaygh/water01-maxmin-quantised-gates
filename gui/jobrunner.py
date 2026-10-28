"""Runs selected seasons of the closed-loop simulation with the functions of scripts/run_cases.py.

    python -m gui.jobrunner q_main:LXB-T050:2010 q_main:LXB-T050:2011 ...      (from the project folder)

Every job is claimed by an exclusive file first, so several workers can process the same list; a complete result is
never recomputed. The lines START, DONE, FAILED and SKIP report the progress to the interface. As in run_cases.py, a
failed season keeps its claim, so that it is not retried before its error has been looked at.
"""
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_cases  # noqa: E402  (adds src/ to the import path and loads the simulation core)


def parse(spec: str):
    case, method, year = spec.split(":")
    year = int(year)
    if case not in run_cases.CASES or method not in run_cases.CASES[case][2] or year not in run_cases.YEARS:
        raise ValueError(f"unknown job {spec}")
    return case, method, year


def main(argv) -> int:
    jobs = [parse(s) for s in argv]
    failed = 0
    print(f"jobs: {len(jobs)}, complete: {sum(run_cases.complete(j) for j in jobs)}", flush=True)
    t0 = time.time()
    for k, job in enumerate(jobs, 1):
        name = "/".join(map(str, job))
        if run_cases.complete(job):
            print(f"SKIP {name} (complete)", flush=True)
            continue
        if not run_cases.claim(job):
            print(f"SKIP {name} (claimed by another process)", flush=True)
            continue
        print(f"START {name}", flush=True)
        try:
            minutes = run_cases.run(job)
            print(f"DONE {name} ({minutes:.1f} min; total {(time.time() - t0) / 60:.1f} min)", flush=True)
        except Exception as e:  # noqa: BLE001 (record the error and continue with the next job)
            path = run_cases.result_path(job).with_suffix(".error.txt")
            path.write_text(traceback.format_exc(), encoding="utf-8")
            print(f"FAILED {name}: {e} (see {path.relative_to(ROOT)})", flush=True)
            failed += 1
        finally:
            claim = run_cases.result_path(job).with_suffix(".claim")
            if claim.exists() and run_cases.complete(job):
                claim.unlink()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
