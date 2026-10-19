"""Configuration (YAML): reference + scenario. Code reads parameters from here and does not hard-code them.

    configs/kegeyli_reference.yaml          -- all parameters (value, status, source)
    configs/scenarios/<name>.yaml            -- `overrides:` (only the parameters that change) and, for options
                                                that the reference case does not use, `additions:` (new parameters
                                                with value, status and source; the reference file stays unchanged)

load(reference, scenario) -> Config; activate(cfg) makes it active (value(name) reads from it).
Each process (including parallel experiment workers) loads and activates its own configuration.
"""
import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

STATUSES = {"observed", "derived", "assumed", "setting"}
ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "configs"
REFERENCE = CONFIG_DIR / "kegeyli_reference.yaml"


@dataclass(frozen=True)
class Parameter:
    value: object
    status: str
    source: str
    section: str = ""

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"Invalid status: {self.status}")


def _is_entry(node):
    return isinstance(node, dict) and "value" in node


def _parse(node, section):
    if _is_entry(node):
        return Parameter(node["value"], node.get("status", "setting"), node.get("source", ""), section)
    return Parameter(node, "setting", "", section)


def _flatten(doc):
    params = {}
    for section, body in doc.items():
        if section == "meta":
            continue
        if not isinstance(body, dict):
            raise ValueError(f"Section '{section}' must be a mapping")
        for name, node in body.items():
            if name in params:
                raise ValueError(f"Duplicate parameter name: {name} ({params[name].section} and {section})")
            params[name] = _parse(node, section)
    return params


@dataclass
class Config:
    params: dict
    meta: dict
    scenario: str = "reference"
    files: dict = field(default_factory=dict)          # {path: sha256}

    def value(self, name):
        try:
            return self.params[name].value
        except KeyError:
            raise KeyError(f"Parameter '{name}' not found in configuration") from None

    def __getattr__(self, name):                       # cfg.epsilon_1, cfg.seed, …
        if name.startswith("_") or name in ("params", "meta", "scenario", "files"):
            raise AttributeError(name)
        return self.value(name)

    # convenience attributes used by the run manifest
    @property
    def dt_minutes(self):
        return int(round(self.value("dt_s") / 60))

    @property
    def raw(self):
        return {k: p.value for k, p in self.params.items()}

    def with_overrides(self, overrides, name="custom"):
        new = copy.deepcopy(self)
        _apply(new.params, overrides)
        new.scenario = name
        return new


def _apply(params, overrides):
    for name, node in (overrides or {}).items():
        if name not in params:
            raise KeyError(f"Scenario overrides an unknown parameter: {name}")
        old = params[name]
        if _is_entry(node):
            params[name] = Parameter(node["value"], node.get("status", old.status), node.get("source", old.source),
                                     old.section)
        else:
            params[name] = Parameter(node, old.status, old.source, old.section)


def _add(params, additions):
    """Scenario-only options: parameters absent from the reference configuration (section "scenario")."""
    for name, node in (additions or {}).items():
        if name in params:
            raise KeyError(f"Scenario adds a parameter that already exists: {name} (use overrides)")
        params[name] = _parse(node, "scenario")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenario_path(scenario):
    if scenario is None or scenario in ("reference", "normal"):
        return CONFIG_DIR / "scenarios" / "normal.yaml"
    p = Path(scenario)
    return p if p.suffix in (".yaml", ".yml") else CONFIG_DIR / "scenarios" / f"{scenario}.yaml"


def load(reference=None, scenario=None):
    ref = Path(reference) if reference else REFERENCE
    doc = yaml.safe_load(ref.read_text(encoding="utf-8"))
    params = _flatten(doc)
    files = {str(ref): _sha(ref)}
    name = "normal"
    sp = scenario_path(scenario)
    if sp.exists():
        sdoc = yaml.safe_load(sp.read_text(encoding="utf-8")) or {}
        _apply(params, sdoc.get("overrides"))
        _add(params, sdoc.get("additions"))
        name = (sdoc.get("meta") or {}).get("name", sp.stem)
        files[str(sp)] = _sha(sp)
    elif scenario not in (None, "reference", "normal"):
        raise FileNotFoundError(sp)
    cfg = Config(params, doc.get("meta", {}), name, files)
    _validate(cfg)
    return cfg


def _validate(cfg):
    v = cfg.value
    if v("steps_per_day") * v("dt_s") != 86400:
        raise ValueError("steps_per_day * dt_s is not equal to 86400")
    if not 0.5 <= v("preissmann_theta") <= 1.0:
        raise ValueError("Preissmann θ must lie in [0.5, 1]")
    if v("sensor") not in v("devices"):
        raise ValueError(f"Sensor '{v('sensor')}' is not in the devices list")


_ACTIVE = None


def activate(cfg):
    global _ACTIVE
    _ACTIVE = cfg
    return cfg


def active():
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = load()
    return _ACTIVE


def value(name):
    return active().value(name)


def optional(name, default=None):
    """Value of a scenario-only option (see `additions`), or `default` when the active configuration lacks it."""
    params = active().params
    return params[name].value if name in params else default
