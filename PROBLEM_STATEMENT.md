# Well Memory: Turning Field Crew Notes into Repair Decisions Worth Millions

**Team:** [Name 1 – Electrical Engineering], [Name 2 – Computer Science / Software Engineering], [Name 3 – Data Science]
**Competition:** DSMLC Canary x Chirality 2026 Datathon – Strathcona Resources case
**Theme:** Optimization (Maintenance and Reliability, Cost and Resources, Monitoring and Decisions)
**Solution form:** Prototype AI/ML application (with a dashboard front end)

## Problem Statement

Strathcona's heavy oil wells need a pump to produce, and the pumps and rod strings fail often. In the competition data, rod, pump and tubing downtime codes account for roughly 160,000 m³ of lost oil, which is about 1.0 million barrels over almost six years. The repair spend logged against those wells is large: field estimates add up to $171.9M for workovers and $40.7M for rod truck jobs.

Repairs often do not last. **59.4% of rod truck jobs happen within 90 days of the previous rod truck job on the same well, and 29.8% within 30 days.** The worst 10% of wells account for 33.8% of all rod truck jobs. The median time to the next job after a rod truck or workover job is 46 days.

When a well fails, the crew writes down what they found. These notes (13,601 job summaries, median 373 characters) describe things like sand fill, broken rotors and tubing scan grades. They are the richest record of what actually went wrong and what was done about it, yet nothing in the structured data captures them. Operators therefore choose a fix from memory, and the company cannot easily see which fixes last longest per dollar.

## Research Question

> **Using retrieval over past crew notes and pre-failure sensor behavior, can we recommend the repair for each well failure that minimizes cost per day of well life, and how much money would that save Strathcona per year?**

This breaks into three measurable parts:

1. **Retrieval accuracy.** For each failure in a held-out period, retrieve only earlier cases and estimate days until the next job. Does that beat a naive baseline (the well's own average, or the field average) on error in days?
2. **Fix ranking.** Across similar cases, which repair types give the lowest cost per day of well life (repair cost plus oil lost, divided by days to the next job)?
3. **Dollar impact.** If each failure had used the best-precedent fix, what is the annual saving in avoided repair spend and recovered oil, with an uncertainty range?

## Motivation

- **Money:** repeat repairs and lost oil are both measurable in this dataset, so the case can be made in dollars, not just accuracy.
- **Real field knowledge:** the crews' own notes are used as evidence, not just numbers.
- **Not just a prediction:** the model's output is a decision (which fix, at what cost) with the evidence attached, which an operator can check against their own judgment.
- **Procurement angle:** the same data shows which pump makes and models are costing the company the most, which is a purchasing decision.

## Approach (summary)

- Embed the crew notes and the sensor behavior in the weeks before each failure, and store both in a vector database.
- No generative model extracts or invents facts. Answers come from retrieving real past cases and computing statistics over them. The embedding model is AI and will be disclosed in the repository.
- Outcome per case: repair cost, days to the next job, and oil lost in between.
- Views built on the same store: precedent lookup for a single failure, pump vendor scorecard, and a well-by-well opportunity map.
- Validation: strictly time-ordered backtest (no future data), with uncertainty shown across the retrieved cases.

## What We Have Verified in the Data

| Check | Result |
|---|---|
| Failures that can be linked to a rod truck or workover job (within 60 days after the failure date) | 98.5% (93.7% on or within 3 days before the failure date) |
| Matched failures with a crew summary / a cost | 99% / 100% |
| Jobs with a following job (so an outcome exists) | 89% |
| Wells with pump make and model recorded | 1,551 of 2,905 (53%) |
| Pump models with at least 20 wells | 55 of 290 |
| Failures on wells with a recorded pump make | 97.9% |
| Failures with 15 or more of the prior 30 days of data: efficiency / RPM / torque / motor current | 91% / 97% / 66% / 50% |

## Known Limitations We Must Design Around

- **The failure log covers only about 22 months.** The handbook gives Dec 2021 to Oct 2026, but 2,871 of 2,873 failures fall in 2025 to 2026 (1,230 in 2025 and 1,641 in 2026). Failure-type labels therefore exist for that window only. The job log spans the full period, so five-year precedent and outcome analysis must use jobs and their text, not the failure table. All time-ordered tests split inside 2025 to 2026 (train before 2026-01-01, test after).
- Pump makes are spelled inconsistently (for example "MANTL" and "Mantl"), so names must be normalized.
- 1,041 of the 1,551 wells with pump data changed pump model over time, so the vendor scorecard must use the dates each pump was installed rather than one model per well.
- Torque and motor current are patchy, so efficiency and RPM carry the sensor signal.
- About 16% of rod truck and workover jobs have a cost of zero or less, so cost needs cleaning and a stated rule.
- Cost is a field estimate. Only one row has an actual final cost.
- "Days to next job" counts the next rod or workover job of any type, and the last job on each well has no outcome (11%).
- Barrel price and netback are assumptions. They will come from Strathcona's published quarterly reports and be clearly labeled.

## Summary of Findings

*To be completed after the build and backtest. Do not fill in numbers until they are produced by the code in this repository.*

## AI Disclosure

*To be completed: embedding model used, any AI coding assistants, and which parts of the code and text they produced.*
