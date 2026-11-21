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

Every number below is produced by a script in this repo (`scripts/`) and uses time-ordered
splits (train on earlier data, test on later). Dollar figures rest on stated assumptions.

**The problem is real in the data.** 61% of repair jobs (rod truck and workover) on a well
happen within 90 days of the previous repair on that well, and rod, rodstring, pump and tubing
downtime codes account for roughly 160,000 m³ of lost oil (about 1.0 million barrels) over
almost six years.

| Question | Test | Result |
|---|---|---|
| Which wells will need a repair in the next 30 days? | Train to Jun 2025, test Jul 2025 onward | AUC 0.816. Of the top 5% flagged wells, 49.5% needed a repair, against a 12.3% base rate (4.0x). History alone: AUC 0.758. Recent repairs only: 0.685. |
| How long will a fix last? | 2026 jobs, retrieving only earlier jobs on other wells | Error (log-days) 0.978 vs 1.150 for the global median. Rank correlation 0.376, against 0.109 for the well's own history. |
| What will the crew find? | 2026 failures; retrieved notes scored against the real note | Lift over random notes +0.067 (95% CI 0.062 to 0.073). Restricted to notes from other fields: +0.070 (0.064 to 0.075), so it is not one field's writing style. Component AUC: pump 0.76, rods 0.76, tubing 0.69. |

**Money.** As of 2026-10-27 the 1,338 producing wells carry an expected 30-day cost of about
**$2.1M (conservative) to $2.8M (mid)**: the job cost plus the oil lost, weighted by each well's
repair probability. Assumptions: oil valued at $32.50 or $61.60 per barrel (Strathcona Q3 2026
release: operating earnings per boe, and sales minus royalties, transport and energy), the
median repair cost from the data, and the average equipment-related lost oil per repair job
from the data, scaled by each well's oil rate. This is **exposure, not a measured saving**. As a
scenario only: capturing 10% of it would be about $2.6M to $3.5M per year if the current
exposure persisted. How much is truly avoidable is not measured here and would need a field trial.

## Limitations (stated up front)

- The failure log covers about 22 months (2025 to 2026) even though the handbook range is longer.
  Component labels exist for that window only. Repair outcomes use the job log, which spans the
  full period.
- The risk label is "any repair job in the next 30 days", which includes planned work such as
  scheduled pump changes. It predicts work needed, not only failures.
- Cross-modal results are moderate (component match 71% vs 62% for random). The portals present
  it as an estimate with its test results, not a diagnosis. Pump model and job type are not controlled.
- Neural sentence embeddings (MiniLM) were tested and did slightly worse than TF-IDF on this
  task (rank correlation 0.337 vs 0.376), so TF-IDF is the default encoder.
- Job costs are field estimates, about 16% of repair jobs have a cost of zero or less (treated
  as missing), and barrel price and lost-oil allowance are assumptions.
- Notes the crews submit in the app are added to memory but do not retrain the
  risk model. The app has no login, and submissions made in it are demo inputs.

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

**Methods**
- `wellsimple/data.py`: cleaning (sensor placeholders and spikes removed), failure-to-job linking
  (98.5% of failures link to a repair job), repair outcomes (days to the next repair job).
- `wellsimple/risk.py`: weekly snapshots of each producing well, 30-day and 7-day sensor
  features, repair history, forward 30-day label; gradient-boosted trees.
- `wellsimple/notes.py`: "Well Memory", nearest-neighbour retrieval over repair-job notes
  (TF-IDF with SVD) with outcome statistics. Every answer is computed from real past jobs.
- `wellsimple/crossmodal.py`: a random forest maps pre-failure sensor features into the crew-note
  text space and returns the nearest real notes and a likely component.
- `wellsimple/scoring.py`: expected dollar loss per well and rank-based reasons.
- `wellsimple/server.py`, `wellsimple/static/`: FastAPI app with the manager and crew portals.

**Validation**: all splits are time-ordered; the retrieval tests exclude the failing well, and the
cross-modal test also excludes the failing well's field; history and label logic has unit tests
(`python -m pytest`, 20 tests). Both portals were exercised in a headless browser.

**External resources**: Strathcona Resources Q3 2026 results release (price and cost assumptions),
OpenStreetMap tiles, Leaflet 1.9.4 and Chart.js 4.4.1 (loaded from CDNs).

**AI disclosure**
- Claude Code (Claude Sonnet 5.5) wrote and reviewed much of the code and tests under the team's
  direction, and drafted analysis scripts. Commits it co-authored carry a `Co-Authored-By` line.
- No generative model creates or extracts any content shown in the product. Retrieval and
  statistics only.
- An optional local sentence-embedding model (MiniLM) is supported and was evaluated, but is not
  the default. The crew portal's Dictate button uses the browser's built-in speech recognition,
  which may send audio to the browser vendor.
