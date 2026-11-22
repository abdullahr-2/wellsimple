"""Unit tests on tiny synthetic frames (no competition data is used or committed)."""
import numpy as np
import pandas as pd

from wellsimple import data


def test_clean_daily_removes_placeholders_and_spikes():
    df = pd.DataFrame(
        {
            "production_date": ["2026-01-01", "2026-01-02"],
            "tubing_pressure_kpa": [1200, 999999],
            "pcp_pump_rod_torque_ftlb": [600, 331460],
            "pump_efficiency_pct": [0.7, 91.4],
            "water_produced_m3": [30, 0],
            "oil_produced_m3": [10, 0],
        }
    )
    out = data.clean_daily(df)
    assert out["tubing_pressure_kpa"].isna().tolist() == [False, True]
    assert out["pcp_pump_rod_torque_ftlb"].isna().tolist() == [False, True]
    assert out["pump_efficiency_pct"].isna().tolist() == [False, True]
    assert out["water_cut"].iloc[0] == 0.75
    assert np.isnan(out["water_cut"].iloc[1])  # zero fluid, not zero water cut


def test_failure_type_normalization():
    assert data.normalize_failure_type("Rods") == "Rods"
    assert data.normalize_failure_type("Parted rod") == "Rods"
    assert data.normalize_failure_type("ES- PCP") == "Pump"
    assert data.normalize_failure_type("Hole in tubing") == "Tubing"
    assert data.normalize_failure_type("Hole in csig") == "Other"


def test_pump_make_normalization():
    assert data.normalize_pump_make("Mantl") == data.normalize_pump_make("MANTL")
    assert data.normalize_pump_make(None) is None
    assert data.normalize_pump_make(float("nan")) is None


def _jobs():
    return pd.DataFrame(
        {
            "uwi": ["a", "a", "a", "b"],
            "job_category": ["Rod Truck", "Workover", "Drilling", "Rod Truck"],
            "start_date": pd.to_datetime(["2026-01-10", "2026-02-09", "2026-03-01", "2026-01-05"]),
            "end_date": pd.to_datetime(["2026-01-10", "2026-02-10", "2026-03-02", "2026-01-05"]),
            "text": ["broken p-rod", "pump change", "drill", "tubing leak"],
            "cost": [5000.0, 40000.0, 9e5, np.nan],
            "is_repair": [True, True, False, True],
        }
    )


def test_job_outcomes_days_to_next_repair():
    out = data.add_job_outcomes(_jobs())
    a = out[out["uwi"] == "a"].sort_values("start_date")
    assert a["life_days"].iloc[0] == 30  # Jan 10 -> Feb 9
    assert a["censored"].tolist() == [False, True]  # drilling job is not a repair
    assert out[out["uwi"] == "b"]["censored"].iloc[0]


def test_link_failures_to_jobs_window():
    f = pd.DataFrame(
        {
            "uwi": ["a", "a", "z"],
            "failure_start_date": pd.to_datetime(["2026-01-08", "2026-02-09", "2026-01-01"]),
        }
    )
    m = data.link_failures_to_jobs(f, _jobs())
    assert len(m) == 2  # well z has no job
    first = m[m["failure_start_date"] == pd.Timestamp("2026-01-08")].iloc[0]
    assert first["lag"] == 2 and first["text"] == "broken p-rod"


def test_clean_daily_drops_duplicate_well_days():
    df = pd.DataFrame({"uwi": ["a", "a", "a"], "production_date": ["2026-10-14", "2026-10-14", "2026-10-15"],
                       "oil_produced_m3": [1.0, 2.0, 3.0]})
    out = data.clean_daily(df)
    assert len(out) == 2 and out["oil_produced_m3"].tolist() == [2.0, 3.0]
