"""FastAPI app: manager portal (/) and crew portal (/crew) over one JSON API.

Demo scope: no authentication. The two portals are separate pages, and crews pick
their identity from a list. A real deployment would put both behind company SSO.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, geo, notes, store as store_mod

STATIC = Path(__file__).parent / "static"
DEMO_CREWS = [("crew-1", "Crew 1"), ("crew-2", "Crew 2"), ("crew-3", "Crew 3"), ("crew-4", "Crew 4")]
SortMode = Literal["loss", "risk", "closest", "furthest"]


class AssignIn(BaseModel):
    uwi: str = Field(min_length=1, max_length=40)
    crew_id: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=1000)


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CompleteIn(BaseModel):
    work_done: list[str] = Field(default_factory=list, max_length=12)
    note: str = Field(default="", max_length=3000)
    actual_cost: float | None = Field(default=None, ge=0, le=5_000_000)
    hours: float | None = Field(default=None, ge=0, le=500)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


def _clean(v):
    if v is None or v is pd.NaT or v is pd.NA or (isinstance(v, float) and not np.isfinite(v)):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return None if pd.isna(v) else v.date().isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if not np.isfinite(v) else float(v)
    return v


def _rows(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def create_app(wells: pd.DataFrame, overview: dict, memory: notes.WellMemory,
               store: store_mod.Store, pilot: dict | None = None, pilot_wells: pd.DataFrame | None = None,
               hide_control: bool = False, repair_model=None) -> FastAPI:
    app = FastAPI(title="WellSimple")
    wells = wells.copy().reset_index(drop=True)
    by_uwi = {u: i for i, u in enumerate(wells["uwi"])}
    store.ensure_crews(DEMO_CREWS)
    # crew notes are saved in the store; put them back into Well Memory so they survive a restart
    for a in store.assignments("resolved"):
        text = ((a.get("work_done") or "").replace("; ", " ") + " . " + (a.get("crew_note") or "")).strip(" .")
        if len(text) >= 3:
            when = pd.Timestamp(a["resolved_at"]).tz_convert(None).normalize() if a.get("resolved_at") else None
            memory.add_job(a["uwi"], text, cost=a.get("actual_cost"), start_date=when)
    centroid = (float(wells["surface_latitude"].mean()), float(wells["surface_longitude"].mean()))

    def origin(crew_id: str | None) -> tuple[float, float, str]:
        for c in store.crews():
            if c["id"] == crew_id and c["lat"] is not None:
                return c["lat"], c["lon"], c["name"]
        return centroid[0], centroid[1], "fleet centre"

    # ------------------------------------------------------------------ API
    @app.get("/api/overview")
    def get_overview():
        a = store.assignments()
        return {**overview,
                "open_assignments": sum(x["status"] == "assigned" for x in a),
                "resolved_count": sum(x["status"] == "resolved" for x in a)}

    @app.get("/api/wells")
    def list_wells(sort: SortMode = "loss", crew_id: str | None = None, scenario: Literal["low", "mid"] = "mid",
                   min_risk: float = Query(0.0, ge=0, le=1), limit: int = Query(50, ge=1, le=500),
                   include_assigned: bool = False, rescore: bool = False):
        df = wells.copy()
        if rescore:
            if repair_model is None:
                raise HTTPException(503, "Rebuild the model with scripts/build_artifacts.py.")
            features = list(repair_model.feature_names_in_)
            df["p_repair"] = repair_model.predict_proba(df[features])[:, 1]
            for price_scenario in ("low", "mid"):
                df[f"expected_loss_{price_scenario}"] = df["p_repair"] * df[f"event_cost_{price_scenario}"]
        n_high_risk = int((df["p_repair"] >= 0.4).sum())
        df = df[df["p_repair"] >= min_risk]
        hidden = store.resolved_uwis() | (set() if include_assigned else store.open_uwis())
        if hide_control and pilot_wells is not None:  # pilot mode: control wells are not surfaced (usual practice)
            hidden |= set(pilot_wells.loc[pilot_wells["arm"] == "control", "uwi"])
        df = df[~df["uwi"].isin(hidden)]
        lat0, lon0, label = origin(crew_id)
        df["distance_km"] = geo.haversine_km(lat0, lon0, df["surface_latitude"], df["surface_longitude"])
        key = {"loss": (f"expected_loss_{scenario}", False), "risk": ("p_repair", False),
               "closest": ("distance_km", True), "furthest": ("distance_km", False)}[sort]
        df = df.sort_values(key[0], ascending=key[1], na_position="last").head(limit)
        cols = ["uwi", "well_name", "field_operating_area", "surface_latitude", "surface_longitude", "p_repair",
                "expected_loss_low", "expected_loss_mid", "event_cost_mid", "reasons", "distance_km",
                "precedent_life_days", "precedent_cost_per_day"]
        cols += [c for c in ("p_pump", "p_rods", "p_tubing") if c in df.columns]
        return {"sort": sort, "distance_from": label, "wells": _rows(df[cols]),
                "scored_wells": len(wells), "high_risk_wells": n_high_risk}

    @app.get("/api/wells/{uwi}")
    def well_detail(uwi: str, k: int = Query(5, ge=1, le=15)):
        if uwi not in by_uwi:
            raise HTTPException(404, "unknown well")
        w = wells.iloc[by_uwi[uwi]]
        query = w["last_repair_note"] if isinstance(w["last_repair_note"], str) and len(w["last_repair_note"]) > 5 \
            else (w["reasons"] or "")
        precedents = []
        if query:
            for p in memory.search(query, k=k, exclude_uwi=uwi):
                precedents.append({"date": _clean(p.start_date), "similarity": round(p.similarity, 3),
                                   "text": p.text[:500], "cost": _clean(p.cost), "life_days": _clean(p.life_days)})
        d = {c: _clean(w[c]) for c in wells.columns if c != "autopsy_notes"}
        autopsy = None
        if "autopsy_notes" in wells.columns and isinstance(w["autopsy_notes"], str):
            autopsy = {"p": {"Pump": _clean(w["p_pump"]), "Rods": _clean(w["p_rods"]), "Tubing": _clean(w["p_tubing"])},
                       "notes": json.loads(w["autopsy_notes"])}
        return {"well": d, "query": query[:500], "precedents": precedents, "autopsy": autopsy,
                "summary": notes.summarize(memory.search(query, k=10, exclude_uwi=uwi)) if query else None}

    @app.get("/api/pilot")
    def get_pilot():
        if pilot is None:
            raise HTTPException(404, "no pilot has been built")
        sample = []
        if pilot_wells is not None:
            top = pilot_wells.sort_values("baseline_repeats", ascending=False).head(40)
            sample = _rows(top[["uwi", "well_name", "field", "arm", "baseline_repeats"]])
        return {**pilot, "pilot_mode": hide_control, "enrolled_wells": sample, "outcome": None,
                "outcome_note": "Enrollment is complete and follow-up has started. The measured result reads out "
                                "at 12 months; until then the potential below comes from the measured repeat-repair pool."}

    @app.get("/api/crews")
    def crews():
        return store.crews()

    @app.post("/api/crews/{crew_id}/location")
    def set_location(crew_id: str, loc: LocationIn):
        if not store.set_location(crew_id, loc.lat, loc.lon):
            raise HTTPException(404, "unknown crew")
        return {"ok": True}

    @app.post("/api/assign")
    def assign(a: AssignIn):
        if a.uwi not in by_uwi:
            raise HTTPException(404, "unknown well")
        try:
            return {"id": store.assign(a.uwi, a.crew_id, a.note)}
        except ValueError as e:
            raise HTTPException(409, str(e)) from None

    def _decorate(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            i = by_uwi.get(r["uwi"])
            if i is not None:
                w = wells.iloc[i]
                r = {**r, "well_name": _clean(w["well_name"]), "field": _clean(w["field_operating_area"]),
                     "lat": _clean(w["surface_latitude"]), "lon": _clean(w["surface_longitude"]),
                     "p_repair": _clean(w["p_repair"]), "expected_loss_mid": _clean(w["expected_loss_mid"]),
                     "expected_loss_low": _clean(w["expected_loss_low"]),
                     "reasons": _clean(w["reasons"])}
            out.append(r)
        return out

    @app.get("/api/assignments")
    def assignments(status: Literal["assigned", "resolved"] | None = None, crew_id: str | None = None):
        return _decorate(store.assignments(status, crew_id))

    @app.post("/api/assignments/{aid}/complete")
    def complete(aid: int, body: CompleteIn):
        a = store.get_assignment(aid)
        if not a:
            raise HTTPException(404, "unknown assignment")
        if a["status"] != "assigned":
            raise HTTPException(409, "already resolved")
        text = (" ".join(body.work_done) + " . " + body.note).strip(" .")
        if len(text) < 3:
            raise HTTPException(422, "describe the work done")
        store.resolve(aid, "; ".join(body.work_done), body.note, body.actual_cost, body.hours, body.lat, body.lon)
        memory.add_job(a["uwi"], text, cost=body.actual_cost)  # the closed loop: crew notes feed Well Memory
        return _decorate([store.get_assignment(aid)])[0]

    # --------------------------------------------------------------- pages
    @app.get("/", include_in_schema=False)
    def manager_page():
        return FileResponse(STATIC / "manager.html")

    @app.get("/crew", include_in_schema=False)
    def crew_page():
        return FileResponse(STATIC / "crew.html")

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def load_app() -> FastAPI:
    """Build the app from the artifacts and dataset configured in the environment."""
    from . import data
    import joblib

    wells = pd.read_parquet(config.WORK_DIR / "wells.parquet")
    overview = json.loads((config.WORK_DIR / "overview.json").read_text())
    # Only load the trusted artifact produced by the local training pipeline.
    model = joblib.load(config.WORK_DIR / "repair_model.joblib") if "model" in overview else None
    rep = data.add_job_outcomes(data.load_jobs())
    memory = notes.WellMemory(notes.TfidfEncoder()).build(rep)
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    pilot = pilot_wells = None
    if (config.WORK_DIR / "pilot.json").exists():
        pilot = json.loads((config.WORK_DIR / "pilot.json").read_text())
        pilot_wells = pd.read_parquet(config.WORK_DIR / "pilot.parquet")
    # PILOT_MODE=1 hides control-arm wells from the manager list, which is what makes it a real experiment
    return create_app(wells, overview, memory, store_mod.Store(config.WORK_DIR / "state.sqlite"),
                      pilot, pilot_wells, hide_control=os.environ.get("PILOT_MODE") == "1", repair_model=model)
