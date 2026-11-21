"""Testing candidate sources of savings against the data.

Each lever is checked the same way: is there an effect that survives controlling for
where and how wells differ? Findings, including negative ones, go in the README.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

PUMP_JOB_TYPES = {"Pump Repair/Replacement", "PCP Replacement", "PCP Upgrade", "Pump Repair"}


def pump_followups(rep: pd.DataFrame, pumps: pd.DataFrame, end: pd.Timestamp,
                   min_jobs: int = 40) -> pd.DataFrame:
    """For each pump job, the pump make installed afterwards and what followed.

    `pumps` has uwi, production_date, make, field (one row per well-day with a pump make).
    Returns uwi, make, field, t (days of follow-up) and event (1 if another repair came).
    """
    pj = rep[rep["job_type"].isin(PUMP_JOB_TYPES)].dropna(subset=["done"]).copy()
    pj["asof"] = (pj["done"] + pd.Timedelta(days=7)).astype("datetime64[ns]")
    pj = pj.sort_values("asof")
    p = pumps.copy()
    p["production_date"] = pd.to_datetime(p["production_date"]).astype("datetime64[ns]")
    p = p.sort_values("production_date")
    m = pd.merge_asof(pj, p[["uwi", "production_date", "make", "field"]], left_on="asof",
                      right_on="production_date", by="uwi", direction="backward",
                      tolerance=pd.Timedelta(days=30)).dropna(subset=["make"])
    m["t"] = np.where(m["censored"], (end - m["done"]).dt.days, m["life_days"])
    m = m[m["t"] > 0].copy()
    m["event"] = (~m["censored"]).astype(int)
    keep = m["make"].value_counts()
    m = m[m["make"].isin(keep[keep >= min_jobs].index)]
    return m[["uwi", "make", "field", "t", "event"]].reset_index(drop=True)


def rate_ratios(df: pd.DataFrame, controls: list[str], ref: str) -> dict[str, float]:
    """Poisson-regression rate ratios of the next repair, by make versus `ref`, with
    optional fixed effects for the columns in `controls` (for example field or well).
    The likelihood uses follow-up time as exposure."""
    X = pd.get_dummies(df[["make"] + controls], drop_first=False).astype(float)
    X = X.drop(columns=[f"make_{ref}"])
    # work in events per year with exposure in years: a target of ~0.003 per day makes the
    # optimizer stop early (found by the confounding test), so keep the scale near 1
    model = PoissonRegressor(alpha=1e-8, max_iter=5000, tol=1e-9)
    exposure_years = df["t"] / 365.0
    model.fit(X, df["event"] / exposure_years, sample_weight=exposure_years)
    return {c.removeprefix("make_"): float(np.exp(b)) for c, b in zip(X.columns, model.coef_) if c.startswith("make_")}


def cluster_bootstrap(df: pd.DataFrame, controls: list[str], ref: str, n: int = 60, seed: int = 0) -> dict:
    """95% interval for each rate ratio, resampling whole wells (jobs on a well are not independent)."""
    rng = np.random.default_rng(seed)
    groups = {u: g for u, g in df.groupby("uwi")}
    wells = np.array(list(groups))
    draws: dict[str, list[float]] = {}
    for _ in range(n):
        pick = rng.choice(wells, len(wells))
        b = pd.concat([groups[u] for u in pick], ignore_index=True)
        try:
            for k, v in rate_ratios(b, controls, ref).items():
                draws.setdefault(k, []).append(v)
        except ValueError:  # a draw that dropped a make entirely
            continue
    return {k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in draws.items() if len(v) > n // 2}
