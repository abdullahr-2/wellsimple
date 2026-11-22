"""The three tables the hosted WellSimple app reads, built from a pipeline run.

Same rows as scripts/export_pages_data.py produces for the hosted demo (facts, wells, terms),
returned as DataFrames so the Databricks job can publish them as Delta tables. The pipeline then
feeds the app directly, with no manual export and import step. Keep this in step with
export_pages_data.py; scripts/verify_app_tables.py compares the two outputs table by table.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def tree_nodes(predictor) -> list:
    out = []
    for n in predictor.nodes:
        if n["is_leaf"]:
            out.append(float(n["value"]))
        else:
            if n["is_categorical"] or math.isnan(n["num_threshold"]) or n["num_threshold"] == -math.inf:
                raise ValueError("Unsupported split in trained risk model")
            threshold = None if math.isinf(n["num_threshold"]) else float(n["num_threshold"])
            out.append([int(n["feature_idx"]), threshold, int(n["left"]), int(n["right"]), bool(n["missing_go_to_left"])])
    return out


def build_app_tables(work: Path, memory) -> dict[str, pd.DataFrame]:
    """`work` is the pipeline's output folder; `memory` a built notes.WellMemory."""
    import joblib

    from .server import _clean

    work = Path(work)
    wells = pd.read_parquet(work / "wells.parquet")
    overview = json.loads((work / "overview.json").read_text())
    pilot = json.loads((work / "pilot.json").read_text())
    enrolled = pd.read_parquet(work / "pilot.parquet")
    if not wells.uwi.is_unique or not enrolled.uwi.is_unique:
        raise ValueError("Rebuild scores and pilot enrollment with one record per well.")
    sample = enrolled.nlargest(40, "baseline_repeats")[["uwi", "well_name", "field", "arm", "baseline_repeats"]]
    pilot.update(pilot_mode=False, enrolled_wells=sample.to_dict("records"), outcome=None,
                 outcome_note="The groups were assigned using historical data. The 12-month field outcome is pending.")
    model = joblib.load(work / "repair_model.joblib")
    features = list(model.feature_names_in_)
    np.testing.assert_allclose(model.predict_proba(wells[features])[:, 1], wells["p_repair"], atol=1e-12, rtol=0)
    arms = enrolled.set_index("uwi")["arm"].to_dict()

    facts = [("overview", compact(overview)), ("pilot", compact(pilot)),
             ("origin", compact([wells.surface_latitude.mean(), wells.surface_longitude.mean()])),
             ("model", compact({"base": float(model._baseline_prediction.item()), "features": features,
                                "trees": len(model._predictors)}))]
    facts += [(f"tree-{i:03}", compact(tree_nodes(p))) for i, (p,) in enumerate(model._predictors)]

    enc = memory.encoder
    terms = [(word, compact((enc.svd.components_[:, j] * enc.tfidf.idf_[j]).tolist()))
             for word, j in enc.tfidf.vocabulary_.items()]

    cols = ["uwi", "well_name", "field_operating_area", "surface_latitude", "surface_longitude",
            "p_repair", "expected_loss_low", "expected_loss_mid", "event_cost_low", "event_cost_mid",
            "reasons", "precedent_life_days", "precedent_cost_per_day"]
    rows = []
    for record in wells.to_dict("records"):
        w = {k: _clean(v) for k, v in record.items()}
        query = w["last_repair_note"] if len(w["last_repair_note"] or "") > 5 else w["reasons"]
        precedents = memory.search(query, k=15, exclude_uwi=w["uwi"]) if query else []
        detail = {"well": {k: v for k, v in w.items() if k != "autopsy_notes"},
                  "query": (query or "")[:500],
                  "vector": enc.encode([query.lower()])[0].tolist() if query else [],
                  "precedents": [{"date": _clean(p.start_date), "text": p.text[:500], "similarity": p.similarity,
                                  "life_days": _clean(p.life_days), "cost": _clean(p.cost)} for p in precedents],
                  "autopsy": {"p": {k: w["p_" + k.lower()] for k in ("Pump", "Rods", "Tubing")},
                              "notes": json.loads(w["autopsy_notes"])}}
        rows.append((w["uwi"], compact({k: w[k] for k in cols}), compact([w[k] for k in features]),
                     compact(detail), arms.get(w["uwi"])))
    return {
        "facts": pd.DataFrame(facts, columns=["key", "value"]),
        "wells": pd.DataFrame(rows, columns=["uwi", "listing", "inputs", "detail", "arm"]),
        "terms": pd.DataFrame(terms, columns=["word", "projection"]),
    }
