"""Build the A/B pilot: enroll, randomize, check balance, validate the test, size the trial.

Outputs (in WORK_DIR, never committed): pilot.json and pilot.parquet.
The A/A check and the power table use real history; the outcome section stays empty
until follow-up data exists after enrollment (no result is invented).

Usage: DATA_DIR=... python scripts/build_pilot.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from wellsimple import abtest, config, data

SEED = 2026
ENROLL_MIN_BASELINE = 1  # at least one repeat repair in the 12 months before enrollment


def main():
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    rep = data.add_job_outcomes(data.load_jobs())
    cols = ["uwi", "production_date", "well_daily_status", "oil_produced_m3", "well_name", "field_operating_area"]
    daily = data.load_daily(cols)
    end = daily["production_date"].max()
    status_day = daily.loc[daily["well_daily_status"].notna(), "production_date"].max()
    today = daily[daily["production_date"] == status_day]
    producing = set(today.loc[today["well_daily_status"] == "Producing", "uwi"])
    meta = today.set_index("uwi")[["well_name", "field_operating_area"]]

    base0 = abtest.well_repeat_counts(rep, producing, end, 0)   # the 12 months before enrollment
    base1 = abtest.well_repeat_counts(rep, producing, end, 1)   # the 12 months before that
    oil30 = daily[(daily["production_date"] > status_day - pd.Timedelta(days=30)) & daily["uwi"].isin(producing)] \
        .groupby("uwi")["oil_produced_m3"].mean().reindex(sorted(producing))
    repairs12 = rep[(rep["start_date"] > end - pd.Timedelta(days=365)) & rep["uwi"].isin(producing)] \
        .groupby("uwi").size().reindex(sorted(producing), fill_value=0)

    # ---- enrollment and randomization -----------------------------------------------------
    pop = pd.DataFrame({"uwi": base0.index, "baseline_repeats": base0.values, "prior_year_repeats": base1.reindex(base0.index).values,
                        "repairs_12m": repairs12.reindex(base0.index).values, "oil_rate_m3d": oil30.reindex(base0.index).values})
    pop = pop.join(meta, on="uwi")
    elig = pop[pop["baseline_repeats"] >= ENROLL_MIN_BASELINE].copy()
    elig["bucket"] = pd.cut(elig["baseline_repeats"], [0, 1, 2, 10**6], labels=["1", "2", "3+"]).astype(str)
    elig["field"] = elig["field_operating_area"].fillna("unknown")
    strata = ["field", "bucket"]
    enrolled = abtest.randomize(elig, strata, seed=SEED)
    bal = abtest.balance_table(enrolled, ["baseline_repeats", "prior_year_repeats", "repairs_12m", "oil_rate_m3d"])
    n_sys, n_ctl = int((enrolled.arm == "system").sum()), int((enrolled.arm == "control").sum())
    print(f"producing {len(pop)} | eligible and enrolled {len(enrolled)} (system {n_sys}, control {n_ctl})")
    print(bal.round(3).to_string(index=False))

    # ---- A/A validation on real history: no intervention, so the test should rarely fire ----
    hist = pd.DataFrame({"uwi": base1.index, "baseline": base1.values, "outcome": base0.reindex(base1.index).values}).join(meta, on="uwi")
    hist = hist[hist["baseline"] >= ENROLL_MIN_BASELINE].copy()
    hist["bucket"] = pd.cut(hist["baseline"], [0, 1, 2, 10**6], labels=["1", "2", "3+"]).astype(str)
    hist["field"] = hist["field_operating_area"].fillna("unknown")
    aa = abtest.aa_false_positive_rate(hist, "outcome", strata, n_trials=200, n_perm=400, seed=SEED)
    print(f"A/A on real history ({len(hist)} wells, 200 random splits): false positive rate {aa['false_positive_rate']:.3f} "
          f"(95% interval {aa['ci_low']:.3f} to {aa['ci_high']:.3f}; expected about 0.05)")

    # ---- power at the enrolled size, calibrated on the real outcome distribution ----------
    rng = np.random.default_rng(SEED)
    counts = hist["outcome"].to_numpy()
    per_arm = min(n_sys, n_ctl)
    effects = (0.2, 0.3, 0.5)
    pw = {f"{int(e*100)}": abtest.power(counts, per_arm, e, rng, sims=600) for e in effects}
    mde = abtest.minimum_detectable_effect(counts, per_arm, rng)
    print(f"power at {per_arm} wells per arm: " + ", ".join(f"{k}% cut {v:.0%}" for k, v in pw.items()) + f" | smallest effect with 80% power: {mde}")

    enrolled[["uwi", "well_name", "field", "bucket", "arm", "baseline_repeats", "prior_year_repeats", "repairs_12m", "oil_rate_m3d"]] \
        .to_parquet(config.WORK_DIR / "pilot.parquet", index=False)
    plan = {
        "status": "enrolled, follow-up in progress", "enrolled_as_of": str(status_day.date()), "earliest_read": str((status_day + pd.Timedelta(days=365)).date()),
        "seed": SEED, "strata": strata, "n_system": n_sys, "n_control": n_ctl,
        "population": "producing wells with at least one repeat repair (a repair job within 30 days of the previous one on the same well) in the 12 months before enrollment",
        "arms": {"system": "the manager portal recommends and tracks action on the well", "control": "usual practice; the well is not surfaced"},
        "primary_outcome": "repeat repairs per well over 12 months after enrollment",
        "secondary_outcomes": ["repair job cost per well", "lost oil (m3) per well"],
        "analysis": "rate ratio (system / control), permutation p-value, bootstrap interval resampling wells within arm; one read at 12 months, no peeking",
        "balance": bal.to_dict("records"),
        "aa_check": {**aa, "wells": int(len(hist))},
        "power": {"wells_per_arm": per_arm, "by_effect_percent": pw, "min_detectable_effect_80pct": mde},
        "effect_size_reference": "Closest published before/after: a root-cause failure analysis program on PCPs in Chad (IPTC 17230, not peer reviewed) cut failure frequency from 0.47 to 0.21, about 55%, comparing 2007 with 2013. It is uncontrolled, a different setting and a physical teardown program, so it shows such programs can work but is not an estimate of our effect.",
    }
    (config.WORK_DIR / "pilot.json").write_text(json.dumps(plan, indent=2, default=float))
    print("wrote pilot.json and pilot.parquet")


if __name__ == "__main__":
    main()
