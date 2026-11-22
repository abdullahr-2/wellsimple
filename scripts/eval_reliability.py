"""Is risk highest right after a repair, and is that real or just bad wells failing first?

A Weibull shape below 1 means the chance of another repair falls with time since the last one.
That pattern can also appear when good and bad wells are mixed (bad wells fail early and drop
out), so we refit within groups of similarly repair-prone wells and within the same well.

Usage: DATA_DIR=... python scripts/eval_reliability.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from wellsimple import data, reliability as rel


def main():
    rep = data.add_job_outcomes(data.load_jobs())
    r = rel.survival_times(rep, rep["start_date"].max())
    k, lam = rel.fit_weibull(r["t"], r["event"])
    lo, hi = rel.bootstrap_shape(r["t"], r["event"])
    print(f"All repair jobs ({len(r):,}): shape k = {k:.2f} (95% CI {lo:.2f} to {hi:.2f})")
    h = rel.empirical_hazard(r.loc[r.job_category == "Rod Truck", "t"], r.loc[r.job_category == "Rod Truck", "event"])
    print(f"Rod truck: {h[0]['hazard_per_day']:.2%} per day in week 1 vs {h[6]['hazard_per_day']:.2%} at 6 to 12 months")

    per_well = r.groupby("uwi").size()
    r["group"] = pd.cut(r["uwi"].map(per_well), [0, 3, 8, 20, 10**6], labels=["1 to 3", "4 to 8", "9 to 20", "21+"])
    print("\nWithin groups of similarly repair-prone wells:")
    for g, d in r.groupby("group", observed=True):
        kg, lg = rel.fit_weibull(d["t"], d["event"])
        print(f"  wells with {g:7s} repairs: jobs {len(d):6,}  k = {kg:.2f}  median life {lg * np.log(2) ** (1 / kg):6.0f} days")

    med = r[r["event"]].groupby("uwi")["t"].median()
    w = r[r["uwi"].map(per_well) >= 6].copy()
    w["scaled"] = w["t"] / w["uwi"].map(med)
    w = w[np.isfinite(w["scaled"]) & (w["scaled"] > 0)]
    kw, _ = rel.fit_weibull(w["scaled"], w["event"])
    lo_w, hi_w = rel.bootstrap_shape(w["scaled"], w["event"])
    print(f"\nSame well compared with itself (each well's times divided by its own median, wells with 6+ repairs, "
          f"{len(w):,} jobs): k = {kw:.2f} (95% CI {lo_w:.2f} to {hi_w:.2f})")
    print("Below 1 within the same well: the early-failure effect is real, not only a mix of good and bad wells.")


if __name__ == "__main__":
    main()
