# WellSimple

A two-portal system that turns field crew knowledge and well sensor data into repair decisions.

- **Manager portal:** overview dashboard, ranked at-risk wells with reasons, job assignment, resolved wells.
- **Crew portal (mobile-first):** assigned wells, precedent cases and diagnosis notes, map with the well and the crew's location, and a quick way to log what was done.
- **Well Memory:** every crew note is stored as a vector alongside the sensor behavior before the job and the outcome after it, so each new failure can retrieve what worked before.

Competition: DSMLC Canary x Chirality 2026 Datathon, Strathcona Resources case.

**Team:** TBD (add member names here)
**Research question and motivation:** see [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md)
**Solution form:** prototype AI/ML application
**Video / slides:** TBD (links to be added before submission)

## Summary of findings

To be completed after the backtests. Numbers are only added once the code in this repo produces them.

## Setup and run

The competition dataset is not included and must not be shared or committed. Extract it
locally (the folder with the three `.parquet` files) and point the project at it:

```
pip install -r requirements.txt

# Windows (PowerShell)
$env:DATA_DIR = "C:\path\to\Competition Dataset"
$env:WORK_DIR = "C:\path\to\artifacts"        # optional, default ./artifacts (git-ignored)

# macOS / Linux
export DATA_DIR="/path/to/Competition Dataset"
```

1. Score the wells and build the tables the portals read (about 1 to 2 minutes):
   `python scripts/build_artifacts.py`
2. Start the app (loads in about 30 seconds):
   `python -m uvicorn wellsimple.server:load_app --factory --port 8000`
3. Open the manager portal at <http://localhost:8000/> and the crew portal at
   <http://localhost:8000/crew> (use a phone on the same network for the real mobile view).

Evaluation scripts (time-ordered backtests): `python scripts/eval_risk.py`,
`python scripts/eval_precedent.py`. Tests: `python -m pytest`.

The app has no login. It is a demo, and assignments and crew submissions made in it are
demo inputs, not field records.

## Methods, validation, external resources, AI disclosure

To be completed. Planned disclosures:

- Text embeddings from an open-source sentence-embedding model, run locally.
- Scikit-learn models for the sensor-to-text and risk models.
- AI coding assistance (Claude Code) was used to write and review code, and commits co-authored by it are marked in the history.
- External data: Strathcona quarterly reports for price and cost assumptions.
