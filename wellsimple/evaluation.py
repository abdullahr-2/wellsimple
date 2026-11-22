"""Held-out evaluation of the risk model with the checks a reviewer asks for.

- Time-ordered split: train before (cutoff - horizon), test from cutoff on.
- Baselines: each well's own historical repair rate, its field's rate, and the fleet rate.
- Confidence intervals by resampling whole wells (snapshots of one well are not independent).
- Calibration: when the model says 40%, do about 40% of those wells need a repair?
- Cold start: wells with little or no repair history at the time of scoring.
- New field: train without a field, test on it (how the model transfers to a new area).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score


def _model():
    return HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, random_state=0)


def top_precision(y, s, frac=0.05):
    k = max(1, int(len(y) * frac))
    return float(np.asarray(y)[np.argsort(-np.asarray(s))[:k]].mean())


def calibration_bins(y, p, n_bins=10) -> list[dict]:
    """Equal-count bins of predicted probability: mean prediction vs observed rate."""
    order = np.argsort(p)
    out = []
    for chunk in np.array_split(order, n_bins):
        if len(chunk):
            out.append({"predicted": float(np.mean(p[chunk])), "observed": float(np.mean(y[chunk])), "n": int(len(chunk))})
    return out


def well_bootstrap(y, s, groups, stats: dict, n=200, seed=0) -> dict:
    """95% intervals for each statistic, resampling whole wells."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in uniq}
    draws = {k: [] for k in stats}
    for _ in range(n):
        ix = np.concatenate([idx[g] for g in rng.choice(uniq, len(uniq))])
        if y[ix].min() == y[ix].max():
            continue
        for k, f in stats.items():
            draws[k].append(f(y[ix], s[ix]))
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items() if v}


def holdout_report(snaps: pd.DataFrame, feats: list[str], field_of: dict, cutoff: pd.Timestamp,
                   horizon: int = 30, n_boot: int = 200) -> dict:
    tr = (snaps["production_date"] < cutoff - pd.Timedelta(days=horizon)).to_numpy()
    te = (snaps["production_date"] >= cutoff).to_numpy()
    y = snaps["label"].to_numpy().astype(int)
    model = _model().fit(snaps.loc[tr, feats], y[tr])
    s = model.predict_proba(snaps.loc[te, feats])[:, 1]
    yt = y[te]
    wells = snaps.loc[te, "uwi"].to_numpy()
    fields = np.array([field_of.get(w, "unknown") for w in wells])

    # baselines from the training period only: share of a well's (or field's) snapshots followed by a repair
    train = snaps.loc[tr, ["uwi", "label"]].assign(field=lambda d: d["uwi"].map(field_of).fillna("unknown"))
    fleet = float(train["label"].mean())
    field_rate = train.groupby("field")["label"].mean()
    well_rate = train.groupby("uwi")["label"].mean()
    s_field = np.array([field_rate.get(f, fleet) for f in fields])
    s_well = np.array([well_rate.get(w, field_rate.get(f, fleet)) for w, f in zip(wells, fields)])

    stats = {"auc": roc_auc_score, "precision_top5": lambda a, b: top_precision(a, b, 0.05)}
    report = {
        "cutoff": str(cutoff.date()), "test_rows": int(te.sum()), "test_wells": int(len(np.unique(wells))),
        "base_rate": float(yt.mean()),
        "model": {"auc": float(roc_auc_score(yt, s)), "precision_top5": top_precision(yt, s),
                  "ci": well_bootstrap(yt, s, wells, stats, n_boot), "brier": float(np.mean((s - yt) ** 2))},
        "baselines": {
            "well_history": {"auc": float(roc_auc_score(yt, s_well)), "precision_top5": top_precision(yt, s_well)},
            "field_average": {"auc": float(roc_auc_score(yt, s_field)), "precision_top5": top_precision(yt, s_field)},
        },
        "calibration": calibration_bins(yt, s),
    }
    # cold start: little repair history when scored
    hist = snaps.loc[te, "repairs_total"].to_numpy()
    cold = {}
    for name, m in (("no previous repair", hist == 0), ("1 to 2 previous repairs", (hist >= 1) & (hist <= 2)),
                    ("3 or more", hist >= 3)):
        if m.sum() > 50 and 0 < yt[m].mean() < 1:
            cold[name] = {"rows": int(m.sum()), "base_rate": float(yt[m].mean()), "auc": float(roc_auc_score(yt[m], s[m])),
                          "precision_top5": top_precision(yt[m], s[m])}
    report["cold_start"] = cold
    # new field: hold out each of the largest fields entirely
    big = pd.Series(fields).value_counts().head(5).index.tolist()
    snap_fields = snaps["uwi"].map(field_of).fillna("unknown").to_numpy()
    nf = {}
    for f in big:
        trf = tr & (snap_fields != f)
        tef = te & (snap_fields == f)
        if tef.sum() < 200 or y[tef].min() == y[tef].max():
            continue
        sf = _model().fit(snaps.loc[trf, feats], y[trf]).predict_proba(snaps.loc[tef, feats])[:, 1]
        nf[f] = {"rows": int(tef.sum()), "auc_unseen_field": float(roc_auc_score(y[tef], sf)),
                 "auc_seen_field": float(roc_auc_score(yt[fields == f], s[fields == f]))}
    report["new_field"] = nf
    return report
