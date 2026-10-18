"""scripts/evaluate_hypotheses.py: tuned/untuned filter and pairing by (year, date)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from _inputs import SUP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/evaluate_hypotheses.py")
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)


def _frame():
    rows = []
    for y in (2010, 2011):                                   # the same calendar days in two years
        for d in ("04-01", "04-02"):
            for m, base in (("LXB", 0.8), ("B0", 0.7)):
                for t in ("tuned", "untuned"):
                    lam = base + (0.01 if y == 2011 else 0.0) + (0.0 if t == "tuned" else -0.5)
                    rows.append(dict(method=m, year=y, date=f"{y}-{d}", tuned=t, iot="phys", **{"lambda": lam}))
    return pd.DataFrame(rows)


def test_filter_by_column_and_pair_by_year_and_date(tmp_path, monkeypatch):
    out = tmp_path / "results/experiment/normal"; out.mkdir(parents=True)
    df = _frame()
    for (m, y, t), g in df.groupby(["method", "year", "tuned"]):
        g.to_csv(out / f"{m}_{y}_{t}_phys.csv", index=False)
    monkeypatch.setattr(ev, "ROOT", tmp_path)
    d = ev.load("tuned", "phys", "normal")
    assert set(d.tuned) == {"tuned"} and len(d) == 8        # untuned rows are excluded
    diff, years = ev.paired(d, "LXB", "B0", "lambda")
    assert len(diff) == 4 and np.allclose(diff, 0.1)          # 2 years × 2 days, each paired within its own year
    assert sorted(years.tolist()) == [2010, 2010, 2011, 2011]


def test_duplicate_or_mismatched_days_are_rejected():
    d = _frame(); d = d[d.tuned == "tuned"]
    with pytest.raises(ValueError):
        ev.paired(d[~((d.method == "B0") & (d.date == "2011-04-02"))], "LXB", "B0", "lambda")
    dup = pd.concat([d, d.iloc[[0]]])
    with pytest.raises(ValueError):
        ev.paired(dup, "LXB", "B0", "lambda")


def _synthetic_full():
    """Synthetic data for all hypotheses: additive IoT factors (known φ); stage 3 reduces Z3."""
    rng = np.random.default_rng(0)
    users = list(ev.USERS)
    effect = {"S": 0.01, "Q": 0.03, "C": 0.02, "E": 0.0}            # relative loss from λ_phys = 0.8
    rows = []
    codes = ["phys", "iot"] + [c for c in ("S", "Q", "C", "E", "SQ", "SC", "SE", "QC", "QE", "CE", "SQC", "SQE",
                                            "SCE", "QCE")]
    for y in range(2010, 2020):
        for k, d in enumerate(pd.date_range(f"{y}-04-01", periods=30)):
            base = 0.8 + 0.01 * rng.standard_normal()
            def add(m, t, i, lam, jitter=0.0):
                r = {f"r_{u}": lam + jitter * (2 * (k % 2) - 1) for u in users}
                rows.append(dict(method=m, year=y, date=d.strftime("%Y-%m-%d"), tuned=t, iot=i, **{"lambda": lam},
                                 **r, **{f"lost_{u}": 0 for u in users}))
            for t in ("tuned", "untuned"):
                for i in ("phys", "iot"):
                    loss = (sum(effect.values()) if i == "iot" else 0.0) + (0.02 if t == "untuned" else 0.0)
                    lam = base * (1 - loss)
                    add("LXB", t, i, lam)
                    for b, gap in (("B0", 0.05), ("B1", 0.1), ("B2", 0.02), ("B3", 0.03), ("Oracle", -0.01)):
                        extra = 2 * loss if b == "B1" else loss
                        add(b, t, i, base * (1 - extra) - gap)
            for c in codes[2:]:
                add("LXB", "tuned", c, base * (1 - sum(effect[x] for x in c)))
            add("LXB-noS3", "tuned", "phys", base, jitter=0.05)
    df = pd.DataFrame(rows)
    rc = [f"r_{u}" for u in users]
    df = df.sort_values(["method", "tuned", "iot", "year", "date"]).reset_index(drop=True)
    df["Z3"] = df.groupby(["method", "tuned", "iot", "year"])[rc].diff().abs().sum(axis=1, min_count=1)
    df["Z2"] = df[rc].mean(axis=1)
    return df


def test_full_pipeline_recovers_known_effects():
    res, table = ev.evaluate(_synthetic_full(), seed=1, supply_csv=SUP)
    get = lambda h, c=None: res[(res.hypothesis == h) & (res.comparison.str.contains(c or ""))]
    assert (get("H1").decision == "superior").all()
    assert get("H2", "B1").query("role == 'primary'").decision.iloc[0] == "supported"
    h3 = get("H3")
    assert h3[h3.comparison.str.startswith("Z3")].decision.iloc[0] == "supported"
    assert not (h3.decision == "rejected").any()
    assert get("H4").decision.iloc[0] == "supported"
    assert (get("H5").role == "descriptive").all()
    assert (get("H6").decision == "not testable").all()                   # no step without head
    phi = table[[c for c in table if c.startswith("phi_")]].mean()
    assert np.allclose(phi.values, [0.01, 0.03, 0.02, 0.0], atol=1e-9)          # additive: φ equals the factor effect
    assert get("H7", "φ").decision.iloc[0] == "supported"
