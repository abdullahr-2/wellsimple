# Pitch plan

Audience (from the kickoff slide, roles only): an applied data and BI analyst at Chirality Research,
a Strathcona data analyst, an operations EIT at another producer, and a downstream applications
specialist. Expect people who know this data, know what a rod string is, and will check numbers.

**One-line pitch:** WellSimple tells a manager which wells to fix first and what it is worth, tells the
crew what past jobs on similar wells found and how long those fixes lasted, and learns from every job
the crew logs.

## Every number we may quote (all reproducible from this repo)

| Claim | Number | Where |
|---|---|---|
| Repairs repeating within 90 days | 61% of repair jobs | `build_artifacts.py` (overview) |
| Lost oil from rod, rodstring, pump, tubing codes | about 160,000 m³ (about 1.0M barrels) | downtime codes in daily data |
| Risk model, held-out Jul 2025+ | AUC 0.816; top 5% flagged wells 49.5% needed a repair vs 12.3% base (4.0x) | `scripts/eval_risk.py` |
| Fix-lifetime precedent | error 0.978 vs 1.150 (global median); rank correlation 0.376 vs 0.109 (well's own history) | `scripts/eval_precedent.py` |
| Sensors to crew notes, 2026 hold-out | lift +0.067 (CI 0.062 to 0.073); other fields only +0.070 (0.064 to 0.075); component AUC 0.76 / 0.76 / 0.69 | `scripts/eval_crossmodal.py` |
| Weibull shape of repair lifetimes | k = 0.61 (CI 0.60 to 0.62) | `wellsimple/reliability.py` |
| Early vs late repeat risk (rod truck) | 3.0% per day in week 1 vs 0.28% per day at 6 to 12 months | overview hazard chart |
| Expected 30-day exposure | $2.1M (conservative) to $2.8M (mid), as of 2026-10-27 | `scoring.py` |

Never quote a saving as measured. The exposure is what is at risk; the share that is avoidable is a
scenario (10% of exposure is about $2.6M to $3.5M a year if exposure persists) that needs a field trial.

## 10-minute finalist talk

1. **The problem (1:00).** Heavy oil wells, every one on a pump. 61% of repairs repeat within 90 days.
   About a million barrels lost to equipment downtime. Open with the repeat number.
2. **What we noticed (1:30).** The reliability slide: risk is highest right after a fix (k = 0.61).
   Say plainly why this matters: scheduled replacement would not pay; repair quality would. Most
   predictive maintenance pitches assume wear-out. The data says otherwise.
3. **Live demo, manager (2:00).** Ranked wells by expected loss, switch to closest-first, open a well,
   show reasons and precedent, assign it to Crew 1.
4. **Live demo, crew on a phone (2:00).** Open the assignment, map with well and own position, "what the
   system knows", log the job in three taps, submit. Back on the manager screen: resolved.
5. **How it works (1:30).** Three parts: risk model, Well Memory (retrieval over crew notes, no
   generative model), sensors-to-notes model. One slide of test results with held-out numbers.
6. **Money and honesty (1:00).** Exposure range and the assumptions. Then limitations: the 22-month
   failure log, moderate cross-modal accuracy, planned work in the label.
7. **Next steps (0:30).** Follow-up "did the fix hold?" prompts, Canary Historian live feed, trial on
   one field.

## 5-minute video (same arc, tighter)

Cold open on the repeat number (0:20). Reliability finding (0:50). Manager demo (1:00). Crew phone demo
(1:00). Method and validation in one slide (1:00). Money, limitations, next steps (0:50). Record the
demo screens, not slides, for minutes 2 to 4. State AI use in the last 10 seconds.

## Likely questions and honest answers

- **Is 0.816 AUC just predicting planned jobs?** Partly possible: the label is any repair job in the
  next 30 days, which includes scheduled pump changes. Sensors still add on top of history (0.758 to
  0.816), and we present it as "likely to need work", not "will fail".
- **How do you know the notes model isn't learning field writing style?** We tested it: restricting
  retrieval to notes from other fields gives the same lift (+0.070 vs +0.067).
- **Why not a language model?** No generative model creates or extracts anything shown. Every note is a
  real past note, so there is nothing to hallucinate and operators can check the source. We also tested
  neural embeddings and they did slightly worse than TF-IDF on this task.
- **Is the early hazard just follow-up visits?** Some of it may be. The next job can be a planned return
  trip. Tell them we flag this caveat on the slide, and that separating planned from unplanned follow-ups
  is the first refinement.
- **Where does the dollar figure come from?** Job cost from the data's field estimates, lost oil per repair
  event measured from downtime codes, oil valued at $32.50 or $61.60 a barrel from Strathcona's Q3 2026
  release. It is exposure, not a measured saving.
- **Only 22 months of failures?** Yes, the failure log is almost entirely 2025 to 2026. Component labels use
  that window; repair outcomes use the full job log.
- **Does it scale / is it commercial?** The scoring is a batch job over daily data, the app is a small
  FastAPI service, and the data layer reads parquet today, and a Databricks (Delta table) version is planned but not built yet. There is no
  login yet; a real deployment would add single sign-on and field-by-field rollout.
- **Why trust crew-submitted notes?** The loop adds them to memory but does not retrain the risk model;
  planned next step is a 30 and 90 day "did it hold?" prompt to label outcomes.

## Rubric map

- **Research depth and domain (25%)**: Weibull shape and the age-replacement result, PCP and rod-string
  context, hazard by time since repair, cost Pareto by crew job type.
- **Technical correctness (25%)**: time-ordered splits, leakage-sensitive tests, parameter-recovery test for
  the Weibull fit, field-exclusion test, 25 unit tests, honest negative result (MiniLM).
- **Insight and business impact (20%)**: ranked by expected dollars, priority modes, exposure range with
  assumptions, limits stated.
- **Presentation (15%)**: one arc, live demo on a phone.
- **Creativity (15%)**: sensors that retrieve real crew notes, closed loop from crew to memory, the finding
  that challenges the usual predictive-maintenance assumption.

## Before presenting

- Run the app from a fresh clone using the README steps at least once.
- Practise the demo with the network off for the offline-queue moment, and have screenshots as a backup.
- Rehearse to 9:30. Do not read slides.
