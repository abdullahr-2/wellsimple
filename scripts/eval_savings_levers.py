"""Where could savings come from? Three candidate levers tested against the data.

1. Dispatch: is there a queue between a failure and its repair job to re-order?
2. Fix choice: within the same wells, do the "durable" fixes cost less per day of life?
3. Pump make: do some makes last longer once field and well differences are controlled?

Usage: DATA_DIR=... python scripts/eval_savings_levers.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from wellsimple import config, data, levers, scoring

FAMILY = {"Rod Repair": "rod", "Corod Rod Repair": "rod", "Stick Rod Repair": "rod", "Polish Rod Repair": "rod",
          "Rod Break - Corod": "rod", "Pump Repair/Replacement": "pump", "PCP Replacement": "pump",
          "PCP Upgrade": "pump", "Pump Repair": "pump", "Tubing Repair": "tubing", "Packer Repair": "tubing"}


def main():
    jobs = data.load_jobs()
    rep = data.add_job_outcomes(jobs)

    print("== 1. Dispatch: delay from failure to repair job")
    m = data.link_failures_to_jobs(data.load_failures(), jobs)
    print(f"  failures linked {len(m)} | same day or earlier {(m.lag <= 0).mean():.1%} | wait > 3 days {(m.lag > 3).mean():.1%} | > 7 days {(m.lag > 7).mean():.1%}")

    print("== 2. Fix choice: same wells, different fix families (cost per day of life)")
    daily = data.load_daily(["uwi", "production_date", "downtime_code_1", "lost_oil_m3"])
    lost_m3 = scoring.lost_m3_per_event(daily, len(rep))
    oil_per_event = lost_m3 * scoring.M3_TO_BBL * scoring.NETBACK_SCENARIOS["low"]
    r = rep.assign(fam=rep["job_type"].map(FAMILY))
    r = r[r["fam"].notna() & r["life_days"].notna() & r["cost"].notna()]
    multi = r.groupby("uwi")["fam"].nunique()
    w = r[r["uwi"].isin(multi[multi >= 2].index)].copy()
    w["cpd"] = w["cost"] / w["life_days"]
    w["cpd_with_oil"] = (w["cost"] + oil_per_event) / w["life_days"]
    print(f"  wells with 2+ fix families: {w['uwi'].nunique()}, jobs {len(w)}  (oil loss per event ${oil_per_event:,.0f} at the conservative price)")
    print(w.groupby("fam").agg(median_cost=("cost", "median"), median_life_days=("life_days", "median"),
                               cost_per_day=("cpd", "median"), cost_per_day_with_oil=("cpd_with_oil", "median")).round(0).to_string())

    print("== 3. Pump make: rate of the next repair, versus PCM (1.00 = same)")
    p = pd.read_parquet(config.DAILY, columns=["uwi", "production_date", "pcp_pump_make", "field_operating_area"])
    p = p.dropna(subset=["pcp_pump_make"]).rename(columns={"field_operating_area": "field"})
    p["make"] = p["pcp_pump_make"].str.strip().str.upper()
    f = levers.pump_followups(rep, p, daily["production_date"].max())
    g = f.groupby("make").agg(jobs=("t", "size"), events=("event", "sum"), years=("t", lambda s: s.sum() / 365))
    g["repairs_per_year"] = g["events"] / g["years"]
    print(g.round(2).to_string())
    multi_make = f.groupby("uwi")["make"].nunique()
    within = f[f["uwi"].isin(multi_make[multi_make >= 2].index)]
    print(f"  {f['uwi'].nunique()} wells, {len(f)} jobs; wells with 2+ makes: {within['uwi'].nunique()} ({len(within)} jobs)")
    out = {}
    for name, df, controls in (("no controls", f, []), ("same field", f, ["field"]), ("same well", within, ["uwi"])):
        est = levers.rate_ratios(df, controls, "PCM")
        ci = levers.cluster_bootstrap(df, controls, "PCM", n=60)
        out[name] = {k: f"{v:.2f} ({ci[k][0]:.2f}-{ci[k][1]:.2f})" if k in ci else f"{v:.2f}" for k, v in est.items()}
    print(pd.DataFrame(out).to_string())


if __name__ == "__main__":
    main()
