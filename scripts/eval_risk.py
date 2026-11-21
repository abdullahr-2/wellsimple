"""Time-ordered evaluation of the well risk model against simple baselines.

Usage: DATA_DIR=... python scripts/eval_risk.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from wellsimple import data, risk

CUTOFF = pd.Timestamp("2025-07-01")


def precision_at_top(y, score, frac):
    k = max(1, int(len(y) * frac))
    return y[np.argsort(-score)[:k]].mean()


def main():
    cols = ["uwi", "production_date", "well_daily_status"] + data.SENSOR_COLS
    daily = data.load_daily(cols + [])
    jobs = data.load_jobs()
    repairs = jobs[jobs["is_repair"]][["uwi", "start_date"]]
    snap = risk.build_snapshots(daily, repairs, step=7, horizon=30)
    print("snapshots", len(snap), "base rate", round(snap.label.mean(), 4))
    tr = snap.production_date < CUTOFF - pd.Timedelta(days=30)  # no label overlap with test
    te = snap.production_date >= CUTOFF
    y = snap.label.values
    results = {}

    def report(name, score):
        results[name] = (
            roc_auc_score(y[te], score[te]),
            average_precision_score(y[te], score[te]),
            precision_at_top(y[te], score[te], 0.05),
            precision_at_top(y[te], score[te], 0.10),
        )

    base = y[te].mean()
    print("test snapshots", te.sum(), "test base rate", round(base, 4))
    rng = np.random.default_rng(0)
    report("random", rng.random(len(snap)))
    report("recent repairs only (repairs_90d)", snap.repairs_90d.fillna(0).values)
    for name, feats in {
        "history features": risk.HISTORY_FEATURES,
        "sensor features": risk.SENSOR_FEATURES,
        "sensor + history": risk.SENSOR_FEATURES + risk.HISTORY_FEATURES,
    }.items():
        m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, random_state=0)
        m.fit(snap.loc[tr, feats], y[tr])
        report(name, m.predict_proba(snap[feats])[:, 1])
    print(f"{'model':36s} {'AUC':>6s} {'AP':>6s} {'P@5%':>6s} {'P@10%':>6s}")
    for k, (a, ap, p5, p10) in results.items():
        print(f"{k:36s} {a:6.3f} {ap:6.3f} {p5:6.3f} {p10:6.3f}")
    print(f"lift at top 5% for sensor + history: {results['sensor + history'][2] / base:.2f}x")


if __name__ == "__main__":
    main()
