"""Paired comparisons for the exploratory controllers and cases, with the same rules as the hypothesis tests
(daily differences, moving-block bootstrap within each season, Wilcoxon with Holm, sign consistency across seasons).

These comparisons were not pre-specified and are reported as exploratory.
  E1  LXB - B3 and LXB - B3V, lambda, "increase", for every variant (tuned/untuned x phys/iot); family {B3, B3V};
  E2  LXB-DA - LXB, lambda, "increase", tuned/iot and untuned/iot;
  E3  P1(LXB-DA) - P1(LXB), daily, "decrease", tuned and untuned. lambda_phys is taken from LXB, because the pulse
      rule is inactive under ideal execution and LXB-DA then coincides with LXB;
  E4  B3V - LXB, lambda, "increase", tuned/iot: the reverse direction of E1;
  E5  H3 with stricter tolerances: lambda with epsilon_1 = 1e-6 and Z2 (sum of r_j) with epsilon_2 = 1e-4;
  E6  reverse gate mismatch (untuned_reverse): LXB - B0, B3, B3V, lambda, "increase", untuned/phys and untuned/iot.
Output: results/exploratory_tests[_<scheme>].csv and .md
Usage: python scripts/compare_exploratory.py [--bootstrap block|circular|season]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_hypotheses as EH  # noqa: E402
from evaluate_hypotheses import VARIANTS, aligned, run_family, series  # noqa: E402
from water01.domain.passport import value  # noqa: E402
from water01.evaluation.hypotheses import evaluate_family  # noqa: E402
from water01.simulation.scenarios import load_config  # noqa: E402

RES = ROOT / "results"
SOURCES = {("LXB", "normal"): "experiment/normal", ("B3", "normal"): "experiment/normal",
           ("B3V", "normal"): "exploratory/b3_feedback", ("LXB-DA", "normal"): "exploratory/deadband_aware"}
REVERSE = "exploratory/untuned_reverse"


def read(folder, pattern="*.csv"):
    files = sorted((RES / folder).glob(pattern))
    if not files:
        sys.exit(f"No results in results/{folder}")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["tuned"] = df.tuned.astype(str); df["iot"] = df.iot.astype(str)
    df["year"] = df.year.astype(int); df["date"] = pd.to_datetime(df.date).dt.strftime("%Y-%m-%d")
    if df.duplicated(["method", "tuned", "iot", "year", "date"]).any():
        sys.exit(f"Duplicate days in results/{folder}")
    return df


def load():
    return pd.concat([read(d, f"{m}_*.csv") for (m, _), d in SOURCES.items()], ignore_index=True)


def lam_diff(df, a, b, tuned, iot):
    x, y, yrs = aligned(series(df, a, tuned, iot, "lambda"), series(df, b, tuned, iot, "lambda"))
    return (x - y).to_numpy(), yrs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bootstrap", choices=("block", "circular", "season"), default="block",
                    help="bootstrap scheme of the daily comparisons (default: block, as for the hypothesis tests)")
    args = ap.parse_args()
    EH.SCHEME = args.bootstrap
    suffix = "" if args.bootstrap == "block" else f"_{args.bootstrap}"
    load_config()
    seed = value("seed")
    df = load(); rows = []
    for tuned, iot in VARIANTS:                                                     # E1
        d, yrs = {}, None
        for b in ("B3", "B3V"):
            d[b], yrs = lam_diff(df, "LXB", b, tuned, iot)
        run_family(rows, "E1", "LXB − ", f"{tuned}/{iot}", d, yrs, "increase", seed, role="exploratory")
    for tuned in ("tuned", "untuned"):                                              # E2, E3
        d, yrs = lam_diff(df, "LXB-DA", "LXB", tuned, "iot")
        run_family(rows, "E2", "LXB-DA − ", f"{tuned}/iot", {"LXB": d}, yrs, "increase", seed, role="exploratory")
        ph = series(df, "LXB", tuned, "phys", "lambda")
        p_lx, p_da = (aligned(ph, series(df, m, tuned, "iot", "lambda")) for m in ("LXB", "LXB-DA"))
        ok = (p_lx[0] > 0).to_numpy()
        pi_lx = ((p_lx[0] - p_lx[1]) / p_lx[0]).to_numpy()[ok]
        pi_da = ((p_da[0] - p_da[1]) / p_da[0]).to_numpy()[ok]
        run_family(rows, "E3", "Π1(LXB-DA) − Π1(", f"{tuned}/iot", {"LXB)": pi_da - pi_lx}, p_lx[2][ok],
                   "decrease", seed, role="exploratory", note=f"days with λ_phys = 0 excluded: {int((~ok).sum())}")
    d, yrs = lam_diff(df, "B3V", "LXB", "tuned", "iot")                             # E4
    run_family(rows, "E4", "B3V − ", "tuned/iot", {"LXB": d}, yrs, "increase", seed, role="exploratory",
               note="reverse direction of E1")
    f = read("experiment/normal", "LXB_20??_tuned_phys.csv").sort_values(["year", "date"]).reset_index(drop=True)
    g = read("experiment/normal", "LXB-noS3_20??_tuned_phys.csv").sort_values(["year", "date"]).reset_index(drop=True)
    if not (f.date.values == g.date.values).all():
        sys.exit("LXB and LXB-noS3 cover different days")
    rc = [c for c in f.columns if c.startswith("r_")]
    for col, diff, eps in (("lambda", (f["lambda"] - g["lambda"]).to_numpy(), value("epsilon_1")),         # E5
                           ("Z2 (sum)", (f[rc].sum(axis=1) - g[rc].sum(axis=1)).to_numpy(), value("epsilon_2"))):
        for r in evaluate_family({"LXB-noS3": diff}, f.year.to_numpy(), "increase", eps=eps, seed=seed,
                                  scheme=args.bootstrap):
            rows.append(dict(hypothesis="E5", comparison=f"{col}: LXB − LXB-noS3", variant="tuned/phys",
                             role="exploratory", estimate=r.estimate, ci_low=r.ci_low, ci_high=r.ci_high,
                             p_raw=r.p_raw, p_holm=r.p_holm, sign_share=r.sign_share, n_days=len(diff),
                             decision=r.decision, note=f"eps = {eps:g}"))
    rev = read(REVERSE)                                                             # E6
    for iot in ("phys", "iot"):
        d, yrs = {}, None
        for b in ("B0", "B3", "B3V"):
            d[b], yrs = lam_diff(rev, "LXB", b, "untuned", iot)
        run_family(rows, "E6", "LXB − ", f"untuned (reverse)/{iot}", d, yrs, "increase", seed, role="exploratory")
    t = pd.DataFrame(rows)
    t.to_csv(RES / f"exploratory_tests{suffix}.csv", index=False)
    lines = ["| Test | Comparison | Variant | Estimate | 95% CI | Holm p | Sign share | Decision |", "|" + "---|" * 8]
    for r in t.itertuples():
        lines.append(f"| {r.hypothesis} | {r.comparison} | {r.variant} | {r.estimate:+.4g} | "
                     f"[{r.ci_low:+.4g}, {r.ci_high:+.4g}] | {r.p_holm:.2g} | {r.sign_share:.1f} | {r.decision} |")
    (RES / f"exploratory_tests{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
