"""Well risk scoring: how likely is a well to need a repair job within the next
`horizon` days, given recent sensor behavior and its repair history?

Snapshots are taken every `step` days per producing well. Features only use
information available on the snapshot date; the label looks forward.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROLL_COLS = [
    "pump_efficiency_pct",
    "pcp_pump_rpm",
    "pcp_pump_rod_torque_ftlb",
    "pcp_pump_electric_current_a",
    "tubing_pressure_kpa",
    "casing_pressure_kpa",
    "oil_produced_m3",
    "water_cut",
    "hours_down",
]
SENSOR_FEATURES = (
    [f"{c}_m30" for c in ROLL_COLS]
    + [f"{c}_m7" for c in ROLL_COLS]
    + [f"{c}_d" for c in ROLL_COLS]  # 7-day mean minus 30-day mean: recent change
)
HISTORY_FEATURES = ["repairs_90d", "repairs_365d", "days_since_repair", "repairs_total"]


def _rolling_features(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.sort_values(["uwi", "production_date"]).reset_index(drop=True)
    g = d.groupby("uwi", sort=False)
    out = d[["uwi", "production_date", "well_daily_status"]].copy()
    for c in ROLL_COLS:
        m30 = g[c].transform(lambda s: s.rolling(30, min_periods=10).mean())
        m7 = g[c].transform(lambda s: s.rolling(7, min_periods=3).mean())
        out[f"{c}_m30"] = m30.astype("float32")
        out[f"{c}_m7"] = m7.astype("float32")
        out[f"{c}_d"] = (m7 - m30).astype("float32")
    return out


def _history_and_label(snap: pd.DataFrame, repairs: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Add repair-history features (strictly before the date) and the forward label."""
    starts = {u: g["start_date"].sort_values().values.astype("datetime64[D]")
              for u, g in repairs.groupby("uwi")}
    n = len(snap)
    r90 = np.zeros(n); r365 = np.zeros(n); since = np.full(n, np.nan); tot = np.zeros(n)
    label = np.zeros(n, dtype=bool)
    pos = 0
    for u, idx in snap.groupby("uwi", sort=False).indices.items():
        arr = starts.get(u)
        if arr is None:
            since[idx] = np.nan
            continue
        dates = snap["production_date"].values[idx].astype("datetime64[D]")
        before = np.searchsorted(arr, dates, side="left")  # jobs strictly before date
        r90[idx] = before - np.searchsorted(arr, dates - np.timedelta64(90, "D"), side="left")
        r365[idx] = before - np.searchsorted(arr, dates - np.timedelta64(365, "D"), side="left")
        tot[idx] = before
        has = before > 0
        last = arr[np.clip(before - 1, 0, None)]
        since[idx] = np.where(has, (dates - last).astype("int64"), np.nan)
        upto = np.searchsorted(arr, dates + np.timedelta64(horizon, "D"), side="right")
        after = np.searchsorted(arr, dates, side="right")  # jobs on/before date
        label[idx] = (upto - after) > 0
    snap = snap.copy()
    snap["repairs_90d"] = r90; snap["repairs_365d"] = r365
    snap["days_since_repair"] = since; snap["repairs_total"] = tot
    snap["label"] = label
    return snap


def latest_snapshot(daily: pd.DataFrame, repairs: pd.DataFrame) -> pd.DataFrame:
    """Features for every producing well on the last day in the data (no label)."""
    feats = _rolling_features(daily)
    # the final calendar day can be a partial day with no status filled in,
    # so use the latest day on which any well has a status
    last_day = feats.loc[feats["well_daily_status"].notna(), "production_date"].max()
    snap = feats[(feats["production_date"] == last_day) & (feats["well_daily_status"] == "Producing")]
    snap = snap.reset_index(drop=True)
    snap = _history_and_label(snap, repairs.dropna(subset=["start_date"]), 30)
    return snap.drop(columns="label")


def build_snapshots(
    daily: pd.DataFrame, repairs: pd.DataFrame, step: int = 7, horizon: int = 30
) -> pd.DataFrame:
    """One row per producing well every `step` days with features and a forward label.

    `repairs` needs columns uwi, start_date (rod truck and workover jobs).
    Snapshots whose horizon runs past the end of the data are dropped.
    """
    feats = _rolling_features(daily)
    last_day = feats["production_date"].max()
    keep = (feats["well_daily_status"] == "Producing") & (
        (feats["production_date"] - feats["production_date"].min()).dt.days % step == 0
    )
    snap = feats[keep & (feats["production_date"] <= last_day - pd.Timedelta(days=horizon))]
    snap = snap.reset_index(drop=True)
    return _history_and_label(snap, repairs.dropna(subset=["start_date"]), horizon)
