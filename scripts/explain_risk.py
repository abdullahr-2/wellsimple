"""What drives the risk model? Permutation importance by signal, on the held-out period.

For each group of related features, scramble those columns together in the test data and
measure how much the model's AUC falls. A big drop means the model leans on that signal.
This describes the model, it does not prove a cause.

Usage: DATA_DIR=... python scripts/explain_risk.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from wellsimple import data, risk

CUTOFF = pd.Timestamp("2025-07-01")
LABELS = {"pump_efficiency_pct": "pump efficiency", "pcp_pump_rpm": "pump RPM", "pcp_pump_rod_torque_ftlb": "rod torque",
          "pcp_pump_electric_current_a": "motor current", "tubing_pressure_kpa": "tubing pressure",
          "casing_pressure_kpa": "casing pressure", "oil_produced_m3": "oil rate", "water_cut": "water cut",
          "hours_down": "recent downtime"}


def main():
    cols = ["uwi", "production_date", "well_daily_status"] + data.SENSOR_COLS
    daily = data.load_daily(cols)
    rep = data.add_job_outcomes(data.load_jobs())
    snap = risk.build_snapshots(daily, rep[["uwi", "start_date"]], step=7, horizon=30)
    feats = risk.SENSOR_FEATURES + risk.HISTORY_FEATURES
    tr = snap.production_date < CUTOFF - pd.Timedelta(days=30)
    te = snap.production_date >= CUTOFF
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, random_state=0)
    m.fit(snap.loc[tr, feats], snap.loc[tr, "label"])
    X, y = snap.loc[te, feats].reset_index(drop=True), snap.loc[te, "label"].to_numpy()
    base = roc_auc_score(y, m.predict_proba(X)[:, 1])
    print(f"held-out AUC {base:.3f} on {len(X)} well-weeks")
    groups = {"repair history (4 features)": risk.HISTORY_FEATURES}
    for c, name in LABELS.items():
        groups[name] = [f for f in risk.SENSOR_FEATURES if f.startswith(c + "_")]
    rng = np.random.default_rng(0)
    rows = []
    for name, cs in groups.items():
        drops = []
        for _ in range(3):
            Xp = X.copy()
            perm = rng.permutation(len(Xp))
            Xp[cs] = Xp[cs].to_numpy()[perm]  # scramble the whole group together, keep rows intact
            drops.append(base - roc_auc_score(y, m.predict_proba(Xp)[:, 1]))
        rows.append((name, float(np.mean(drops))))
    out = pd.DataFrame(rows, columns=["signal", "auc_drop"]).sort_values("auc_drop", ascending=False)
    print(out.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
