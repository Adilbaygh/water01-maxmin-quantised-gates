"""Package structure: layers import only permitted layers; no stale flat modules remain."""
import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "water01"
ALLOWED = {
    "domain": {"domain"},
    "hydraulics": {"domain", "hydraulics"},
    "optimization": {"domain", "optimization"},
    "iot": {"domain", "iot"},
    "control": {"domain", "optimization", "iot", "control"},
    "evaluation": {"domain", "optimization", "evaluation"},
    "simulation": {"domain", "hydraulics", "optimization", "iot", "control", "evaluation", "simulation"},
}
OLD_FLAT = ("command", "config", "controllers", "data", "energy", "estimator", "execution", "experiment", "gates",
            "geometry", "idmodel", "lexlp", "metrics", "node", "plant", "price")


def _imported_layers(path, layer):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level:
            parts = (n.module or "").split(".")
            if n.level > 1 and not n.module:
                continue                                   # package root (__version__) is allowed for all
            out.add(layer if n.level == 1 else parts[0])
        elif isinstance(n, ast.ImportFrom) and (n.module or "").startswith("water01."):
            out.add(n.module.split(".")[1])
    return out


def test_layers_respect_dependencies():
    bad = []
    for layer, allowed in ALLOWED.items():
        for f in (PKG / layer).glob("*.py"):
            extra = _imported_layers(f, layer) - allowed
            if extra:
                bad.append(f"{layer}/{f.name}: {sorted(extra)}")
    assert not bad, bad


def test_no_stale_flat_modules():
    stale = [m + ".py" for m in OLD_FLAT if (PKG / f"{m}.py").exists()]
    assert not stale, f"Remove the stale flat modules (see the package layout in README): {stale}"
