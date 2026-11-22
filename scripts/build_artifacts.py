"""Score every producing well and write the tables the two portals read.

Outputs (in WORK_DIR, default ./artifacts, never committed):
  wells.parquet     one row per producing well: risk, expected loss, reasons, precedent
  overview.json     fleet KPIs and chart series for the manager dashboard

Usage: DATA_DIR=... python scripts/build_artifacts.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import joblib

from wellsimple import config, crossmodal, data, evaluation, notes, physics, reliability, risk, scoring

META = ["uwi", "production_date", "well_name", "field_operating_area", "facility_name",
        "surface_latitude", "surface_longitude"]


def main():
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["uwi", "production_date", "well_daily_status", "downtime_code_1", "pcp_pump_displacement_m3d100rpm"] + data.SENSOR_COLS
    daily = data.load_daily(cols)
    jobs = data.load_jobs()
    rep = data.add_job_outcomes(jobs)
    repairs = rep[["uwi", "start_date"]]

    print("training risk model ...")
    phys = physics.physics_features(daily, repairs)  # PCP physics: efficiency drop, torque, fatigue index
    snaps = risk.build_snapshots(daily, repairs, step=7, horizon=30).merge(phys, on=["uwi", "production_date"], how="left")
    model = scoring.fit_model(snaps)
    latest = risk.latest_snapshot(daily, repairs).merge(phys, on=["uwi", "production_date"], how="left")
    feats = scoring.MODEL_FEATURES
    latest["p_repair"] = model.predict_proba(latest[feats])[:, 1]

    meta = pd.read_parquet(config.DAILY, columns=META)
    meta["production_date"] = pd.to_datetime(meta["production_date"])
    meta = meta.sort_values("production_date").groupby("uwi").tail(1).drop(columns="production_date")
    for c in ("surface_latitude", "surface_longitude"):
        meta[c] = pd.to_numeric(meta[c], errors="coerce")
    wells = latest.merge(meta, on="uwi", how="left")

    # ---- dollars ---------------------------------------------------------
    n_events = len(rep)
    lost_per_event = scoring.lost_m3_per_event(daily, n_events)
    fleet_rate = float(wells["oil_produced_m3_m30"].mean())
    typical_cost = scoring.mean_repair_cost(rep["cost"])  # mean, capped: this feeds an expected value
    for name, nb in scoring.NETBACK_SCENARIOS.items():
        loss = scoring.expected_loss(wells["p_repair"], wells["oil_produced_m3_m30"],
                                     typical_cost, lost_per_event, fleet_rate, nb)
        wells[f"event_cost_{name}"] = loss["event_cost"]
        wells[f"expected_loss_{name}"] = loss["expected_loss"]

    # ---- reasons and last repair ----------------------------------------
    wells["reasons"] = wells.apply(lambda r: "; ".join(scoring.reasons_for(r, wells)), axis=1)
    last = rep.sort_values("start_date").groupby("uwi").tail(1).set_index("uwi")
    wells["last_repair_date"] = wells["uwi"].map(last["start_date"])
    wells["last_repair_note"] = wells["uwi"].map(last["text"]).fillna("")

    # ---- precedent from each well's last note (earlier jobs, other wells) ---
    print("building precedent index ...")
    mem = notes.WellMemory(notes.TfidfEncoder()).build(rep)
    pm, pc, pl = [], [], []
    for r in wells.itertuples():
        if len(r.last_repair_note) < 6:
            pm.append(None); pc.append(None); pl.append(None); continue
        s = notes.summarize(mem.search(r.last_repair_note, k=10, exclude_uwi=r.uwi))
        pm.append(s["median_life_days"]); pc.append(s["median_cost"]); pl.append(s["cost_per_day_of_life"])
    wells["precedent_life_days"] = pm
    wells["precedent_cost"] = pc
    wells["precedent_cost_per_day"] = pl

    # ---- sensors-to-crew-notes: likely component and the real notes it resembles ----
    print("training cross-modal model ...")
    cm_ds = crossmodal.failure_dataset(daily, data.load_failures(), jobs)
    cm = crossmodal.CrossModal().fit(cm_ds)
    pr = cm.proba(wells)
    wells["p_pump"], wells["p_rods"], wells["p_tubing"] = pr["Pump"].values, pr["Rods"].values, pr["Tubing"].values
    allowed = wells["uwi"].to_numpy(object)[:, None] != cm.notes_["uwi"].to_numpy(object)[None, :]
    wells["autopsy_notes"] = [
        json.dumps([{"text": cm.notes_["text"].iloc[i][:400], "component": cm.notes_["failure_class"].iloc[i]} for i in ix])
        for ix in cm.retrieve(wells, 3, allowed)]

    wells.to_parquet(config.WORK_DIR / "wells.parquet", index=False)

    # ---- dashboard series ------------------------------------------------
    monthly = daily.assign(month=daily["production_date"].dt.to_period("M").astype(str)).groupby("month").agg(
        oil_m3=("oil_produced_m3", "sum"), lost_oil_m3=("lost_oil_m3", "sum")).reset_index()
    rj = rep.assign(month=rep["start_date"].dt.to_period("M").astype(str)).groupby("month").agg(
        repair_jobs=("uwi", "size"), repair_cost=("cost", "sum")).reset_index()
    code = daily[daily["downtime_code_1"].notna() & (daily["lost_oil_m3"] > 0)]
    by_code = code.groupby("downtime_code_1")["lost_oil_m3"].sum().sort_values(ascending=False).head(8)
    repeat90 = float((rep.sort_values(["uwi", "start_date"]).groupby("uwi")["start_date"].diff().dt.days <= 90).mean())
    overview = {
        "as_of": str(daily["production_date"].max().date()),
        "model": {
            "name": type(model).__name__,
            "snapshot_date": str(latest["production_date"].max().date()),
            "daily_rows": len(daily), "job_rows": len(jobs),
            "training_snapshots": len(snaps), "features": len(feats),
        },
        "producing_wells": int(len(wells)),
        "high_risk_wells": int((wells["p_repair"] >= 0.4).sum()),
        "expected_loss_low": float(wells["expected_loss_low"].sum()),
        "expected_loss_mid": float(wells["expected_loss_mid"].sum()),
        "repair_repeat_90d_share": repeat90,
        "lost_m3_per_event": lost_per_event,
        "typical_repair_cost": typical_cost,
        "netback_scenarios": scoring.NETBACK_SCENARIOS,
        "monthly": monthly.merge(rj, on="month", how="outer").fillna(0).to_dict("records"),
        "lost_by_code": by_code.round(0).to_dict(),
    }
    # ---- reliability: do fixes last? (Weibull on repair lifetimes, censored at the data end) ----
    rt = reliability.survival_times(rep, daily["production_date"].max())
    k, lam = reliability.fit_weibull(rt["t"], rt["event"])
    lo, hi = reliability.bootstrap_shape(rt["t"], rt["event"])
    event_cost = typical_cost + lost_per_event * scoring.M3_TO_BBL * scoring.NETBACK_SCENARIOS["low"]
    overview["reliability"] = {
        "shape": k, "shape_ci": [lo, hi], "scale_days": lam,
        "shape_by_category": {c: reliability.fit_weibull(g["t"], g["event"])[0] for c, g in rt.groupby("job_category")},
        "hazard": reliability.empirical_hazard(rt[rt["job_category"] == "Rod Truck"]["t"], rt[rt["job_category"] == "Rod Truck"]["event"]),
        "age_replacement": reliability.optimal_age_replacement(k, lam, typical_cost, event_cost),
        "pareto": reliability.job_type_pareto(rt).to_dict("records"),
        "repeat_spend": [reliability.repeat_spend(rep, d) for d in (30, 90)],
    }
    joblib.dump(model, config.WORK_DIR / "repair_model.joblib")
    # ---- model quality on a held-out period (time-ordered), for the portal and README ----
    print("evaluating on the held-out period ...")
    field_of = meta.set_index("uwi")["field_operating_area"].to_dict()
    overview["model_quality"] = evaluation.holdout_report(snaps, scoring.MODEL_FEATURES, field_of, pd.Timestamp("2025-07-01"))

    # ---- concentration: how much of the repair work sits on the worst wells ----
    def concentration(counts):
        c = np.sort(counts.to_numpy())[::-1]
        cum = np.cumsum(c) / c.sum()
        pts = [{"wells_pct": p, "jobs_pct": float(cum[max(0, int(np.ceil(len(c) * p / 100)) - 1)])} for p in range(1, 101)]
        return {"wells": int(len(c)), "points": pts, "top10_share": float(cum[int(np.ceil(len(c) * 0.10)) - 1])}
    overview["concentration"] = {
        "all_repairs": concentration(rep.groupby("uwi").size()),
        "rod_truck": concentration(rep[rep["job_category"] == "Rod Truck"].groupby("uwi").size()),
    }

    (config.WORK_DIR / "overview.json").write_text(json.dumps(overview, indent=2, default=float))
    print(f"wrote {len(wells)} wells; expected 30-day loss ${overview['expected_loss_low']:,.0f} to ${overview['expected_loss_mid']:,.0f}")


if __name__ == "__main__":
    main()
