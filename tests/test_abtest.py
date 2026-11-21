import numpy as np
import pandas as pd

from wellsimple import abtest


def _wells(n=240, seed=0, effect=0.0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"uwi": [f"w{i}" for i in range(n)], "field": np.where(np.arange(n) % 3 == 0, "A", "B"),
                       "baseline": rng.poisson(1.5, n) + 1})
    df["bucket"] = pd.cut(df["baseline"], [0, 1, 2, 99], labels=["1", "2", "3+"]).astype(str)
    df["followup"] = rng.poisson(df["baseline"] * 0.9)
    return df


def test_randomization_is_balanced_within_strata_and_reproducible():
    d = abtest.randomize(_wells(), ["field", "bucket"], seed=3)
    for _, g in d.groupby(["field", "bucket"]):
        assert abs((g.arm == "system").sum() - (g.arm == "control").sum()) <= 1
    d2 = abtest.randomize(_wells(), ["field", "bucket"], seed=3)
    assert d.arm.tolist() == d2.arm.tolist()                       # same seed, same assignment
    assert d.arm.tolist() != abtest.randomize(_wells(), ["field", "bucket"], seed=4).arm.tolist()
    bt = abtest.balance_table(d, ["baseline"])
    assert abs(bt.smd.iloc[0]) < 0.2


def test_analysis_detects_a_real_effect_and_the_interval_contains_it():
    df = _wells(600)
    df = abtest.randomize(df, ["field", "bucket"], seed=1)
    rng = np.random.default_rng(5)
    treated = (df.arm == "system").to_numpy()
    df["followup"] = np.where(treated, rng.binomial(df.followup.to_numpy(), 0.5), df.followup)  # true 50% cut
    r = abtest.analyze(df, "followup", n_perm=2000, n_boot=500)
    assert r["p_value"] < 0.01
    assert r["ci_low"] < 0.5 < r["ci_high"] and r["rate_ratio"] < 0.65


def test_analysis_does_not_invent_effects_when_there_is_none():
    r = abtest.aa_false_positive_rate(_wells(300, seed=2), "followup", ["field", "bucket"], n_trials=120, n_perm=300)
    assert r["false_positive_rate"] < 0.12   # about 5% expected; generous bound for 120 trials


def test_power_and_minimum_detectable_effect():
    counts = np.array([0] * 70 + [1] * 15 + [2] * 8 + [5] * 5 + [12] * 2)
    rng = np.random.default_rng(0)
    assert abtest.power(counts, 150, 0.0, rng, sims=300) < 0.10
    assert abtest.power(counts, 150, 0.6, rng, sims=300) > abtest.power(counts, 150, 0.2, rng, sims=300)
    small = abtest.minimum_detectable_effect(counts, 600, rng, sims=200)
    large = abtest.minimum_detectable_effect(counts, 60, rng, sims=200)
    assert small is not None and (large is None or large >= small)   # more wells detect smaller effects


def test_repeat_counts_window():
    rep = pd.DataFrame({"uwi": ["a", "a", "a", "b"],
                        "start_date": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-09-01", "2026-02-01"])})
    c = abtest.well_repeat_counts(rep, {"a", "b", "c"}, pd.Timestamp("2026-10-27"))
    assert c.to_dict() == {"a": 1, "b": 0, "c": 0}   # a's second job is 9 days after the first
