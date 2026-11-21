"""Time-ordered test of the sensor-to-crew-note model.

Trains on failures before 2026, tests on 2026 failures. Retrieval is scored three ways
to separate real diagnosis from local writing style:
  - other wells only
  - other fields only (a retrieved note can never come from the failing well's field)
Usage: DATA_DIR=... python scripts/eval_crossmodal.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score

from wellsimple import crossmodal, data

CUTOFF = pd.Timestamp("2026-01-01")
K = 10


def main():
    cols = ["uwi", "production_date", "well_daily_status"] + data.SENSOR_COLS
    daily = data.load_daily(cols)
    jobs = data.load_jobs()
    f = data.load_failures()
    ds = crossmodal.failure_dataset(daily, f, jobs)
    print("failures with note + features:", len(ds), "| feature coverage", round(ds[crossmodal.MECH_FEATURES].notna().mean().mean(), 2))
    tr = (ds["failure_start_date"] < CUTOFF).values
    te = ~tr
    model = crossmodal.CrossModal().fit(ds[tr])
    test = ds[te].reset_index(drop=True)
    train = model.notes_
    print("train", len(train), "test", len(test))

    # ---- component prediction (rods / pump / tubing) ----
    pr = model.proba(test)
    for k in crossmodal.CLASSES:
        print(f"  {k:6s} AUC {roc_auc_score((test.failure_class == k).astype(int), pr[k]):.3f}")

    # ---- note retrieval, scored with an independent full TF-IDF space ----
    tf = TfidfVectorizer(min_df=3, stop_words="english", sublinear_tf=True, max_features=8000).fit(train["text"])
    Ttr, Tte = tf.transform(train["text"]), tf.transform(test["text"])
    rng = np.random.default_rng(0)

    def score(idx_lists, i0=0):
        return np.array([(Ttr[ix] @ Tte[r + i0].T).toarray().mean() for r, ix in enumerate(idx_lists)])

    for label, col in (("other wells", "uwi"), ("other fields", "field_operating_area")):
        allowed = (test[col].to_numpy(dtype=object)[:, None] != train[col].to_numpy(dtype=object)[None, :])
        got = model.retrieve(test, K, allowed)
        rand = []
        for r in range(len(test)):
            pool = np.where(allowed[r])[0]
            rand.append(list(rng.choice(pool, K, replace=len(pool) < K)))
        a, b = score(got), score(rand)
        d = a - b
        ci = np.percentile([rng.choice(d, len(d)).mean() for _ in range(2000)], [2.5, 97.5])
        match = lambda ix_l: np.mean([(train.failure_class.values[ix] == test.failure_class.values[r]).mean() for r, ix in enumerate(ix_l)])
        print(f"retrieval, {label}: cosine to true note: model {a.mean():.4f} | random {b.mean():.4f} | lift {d.mean():.4f} CI [{ci[0]:.4f}, {ci[1]:.4f}]"
              f" | component match: model {match(got):.3f} vs random {match(rand):.3f}")


if __name__ == "__main__":
    main()
