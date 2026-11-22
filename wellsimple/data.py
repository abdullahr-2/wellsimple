"""Loading and cleaning of the three competition files.

Cleaning rules come from checks run on the data:
 - pressure placeholders such as 999999 are set to missing
 - torque, motor current and pump efficiency have impossible spikes, set to missing
 - job costs of zero or less are set to missing (about 16% of rod/workover jobs)
 - duplicate well-day rows are dropped (one row per well per day)
 - the failure log is almost entirely 2025-2026, so outcome analysis for earlier
   years must use the job log, not the failure table
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

SENSOR_COLS = [
    "pump_efficiency_pct",
    "pcp_pump_rpm",
    "pcp_pump_rod_torque_ftlb",
    "pcp_pump_electric_current_a",
    "tubing_pressure_kpa",
    "casing_pressure_kpa",
    "oil_produced_m3",
    "water_produced_m3",
    "hours_on_prod",
    "hours_down",
    "lost_oil_m3",
]

# upper bounds beyond which a reading is treated as a sensor fault
_SPIKE_LIMITS = {
    "pcp_pump_rod_torque_ftlb": 20000,
    "pcp_pump_electric_current_a": 500,
    "pump_efficiency_pct": 5,  # stored as a decimal, so >5 is not a real efficiency
}


def clean_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric conversion, placeholder removal and water cut."""
    df = df.copy()
    if "production_date" in df:
        df["production_date"] = pd.to_datetime(df["production_date"])
    if {"uwi", "production_date"} <= set(df.columns):
        # the raw file repeats some well-days (58 rows on 2 wells in Oct 2026); keep one row per well per day
        df = df.drop_duplicates(["uwi", "production_date"], keep="last").reset_index(drop=True)
    for c in SENSOR_COLS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in ("tubing_pressure_kpa", "casing_pressure_kpa"):
        if c in df:
            df.loc[df[c] >= config.PRESSURE_PLACEHOLDER, c] = np.nan
    for c, hi in _SPIKE_LIMITS.items():
        if c in df:
            df.loc[df[c] > hi, c] = np.nan
    if {"water_produced_m3", "oil_produced_m3"} <= set(df.columns):
        total = (df["water_produced_m3"] + df["oil_produced_m3"]).replace(0, np.nan)
        df["water_cut"] = df["water_produced_m3"] / total
    return df


def load_daily(columns: list[str] | None = None) -> pd.DataFrame:
    return clean_daily(pd.read_parquet(config.DAILY, columns=columns))


def normalize_failure_type(x) -> str:
    """Collapse the messy free-text failure_type into four classes."""
    s = str(x).lower()
    if "rod" in s:
        return "Rods"
    if "pump" in s or "pcp" in s or "rotor" in s or "stator" in s:
        return "Pump"
    if "tub" in s or "tbg" in s:
        return "Tubing"
    return "Other"


def normalize_pump_make(x) -> str | None:
    """Fix inconsistent spelling such as MANTL / Mantl."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).strip()
    return s.upper() if s else None


def load_failures() -> pd.DataFrame:
    f = pd.read_parquet(config.FAILURES)
    f["failure_start_date"] = pd.to_datetime(f["failure_start_date"], errors="coerce")
    f = f.dropna(subset=["failure_start_date"]).reset_index(drop=True)
    f["failure_class"] = f["failure_type"].map(normalize_failure_type)
    return f


def load_jobs() -> pd.DataFrame:
    j = pd.read_parquet(config.JOBS)
    for c in ("start_date", "end_date"):
        j[c] = pd.to_datetime(j[c], errors="coerce")
    j["cost"] = pd.to_numeric(j["field_est_total"], errors="coerce")
    j.loc[j["cost"] <= 0, "cost"] = np.nan
    j["text"] = (
        j["objective"].fillna("").astype(str) + " . " + j["summary"].fillna("").astype(str)
    ).str.strip(" .").str.lower()
    j["is_repair"] = j["job_category"].isin(["Rod Truck", "Workover"])
    return j


def add_job_outcomes(jobs: pd.DataFrame) -> pd.DataFrame:
    """For repair jobs, add days until the next repair job on the same well.

    life_days is None for the last job on a well (no outcome observed). A well
    with a following job within 0 days or less is treated as unobserved.
    """
    r = jobs[jobs["is_repair"]].dropna(subset=["start_date"]).copy()
    r = r.sort_values(["uwi", "start_date"])
    r["next_start"] = r.groupby("uwi")["start_date"].shift(-1)
    r["done"] = r["end_date"].fillna(r["start_date"])
    r["life_days"] = (r["next_start"] - r["done"]).dt.days.astype("float64")
    r.loc[r["life_days"] <= 0, "life_days"] = np.nan
    # right-censoring flag: no later job observed
    r["censored"] = r["next_start"].isna()
    return r


def link_failures_to_jobs(
    failures: pd.DataFrame, jobs: pd.DataFrame, lo: int = -3, hi: int = 60
) -> pd.DataFrame:
    """Match each failure to the first repair job at the same well in [lo, hi] days."""
    f = failures.reset_index().rename(columns={"index": "fid"})
    rj = jobs[jobs["is_repair"]].dropna(subset=["start_date"])
    cols = [c for c in ("uwi", "start_date", "text", "cost", "job_category") if c in rj]
    m = f.merge(rj[cols], on="uwi")
    m["lag"] = (m["start_date"] - m["failure_start_date"]).dt.days
    m = m[(m["lag"] >= lo) & (m["lag"] <= hi)]
    m = m.sort_values(["fid", "lag"]).drop_duplicates("fid")
    return m.drop(columns="index", errors="ignore")
