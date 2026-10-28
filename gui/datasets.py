"""Data of the project for the interface: configuration, recorded supply and demand, stored daily results and their
summaries. Independent of the graphical toolkit."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .project import CONFIGS, CORE_LOCK, RUNS, SUPPLY_FILE, YEARS, add_import_paths, read_yaml

USERS = ("Abad-Yarmish", "R-1", "Khalkabad-2", "Kanly-Yab", "K-2", "Lower Kegeyli")
REGULATORS = USERS[:5]


# --------------------------------------------------------------------------------------------------------------------
# configuration


def scenarios() -> list[tuple[str, str]]:
    """(name, description) of the scenarios in configs/scenarios."""
    out = []
    for f in sorted((CONFIGS / "scenarios").glob("*.yaml")):
        try:
            meta = (read_yaml(f) or {}).get("meta", {})
        except Exception:  # noqa: BLE001
            meta = {}
        out.append((f.stem, str(meta.get("description", ""))))
    out.sort(key=lambda r: (r[0] != "normal", r[0]))
    return out


def config_rows(scenario: str = "normal") -> pd.DataFrame:
    """Parameters of the reference configuration with the overrides of a scenario: section, name, value, unit-free
    status (observed, derived, assumed, setting) and source."""
    base = read_yaml(CONFIGS / "kegeyli_reference.yaml") or {}
    over = {}
    if scenario and scenario != "normal":
        f = CONFIGS / "scenarios" / f"{scenario}.yaml"
        if f.exists():
            over = (read_yaml(f) or {}).get("overrides") or {}
    rows = []
    for section, params in base.items():
        if section == "meta" or not isinstance(params, dict):
            continue
        for name, spec in params.items():
            value, status, source = _spec(spec)
            changed = name in over
            if changed:
                value, status2, source2 = _spec(over[name])
                status, source = status2 or status, f"[{scenario}] {source2}" if source2 else f"[{scenario}]"
            rows.append({"section": section, "parameter": name, "value": _fmt(value), "status": status,
                         "source": source, "scenario": "yes" if changed else ""})
    return pd.DataFrame(rows)


def _spec(spec):
    if isinstance(spec, dict) and "value" in spec:
        return spec["value"], str(spec.get("status", "")), str(spec.get("source", ""))
    return spec, "setting", ""


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_fmt(v)}" for k, v in value.items()) + "}"
    return str(value)


# --------------------------------------------------------------------------------------------------------------------
# recorded supply and plan-derived demand


def supply_season(year: int) -> pd.DataFrame:
    """Daily discharge recorded at the Kegeyli head regulator in the growing season (1 April - 30 September); blank
    entries are marked."""
    df = pd.read_csv(SUPPLY_FILE, parse_dates=["date"])
    df = df[(df.date.dt.year == year) & df.date.dt.month.between(4, 9)].copy()
    df["blank"] = df["kegeyli_Q"].isna()
    return df[["date", "kegeyli_Q", "blank"]].reset_index(drop=True)


def node_season(year: int) -> pd.DataFrame:
    """Daily volume available at the node, W = eta S day, the demand of the six outlets and the continuous max-min
    level lambda* = min{1, W / sum D} (as in the closed loop)."""
    add_import_paths()
    from analysis_common import node_water
    with CORE_LOCK:
        dates, A, D = node_water(year)
    df = pd.DataFrame({"date": dates, "W_m3": A})
    for j, u in enumerate(USERS):
        df[f"D_{u}"] = D[j]
    total = D.sum(axis=0)
    df["D_total_m3"] = total
    df["lambda_star"] = np.where(total > 0, np.minimum(1.0, A / np.where(total > 0, total, 1.0)), np.nan)
    return df


# --------------------------------------------------------------------------------------------------------------------
# stored daily results

_cache: dict = {}


def load_runs(case: str, method: str, years=None) -> pd.DataFrame:
    """Daily rows of the stored seasons of (case, method); files are cached by their modification time."""
    frames = []
    for y in (years or YEARS):
        f = RUNS / case / f"{method}_{y}.csv"
        if not f.exists():
            continue
        key = (str(f), f.stat().st_mtime)
        if key not in _cache:
            _cache[key] = pd.read_csv(f, parse_dates=["date"])
        frames.append(_cache[key])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def dekad_key(dates: pd.Series) -> pd.Series:
    """Calendar dekad of each date: days 1-10, 11-20 and 21 to the end of the month."""
    d = pd.to_datetime(dates)
    return d.dt.year * 1000 + d.dt.month * 10 + np.minimum((d.dt.day - 1) // 10, 2)


def dekad_errors(df: pd.DataFrame, user: str) -> pd.DataFrame:
    """Error of the delivery over calendar dekads, |sum V - sum x| / sum D, of one outlet."""
    if df.empty:
        return pd.DataFrame(columns=["dekad", "start", "V", "x", "D", "error"])
    g = df.assign(dekad=dekad_key(df["date"])).groupby("dekad").agg(
        start=("date", "min"), V=(f"V_{user}", "sum"), x=(f"x_{user}", "sum"), D=(f"D_{user}", "sum"))
    g["error"] = (g["V"] - g["x"]).abs() / g["D"].where(g["D"] > 0)
    return g.reset_index()


def summary(df: pd.DataFrame, user: str) -> dict:
    """Outcome of one rule over the selected seasons, for the node and for one outlet."""
    if df.empty:
        return {}
    out = {"seasons": int(df["year"].nunique()), "days": int(len(df)),
           "mean_lambda": float(df["lambda"].mean()), "min_lambda": float(df["lambda"].min()),
           "days_lambda_zero": int((df["lambda"] <= 1e-6).sum())}
    D, x, V = df[f"D_{user}"], df[f"x_{user}"], df[f"V_{user}"]
    xt = df.get(f"xt_{user}", x)
    out["delivery_ratio"] = float(V.sum() / D.sum()) if D.sum() > 0 else float("nan")
    out["volume_over_plan"] = float(V.sum() / x.sum()) if x.sum() > 0 else float("nan")
    out["days_positive_plan"] = int((x > 1e-6).sum())
    out["days_without_water"] = int(((x > 1e-6) & (V <= 1e-6)).sum())
    out["mean_abs_error_m3"] = float((V - xt).abs().mean())
    dk = dekad_errors(df, user)["error"].dropna()
    out["dekad_error_mean"] = float(dk.mean()) if len(dk) else float("nan")
    out["dekad_error_max"] = float(dk.max()) if len(dk) else float("nan")
    if f"open_{user}" in df:
        out["open_steps_per_day"] = float(df[f"open_{user}"].mean())
    if f"pulses_{user}" in df:
        out["pulses_per_day"] = float(df[f"pulses_{user}"].mean())
    return out


SUMMARY_LABELS = (
    ("seasons", "Seasons", "{:d}"),
    ("days", "Days", "{:d}"),
    ("mean_lambda", "Mean daily λ", "{:.4f}"),
    ("min_lambda", "Smallest daily λ", "{:.4f}"),
    ("days_lambda_zero", "Days with λ = 0", "{:d}"),
    ("delivery_ratio", "Delivery ratio ΣV / ΣD", "{:.4f}"),
    ("volume_over_plan", "Delivered volume / planned volume", "{:.4f}"),
    ("days_positive_plan", "Days with a positive plan", "{:d}"),
    ("days_without_water", "Positive plan, no water", "{:d}"),
    ("mean_abs_error_m3", "Mean |delivery − daily target|, m³", "{:.1f}"),
    ("dekad_error_mean", "Dekad error, unweighted mean", "{:.4f}"),
    ("dekad_error_max", "Dekad error, largest", "{:.4f}"),
    ("open_steps_per_day", "Open steps per day", "{:.2f}"),
    ("pulses_per_day", "Pulses per day", "{:.2f}"),
)


def table_file(path: Path, max_rows: int = 20000) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, nrows=max_rows)
    if path.suffix.lower() == ".json":
        return pd.json_normalize(pd.read_json(path, typ="series").to_dict())
    raise ValueError(f"unsupported table {path.name}")
