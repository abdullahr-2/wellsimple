import numpy as np
import pandas as pd

from wellsimple import levers


def _synthetic(rate_a=1.0, rate_b=2.0, n=1500, seed=0, field_effect=False):
    """Follow-up data where make B truly has twice the repair rate of make A."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        make = "A" if i % 2 == 0 else "B"
        field = "F1" if i % 3 else "F2"
        rate = (rate_a if make == "A" else rate_b) * ((1.5 if field == "F2" else 1.0) if field_effect else 1.0)
        life = rng.exponential(365 / rate)
        t = min(life, 500.0)
        rows.append({"uwi": f"w{i}", "make": make, "field": field, "t": t, "event": int(life <= 500.0)})
    return pd.DataFrame(rows)


def test_rate_ratio_recovers_known_effect_with_censoring():
    rr = levers.rate_ratios(_synthetic(), [], ref="A")
    assert abs(rr["B"] - 2.0) / 2.0 < 0.15


def test_field_control_removes_confounding():
    # make B is installed more often in the harsher field F2, which raises everyone's rate there
    rng = np.random.default_rng(1)
    rows = []
    for i in range(4000):
        field = "F2" if i % 2 else "F1"
        make = "B" if (field == "F2") == (rng.random() < 0.8) else "A"  # B concentrated in F2
        rate = 1.0 * (2.0 if field == "F2" else 1.0)  # no make effect at all
        life = rng.exponential(365 / rate)
        rows.append({"uwi": f"w{i}", "make": make, "field": field, "t": min(life, 600.0), "event": int(life <= 600.0)})
    df = pd.DataFrame(rows)
    naive = levers.rate_ratios(df, [], "A")["B"]
    adjusted = levers.rate_ratios(df, ["field"], "A")["B"]
    assert naive > 1.3                    # looks worse without controls
    assert abs(adjusted - 1.0) < 0.12     # controlling for field removes the false effect


def test_bootstrap_interval_contains_truth():
    df = _synthetic(n=1200)
    ci = levers.cluster_bootstrap(df, [], "A", n=30)
    lo, hi = ci["B"]
    assert lo < 2.0 < hi
