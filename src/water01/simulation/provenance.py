"""Provenance of the simulation results (Section 2.10).

Each result file is accompanied by <result>.meta.json with the software environment (Python, platform, NumPy, SciPy,
pandas, PyYAML and HiGHS versions), the SHA-256 checksums of the source code and of the input files, the run
parameters, and any deviation from the versions pinned in requirements.txt. LP solutions can depend on the solver
version and on the platform (BLAS, compiler), so the environment of every run is recorded.
"""
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

PINNED = ("numpy", "scipy", "pandas", "PyYAML")


def _version(module):
    try:
        mod = __import__({"PyYAML": "yaml"}.get(module, module))
        return getattr(mod, "__version__", "unknown")
    except ImportError:
        return None


def highs_version():
    try:
        from scipy.optimize._highspy import _core
        return f"{_core.HIGHS_VERSION_MAJOR}.{_core.HIGHS_VERSION_MINOR}.{_core.HIGHS_VERSION_PATCH}"
    except Exception:                                           # private SciPy API may change
        return "unknown"


def environment_info():
    from .. import __version__
    info = {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
            "water01": __version__, "highs": highs_version()}
    info.update({m: _version(m) for m in PINNED})
    return info


def read_pins(requirements_path):
    pins = {}
    for line in Path(requirements_path).read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if "==" in line:
            name, ver = line.split("==", 1)
            pins[name.strip()] = ver.strip()
    return pins


def pin_mismatches(requirements_path):
    """Differences from the versions pinned in requirements.txt: {package: (pinned, installed)}."""
    env = environment_info()
    return {k: (v, env.get(k)) for k, v in read_pins(requirements_path).items() if k in env and env[k] != v}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_sha256(root):
    """One checksum of the simulation code: SHA-256 over the relative POSIX path and the bytes of every
    src/**/*.py file and of scripts/run_experiment.py (which writes the result rows), in sorted order, with line
    endings normalised so that the value is platform independent."""
    root = Path(root); h = hashlib.sha256()
    files = list((root / "src").rglob("*.py")) + [p for p in [root / "scripts/run_experiment.py"] if p.exists()]
    for p in sorted(files, key=lambda q: q.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def relative_posix(path, root):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def config_inputs(cfg, root):
    """Active configuration files (reference and scenario) as POSIX paths relative to root."""
    return tuple(relative_posix(p, root) for p in cfg.files)


def write_metadata(result_path, root, inputs=(), params=None, cfg=None):
    """Write <result>.meta.json next to result_path; inputs are files (relative to root) whose checksums are kept."""
    root = Path(root); result_path = Path(result_path)
    req = root / "requirements.txt"
    meta = {"result": result_path.name, "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "command": " ".join(sys.argv), "environment": environment_info(),
            "pin_mismatches": pin_mismatches(req) if req.exists() else "requirements.txt not found",
            "code_sha256": code_sha256(root),
            "inputs": {Path(p).as_posix(): sha256(root / p) for p in inputs}, "params": params or {}}
    if cfg is not None:
        meta["scenario"] = cfg.scenario
        meta["config"] = {k: {"value": p.value, "status": p.status} for k, p in cfg.params.items()}
    out = result_path.with_suffix(result_path.suffix + ".meta.json")
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out
