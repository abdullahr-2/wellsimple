"""Physics-based features for progressing cavity pumps (PCPs).

A PCP is a positive-displacement pump: a steel rotor turns inside a rubber (elastomer) stator,
driven from surface by a rod string. That gives a few relations we can use directly.

  Theoretical rate   Q_theo = displacement (m3/d at 100 RPM) x RPM / 100
  Volumetric eff.    eta = Q_actual / Q_theo. The shortfall is "slip": fluid leaking back across
                     the rotor-stator seal lines, which grows as the stator wears.
  Hydraulic torque   energy balance (power = Q x dP = torque x angular speed) gives
                     T_hyd = (volume per revolution) x dP / (2 pi), so at a given pump size torque
                     tracks the pressure the pump works against, plus friction (sand, a swollen or
                     tight elastomer) and viscous drag (heavy oil).
  Rod string         load is mainly torsional and it turns once per pump revolution, so fatigue
                     builds with revolutions under load (Miner's rule: damage adds up per cycle,
                     weighted by stress to a power).

Each feature uses only data up to its own day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FLEET_TORQUE_PER_DISP = 9.18  # median rod torque (ft-lbf) per unit displacement across producing well-days
FATIGUE_EXPONENT = 3.0        # S-N style stress exponent; an assumption for the fatigue index, not a measured value

PHYSICS_FEATURES = [
    "eff_drop_rate",       # change in volumetric efficiency per day (7-day mean now vs 23 days earlier)
    "rpm_cv30",            # speed variability over 30 days (operator changes, unstable drive)
    "torque_spike",        # 7-day max torque / 30-day median torque (slugs of sand, sticking)
    "torque_per_disp_m30", # torque normalised by pump size: a proxy for differential pressure + friction
    "torque_per_disp_d",   # its recent change (7-day minus 30-day)
    "revs_since_repair",   # pump (and rod) revolutions since the last repair job, millions
    "fatigue_since_repair",# revolutions weighted by (relative torque)^3 since the last repair job, millions
]


def _group_roll(s: pd.Series, by: pd.Series, window: int, how: str, min_periods: int) -> pd.Series:
    r = s.groupby(by, sort=False).rolling(window, min_periods=min_periods)
    out = getattr(r, how)()
    return out.reset_index(level=0, drop=True).sort_index()


def physics_features(daily: pd.DataFrame, repairs: pd.DataFrame) -> pd.DataFrame:
    """Per well-day physics features. `daily` needs uwi, production_date, pump_efficiency_pct,
    pcp_pump_rpm, pcp_pump_rod_torque_ftlb, pcp_pump_displacement_m3d100rpm, hours_on_prod.
    `repairs` needs uwi, start_date. Returns uwi, production_date and PHYSICS_FEATURES."""
    d = daily.sort_values(["uwi", "production_date"]).reset_index(drop=True)
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float)
    eff, rpm, torque = num("pump_efficiency_pct"), num("pcp_pump_rpm"), num("pcp_pump_rod_torque_ftlb")
    disp, hours = num("pcp_pump_displacement_m3d100rpm"), num("hours_on_prod").fillna(0).clip(0, 24)
    eff = eff.where(eff <= 5)                       # stored as a decimal; larger values are faults
    torque = torque.where(torque <= 20000)
    disp = disp.where(disp > 0)
    u = d["uwi"]
    out = d[["uwi", "production_date"]].copy()

    eff7 = _group_roll(eff, u, 7, "mean", 3)
    out["eff_drop_rate"] = (eff7 - eff7.groupby(u).shift(23)) / 23.0
    rpm_m = _group_roll(rpm, u, 30, "mean", 10)
    rpm_s = _group_roll(rpm, u, 30, "std", 10)
    out["rpm_cv30"] = rpm_s / rpm_m.where(rpm_m > 0)
    t_max7 = _group_roll(torque, u, 7, "max", 3)
    t_med30 = _group_roll(torque, u, 30, "median", 10)
    out["torque_spike"] = t_max7 / t_med30.where(t_med30 > 0)
    tpd = torque / disp
    tpd30 = _group_roll(tpd, u, 30, "mean", 10)
    out["torque_per_disp_m30"] = tpd30
    out["torque_per_disp_d"] = _group_roll(tpd, u, 7, "mean", 3) - tpd30

    # revolutions and fatigue since the last repair job on the well
    revs = (rpm.fillna(0).clip(lower=0) * 60.0 * hours)
    rel = (tpd / FLEET_TORQUE_PER_DISP).fillna(1.0).clip(0, 5)
    damage = revs * rel ** FATIGUE_EXPONENT
    starts = {w: g["start_date"].sort_values().values.astype("datetime64[ns]") for w, g in repairs.groupby("uwi")}
    epoch = np.zeros(len(d), dtype=np.int64)
    dates = d["production_date"].values.astype("datetime64[ns]")
    for w, idx in d.groupby("uwi", sort=False).indices.items():
        arr = starts.get(w)
        if arr is not None:
            epoch[idx] = np.searchsorted(arr, dates[idx], side="right")  # a repair on day D resets from D on
    key = [u, pd.Series(epoch, index=d.index)]
    out["revs_since_repair"] = revs.groupby(key).cumsum() / 1e6
    out["fatigue_since_repair"] = damage.groupby(key).cumsum() / 1e6
    for c in PHYSICS_FEATURES:
        out[c] = out[c].replace([np.inf, -np.inf], np.nan).astype("float32")
    return out
