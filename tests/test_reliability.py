import numpy as np
import pandas as pd

from wellsimple import reliability as rel


def _sample(k, lam, n=4000, censor_at=None, seed=0):
    rng = np.random.default_rng(seed)
    t = lam * rng.weibull(k, n)
    e = np.ones(n, bool)
    if censor_at:
        e = t <= censor_at
        t = np.minimum(t, censor_at)
    return t, e


def test_weibull_recovers_known_parameters_with_censoring():
    for k in (0.6, 1.0, 2.5):
        t, e = _sample(k, 100.0, censor_at=150.0)
        fk, fl = rel.fit_weibull(t, e)
        assert abs(fk - k) / k < 0.06 and abs(fl - 100) / 100 < 0.08, (k, fk, fl)


def test_hazard_falls_when_shape_below_one():
    t, e = _sample(0.6, 100.0)
    h = rel.empirical_hazard(t, e, bins=(0, 10, 50, 200, 5000))
    rates = [x["hazard_per_day"] for x in h]
    assert rates[0] > rates[1] > rates[2] > rates[3]


def test_age_replacement_only_exists_for_wear_out():
    no = rel.optimal_age_replacement(0.6, 100.0, 1000.0, 5000.0)
    assert not no["exists"] and "restarts" in no["reason"]
    yes = rel.optimal_age_replacement(3.0, 100.0, 1000.0, 5000.0)
    assert yes["exists"] and 0 < yes["T_days"] < 200
    assert yes["cost_per_day"] < yes["run_to_failure_cost_per_day"]  # preventive beats run-to-failure
    assert not rel.optimal_age_replacement(3.0, 100.0, 5000.0, 1000.0)["exists"]


def test_survival_times_censors_last_job():
    rep = pd.DataFrame({
        "censored": [False, True], "life_days": [30.0, np.nan],
        "done": pd.to_datetime(["2026-01-01", "2026-10-01"]),
    })
    out = rel.survival_times(rep, pd.Timestamp("2026-10-31"))
    assert out["t"].tolist() == [30.0, 30.0] and out["event"].tolist() == [True, False]


def test_pareto_ranks_by_total_cost():
    rows = []
    for jt, n, cost in (("Rod Repair", 200, 5000.0), ("Pump Repair", 160, 20000.0), ("Tiny", 5, 1e6)):
        rows += [{"job_type": jt, "cost": cost, "life_days": 20.0}] * n
    p = rel.job_type_pareto(pd.DataFrame(rows), min_jobs=150)
    assert p["job_type"].tolist() == ["Pump Repair", "Rod Repair"]  # 'Tiny' filtered out by min_jobs


def test_repeat_spend_counts_only_jobs_after_a_recent_repair():
    rep = pd.DataFrame({
        "uwi": ["a", "a", "a", "b"],
        "start_date": pd.to_datetime(["2025-01-01", "2025-01-11", "2025-06-01", "2025-01-05"]),
        "cost": [100.0, 400.0, 900.0, 50.0],
    })
    s = rel.repeat_spend(rep, 30)
    assert s["jobs"] == 1 and s["cost"] == 400.0           # only a's second job is within 30 days
    assert abs(s["share_of_jobs"] - 0.25) < 1e-9
    assert rel.repeat_spend(rep, 400)["jobs"] == 2          # a's third job is 141 days after the second
