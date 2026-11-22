import numpy as np
import pandas as pd

from wellsimple import evaluation


def test_calibration_bins_match_a_well_calibrated_score():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 20000)
    y = (rng.uniform(0, 1, 20000) < p).astype(int)   # outcomes drawn from the scores themselves
    for b in evaluation.calibration_bins(y, p):
        assert abs(b["predicted"] - b["observed"]) < 0.03


def test_top_precision_and_bootstrap_interval():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 50)
    s = np.where(y == 1, 0.9, 0.1) + np.random.default_rng(1).normal(0, 0.01, len(y))
    assert evaluation.top_precision(y, s, 0.1) == 1.0
    groups = np.repeat(np.arange(50), 10)
    ci = evaluation.well_bootstrap(y, s, groups, {"auc": lambda a, b: float((b[a == 1].mean() > b[a == 0].mean()))}, n=50)
    assert ci["auc"] == [1.0, 1.0]


def test_holdout_report_beats_baselines_on_learnable_signal():
    rng = np.random.default_rng(2)
    rows = []
    for w in range(120):
        for k in range(40):
            x = rng.normal()
            rows.append({"uwi": f"w{w}", "production_date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=7 * k),
                         "x": x, "repairs_total": k // 10, "label": int(rng.uniform() < 1 / (1 + np.exp(-2 * x)))})
    snaps = pd.DataFrame(rows)
    field_of = {f"w{w}": ("A" if w % 2 else "B") for w in range(120)}
    r = evaluation.holdout_report(snaps, ["x"], field_of, pd.Timestamp("2025-07-01"), n_boot=30)
    assert r["model"]["auc"] > 0.75
    assert r["model"]["auc"] > r["baselines"]["field_average"]["auc"] + 0.1
    lo, hi = r["model"]["ci"]["auc"]
    assert lo <= r["model"]["auc"] <= hi
    assert len(r["calibration"]) == 10
