"""Does PCP physics hold in the data, add to the risk model, and match what crews found?

A. Data check: recorded volumetric efficiency vs actual liquid / theoretical rate.
B. Risk model with and without physics features (time-ordered, paired bootstrap by well).
C. Engineering check: for each failure mechanism a production engineer would infer from the
   sensors, is the matching finding more common in the crew's note for the next repair job?

Usage: DATA_DIR=... python scripts/eval_physics.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from wellsimple import config, data, physics, risk

CUTOFF = pd.Timestamp("2025-07-01")
COLS = ["uwi", "production_date", "well_daily_status", "pcp_pump_displacement_m3d100rpm"] + data.SENSOR_COLS

# mechanism: (sensor signature in words, crew-note pattern that would confirm it)
MECHANISMS = {
    "Stator wear / slippage": ("efficiency falling at steady speed", r"worn|wear|stator|rotor|low eff|pump change|replaced? pump|swap"),
    "Sand or solids loading": ("torque spikes or torque rising for its pump size", r"sand|fill|bail|clean ?out|plug"),
    "Rod fatigue / overload": ("many loaded revolutions since the last repair", r"broke|broken|parted|parted rod|part rod|pin|coupling|twist"),
    "Gas interference": ("high casing pressure with low efficiency", r"\bgas\b|gas lock|gassy|foam"),
    "Dry running / pump-off": ("very low efficiency at normal speed", r"burn|burnt|dry|pumped off|pump off|heat|hot"),
}


def main():
    daily = data.clean_daily(pd.read_parquet(config.DAILY, columns=COLS))
    rep = data.add_job_outcomes(data.load_jobs())
    repairs = rep[["uwi", "start_date"]]

    # ---- A. physics check -------------------------------------------------------------------
    p = daily[(daily.well_daily_status == "Producing") & (daily.pcp_pump_rpm > 0)].copy()
    p["disp"] = pd.to_numeric(p["pcp_pump_displacement_m3d100rpm"], errors="coerce")
    theo = p["disp"] * p["pcp_pump_rpm"] / 100 * (p["hours_on_prod"].clip(0, 24) / 24)
    calc = (p["oil_produced_m3"] + p["water_produced_m3"]) / theo.where(theo > 1)
    ok = calc.notna() & p["pump_efficiency_pct"].notna()
    err = (calc[ok] - p.loc[ok, "pump_efficiency_pct"]).abs()
    print("== A. Is recorded efficiency the PCP volumetric efficiency (actual / displacement x RPM)?")
    print(f"  {ok.sum():,} producing well-days | within 0.02: {(err < 0.02).mean():.1%} | within 0.10: {(err < 0.10).mean():.1%} "
          f"| correlation {np.corrcoef(calc[ok].clip(0, 2), p.loc[ok, 'pump_efficiency_pct'].clip(0, 2))[0, 1]:.3f}")

    # ---- B. risk model with physics ---------------------------------------------------------
    phys = physics.physics_features(daily, repairs)
    snap = risk.build_snapshots(daily, repairs, step=7, horizon=30)
    snap = snap.merge(phys, on=["uwi", "production_date"], how="left")
    base_f = risk.SENSOR_FEATURES + risk.HISTORY_FEATURES
    full_f = base_f + physics.PHYSICS_FEATURES
    tr = (snap.production_date < CUTOFF - pd.Timedelta(days=30)).to_numpy()
    te = (snap.production_date >= CUTOFF).to_numpy()
    y = snap["label"].to_numpy()
    mk = lambda: HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, random_state=0)
    s_base = mk().fit(snap.loc[tr, base_f], y[tr]).predict_proba(snap.loc[te, base_f])[:, 1]
    m_full = mk().fit(snap.loc[tr, full_f], y[tr])
    s_full = m_full.predict_proba(snap.loc[te, full_f])[:, 1]
    s_phys_hist = mk().fit(snap.loc[tr, physics.PHYSICS_FEATURES + risk.HISTORY_FEATURES], y[tr]) \
        .predict_proba(snap.loc[te, physics.PHYSICS_FEATURES + risk.HISTORY_FEATURES])[:, 1]
    yt, wells = y[te], snap.loc[te, "uwi"].to_numpy()
    print("== B. Risk model, held-out Jul 2025+ (AUC)")
    print(f"  existing features {roc_auc_score(yt, s_base):.3f} | + physics {roc_auc_score(yt, s_full):.3f} | "
          f"physics + history only {roc_auc_score(yt, s_phys_hist):.3f}")
    rng = np.random.default_rng(0)
    uw = np.unique(wells); idx_by = {w: np.where(wells == w)[0] for w in uw}
    diffs = []
    for _ in range(200):
        ix = np.concatenate([idx_by[w] for w in rng.choice(uw, len(uw))])
        diffs.append(roc_auc_score(yt[ix], s_full[ix]) - roc_auc_score(yt[ix], s_base[ix]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"  gain from physics {np.mean(diffs):+.4f} (95% CI {lo:+.4f} to {hi:+.4f}, resampling wells)")
    Xte = snap.loc[te, full_f].reset_index(drop=True)
    for f in physics.PHYSICS_FEATURES:
        Xp = Xte.copy(); Xp[f] = Xp[f].to_numpy()[rng.permutation(len(Xp))]
        print(f"    {f:22s} AUC drop when scrambled {roc_auc_score(yt, s_full) - roc_auc_score(yt, m_full.predict_proba(Xp)[:, 1]):+.4f}")

    # ---- C. sensor signature vs what the crew found ----------------------------------------
    feats = risk._rolling_features(daily)[["uwi", "production_date", "pump_efficiency_pct_m30", "pcp_pump_rpm_m30", "casing_pressure_kpa_m30"]]
    feats = feats.merge(phys, on=["uwi", "production_date"]).sort_values("production_date")
    feats["production_date"] = feats["production_date"].astype("datetime64[ns]")
    jobs = rep[rep["text"].str.len() > 20].copy()
    jobs["asof"] = (jobs["start_date"] - pd.Timedelta(days=1)).astype("datetime64[ns]")
    j = pd.merge_asof(jobs.sort_values("asof"), feats, left_on="asof", right_on="production_date", by="uwi",
                      direction="backward", tolerance=pd.Timedelta(days=3))
    q = lambda c, p: j[c].quantile(p)
    sig = {
        "Stator wear / slippage": (j.eff_drop_rate <= q("eff_drop_rate", .15)) & (j.rpm_cv30 <= q("rpm_cv30", .5)),
        "Sand or solids loading": (j.torque_spike >= q("torque_spike", .85)) | (j.torque_per_disp_d >= q("torque_per_disp_d", .85)),
        "Rod fatigue / overload": j.fatigue_since_repair >= q("fatigue_since_repair", .85),
        "Gas interference": (j.casing_pressure_kpa_m30 >= q("casing_pressure_kpa_m30", .85)) & (j.pump_efficiency_pct_m30 <= q("pump_efficiency_pct_m30", .3)),
        "Dry running / pump-off": (j.pump_efficiency_pct_m30 <= q("pump_efficiency_pct_m30", .10)) & (j.pcp_pump_rpm_m30 >= q("pcp_pump_rpm_m30", .3)),
    }
    print(f"== C. Sensor signature before a repair vs the crew's note ({len(j):,} repair jobs with notes, 2021 to 2026)")
    print(f"  {'mechanism':26s} {'jobs w/ sig':>11s} {'note match | sig':>17s} {'| no sig':>9s} {'ratio':>6s} {'95% CI':>15s}")
    for name, (desc, pat) in MECHANISMS.items():
        s = sig[name].fillna(False).to_numpy()
        hit = j["text"].str.contains(pat, flags=re.I, regex=True).to_numpy()
        a, n1, c, n0 = hit[s].sum(), s.sum(), hit[~s].sum(), (~s).sum()
        p1, p0 = a / max(n1, 1), c / max(n0, 1)
        rr = p1 / p0 if p0 > 0 else np.nan
        se = np.sqrt(1 / max(a, 1) - 1 / max(n1, 1) + 1 / max(c, 1) - 1 / max(n0, 1))
        lo_rr, hi_rr = rr * np.exp(-1.96 * se), rr * np.exp(1.96 * se)
        print(f"  {name:26s} {n1:11,d} {p1:17.1%} {p0:9.1%} {rr:6.2f} {lo_rr:7.2f} to {hi_rr:5.2f}")
    print("  (ratio > 1 with a CI above 1: crews found that mechanism more often after the signature)")

    # ---- D. when do rod breaks happen? (infant mortality vs wear-out fatigue) --------------
    brk = j["text"].str.contains(MECHANISMS["Rod fatigue / overload"][1], flags=re.I, regex=True)
    rodjob = j["job_type"].fillna("").str.contains("Rod", case=False)
    since = (j["start_date"] - j.groupby("uwi")["start_date"].shift(1)).dt.days
    jj = j.sort_values(["uwi", "start_date"]).copy()
    jj["days_since_prev"] = jj.groupby("uwi")["start_date"].diff().dt.days
    b = jj[rodjob.reindex(jj.index) & brk.reindex(jj.index)]
    o = jj[~brk.reindex(jj.index)]
    print("== D. Rod breaks: early failures or wear-out fatigue?")
    print(f"  rod jobs whose note reports a break: {len(b):,} | median days since previous repair {b.days_since_prev.median():.0f} "
          f"| median loaded revolutions since repair {b.revs_since_repair.median():.2f}M")
    print(f"  repair jobs without a break in the note: {len(o):,} | median days since previous repair {o.days_since_prev.median():.0f} "
          f"| median revolutions {o.revs_since_repair.median():.2f}M")
    print(f"  share of rod-break jobs within 30 days of the previous repair: {(b.days_since_prev <= 30).mean():.0%} "
          f"(all repair jobs: {(jj.days_since_prev <= 30).mean():.0%})")


if __name__ == "__main__":
    main()
