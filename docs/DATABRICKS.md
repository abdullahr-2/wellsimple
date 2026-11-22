# WellSimple on Databricks

How the project runs on Databricks, and the contract between the data pipeline and the app.

## Layout

| Schema | Owner | Contents |
|---|---|---|
| `workspace.wellsimple_pipeline` | the pipeline job | raw data, scored outputs, app-ready tables, notes for Vector Search |
| `workspace.wellsimple` | the app | the app's own tables and saved state (`app_state`) |

The pipeline never writes to `workspace.wellsimple`. The app reads the pipeline's `app_*` tables (or copies them).

## Pipeline tables (`workspace.wellsimple_pipeline`)

| Table | Rows | What it is |
|---|---|---|
| `bronze_daily_production` | 5,075,590 | raw daily file, as delivered |
| `bronze_well_jobs` | 15,610 | raw job log |
| `bronze_production_failures` | 2,873 | raw failure log |
| `gold_wells_scored` | 1,336 | one row per producing well: risk, expected loss, reasons, likely component, precedent |
| `gold_pilot_wells` | 369 | A/B pilot enrollment: arm, strata, baseline |
| `gold_facts` | 2 | `overview` and `pilot` JSON (dashboard numbers) |
| `gold_repair_notes` | 13,854 | every repair note with outcome (cost, days it lasted) and a 100-dimension vector; change data feed on for Vector Search |
| `app_facts` | 254 | same shape as the app's `facts`: overview, pilot, map origin, the risk model as decision trees |
| `app_wells` | 1,336 | same shape as the app's `wells`: listing, model inputs, detail (precedents, likely finding), pilot arm |
| `app_terms` | 4,848 | same shape as the app's `terms`: each word's search projection |
| `pipeline_runs` | 1 per run | when each run finished, how long it took, row counts |

Raw files live in the volume `/Volumes/workspace/wellsimple_pipeline/raw/` (restricted competition data, datathon use only).
The job writes its working files to `/Volumes/workspace/wellsimple_pipeline/artifacts/`.

## First run (2026-11-21)

The job ran successfully on serverless in 339 seconds and published every table above. Comparing its app tables with
the app's current ones (`scripts/verify_app_tables.py`): same 1,336 wells, same pilot arms, same 254 facts keys and
4,848-word vocabulary, but **the app's current model is older**: 31 features against 38 in the pipeline (the seven
PCP physics features were added after the app's export). The app's scoring code (`pages/model.js`) reads feature
positions from the model itself, so it works unchanged with the 38-feature model.

Model scores also depend slightly on library versions: the same code scored on a laptop (scikit-learn 1.9.1) and on
Databricks (1.6.1) differs by 0.007 on average (correlation 0.9956; 58 of the top 67 wells agree). Running the
pipeline in one place, the Databricks job, keeps the model and the app's inputs consistent.

## Switching the app to the pipeline tables

`app_facts`, `app_wells` and `app_terms` are built by the same logic as `scripts/export_pages_data.py`
(`wellsimple/app_tables.py`). Check they can replace the current tables:

```
python scripts/verify_app_tables.py --profile <profile> --warehouse <sql-warehouse-id>
```

It compares wells, pilot arms, risk scores, facts keys, model shape and vocabulary, and prints `RESULT`.

To let every pipeline run refresh the app, add `"--publish-app-schema", "workspace.wellsimple"` to the job parameters
in `databricks.yml`. After publishing its own tables, the job then runs
`CREATE OR REPLACE TABLE workspace.wellsimple.{facts,wells,terms} AS SELECT * FROM workspace.wellsimple_pipeline.app_*`.
`app_state` (assignments and crew notes) is never touched. This is off by default because it writes to the app's
schema; the app owner turns it on. The manual export, `prepare_databricks_data.py` and `import_databricks_data.py`
steps are then no longer needed.

## Deploying and running the pipeline

Prerequisites: the Databricks CLI, a profile for the workspace, and the three parquet files in the `raw` volume.

```
databricks bundle deploy --profile <profile>
databricks bundle run wellsimple_pipeline --profile <profile>
```

The job runs `databricks/pipeline_job.py` on serverless compute, environment version 4 (Python 3.12, pandas 2.2,
numpy 2.1, scikit-learn 1.6). Nothing extra is installed: on environment 2, installing newer pandas and pyarrow on
top of the built-in libraries broke numpy for scipy and scikit-learn (`databricks/env_check.py` prints the versions).

## Free Edition limits that shape this

One Vector Search endpoint, up to 3 apps (each stops after 24 hours and can be restarted), serverless compute only,
restricted outbound internet.
