"""Turn model output into what a manager needs: risk, dollars and reasons per well."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from . import risk

M3_TO_BBL = 6.2898

# Net value of one extra barrel, C$/bbl. Defaults come from Strathcona's Q3 2026
# release: operating earnings 32.50 $/boe (low) and sales minus royalties,
# transport and energy about 61.60 $/boe (mid). These are assumptions, not data.
NETBACK_SCENARIOS = {"low": 32.50, "mid": 61.60}

# Human-readable labels for the strongest feature signals.
REASON_LABELS = {
    "pump_efficiency_pct_d": ("Pump efficiency falling", -1),
    "pump_efficiency_pct_m30": ("Low pump efficiency", -1),
    "pcp_pump_rod_torque_ftlb_m30": ("High rod torque", 1),
    "pcp_pump_rod_torque_ftlb_d": ("Rod torque rising", 1),
    "pcp_pump_electric_current_a_m30": ("High motor current", 1),
    "casing_pressure_kpa_m30": ("High casing pressure", 1),
    "tubing_pressure_kpa_m30": ("High tubing pressure", 1),
    "water_cut_m30": ("High water cut", 1),
    "oil_produced_m3_d": ("Oil rate down vs 30-day average", -1),
    "hours_down_m7": ("Recent downtime", 1),
    "repairs_90d": ("Repaired recently (repeat risk)", 1),
    "repairs_365d": ("Frequent repairs this year", 1),
    "days_since_repair": ("Long time since last repair", 1),
}


def fit_model(snapshots: pd.DataFrame) -> HistGradientBoostingClassifier:
    feats = risk.SENSOR_FEATURES + risk.HISTORY_FEATURES
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, random_state=0)
    return m.fit(snapshots[feats], snapshots["label"])


def reasons_for(row: pd.Series, ref: pd.DataFrame, top: int = 3, pct: float = 0.85) -> list[str]:
    """Flag features where this well is unusual versus the producing fleet today.

    Rank-based and model-agnostic: a reason appears when the well sits in the
    worst `1 - pct` of the fleet in the direction that signals trouble.
    """
    scored = []
    for col, (label, sign) in REASON_LABELS.items():
        v = row.get(col)
        if v is None or not np.isfinite(v):
            continue
        rank = (ref[col].dropna() < v).mean()
        bad = rank if sign > 0 else 1 - rank
        if bad >= pct:
            scored.append((bad, label))
    return [lab for _, lab in sorted(scored, reverse=True)[:top]]


def expected_loss(
    p_repair: pd.Series,
    oil_rate_m3d: pd.Series,
    typical_cost: float,
    lost_m3_per_event: float,
    fleet_oil_rate: float,
    netback_per_bbl: float,
) -> pd.DataFrame:
    """Expected dollars at risk from a repair in the next 30 days.

    cost of the job plus oil lost, scaled to this well's rate relative to the fleet
    (a high-rate well loses more oil per event than a low-rate one).
    """
    rate = oil_rate_m3d.fillna(fleet_oil_rate).clip(lower=0)
    lost_m3 = lost_m3_per_event * rate / max(fleet_oil_rate, 1e-9)
    lost_dollars = lost_m3 * M3_TO_BBL * netback_per_bbl
    event_cost = typical_cost + lost_dollars
    return pd.DataFrame({"event_cost": event_cost, "expected_loss": p_repair * event_cost})


def lost_m3_per_event(daily: pd.DataFrame, n_repair_events: int) -> float:
    """Average equipment-related lost oil per repair job, measured from the data."""
    code = daily["downtime_code_1"].fillna("").str.contains("Downhole", case=False)
    return float(daily.loc[code, "lost_oil_m3"].sum() / max(n_repair_events, 1))
