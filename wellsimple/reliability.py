"""Reliability engineering on repair lifetimes.

A "lifetime" is the time from the end of a repair job to the next repair job on the
same well; jobs with no later job are right-censored at the end of the data.

Key idea: the Weibull shape parameter k says how risk changes with time since a fix.
 - k > 1: wear-out. Risk rises with age, so planned replacement before failure can pay
          (the classic age-replacement policy).
 - k < 1: infant mortality. Risk is highest right after a fix and falls with time, so
          replacing a running unit on a schedule *resets* it into the riskiest period.
          Better repair quality, not a replacement schedule, is what saves money.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def survival_times(rep: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    """Add `t` (days observed) and `event` (True if a later repair was seen) to repair jobs
    produced by data.add_job_outcomes."""
    r = rep.copy()
    r["t"] = np.where(r["censored"], (end - r["done"]).dt.days, r["life_days"])
    r = r[r["t"] > 0]
    r["event"] = ~r["censored"]
    return r


def fit_weibull(t, event) -> tuple[float, float]:
    """Maximum-likelihood Weibull (shape k, scale lambda in days) with right censoring."""
    t = np.asarray(t, float)
    e = np.asarray(event, bool)

    def nll(p):
        k, lam = np.exp(p)
        z = t / lam
        return -(np.sum(e * (np.log(k / lam) + (k - 1) * np.log(z))) - np.sum(z ** k))

    # tight tolerances: the default stops early on flat likelihoods (seen for k = 2.5)
    best = None
    for k0 in (0.7, 1.5):  # two starting shapes guard against a poor local stop
        res = minimize(nll, [np.log(k0), np.log(np.mean(t))], method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-8, "fatol": 1e-10})
        if best is None or res.fun < best.fun:
            best = res
    k, lam = np.exp(best.x)
    return float(k), float(lam)


def bootstrap_shape(t, event, n: int = 40, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    t = np.asarray(t, float)
    e = np.asarray(event, bool)
    ks = []
    for _ in range(n):
        i = rng.integers(0, len(t), len(t))
        ks.append(fit_weibull(t[i], e[i])[0])
    lo, hi = np.percentile(ks, [2.5, 97.5])
    return float(lo), float(hi)


def empirical_hazard(t, event, bins=(0, 7, 14, 30, 60, 90, 180, 365, 5000)) -> list[dict]:
    """Per-day repair rate in each interval of time since the last repair, among jobs still
    'alive' (no repeat yet) at the start of the interval."""
    t = np.asarray(t, float)
    e = np.asarray(event, bool)
    out = []
    for a, b in zip(bins[:-1], bins[1:]):
        at_risk = int((t > a).sum())
        events = int(((t > a) & (t <= b) & e).sum())
        out.append({"from": a, "to": b, "at_risk": at_risk, "events": events,
                    "hazard_per_day": events / max(at_risk, 1) / (b - a)})
    return out


def optimal_age_replacement(k: float, lam: float, cost_planned: float, cost_failure: float,
                            horizon_days: float | None = None) -> dict:
    """Barlow-Proschan age replacement: choose the age T at which to replace a unit that
    has not failed, minimizing cost per day. Exists only when risk rises with age (k > 1)
    and failure costs more than a planned replacement."""
    if k <= 1:
        return {"exists": False, "reason": f"Because the shape (k = {k:.2f}) is at or below 1, risk falls with age, so "
                                           "replacing a unit that is still running only restarts the high-risk period "
                                           "and scheduled age-based replacement would not pay."}
    if cost_failure <= cost_planned:
        return {"exists": False, "reason": "a failure does not cost more than planned replacement."}
    horizon = horizon_days or 5 * lam
    ts = np.linspace(1, horizon, 4000)
    surv = np.exp(-(ts / lam) ** k)
    area = np.concatenate([[0], np.cumsum((surv[1:] + surv[:-1]) / 2 * np.diff(ts))]) + ts[0] * 1.0
    rate = (cost_planned * surv + cost_failure * (1 - surv)) / area
    i = int(np.argmin(rate))
    run_to_failure = cost_failure / (lam * np.exp(_gammaln(1 + 1 / k)))
    return {"exists": True, "T_days": float(ts[i]), "cost_per_day": float(rate[i]),
            "run_to_failure_cost_per_day": float(run_to_failure)}


def _gammaln(x):
    from scipy.special import gammaln
    return gammaln(x)


def repeat_spend(rep: pd.DataFrame, days: int) -> dict:
    """Spend on repair jobs that started within `days` of the previous repair on the same well.

    This is an observed pool of spend, a ceiling on what better repairs could address.
    It is not a saving: some repeats are planned follow-up visits or unrelated failures.
    """
    r = rep.sort_values(["uwi", "start_date"]).copy()
    r["gap"] = r.groupby("uwi")["start_date"].diff().dt.days
    rr = r[(r["gap"] > 0) & (r["gap"] <= days)]
    years = max((rep["start_date"].max() - rep["start_date"].min()).days / 365.25, 1e-9)
    return {"days": days, "jobs": int(len(rr)), "share_of_jobs": float(len(rr) / max(len(r), 1)),
            "cost": float(rr["cost"].sum()), "cost_per_year": float(rr["cost"].sum() / years),
            "share_of_cost": float(rr["cost"].sum() / max(r["cost"].sum(), 1e-9))}


def job_type_pareto(rep_t: pd.DataFrame, min_jobs: int = 150, top: int = 10) -> pd.DataFrame:
    """Where the repair money goes, by the crews' own job_type, with how well each fix holds."""
    g = rep_t.groupby("job_type")
    d = pd.DataFrame({
        "jobs": g.size(),
        "total_cost": g["cost"].sum(),
        "median_cost": g["cost"].median(),
        "median_life_days": g["life_days"].median(),
        "repeat_30d_share": g["life_days"].apply(lambda s: float((s.dropna() <= 30).mean()) if s.notna().any() else np.nan),
    })
    d = d[d["jobs"] >= min_jobs].sort_values("total_cost", ascending=False).head(top).reset_index()
    d["share_of_cost"] = d["total_cost"] / rep_t["cost"].sum()
    return d
