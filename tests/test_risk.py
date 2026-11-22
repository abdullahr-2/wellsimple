"""Checks the leakage-sensitive parts of risk.py on a hand-built example."""
import numpy as np
import pandas as pd

from wellsimple import risk


def _daily(n=120):
    dates = pd.date_range("2026-01-01", periods=n)
    d = pd.DataFrame({"uwi": "w1", "production_date": dates, "well_daily_status": "Producing"})
    for c in risk.ROLL_COLS:
        d[c] = 1.0
    return d


def test_history_is_strictly_before_and_label_looks_forward():
    daily = _daily()
    # repair jobs on day 40 and day 70 (0-indexed from 2026-01-01)
    repairs = pd.DataFrame(
        {"uwi": "w1", "start_date": pd.to_datetime(["2026-02-10", "2026-03-12"])}
    )
    snap = risk.build_snapshots(daily, repairs, step=1, horizon=30)
    row = lambda s: snap[snap.production_date == pd.Timestamp(s)].iloc[0]

    # day before the first job: no history yet, label True (job in next 30 days)
    r = row("2026-02-09")
    assert r.repairs_total == 0 and np.isnan(r.days_since_repair) and r.label

    # the job day itself is not counted as history and not counted as future
    r = row("2026-02-10")
    assert r.repairs_total == 0

    # day after: history sees the job, 1 day since
    r = row("2026-02-11")
    assert r.repairs_total == 1 and r.days_since_repair == 1 and r.repairs_90d == 1
    assert r.label  # next job is Mar 12, 29 days later

    # two days after Mar 12 job with nothing following within horizon -> label False
    r = row("2026-03-14")
    assert r.repairs_total == 2 and r.days_since_repair == 2 and not r.label


def test_snapshots_near_end_of_data_are_dropped():
    daily = _daily(60)
    snap = risk.build_snapshots(daily, pd.DataFrame({"uwi": [], "start_date": []}), step=1, horizon=30)
    assert snap.production_date.max() <= daily.production_date.max() - pd.Timedelta(days=30)


def test_latest_snapshot_scores_each_well_once_on_a_duplicate_reporting_day():
    daily = _daily()
    duplicated = pd.concat([daily, daily.tail(1)], ignore_index=True)
    snap = risk.latest_snapshot(duplicated, pd.DataFrame({"uwi": [], "start_date": []}))
    assert snap.uwi.tolist() == ["w1"]
