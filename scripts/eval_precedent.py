"""How long will a repair last? Backtest of the precedent engine with survival methods.

For every repair job in 2026 we predict its life (days until the next repair on the well) from
the most similar earlier jobs on OTHER wells, three ways:
  text     the crew note (TF-IDF)
  sensors  the well's sensor and PCP-physics features the day before the job
  both     the average of the two similarities
Strict time-ordering: a past job's outcome is used only as far as it was known on the query day
(if its next repair came later, it counts as still running, i.e. censored, at that point).
The prediction is the Kaplan-Meier median of the neighbours, so censored jobs are used, not
dropped. Baselines: the fleet, the job's field, and the well's own history.
Scored with the concordance index (handles censored test jobs), error in log-days on test jobs
with an observed outcome, intervals by resampling wells, and a calibration table.

Usage: DATA_DIR=... python scripts/eval_precedent.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.preprocessing import normalize

from wellsimple import config, data, notes, physics, reliability as rel, risk

CUTOFF = pd.Timestamp("2026-01-01")
K = 25
MECH = [f for f in risk.SENSOR_FEATURES if not f.startswith(("oil_produced", "hours_down"))]


def main():
    daily = data.load_daily(["uwi", "production_date", "well_daily_status", "pcp_pump_displacement_m3d100rpm"] + data.SENSOR_COLS)
    end = daily["production_date"].max()
    rep = data.add_job_outcomes(data.load_jobs())
    rep = rel.survival_times(rep, end)                      # t, event as known at the end of the data
    rep = rep[rep["text"].str.len() > 5].reset_index(drop=True)

    # sensor + physics features on the day before each job
    phys = physics.physics_features(daily, rep[["uwi", "start_date"]])
    feats = risk._rolling_features(daily)[["uwi", "production_date"] + MECH].merge(phys, on=["uwi", "production_date"])
    feats["production_date"] = feats["production_date"].astype("datetime64[ns]")
    rep["asof"] = (rep["start_date"] - pd.Timedelta(days=1)).astype("datetime64[ns]")
    rep["_i"] = np.arange(len(rep))
    m = pd.merge_asof(rep[["_i", "uwi", "asof"]].sort_values("asof"), feats.sort_values("production_date"), left_on="asof",
                      right_on="production_date", by="uwi", direction="backward", tolerance=pd.Timedelta(days=3)).sort_values("_i")
    scols = MECH + physics.PHYSICS_FEATURES
    S = m[scols].to_numpy(float)
    start = rep["start_date"].to_numpy("datetime64[ns]")
    train = start < np.datetime64(CUTOFF)
    med, sd = np.nanmedian(S[train], axis=0), np.nanstd(S[train], axis=0) + 1e-9
    S = normalize(np.nan_to_num((S - med) / sd))            # missing -> training median
    has_sensors = m[scols].notna().mean(axis=1).to_numpy() >= 0.5

    enc = notes.TfidfEncoder(100).fit(rep.loc[train, "text"].tolist())
    T = enc.encode(rep["text"].tolist())

    meta = pd.read_parquet(config.DAILY, columns=["uwi", "production_date", "field_operating_area"])
    field_of = meta.sort_values("production_date").groupby("uwi")["field_operating_area"].last()
    field = rep["uwi"].map(field_of).fillna("unknown").to_numpy()
    uwi = rep["uwi"].to_numpy()
    done = rep["done"].to_numpy("datetime64[ns]")
    full_t, full_e = rep["t"].to_numpy(float), rep["event"].to_numpy(bool)

    def as_known(idx, when):
        """Outcomes of jobs `idx` as they were known on date `when`."""
        elapsed = (when - done[idx]).astype("timedelta64[D]").astype(float)
        keep = elapsed > 0
        idx, elapsed = idx[keep], elapsed[keep]
        e = full_e[idx] & (full_t[idx] <= elapsed)
        return np.minimum(full_t[idx], elapsed), e

    def km_pred(t, e):
        if len(t) == 0:
            return np.nan
        v = rel.km_median(t, e)
        return v if v is not None else float(np.max(t))      # over half still running: longest known time (a floor)

    cutoff64 = np.datetime64(CUTOFF)
    gt, ge = as_known(np.where(train)[0], cutoff64)
    global_pred = km_pred(gt, ge)
    field_pred = {}
    for f in np.unique(field):
        ix = np.where(train & (field == f))[0]
        if len(ix) >= 30:
            ft, fe = as_known(ix, cutoff64)
            field_pred[f] = km_pred(ft, fe)

    test = np.where(~train)[0]
    preds = {k: np.full(len(test), np.nan) for k in ("text", "sensors", "both", "well history", "field", "fleet")}
    for n, q in enumerate(test):
        cand = np.where((start < start[q]) & (uwi != uwi[q]))[0]
        sims = {"text": T[cand] @ T[q], "sensors": S[cand] @ S[q]}
        sims["both"] = 0.5 * sims["text"] + 0.5 * sims["sensors"]
        for name, sim in sims.items():
            top = cand[np.argpartition(-sim, K)[:K]]
            preds[name][n] = km_pred(*as_known(top, start[q]))
        own = np.where((uwi == uwi[q]) & (start < start[q]))[0]
        preds["field"][n] = field_pred.get(field[q], global_pred)
        preds["fleet"][n] = global_pred
        preds["well history"][n] = km_pred(*as_known(own, start[q])) if len(own) >= 2 else preds["field"][n]

    tt, te_ = full_t[test], full_e[test]
    wells = uwi[test]
    rng = np.random.default_rng(0)
    uw = np.unique(wells)
    idx_by = {w: np.where(wells == w)[0] for w in uw}
    print(f"test jobs (2026): {len(test):,} on {len(uw):,} wells | outcome observed for {te_.mean():.0%}, still running for the rest")
    print(f"with sensor data the day before: {has_sensors[test].mean():.0%}")
    print(f"{'method':14s} {'C-index':>8s} {'95% CI':>15s} {'log-day error (observed)':>26s}")
    for name, p in preds.items():
        c = rel.concordance_index(tt, te_, p)
        boots = []
        for _ in range(100):
            ix = np.concatenate([idx_by[w] for w in rng.choice(uw, len(uw))])
            boots.append(rel.concordance_index(tt[ix], te_[ix], p[ix]))
        lo, hi = np.nanpercentile(boots, [2.5, 97.5])
        obs = te_ & np.isfinite(p)
        mae = np.mean(np.abs(np.log1p(p[obs]) - np.log1p(tt[obs])))
        print(f"{name:14s} {c:8.3f} {lo:7.3f} to {hi:5.3f} {mae:26.3f}")
    sub = has_sensors[test]
    print(f"\nonly jobs with sensor data ({sub.sum():,}): " + ", ".join(
        f"{k} {rel.concordance_index(tt[sub], te_[sub], preds[k][sub]):.3f}" for k in ("text", "sensors", "both")))

    best = preds["both"]
    q = pd.qcut(best, 5, labels=False, duplicates="drop")
    print("\nCalibration of 'both' (predicted vs Kaplan-Meier actual median, days):")
    for b in sorted(set(q[~np.isnan(q)])):
        ix = q == b
        actual = rel.km_median(tt[ix], te_[ix])
        print(f"  predicted ~{np.median(best[ix]):5.0f} | actual {('>' + str(int(tt[ix].max()))) if actual is None else int(actual):>6} | jobs {ix.sum()}")


if __name__ == "__main__":
    main()
