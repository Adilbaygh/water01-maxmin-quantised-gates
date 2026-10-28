"""Paths, metadata and inventory of the project, independent of the graphical toolkit."""
from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import threading
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
CONFIGS = ROOT / "configs"
DATA = ROOT / "DATA" / "processed"
RESULTS = ROOT / "results"
RUNS = RESULTS / "runs"
ANALYSIS = RESULTS / "analysis"
FIGURES = RESULTS / "figures"
VERIFICATION = RESULTS / "verification"
INPUTS = RESULTS / "inputs"
DOCS = ROOT / "docs"
TESTS = ROOT / "tests"
PAPER = ROOT / "paper"
PAPER_SRC = PAPER / "src"
PAPER_TOOLS = PAPER / "tools"

# the simulation core keeps one active configuration (water01.simulation.scenarios.load_config); computations of the
# interface that activate a scenario hold this lock
CORE_LOCK = threading.RLock()

SUPPLY_FILE = DATA / "rashod_2010_2019_daily.csv"
DEMAND_FILE = DATA / "demand_decadal.csv"
YEARS = tuple(range(2010, 2020))

# Description of the simulation cases (scripts/run_cases.py, Table 2 of the article). The case definitions themselves
# are read from scripts/run_cases.py; these labels only describe them.
CASE_LABELS = {
    "phys": "Ideal execution (reference)",
    "q_main": "Quantised actuator, baseline",
    "q_theta": "Quantised actuator, other thresholds",
    "iot_main": "Full device chain",
    "q_deadband_low": "Deadband 0.25% (k = 3)",
    "q_deadband_high": "Deadband 1% (k = 10)",
    "q_cd_low": "Gate coefficient -20%",
    "q_cd_high": "Gate coefficient +20%",
    "q_leak_005mm": "Leaking regulators",
    "q_rating": "Outlet rating errors",
}
RULE_LABELS = {
    "LXB": "Direct execution",
    "LXB-T000": "Pulse rule, θ = 0",
    "LXB-T025": "Pulse rule, θ = 0.25",
    "LXB-T050": "Pulse rule, θ = 0.5",
    "LXB-T075": "Pulse rule, θ = 0.75",
    "LXB-ES": "Equal split with pulse fallback",
    "LXB-CO": "Carry-over",
}


def add_import_paths():
    """Make the packages of src/ and the modules of scripts/ importable."""
    for p in (SCRIPTS, SRC):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


# --------------------------------------------------------------------------------------------------------------------
# metadata of the project and of the environment


def read_yaml(path: Path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def citation() -> dict:
    p = ROOT / "CITATION.cff"
    if not p.exists():
        return {}
    try:
        return read_yaml(p) or {}
    except Exception:  # noqa: BLE001 (metadata is optional)
        return {}


def git_state(root: Path = ROOT) -> dict:
    """Branch, commit and tag of the working copy, read from the .git folder (no git executable needed). An annotated
    tag is followed to its commit when the tag object is loose or peeled in packed-refs."""
    out = {"branch": None, "commit": None, "tag": None}
    git = Path(root) / ".git"
    if not git.is_dir():
        return out
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        refs, peeled, last = {}, {}, None
        packed = git / "packed-refs"
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.startswith("^") and last:
                    peeled[last] = line[1:].strip()
                elif line and not line.startswith("#"):
                    sha, ref = line.split(" ", 1)
                    last = ref.strip()
                    refs[last] = sha
        for ref_file in (git / "refs").rglob("*"):
            if ref_file.is_file():
                refs[ref_file.relative_to(git).as_posix()] = ref_file.read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            out["branch"] = ref.rsplit("/", 1)[-1]
            out["commit"] = refs.get(ref)
        else:
            out["commit"] = head
        if out["commit"]:
            tags = [r.rsplit("/", 1)[-1] for r, sha in refs.items() if r.startswith("refs/tags/")
                    and out["commit"] in (sha, peeled.get(r), _tag_target(git, sha))]
            out["tag"] = ", ".join(sorted(tags)) or None
    except (OSError, ValueError):
        pass
    return out


def _tag_target(git: Path, sha: str) -> str | None:
    """The object an annotated tag points to, when the tag object is stored loose in .git/objects."""
    import zlib
    try:
        data = zlib.decompress((git / "objects" / sha[:2] / sha[2:]).read_bytes())
    except (OSError, zlib.error, ValueError):
        return None
    if not data.startswith(b"tag "):
        return None
    for line in data.split(b"\0", 1)[-1].splitlines():
        if line.startswith(b"object "):
            return line.split()[1].decode("ascii", "replace")
    return None


def requirement_pins() -> dict:
    """Package -> (operator, version, optional) from requirements.txt; a package whose comment says that it is needed
    "only" by one script is optional."""
    pins = {}
    p = ROOT / "requirements.txt"
    if not p.exists():
        return pins
    for raw in p.read_text(encoding="utf-8").splitlines():
        line, _, comment = raw.partition("#")
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*(==|>=)\s*([^\s;]+)", line.strip())
        if m:
            pins[m.group(1)] = (m.group(2), m.group(3), "only" in comment.lower())
    return pins


ENV_STATES = ("ok", "different", "old", "missing", "optional")


def environment() -> list[tuple[str, str, str, str]]:
    """(package, installed version, required version, state) for Python and the packages of requirements.txt. State:
    ok; different (another version than the one of the reported results, which may change the last digits); old
    (below the minimum version); missing; optional (not installed, needed by one script only)."""
    rows = [("Python", platform.python_version(), "3.13", "ok" if sys.version_info[:2] == (3, 13) else "different")]
    for name, (op, ver, optional) in requirement_pins().items():
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            rows.append((name, "-", f"{op}{ver}", "optional" if optional else "missing"))
            continue
        if op == "==":
            state = "ok" if have == ver else "different"
        else:
            state = "ok" if _version_tuple(have) >= _version_tuple(ver) else "old"
        rows.append((name, have, f"{op}{ver}", state))
    return rows


def _version_tuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def verify_core_manifest() -> tuple[int, list[str]]:
    """Checks the files of the simulation core against docs/CORE_MANIFEST.sha256 (line endings normalised to LF).
    Returns (number of files, files that differ or are missing)."""
    manifest = DOCS / "CORE_MANIFEST.sha256"
    bad, n = [], 0
    if not manifest.exists():
        return 0, ["docs/CORE_MANIFEST.sha256 not found"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, rel = line.split(None, 1)
        rel = rel.strip().lstrip("*")
        n += 1
        f = SRC / rel
        if not f.exists():
            bad.append(f"{rel} (missing)")
            continue
        if hashlib.sha256(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != digest:
            bad.append(rel)
    return n, bad


# --------------------------------------------------------------------------------------------------------------------
# simulation cases and the state of the stored seasons


@lru_cache(maxsize=1)
def cases() -> dict:
    """case -> (scenario, chain, methods), phases and seasons, read from scripts/run_cases.py without importing the
    simulation core."""
    import ast
    ns = {}
    try:
        tree = ast.parse((SCRIPTS / "run_cases.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        tree = None
    for node in (tree.body if tree else []):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("CASES", "PHASES"):
            try:
                ns[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return {"cases": ns.get("CASES", {}), "phases": ns.get("PHASES", {}), "years": YEARS}


@dataclass
class Job:
    case: str
    method: str
    year: int
    state: str          # done | claimed | error | partial | missing
    minutes: float | None = None
    created: str | None = None

    @property
    def spec(self) -> str:
        return f"{self.case}:{self.method}:{self.year}"


def result_path(case: str, method: str, year: int) -> Path:
    return RUNS / case / f"{method}_{year}.csv"


def job_state(case: str, method: str, year: int) -> Job:
    """State of one stored season, with the completeness test of scripts/run_cases.py (as many daily rows as the
    season has days)."""
    p = result_path(case, method, year)
    meta = p.with_name(p.name + ".meta.json")
    minutes = created = None
    if p.exists() and meta.exists():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            with open(p, encoding="utf-8") as f:
                rows = sum(1 for _ in f) - 1
            minutes, created = m.get("minutes"), m.get("created_utc")
            if rows == int(m["params"]["days"]):
                return Job(case, method, year, "done", minutes, created)
        except (OSError, ValueError, KeyError):
            pass
    claim, error = p.with_suffix(".claim"), p.with_suffix(".error.txt")
    try:
        # a failed run keeps its claim and writes the error afterwards; a claim newer than the error is a new run
        if error.exists() and (not claim.exists() or error.stat().st_mtime >= claim.stat().st_mtime):
            return Job(case, method, year, "error", minutes, created)
    except OSError:
        pass
    if claim.exists():
        return Job(case, method, year, "claimed", minutes, created)
    if p.exists() or p.with_name(p.name + ".part").exists():
        return Job(case, method, year, "partial", minutes, created)
    return Job(case, method, year, "missing", minutes, created)


def inventory() -> list[Job]:
    c = cases()
    return [job_state(case, method, y) for case, (_, _, methods) in c["cases"].items() for method in methods
            for y in c["years"]]


def release_claim(case: str, method: str, year: int) -> list[Path]:
    """Removes the claim and the partial file of a season that is not being computed (left by an interrupted or failed
    run), so that the season can be computed again. Returns the removed files."""
    p = result_path(case, method, year)
    removed = []
    for f in (p.with_suffix(".claim"), p.with_name(p.name + ".part")):
        if f.exists():
            f.unlink()
            removed.append(f)
    return removed


def available_methods(case: str) -> list[str]:
    folder = RUNS / case
    if not folder.is_dir():
        return []
    found = {f.stem.rsplit("_", 1)[0] for f in folder.glob("*.csv")}
    order = list(cases()["cases"].get(case, ("", "", ()))[2])
    return [m for m in order if m in found] + sorted(found - set(order))


def available_cases() -> list[str]:
    order = list(cases()["cases"])
    found = [c for c in order if available_methods(c)]
    if RUNS.is_dir():
        found += sorted(d.name for d in RUNS.iterdir()
                        if d.is_dir() and d.name not in order and available_methods(d.name))
    return found


def available_years(case: str, method: str) -> list[int]:
    return sorted(int(f.stem.rsplit("_", 1)[1]) for f in (RUNS / case).glob(f"{method}_*.csv")
                  if f.stem.rsplit("_", 1)[1].isdigit())


def describe_table(path: Path) -> str:
    """Title of an analysis table: the first heading of the Markdown file written next to the CSV file."""
    md = path.with_suffix(".md")
    if md.exists():
        for line in md.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip()
    return ""
