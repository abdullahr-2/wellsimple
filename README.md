# WellSimple

A two-portal system that turns field crew knowledge and well sensor data into repair decisions.

- **Manager portal:** overview dashboard, ranked at-risk wells with reasons, job assignment, resolved wells.
- **Crew portal (mobile-first):** assigned wells, precedent cases and diagnosis notes, map with the well and the crew's location, and a quick way to log what was done.
- **Well Memory:** every repair note (13,854 from the job log, plus each note a crew submits) is stored as a vector with the outcome of that job (cost, how long the fix lasted) in **Chroma**, an embedded vector database saved to disk, and searched by cosine similarity with filters (earlier jobs only, other wells only). A separate model links pre-failure sensor behavior to the notes. See "Vector database and scalability" below.

Competition: DSMLC Canary x Chirality 2026 Datathon, Strathcona Resources case.

**Team:** TBD (add member names here)
**Research question and motivation:** see [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md)
**Solution form:** prototype AI/ML application
**Slides:** https://www.canva.com/design/DAHbnTawanU/qvB8aHGXQ83KIqfmewKOVA
**Video:**  https://youtu.be/rk2eHiXGtqk
## Summary of findings

Every number below is produced by a script in this repo (`scripts/`) and uses time-ordered
splits (train on earlier data, test on later). Dollar figures rest on stated assumptions.

**The problem is real in the data.** 61% of repair jobs (rod truck and workover) on a well
happen within 90 days of the previous repair on that well, and rod, rodstring, pump and tubing
downtime codes account for roughly 160,000 m³ of lost oil (about 1.0 million barrels) over
almost six years.

| Question | Test | Result |
|---|---|---|
| Which wells will need a repair in the next 30 days? | Train to Jun 2025, test Jul 2025 onward (85,057 well-weeks) | AUC **0.818 (95% CI 0.808 to 0.826)**, against 0.716 for each well's own repair history and 0.678 for the field average. Of the top 5% flagged, 48.6% needed a repair (CI 45.1% to 52.1%) against a 12.3% base rate. Well calibrated: predicted 42% came true 43% of the time, 27% came true 28%. A field the model never saw loses only 0.01 to 0.02 AUC. Sensors lift it from 0.758 (history alone) to 0.818. |
| How long will a fix last? | Every 2026 repair job, including the 35% still running (Kaplan-Meier, strict timing) | Concordance **0.693** (CI 0.675 to 0.708) from the crew note, against 0.584 from sensors, 0.575 for the field average and 0.566 for the well's own history. Calibrated: predicted 23 / 38 / 55 / 98 / 224 days, actual 20 / 31 / 55 / 83 / 226. |
| What will the crew find? | 2026 failures; retrieved notes scored against the real note | Lift over random notes +0.067 (95% CI 0.062 to 0.073). Restricted to notes from other fields: +0.070 (0.064 to 0.075), so it is not one field's writing style. Component AUC: pump 0.76, rods 0.76, tubing 0.69. |

**Each data source wins its own question.** Sensors answer *when* a well will need a repair (risk
model); the crew's own note answers *how long* a fix will last (adding sensors to the note did not
help: 0.688 vs 0.693). We report that rather than force sensors into both.

**PCP physics, tested against what crews found** (full detail in [docs/DOMAIN.md](docs/DOMAIN.md)). The
recorded efficiency is the pump's volumetric efficiency (actual / displacement x RPM; 72% of well-days
agree within 0.02). Physics features (efficiency drop rate, torque spikes, torque per unit displacement,
revolutions and a Miner's-rule fatigue index since the last repair) add AUC +0.0022 (CI +0.0006 to
+0.0037). Checking the textbook reading of sensor signatures against 13,462 crew notes: gas interference
is confirmed (crews mention gas 3.6 times as often, CI 2.1 to 6.2) and stator wear weakly (1.07x), while
the sand, rod-fatigue and dry-running signatures are not, so the portal calls them "unusual signals", not
causes. Rod breaks are not early failures (35% within 30 days of the previous repair, the same as all repairs).

**Repairs are concentrated.** The worst 10% of wells take 35% of all repair jobs (34% of rod-truck jobs).

**Do fixes last? Not for long, and that changes the strategy.** Fitting a Weibull model to the time
between repair jobs (right-censored at the end of the data) gives a shape of k = 0.61 (95% CI 0.60 to
0.62; rod-truck jobs 0.66, workovers 0.71). A shape below 1 means risk is highest right after a fix
and falls with time: rod-truck jobs are about 10 times likelier to need another visit in the first
week (3.0% per day) than 6 to 12 months later (0.28% per day). Classic age-based replacement only
pays when k is above 1, so scheduled replacement of running equipment would not pay here; the saving
is in making each repair last. This is not just bad wells failing first: within groups of similarly
repair-prone wells k is 0.62 to 0.79, and comparing each well with itself k = 0.71 (95% CI 0.70 to 0.73)
(`scripts/eval_reliability.py`). Likely causes are the root cause not being fixed, installation problems
and new parts settling in. What pays: getting the repair right, watching wells closely in the first weeks
after a repair, and redesigning the chronic wells (the 21+ repair wells are closest to constant risk, k = 0.79). By crew job type, rod repairs repeat within 30 days 44% to 50% of the
time (median fix lasts 31 to 38 days), against 14% to 20% for pump replacement (median 114 to 134 days).
Caveat: the next job on a well can be a planned follow-up visit, so some early risk is return trips.

**Money.** Three different numbers, kept separate on purpose.

1. *Exposure (modelled).* As of 2026-10-27 the 1,336 distinct producing wells carry an expected 30-day cost
   of about **$3.8M (conservative) to $4.6M (mid)**: each well's repair probability times (the
   average repair cost, $17,461, plus the oil lost during a repair). About $3.0M of that is job
   cost and $0.8M to $1.6M is lost oil. Only the oil part depends on the barrel price (valued at
   $32.50 or $61.60 from Strathcona's Q3 2026 release: operating earnings per boe, and sales minus
   royalties, transport and energy). The job-cost part depends on the data's field cost estimates.
   Sanity check: repair jobs in the final 12 months cost about $3.8M per 30 days across all wells,
   so the job-cost part is the right scale. **Exposure is mostly spend the company will incur
   anyway. It is not new money, and it is not a saving.**
2. *Addressable pool (measured).* Repair jobs that start within 30 days of a previous repair on the
   same well are 34% of all repair jobs and about **$13.9M a year** of field-estimated cost (38% of
   repair spend); within 90 days, 60% of jobs and about $20.1M a year (55%). This is a ceiling on what
   better repairs could address, not a saving: some repeats are planned follow-up visits or unrelated
   failures.
3. *Savings (not measured).* Illustration only: if better repairs removed 10% of the 30-day repeat
   spend, that would be about $1.4M a year before counting oil. Nothing in this historical data is an
   intervention, so a saving cannot be measured from it. See the next section for what we tested and
   for the trial that would measure it.

## Can we measure savings? What the data supports

We tested the three places a saving could come from (`scripts/eval_savings_levers.py`). Two found
nothing to save and one is a hypothesis, not a result.

| Lever | Result | Verdict |
|---|---|---|
| Dispatch order | 93.7% of failures get a repair job the same day or earlier; 0.9% wait more than 3 days | Nothing to re-order |
| Choice of fix | In the same 812 wells, cost per day of life including lost oil: rod fix $246, pump $306, tubing $397 | The cheap fix already wins; fixes are not interchangeable |
| Pump make | Rate of the next repair versus PCM, between wells: MANTL 0.65 (0.54 to 0.80), BMW 0.60 (0.46 to 0.78), Europump 0.72 (0.53 to 0.89), Weatherford 0.79 (0.69 to 0.94), LSI 1.12 (0.95 to 1.28). Within the same well (308 wells with 2+ makes): all intervals include 1 and BMW reverses to 1.56 (1.13 to 2.50) | Suggestive between wells, not confirmed within wells. A hypothesis for a pilot |

**Measuring the saving needs a trial, and the data tells us how big** (`scripts/trial_power.py`).
Repeat repairs are lumpy: 72% of producing wells had none in the last 12 months and one had 17. We
resampled real wells, gave half a hypothetical reduction in repeats, and counted how often a standard
test detects it in a 12-month trial:

| Wells per arm | 20% fewer repeats | 30% fewer | 50% fewer |
|---|---|---|---|
| 100 (whole fleet) | 8% | 16% | 46% |
| 400 (whole fleet) | 25% | 52% | 96% |
| 669 (whole fleet, half each) | 38% | 76% | 100% |
| 100 (only wells that repeated last year) | 15% | 27% | 76% |
| 150 (only wells that repeated last year) | 17% | 36% | 92% |

So: a 12-month pilot on about 100 to 150 repeat-prone wells per arm can reliably detect a 50% reduction.
Smaller effects need a longer trial or a within-well crossover. Each 10% of the measured $13.9M a year
repeat pool is about $1.4M a year (field-estimated repair spend, before oil).

## The A/B pilot (built and enrolled, follow-up in progress)

Savings are measured by an experiment, so we built one. `python scripts/build_pilot.py` enrolls and
randomizes real wells, and the manager portal's **A/B pilot** tab shows the plan and status.

- **Population:** the 369 producing wells that had at least one repeat repair in the last 12 months
  (a repair job within 30 days of the previous one on the same well).
- **Arms:** 186 "system" wells (the portal recommends and tracks action) and 183 "control" wells (usual
  practice). Assignment is random within field and baseline-repeat strata with a fixed seed (2026).
  Setting `PILOT_MODE=1` hides control wells from the manager list so the experiment is not contaminated.
- **Balance:** standardized differences at enrollment are -0.10 for baseline repeats, -0.13 for prior-year
  repeats, -0.01 for repairs in 12 months and +0.09 for oil rate. Prior-year repeats are slightly over the usual
  0.1 guide (the system arm has a little less history of repeats), so the read at 12 months should also be
  reported adjusted for baseline repeats.
- **Pre-specified analysis:** primary outcome is repeat repairs per well over 12 months; rate ratio with a
  permutation p-value and a bootstrap interval; one read at 12 months, no peeking.
- **The test is validated on real history (A/A check):** randomizing 404 real repeat-prone wells 200 times
  with no intervention, the analysis wrongly reported a difference 4.0% of the time (95% interval 1.3% to
  6.7%), which is the expected 5%. So it does not invent effects. Unit tests also confirm it detects and
  brackets a known 50% effect.
- **Power at 183 wells per arm:** 24% for a 20% cut, 50% for a 30% cut, 96% for a 50% cut; the smallest
  effect with 80% power is 50%. Smaller effects need a longer pilot or more wells.
- **Result:** the measured result reads out 12 months after enrollment (first read 2027-10-26) and will
  replace the potential figures. Until then, the potential is about $5.0M a year at a 30% cut in repeat
  repairs, up to about $9.1M at the 55% a published program achieved (range $1.7M to $9.1M, from the
  measured $13.9M a year repeat-repair pool plus lost oil). The outcome is never simulated.

**Outside "after" data: what exists and what it can and cannot show.** Data from our system on these wells
cannot exist yet, because nothing has been deployed. Published before/after results from other operators do
exist, and we looked (public supplementary data is allowed if disclosed; no external dataset feeds any model).
The closest documented case is a [JPT report](https://jpt.spe.org/applying-root-cause-failure-analysis-enhances-artificial-lift-performance)
(June 2014) of IPTC paper 17230 by ExxonMobil and GE authors on a field in Chad:

- A root-cause failure analysis (RCFA) program: every failed unit dismantled and inspected, weekly failure
  review meetings, and an Extended Run Life Team aimed at short runs (under 90 days) and repeat failures
  within 365 days, which is the same problem we target.
- PCP failures per month fell from 6 (2007, 155 wells) to 3.7 (July 2013, 210 wells). Their reported "failure
  frequency" fell from 0.47 to 0.21, about 55% (our arithmetic). Checking the paper's four pairs, the figures
  match failures per well per year (monthly failures x 12 / wells), which is our inference, not stated.
- **Limits:** a before/after comparison over six years, not a controlled trial; the well population and other
  practices changed and are not adjusted for; not peer reviewed; a different country and a physical
  teardown program, not software. It is evidence that this kind of program can work, not an estimate of our
  effect on Strathcona's wells. Other sources we found were weaker (a modelled 6.4% saving, a cross-industry
  survey correlation of 36% lower unplanned downtime, and vendor claims) and are not used.

**What the repeat pool would be worth under different results.** Scenarios, not measurements. Repair
spend is 13.9M a year times the reduction; lost oil is about $2.6M a year at the conservative price times
the reduction. Applying a reduction in all PCP failures to the 30-day repeat pool is an analogy.

| If repeat repairs fall by | Repair spend | Lost oil (conservative) | About per year |
|---|---|---|---|
| 10% | $1.4M | $0.3M | $1.7M |
| 20% | $2.8M | $0.5M | $3.3M |
| 30% | $4.2M | $0.8M | $5.0M |
| 50% (pilot's detectable size) | $6.9M | $1.3M | $8.3M |
| 55% (Chad PCP benchmark) | $7.6M | $1.4M | $9.1M |

## Vector database and scalability

Well Memory runs on **Chroma**, an embedded vector database stored in `WORK_DIR/vectors`. It needs no server, keeps
the index between restarts (startup drops from about 13 s to 8 s once built) and stores crew notes permanently.
`VECTOR_BACKEND=memory` switches to exact in-memory search, and the app falls back to it automatically if Chroma is not
installed. Backtests always use exact search so their numbers are exact. Measured in `scripts/bench_vector_search.py`:

| Test | Exact search | Chroma |
|---|---|---|
| Real notes (13,854): same top 10 as exact search, with the app's filters | reference | **99.8%** over 299 real queries |
| Real notes: time per search | 5 ms | 31 ms |
| 100,000 random vectors with filters (speed test) | 4 ms, exact | 286 ms, 59% recall |
| 500,000 random vectors with filters (speed test) | 18 ms, exact | 1.7 s, 30% recall |

On Databricks the notes are also indexed in **Databricks Vector Search** (endpoint `wellsimple-vs`), which matches
exact search on 99.2% of 300 real filtered queries (`scripts/check_vector_search.py`; see docs/DATABRICKS.md).

What this means for scaling. At Strathcona's pace (about 2,400 notes a year) exact search stays in the milliseconds for
centuries of notes, so speed is not the bottleneck. Approximate vector indexes like Chroma's pay off at tens of millions
of vectors, and with filters they need tuning and a recall check (on random vectors, the hardest case, raising Chroma's
search effort did not lift recall). The database's real value here is durability and sharing: in production the same
interface would sit on Databricks Vector Search or Postgres with pgvector, so several app servers share one store,
with exact or tuned search chosen by measured recall.

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
  risk model. The local app has no login. The hosted competition demo requires a presenter login. Submissions are demo inputs.

## Setup and run

### Hosted competition demo

Open [WellSimple](https://wellsimple.holize.ca), sign in with the presenter credentials, select **At-risk wells**, and click **Score producing wells**. The browser runs the trained gradient-boosted trees on the actual fleet snapshot and ranks available wells by their 30-day repair probability. Select a well for related historical jobs and sensor-based component estimates. Assignments and crew submissions are shared across signed-in devices. The A/B pilot tab reports enrollment, baseline balance and statistical power.

The three source Parquet files are used locally. The hosted API reads model inputs, fitted tree parameters, retrieval results, pilot statistics and shared crew state from the private `workspace.wellsimple` Databricks schema. The website authenticates as the scoped `wellsimple-hosted` service principal through the Pages secret `DATABRICKS_CLIENT_SECRET`. The production Pages secret `DEMO_PASSWORD` controls access for the username `demo`. The build directory contains only application code and static assets. The historical data is a fixed snapshot; automated refresh is not yet configured.

The current Databricks tables were initialized from the private export with `scripts/prepare_databricks_data.py` and `scripts/import_databricks_data.py`. The app-state table contains live crew submissions and must be preserved during subsequent data refreshes. Run `python scripts/build_pages.py` and deploy `dist-pages/site` to the production branch of `holize-wellsimple` after validating changes. The scored fleet and pilot use one entry per well identifier, including wells with repeated rows on the last reporting day.

### Local Python demo

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

**Easiest on Windows:** `.\run_demo.ps1 -DataDir "C:\path\to\Competition Dataset"` does steps 1 to 3 for you
(it builds what is missing, starts the app and opens the browser). If `localhost` does not load, the app is
not running: keep that window open, and try `http://127.0.0.1:8000/` instead.

1. Score the wells and build the tables the portals read (about 1 to 2 minutes):
   `python scripts/build_artifacts.py`, then enroll the A/B pilot: `python scripts/build_pilot.py`
2. Start the app (loads in about 30 seconds):
   `python -m uvicorn wellsimple.server:load_app --factory --port 8000`
3. Open the manager portal at <http://localhost:8000/> and the crew portal at
   <http://localhost:8000/crew> (use a phone on the same network for the real mobile view).

**Rerun everything with one command:** `python scripts/run_all.py` runs the tests, builds the tables and the
pilot, and runs every evaluation (about 8 to 10 minutes on a laptop), saving each report to `WORK_DIR/reports/`.
Individual evaluations: `eval_risk.py`, `explain_risk.py`, `eval_physics.py`, `eval_precedent.py`,
`eval_crossmodal.py`, `eval_savings_levers.py`, `trial_power.py`, `compare_models.py` (needs the optional
`xgboost` and `lightgbm`). Tests: `python -m pytest`.

The local app has no login. Assignments and crew submissions made in it are
demo inputs, not field records.

## Methods, validation, external resources, AI disclosure

**Methods**
- `wellsimple/data.py`: cleaning (sensor placeholders and spikes removed), failure-to-job linking
  (98.5% of failures link to a repair job), repair outcomes (days to the next repair job).
- `wellsimple/risk.py`: weekly snapshots of each producing well, 30-day and 7-day sensor
  features, repair history, forward 30-day label; gradient-boosted trees. On the same held-out split, scikit-learn
  boosting (AUC 0.816), XGBoost (0.817) and LightGBM (0.816) are indistinguishable, and logistic regression
  is lower (0.785), so we kept scikit-learn (no extra dependency, handles missing values natively); see
  `scripts/compare_models.py`.
- `wellsimple/physics.py`: PCP physics features (volumetric efficiency trend, speed variability, torque spikes,
  torque per unit displacement, revolutions and a fatigue index since the last repair). See docs/DOMAIN.md.
- `wellsimple/evaluation.py`: held-out report for the risk model (baselines, well-resampled intervals,
  calibration, cold start, unseen field), shown in the manager portal.
- `wellsimple/vectorstore.py`: the vector store interface with two backends (exact in-memory search and the Chroma
  vector database), the same filters on both; `scripts/bench_vector_search.py` checks they agree and benchmarks them.
- `wellsimple/notes.py`: "Well Memory", nearest-neighbour retrieval over repair-job notes
  (TF-IDF with SVD) with outcome statistics. Every answer is computed from real past jobs.
- `wellsimple/crossmodal.py`: a random forest maps pre-failure sensor features into the crew-note
  text space and returns the nearest real notes and a likely component.
- `wellsimple/reliability.py`: censored Weibull fit of repair lifetimes, empirical hazard, the
  age-replacement test (Barlow-Proschan), a job-type cost Pareto, Kaplan-Meier medians and the
  concordance index.
- `wellsimple/levers.py`: tests of candidate savings sources (pump-make rate ratios with field and
  well controls, cluster bootstrap intervals). `scripts/trial_power.py`: data-calibrated trial design.
- `wellsimple/abtest.py`: pilot enrollment, stratified randomization, balance check, the pre-specified analysis
  (rate ratio, permutation test, bootstrap), the A/A false-positive check and power.
- `wellsimple/scoring.py`: expected dollar loss per well and rank-based reasons.
- `wellsimple/server.py`, `wellsimple/static/`: FastAPI app with the manager and crew portals.

**Validation**: all splits are time-ordered; the retrieval tests exclude the failing well, and the
cross-modal test also excludes the failing well's field; history and label logic has unit tests
(`python -m pytest`, 53 tests, including recovery of known Weibull and rate-ratio parameters, a test that field controls remove a false make effect, an A/A false-positive test and detection of a known effect in the A/B analysis). Both portals were exercised in a headless browser.

**External resources**: Strathcona Resources Q3 2026 results release (price and cost assumptions), the JPT
articles cited in docs/DOMAIN.md,
OpenStreetMap tiles, Leaflet 1.9.4 and Chart.js 4.4.1 (loaded from CDNs).

**AI disclosure**
- Claude Code (Claude Sonnet 5.5, later Claude Opus 5.5) wrote and reviewed much of the code and tests under the team's
  direction, and drafted analysis scripts. Commits it co-authored carry a `Co-Authored-By` line.
- No generative model creates or extracts any content shown in the product. Retrieval and
  statistics only.
- An optional local sentence-embedding model (MiniLM) is supported and was evaluated, but is not
  the default. The crew portal's Dictate button uses the browser's built-in speech recognition,
  which may send audio to the browser vendor. Dictation works in Chrome and Edge (with microphone permission and an internet connection). Brave, Firefox and plain Chromium often expose the button but cannot start it, so the portal says so and points to the keyboard's own microphone key.
