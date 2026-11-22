# WellSimple: Fewer Repeat Repairs on Heavy Oil Wells

**Team:** [Name 1 – Electrical Engineering], [Name 2 – Computer Science / Software Engineering], [Name 3 – Data Science]
**Competition:** DSMLC Canary x Chirality 2026 Datathon – Strathcona Resources case
**Theme:** Optimization (Maintenance and Reliability, Cost and Resources, Monitoring and Decisions)
**Solution form:** Prototype AI/ML application: a manager portal and a mobile crew portal

Every number below is produced by a script in this repository (named in brackets). Dollar figures rest on
stated assumptions. Full results are in the [README](README.md); the engineering is in [docs/DOMAIN.md](docs/DOMAIN.md).

## Problem Statement

Every producing well in this dataset lifts heavy oil with a progressing cavity pump (PCP), turned from surface
through a rod string. Pumps, rods and tubing fail often. Rod, rodstring, pump and tubing downtime codes account for
about 160,000 m³ of lost oil (about 1.0 million barrels) over almost six years, and field cost estimates for repair
jobs run to $171.9M for workovers and $40.7M for rod truck jobs.

**Repairs often do not last.** 61% of repair jobs (rod truck and workover) come within 90 days of another repair on
the same well (59.4% for rod truck jobs alone), and 34% within 30 days. Repair spend that lands within 30 days of a
previous repair is about **$13.9M a year**, plus about $2.6M of lost oil at a conservative oil price [build_artifacts.py].
The work is concentrated: **the worst 10% of wells take 35% of all repair jobs**.

Three kinds of evidence exist but are not used together: daily sensor readings from the pumps, the repair history,
and the crews' own notes on what they found (13,601 job summaries). Managers decide which well to send a crew to from
experience, and crews choose a fix from memory.

## Research Question

> **Can sensor data, repair history and crew notes tell Strathcona which wells will need a repair next, what the
> crew is likely to find, and how long a fix will last, accurately enough to prioritize the work; and what could
> fewer repeat repairs be worth?**

Five measurable parts, all tested on later data than the models learned from:

1. **When:** predict which producing wells need a repair in the next 30 days, against each well's own history and the
   field average.
2. **How long:** predict how long a repair will last, using survival methods so repairs still running are counted.
3. **What:** from sensors alone, predict the failing component and retrieve real notes from wells that behaved
   similarly.
4. **Why it keeps happening:** does the risk of another repair rise with age (wear-out) or peak right after a repair?
   The answer decides whether scheduled replacement or better repairs is the lever.
5. **What it is worth:** measure the repeat-repair pool, test where a saving could come from, and design the
   experiment that measures it.

## Motivation

- **Money:** repeat repairs and the oil lost while wells are down are measurable in this data.
- **Field knowledge:** the crews' notes are used as evidence, and new notes feed back into the system.
- **Decisions, not scores:** a ranked list of wells with reasons, likely findings and how long similar fixes lasted,
  which a production engineer can check against their own judgment.
- **Trust:** no generative model creates or extracts anything shown; every answer comes from real past jobs and
  statistics over them.

## Approach

- **Risk model** [risk.py, physics.py]: weekly snapshots of each producing well with 30-day and 7-day sensor trends,
  repair history and PCP physics features (efficiency drop rate, torque spikes, torque per unit displacement,
  revolutions and a fatigue index since the last repair); gradient-boosted trees.
- **Well Memory** [notes.py]: retrieval over past repair notes with the outcome of each job.
- **Sensors to crew notes** [crossmodal.py]: maps pre-failure sensor behavior to the likely component and to real
  notes from similar wells.
- **Reliability** [reliability.py]: Weibull and Kaplan-Meier survival analysis of the time between repairs.
- **Two portals** [server.py]: a manager portal (top 10 wells to act on, ranked list with priority modes, map,
  assignment, resolved work, model quality, A/B pilot) and a mobile crew portal (assigned wells, map with own
  location, likely findings, quick job log with dictation and offline queueing).
- **A/B pilot** [abtest.py, build_pilot.py]: randomized, pre-registered experiment to measure the saving.

## Summary of Findings

1. **When (risk of a repair in 30 days)** [evaluation.py]: AUC **0.818** (95% CI 0.808 to 0.826), against 0.716 for
   each well's own history and 0.678 for the field average. Of the top 5% flagged wells, 48.6% needed a repair against
   a 12.3% base rate. Well calibrated (when it says 42%, 43% happen). A field the model never saw loses only 0.01 to
   0.02 AUC. Sensors raise it from 0.758 (history alone).
2. **How long (fix lifetime)** [eval_precedent.py]: concordance **0.693** from the crew note (95% CI 0.675 to 0.708),
   against 0.584 from sensors, 0.575 for the field average and 0.566 for the well's own history; predicted
   23 / 38 / 55 / 98 / 224 days against actual 20 / 31 / 55 / 83 / 226. **Sensors answer "when", crew notes answer
   "how long".**
3. **What (likely finding)** [eval_crossmodal.py]: component AUC 0.76 (pump), 0.76 (rods), 0.69 (tubing). Retrieved notes
   are closer to the real note than random ones, also when restricted to other fields (+0.070, CI 0.064 to 0.075).
4. **PCP physics** [eval_physics.py]: recorded efficiency matches actual / (displacement x RPM) on 72% of well-days within
   0.02; physics features add AUC +0.0022 (CI +0.0006 to +0.0037). Against 13,462 crew notes, the gas-interference
   signature is confirmed (3.6x, CI 2.1 to 6.2) and stator wear weakly (1.07x); sand, rod-fatigue and dry-running
   signatures are not, so the portal shows them as signals, not causes.
5. **Why it keeps happening** [eval_reliability.py]: risk is highest right after a repair. Weibull shape **k = 0.61**
   (CI 0.60 to 0.62); rod truck jobs are about 10 times likelier to need another visit in the first week (3.0% per day)
   than at 6 to 12 months (0.28%). This holds **within the same well** (k = 0.71, CI 0.70 to 0.73), so it is not only bad
   wells failing first. Because scheduled replacement adds a new repair and its early risk, it would not pay; the lever
   is getting repairs right, watching wells closely in the first weeks after a repair, and redesigning the chronic wells.
6. **Worth** [eval_savings_levers.py, trial_power.py, build_pilot.py]: savings cannot be measured from history, because
   nothing in it is an intervention. Dispatch order has nothing to re-order (93.7% of failures are repaired the same
   day); the cheap rod fix already has the lowest cost per day of life; pump-make differences seen between wells are
   not confirmed within wells. Better repairs **could potentially save about $1.7M to $9.1M a year**, depending on how
   many repeat repairs they prevent (10% to 55%, the upper end matching a published root-cause program, IPTC 17230).
   The **A/B pilot** that measures it is enrolled: 369 repeat-prone wells, 186 system and 183 control, with a test
   validated on real history (4.0% false positives with no intervention) and 96% power for a 50% cut, read at 12 months.

## Limitations

- The failure log covers about 22 months (2,871 of 2,873 failures are in 2025 to 2026); component labels exist only for
  that window. Repair outcomes use the job log, which spans the full period.
- The risk label is any repair job in the next 30 days, which includes planned work.
- The next job on a well can be a planned follow-up visit, so some early risk is return trips.
- Job costs are field estimates (about 16% are zero or negative and treated as missing); oil prices are assumptions from
  Strathcona's Q3 2026 release ($32.50 and $61.60 per barrel).
- Torque and motor current are missing for a third to a half of pre-failure windows.
- The raw daily file repeats 58 well-days on 2 wells; they are removed in cleaning.
- The pilot arms differ slightly on prior-year repeats (standardized difference -0.13), so the 12-month read should also
  be reported adjusted for baseline repeats.
- The app has no login, and assignments and notes made in it are demo inputs.

## AI Disclosure

- Claude Code (Claude Sonnet 5.5, later Claude Opus 5.5) wrote and reviewed much of the code, tests, analysis scripts
  and documentation under the team's direction. Commits it co-authored carry a `Co-Authored-By` line.
- No generative model creates or extracts content shown in the product. A local sentence-embedding model (MiniLM) was
  evaluated and not used by default. The crew portal's Dictate button uses the browser's own speech recognition.
