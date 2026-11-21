"""How big a field trial would it take to measure the saving?

We cannot measure savings from history alone because nothing in the data is an intervention.
This script calibrates a trial on the real data: the outcome is repeat repairs (a repair job
starting within 30 days of the previous repair on the same well) per well per year. Wells are
resampled from the real last-12-month distribution, half get a hypothetical reduction in
repeats, and we count how often a standard test detects it.

Usage: DATA_DIR=... python scripts/trial_power.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from wellsimple import data, reliability
from wellsimple.abtest import power, well_repeat_counts


def main():
    jobs = data.load_jobs()
    rep = data.add_job_outcomes(jobs)
    daily = data.load_daily(["uwi", "production_date", "well_daily_status"])
    last_day = daily.loc[daily["well_daily_status"].notna(), "production_date"].max()
    producing = set(daily.loc[(daily["production_date"] == last_day) & (daily["well_daily_status"] == "Producing"), "uwi"])
    end = daily["production_date"].max()
    series = well_repeat_counts(rep, producing, end)
    counts = series.to_numpy()
    prior = well_repeat_counts(rep, producing, end, years_back=1)
    targeted = series[prior >= 1].to_numpy()  # wells that already had a repeat the year before
    pool = reliability.repeat_spend(rep, 30)
    per_repeat = pool["cost"] / max(pool["jobs"], 1)
    print(f"producing wells {len(counts)} | repeat repairs per well-year: mean {counts.mean():.2f}, "
          f"{(counts == 0).mean():.0%} of wells had none, max {counts.max()}")
    print(f"measured repeat pool: ${pool['cost_per_year']:,.0f} a year, ${per_repeat:,.0f} per repeat job (field estimates)")
    rng = np.random.default_rng(0)
    sizes = (50, 100, 200, 400, 669)
    effects = (0.10, 0.20, 0.30, 0.50)
    table = pd.DataFrame({f"{int(e*100)}% fewer": [power(counts, n, e, rng) for n in sizes] for e in effects},
                         index=[f"{n} wells per arm" for n in sizes])
    print("\nPower (share of simulated 12-month trials that detect the reduction at alpha = 0.05):")
    print(table.round(2).to_string())
    sizes_t = tuple(n for n in (25, 50, 100, 150) if n < len(targeted))
    print(f"\nTargeted design: only wells with at least one repeat in the prior 12 months "
          f"({len(targeted)} wells, mean {targeted.mean():.2f} repeats per well-year, {(targeted == 0).mean():.0%} had none):")
    tt = pd.DataFrame({f"{int(e*100)}% fewer": [power(targeted, n, e, rng) for n in sizes_t] for e in effects},
                      index=[f"{n} wells per arm" for n in sizes_t])
    print(tt.round(2).to_string())
    print("\nValue of each effect if it held across the whole producing fleet:")
    for e in effects:
        print(f"  {int(e*100)}% fewer repeats: about ${pool['cost_per_year'] * e:,.0f} a year of repair spend (before oil)")


if __name__ == "__main__":
    main()
