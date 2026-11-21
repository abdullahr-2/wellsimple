"""Cross-modal retrieval: from sensor behavior before a failure to the crew notes
that wells like this produced ("sensors that speak crew language").

A regression forest maps pre-failure sensor features into the text space of past
crew notes; the nearest real notes in that space are returned. A second forest gives
the likely failing component. Nothing is generated: every returned note is a real
past note.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import normalize

from . import data, notes, risk

# mechanical signals only: oil rate and downtime can mean "already stopped", not diagnosis
MECH_FEATURES = [f for f in risk.SENSOR_FEATURES if not f.startswith(("oil_produced", "hours_down"))]
CLASSES = ["Pump", "Rods", "Tubing"]


def failure_dataset(daily: pd.DataFrame, failures: pd.DataFrame, jobs: pd.DataFrame) -> pd.DataFrame:
    """One row per failure that has a crew note: pre-failure sensor features, note text,
    failure class and field. Features are read on the last day before the failure."""
    f = data.link_failures_to_jobs(failures, jobs)
    f = f[f["text"].str.len() > 5].copy()
    d = daily[daily["uwi"].isin(f["uwi"].unique())]
    feats = risk._rolling_features(d)[["uwi", "production_date"] + MECH_FEATURES]
    feats["production_date"] = feats["production_date"].astype("datetime64[ns]")
    feats = feats.sort_values("production_date")
    f["asof"] = (f["failure_start_date"] - pd.Timedelta(days=1)).astype("datetime64[ns]")
    f = f.sort_values("asof")
    out = pd.merge_asof(f, feats, left_on="asof", right_on="production_date", by="uwi",
                        direction="backward", tolerance=pd.Timedelta(days=3))
    return out.drop(columns=["production_date", "asof"]).reset_index(drop=True)


class CrossModal:
    def __init__(self, dims: int = 40, trees: int = 300, seed: int = 0):
        self.enc = notes.TfidfEncoder(dims)
        self.imp = SimpleImputer(strategy="median", keep_empty_features=True)
        self.reg = RandomForestRegressor(trees, min_samples_leaf=5, max_features=0.4, random_state=seed, n_jobs=-1)
        self.clf = RandomForestClassifier(trees, min_samples_leaf=5, class_weight="balanced",
                                          random_state=seed, n_jobs=-1)
        self.notes_: pd.DataFrame | None = None
        self.vecs_: np.ndarray | None = None

    def fit(self, df: pd.DataFrame) -> "CrossModal":
        z = self.enc.fit(df["text"].tolist()).encode(df["text"].tolist())
        x = self.imp.fit_transform(df[MECH_FEATURES].values)
        self.reg.fit(x, z)
        keep = df["failure_class"].isin(CLASSES).values
        self.clf.fit(x[keep], df.loc[keep, "failure_class"].values)
        self.notes_ = df.reset_index(drop=True)
        self.vecs_ = z.astype("float32")
        return self

    def _x(self, feats: pd.DataFrame) -> np.ndarray:
        return self.imp.transform(feats[MECH_FEATURES].values)

    def predict_vec(self, feats: pd.DataFrame) -> np.ndarray:
        return normalize(self.reg.predict(self._x(feats)))

    def proba(self, feats: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(self.clf.predict_proba(self._x(feats)), columns=self.clf.classes_, index=feats.index)

    def retrieve(self, feats: pd.DataFrame, k: int = 3, allowed: np.ndarray | None = None) -> list[list[int]]:
        """Row indices (into notes_) of the nearest real notes for each feature row.
        `allowed` is an optional boolean matrix (n_queries x n_notes) for exclusions."""
        sims = self.predict_vec(feats) @ self.vecs_.T
        if allowed is not None:
            sims = np.where(allowed, sims, -np.inf)
        return [list(np.argsort(-s)[:k]) for s in sims]
