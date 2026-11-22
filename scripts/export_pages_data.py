"""Export the trained application to private D1 tables. Never put this SQL in the static site."""
import json
import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd

from wellsimple import config, data, notes
from wellsimple.server import DEMO_CREWS, _clean
from wellsimple.store import SCHEMA


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def tree_nodes(predictor):
    result = []
    for n in predictor.nodes:
        if n["is_leaf"]:
            result.append(float(n["value"]))
        else:
            if n["is_categorical"] or math.isnan(n["num_threshold"]) or n["num_threshold"] == -math.inf:
                raise ValueError("Unsupported split in trained risk model")
            # sklearn uses +infinity to split all observed values from missing ones.
            threshold = None if math.isinf(n["num_threshold"]) else float(n["num_threshold"])
            result.append([int(n["feature_idx"]), threshold,
                           int(n["left"]), int(n["right"]), bool(n["missing_go_to_left"])])
    return result


def main():
    work = config.WORK_DIR
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
    assert list(model.feature_names_in_) == features
    memory = notes.WellMemory(notes.TfidfEncoder()).build(data.add_job_outcomes(data.load_jobs()))
    arms = enrolled.set_index("uwi")["arm"].to_dict()
    path = work / "competition-import.sql"
    # SQL values come from real free-text notes. SQLite quotes them before export.
    with sqlite3.connect(":memory:") as quoting, path.with_suffix(".tmp").open("w", encoding="utf-8") as out:
        def insert(table, values):
            # Hex-encoded UTF-8 text keeps newlines, SQL punctuation and Unicode literal.
            literals = [("CAST(X'" + v.encode().hex() + "' AS TEXT)") if isinstance(v, str)
                        else quoting.execute("SELECT quote(?)", (v,)).fetchone()[0] for v in values]
            out.write(f"INSERT OR REPLACE INTO {table} VALUES (" + ",".join(literals) + ");\n")

        out.write(SCHEMA + """
CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wells (uwi TEXT PRIMARY KEY, listing TEXT, inputs TEXT, detail TEXT, arm TEXT);
CREATE TABLE IF NOT EXISTS terms (word TEXT PRIMARY KEY, projection TEXT);
CREATE TABLE IF NOT EXISTS note_vectors (aid INTEGER PRIMARY KEY, vector TEXT);
""")
        for cid, name in DEMO_CREWS:
            out.write(f"INSERT OR IGNORE INTO crews(id,name) VALUES ('{cid}','{name}');\n")
        insert("facts", ["overview", compact(overview)])
        insert("facts", ["pilot", compact(pilot)])
        insert("facts", ["origin", compact([wells.surface_latitude.mean(), wells.surface_longitude.mean()])])
        insert("facts", ["model", compact({"base": float(model._baseline_prediction.item()),
                                         "features": features, "trees": len(model._predictors)})])
        # Keep each SQL statement below D1's statement-size limit.
        for i, (predictor,) in enumerate(model._predictors):
            insert("facts", [f"tree-{i:03}", compact(tree_nodes(predictor))])
        # TF-IDF scaling followed by the original SVD projection. L2 normalization
        # before projection cancels when the resulting vector is normalized again.
        enc = memory.encoder
        for word, j in enc.tfidf.vocabulary_.items():
            projection = enc.svd.components_[:, j] * enc.tfidf.idf_[j]
            insert("terms", [word, compact(projection.tolist())])
        cols = ["uwi", "well_name", "field_operating_area", "surface_latitude", "surface_longitude",
                "p_repair", "expected_loss_low", "expected_loss_mid", "event_cost_low", "event_cost_mid",
                "reasons", "precedent_life_days", "precedent_cost_per_day"]
        for record in wells.to_dict("records"):
            w = {k: _clean(v) for k, v in record.items()}
            query = w["last_repair_note"] if len(w["last_repair_note"] or "") > 5 else w["reasons"]
            precedents = memory.search(query, k=15, exclude_uwi=w["uwi"]) if query else []
            detail = {"well": {k: v for k, v in w.items() if k != "autopsy_notes"},
                      "query": (query or "")[:500],
                      "vector": enc.encode([query.lower()])[0].tolist() if query else [],
                      "precedents": [{"date": _clean(p.start_date), "text": p.text[:500],
                                      "similarity": p.similarity, "life_days": _clean(p.life_days),
                                      "cost": _clean(p.cost)} for p in precedents],
                      "autopsy": {"p": {k: w["p_" + k.lower()] for k in ("Pump", "Rods", "Tubing")},
                                  "notes": json.loads(w["autopsy_notes"])}}
            insert("wells", [w["uwi"], compact({k: w[k] for k in cols}), compact([w[k] for k in features]),
                             compact(detail), arms.get(w["uwi"])])
    path.with_suffix(".tmp").replace(path)
    print(f"Exported {len(wells)} wells and {len(model._predictors)} trained trees to {path}")


if __name__ == "__main__":
    main()
