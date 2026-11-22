"""Is scikit-learn's HistGradientBoosting a fair choice for the risk model?

Compares it with XGBoost, LightGBM and a plain logistic regression on the same time-ordered
split and the same features. XGBoost and LightGBM are optional installs used only here.

Usage: DATA_DIR=... python scripts/compare_models.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wellsimple import data, risk

CUTOFF = pd.Timestamp("2025-07-01")


def top_precision(y, score, frac):
    k = max(1, int(len(y) * frac))
    return y[np.argsort(-score)[:k]].mean()


def main():
    from lightgbm import LGBMClassifier
    from xgboost import XGBClassifier

    daily = data.load_daily(["uwi", "production_date", "well_daily_status"] + data.SENSOR_COLS)
    rep = data.add_job_outcomes(data.load_jobs())
    snap = risk.build_snapshots(daily, rep[["uwi", "start_date"]], step=7, horizon=30)
    feats = risk.SENSOR_FEATURES + risk.HISTORY_FEATURES
    tr = (snap.production_date < CUTOFF - pd.Timedelta(days=30)).to_numpy()
    te = (snap.production_date >= CUTOFF).to_numpy()
    X, y = snap[feats], snap["label"].to_numpy()
    shared = dict(max_depth=4, learning_rate=0.06, random_state=0)
    models = {
        "sklearn HistGradientBoosting (ours)": HistGradientBoostingClassifier(max_iter=250, **shared),
        "XGBoost": XGBClassifier(n_estimators=250, tree_method="hist", n_jobs=4, eval_metric="logloss", **shared),
        "LightGBM": LGBMClassifier(n_estimators=250, n_jobs=4, verbose=-1, **shared),
        "Logistic regression (baseline)": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                                        LogisticRegression(max_iter=2000)),
    }
    print(f"train {tr.sum()} well-weeks, test {te.sum()} (base rate {y[te].mean():.3f})")
    print(f"{'model':36s} {'AUC':>6s} {'AP':>6s} {'P@5%':>6s} {'P@10%':>6s} {'fit s':>6s}")
    for name, m in models.items():
        t0 = time.time()
        m.fit(X[tr], y[tr])
        s = m.predict_proba(X[te])[:, 1]
        print(f"{name:36s} {roc_auc_score(y[te], s):6.3f} {average_precision_score(y[te], s):6.3f} "
              f"{top_precision(y[te], s, .05):6.3f} {top_precision(y[te], s, .10):6.3f} {time.time() - t0:6.1f}")


if __name__ == "__main__":
    main()
