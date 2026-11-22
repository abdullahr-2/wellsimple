"""WellSimple pipeline as a Databricks job (serverless).

Runs the same code as a laptop run, reading the raw competition files from a Unity Catalog
volume, then publishes the results as Delta tables in workspace.wellsimple_pipeline:

  gold_wells_scored   one row per producing well: risk, expected loss, reasons, likely component
  gold_pilot_wells    A/B pilot enrollment (arm, strata, baseline)
  gold_facts          overview and pilot JSON (the dashboard numbers)
  app_facts, app_wells, app_terms   the three tables the app reads (same shape as the hosted demo)
  gold_repair_notes   every repair note with its outcome and a 100-dimension vector
                      (change data feed on, so Databricks Vector Search can sync from it)
  pipeline_runs       one row per run: when, how many rows, how long

Deployed and run with the bundle in databricks.yml:  databricks bundle run wellsimple_pipeline
"""
import argparse
import json
import os
import runpy
import sys
import time
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    # serverless runs this file without __file__, so the bundle passes its own folder in
    ap.add_argument("--root", default=None, help="folder holding the deployed repo files")
    ap.add_argument("--catalog", default="workspace")
    ap.add_argument("--schema", default="wellsimple_pipeline")
    # optional: refresh the app's read-only tables (facts, wells, terms) in this schema after a run.
    # Off by default because it writes to the app's schema; app_state (assignments, notes) is never touched.
    ap.add_argument("--publish-app-schema", default="", help="e.g. workspace.wellsimple")
    ap.add_argument("--vector-index", default="workspace.wellsimple_pipeline.repair_notes_index",
                    help="Databricks Vector Search index to re-sync after the notes table is rewritten")
    args = ap.parse_args()
    ROOT = Path(args.root) if args.root else Path(globals().get("__file__", ".")).resolve().parents[1]
    raw = f"/Volumes/{args.catalog}/{args.schema}/raw"
    work = f"/Volumes/{args.catalog}/{args.schema}/artifacts"
    os.environ["DATA_DIR"], os.environ["WORK_DIR"] = raw, work  # set before wellsimple.config is imported
    sys.path.insert(0, str(ROOT))
    t0 = time.time()

    runpy.run_path(str(ROOT / "scripts" / "build_artifacts.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "scripts" / "build_pilot.py"), run_name="__main__")

    import pandas as pd
    from pyspark.sql import SparkSession
    from pyspark.sql import types as T

    from wellsimple import data, notes

    spark = SparkSession.builder.getOrCreate()
    fq = lambda name: f"{args.catalog}.{args.schema}.{name}"

    def publish(df: pd.DataFrame, name: str, comment: str, schema=None, cdf=False):
        sdf = spark.createDataFrame(df, schema=schema) if schema is not None else spark.createDataFrame(df)
        sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(fq(name))
        spark.sql(f"COMMENT ON TABLE {fq(name)} IS '{comment}'")
        if cdf:
            spark.sql(f"ALTER TABLE {fq(name)} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
        print(f"published {fq(name)}: {len(df):,} rows")
        return len(df)

    # scored wells: complex columns kept as JSON text so every consumer can read them
    wells = pd.read_parquet(f"{work}/wells.parquet")
    for c in wells.columns:
        if wells[c].dtype == object:
            wells[c] = wells[c].astype(str)
    for c in wells.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
        wells[c] = wells[c].astype(str)
    counts = {"gold_wells_scored": publish(wells, "gold_wells_scored", "Producing wells scored by the WellSimple risk model")}
    counts["gold_pilot_wells"] = publish(pd.read_parquet(f"{work}/pilot.parquet"), "gold_pilot_wells", "A/B pilot enrollment")
    facts = pd.DataFrame({"key": ["overview", "pilot"],
                          "value": [Path(f"{work}/overview.json").read_text(), Path(f"{work}/pilot.json").read_text()]})
    counts["gold_facts"] = publish(facts, "gold_facts", "Dashboard JSON: overview and pilot")

    # repair notes with vectors, ready for Databricks Vector Search (Delta Sync, self-managed embeddings)
    rep = data.add_job_outcomes(data.load_jobs())
    mem = notes.WellMemory(notes.TfidfEncoder()).build(rep)
    j = mem.jobs
    nt = pd.DataFrame({
        "note_id": j["vid"], "uwi": j["uwi"].astype(str), "start_date": j["start_date"].dt.strftime("%Y-%m-%d"),
        "start_day": [int(d.value // 86_400_000_000_000) for d in j["start_date"]],
        "job_type": j["job_type"].astype(str), "text": j["text"].astype(str),
        "cost": j["cost"].astype(float), "life_days": j["life_days"].astype(float), "censored": j["censored"].astype(bool),
        "embedding": [list(map(float, v)) for v in mem.vecs],
    })
    schema = T.StructType([
        T.StructField("note_id", T.StringType(), False), T.StructField("uwi", T.StringType()),
        T.StructField("start_date", T.StringType()), T.StructField("start_day", T.LongType()),
        T.StructField("job_type", T.StringType()), T.StructField("text", T.StringType()),
        T.StructField("cost", T.DoubleType()), T.StructField("life_days", T.DoubleType()),
        T.StructField("censored", T.BooleanType()), T.StructField("embedding", T.ArrayType(T.FloatType())),
    ])
    counts["gold_repair_notes"] = publish(nt, "gold_repair_notes", "Repair notes with outcomes and TF-IDF/SVD vectors",
                                          schema=schema, cdf=True)

    # the three tables the app reads (same shape as the hosted demo's facts / wells / terms)
    from wellsimple.app_tables import build_app_tables

    for name, df in build_app_tables(Path(work), mem).items():
        counts[f"app_{name}"] = publish(df, f"app_{name}", f"App-ready {name} table, rebuilt by the pipeline on every run")

    if args.publish_app_schema:
        for name in ("facts", "wells", "terms"):
            spark.sql(f"CREATE OR REPLACE TABLE {args.publish_app_schema}.{name} AS SELECT * FROM {fq('app_' + name)}")
            print(f"refreshed {args.publish_app_schema}.{name} from {fq('app_' + name)}")
        counts["published_to"] = args.publish_app_schema

    # keep Databricks Vector Search in step with the notes table (skipped if the index does not exist yet)
    try:
        from databricks.sdk import WorkspaceClient

        WorkspaceClient().vector_search_indexes.sync_index(args.vector_index)
        counts["vector_index_sync"] = "triggered"
        print(f"triggered sync of {args.vector_index}")
    except Exception as e:  # the pipeline's tables are already published; a missing index is not a failure
        counts["vector_index_sync"] = f"skipped: {type(e).__name__}"
        print(f"vector index sync skipped: {e}")

    run = pd.DataFrame([{"finished_at": pd.Timestamp.now(tz="UTC").isoformat(), "seconds": round(time.time() - t0, 1),
                         "row_counts": json.dumps(counts)}])
    sdf = spark.createDataFrame(run)
    sdf.write.mode("append").saveAsTable(fq("pipeline_runs"))
    print(f"done in {time.time() - t0:.0f}s: {counts}")


if __name__ == "__main__":
    main()
