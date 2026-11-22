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
| Repairs repeating within 90 days | 61% of repair jobs (rod truck + workover) follow another repair on the same well within 90 days. If quoting rod truck only, it is 59.4%: say which | `build_artifacts.py` (overview) |
| Concentration | the worst 10% of wells take 35% of all repair jobs (34% of rod-truck jobs) | overview chart |
| Lost oil from rod, rodstring, pump, tubing codes | about 160,000 m³ (about 1.0M barrels) | downtime codes in daily data |
| Risk model, held-out Jul 2025+ | AUC 0.818 (95% CI 0.808 to 0.826) vs 0.716 well history, 0.678 field average; top 5% flagged: 48.6% needed a repair vs 12.3% base; calibrated (says 42%, 43% happen) | `evaluation.py`, portal "Can you trust the risk score?" |
| Unseen field | trained without a field, AUC drops only 0.01 to 0.02 | `evaluation.py` |
| Fix lifetime (survival) | concordance 0.693 from the crew note vs 0.584 sensors, 0.575 field, 0.566 well history; predicted 23/38/55/98/224 days vs actual 20/31/55/83/226 | `scripts/eval_precedent.py` |
| PCP physics check | recorded efficiency = actual / (displacement x RPM): 72% of well-days within 0.02; physics features add AUC +0.0022 (CI +0.0006 to +0.0037) | `scripts/eval_physics.py` |
| Engineer's reading vs crew findings | gas interference signature confirmed 3.6x (CI 2.1 to 6.2); stator wear 1.07x; sand, rod fatigue, dry running not confirmed | `scripts/eval_physics.py`, docs/DOMAIN.md |
| Sensors to crew notes, 2026 hold-out | lift +0.067 (CI 0.062 to 0.073); other fields only +0.070 (0.064 to 0.075); component AUC 0.76 / 0.76 / 0.69 | `scripts/eval_crossmodal.py` |
| Weibull shape of repair lifetimes | k = 0.61 (CI 0.60 to 0.62) | `wellsimple/reliability.py` |
| Early vs late repeat risk (rod truck) | 3.0% per day in week 1 vs 0.28% per day at 6 to 12 months | overview hazard chart |
| Expected 30-day exposure (modelled) | $3.8M (conservative) to $4.6M (mid), as of 2026-10-27; about $3.0M of it is job cost, $0.8M to $1.6M is lost oil | `scoring.py` |
| Repair spend within 30 days of a previous repair (measured) | 34% of repair jobs, about $13.9M a year (38% of repair spend) | `reliability.repeat_spend` |
| Repair spend within 90 days of a previous repair (measured) | 60% of repair jobs, about $20.1M a year (55% of repair spend) | `reliability.repeat_spend` |

**We do not claim a measured saving, and that is a strength. We built the experiment that measures it.** We tested where a saving could come from
(`scripts/eval_savings_levers.py`): dispatch order has nothing to save (93.7% of failures are repaired the
same day), the cheap rod fix already has the lowest cost per day of life, and pump-make differences appear
between wells but not reliably within a well. The honest deliverable is the implementation plan: a
12-month pilot on 100 to 150 repeat-prone wells per arm detects a 50% cut in repeats about 76% to 92% of the
time (`scripts/trial_power.py`); each 10% of the $13.9M a year repeat pool is about $1.4M a year.

Never quote a saving as measured. Exposure is mostly spend the company incurs anyway, so do not call
it money to be made. The measured pool is the repeat-repair spend (about $13.9M a year within 30 days):
it is a ceiling, not a saving. Say "if better repairs removed 10% of it, that is about $1.4M a year" as
an illustration, and that a field trial would measure the real figure.

## The sentence to use for the money claim

"Based on Strathcona's own data and our pilot design, better repairs could potentially save between about
$1.7M and $9.1M a year, depending on how many repeat repairs they prevent. The measured pool behind that is
$13.9M a year of repair spend plus about $2.6M of lost oil. The A/B pilot is built to measure the real number."

Keep the word "potentially" and the "depending on" clause. Do not say "will save" or give a single figure.

## 10-minute finalist talk (about 9:30, leaves a buffer)

1. **The problem (1:00).** Heavy oil wells, every one on a progressing cavity pump. 61% of repairs come within
   90 days of another repair on the same well, and the worst 10% of wells take 35% of all repair jobs (show the
   concentration chart). About $13.9M a year of repair spend lands within 30 days of a previous repair.
2. **The engineering (1:30).** One slide of PCP physics: efficiency = actual / (displacement x RPM), torque
   scales with pressure, friction and viscosity, rods fail in torsion. We checked the data obeys it (72% within
   0.02), then checked an engineer's reading of the sensors against 13,462 crew notes: gas interference confirmed,
   stator wear weakly, sand and rod fatigue not. Then the reliability finding: risk is highest right after a fix
   (k = 0.61), so scheduled replacement would not pay and repair quality would.
3. **Live demo, manager (1:45).** "Act on these 10 first", open a well (reasons, likely component, how long
   similar fixes lasted), assign it to Crew 1.
4. **Live demo, crew on a phone (1:45).** Map with well and own position, what the system knows, log the job in
   three taps with dictation, submit. Back on the manager screen: resolved.
5. **Why trust it (1:15).** The "Can you trust the risk score?" panel: 0.818 vs 0.716 and 0.678 baselines,
   calibration on the line, unseen fields barely lose accuracy. Each data source wins its own question: sensors
   say when, crew notes say how long. No generative model, so nothing is made up.
6. **Money and the pilot (1:15).** Could potentially save about $1.7M to $9.1M a year, depending on how many
   repeat repairs are prevented. The A/B pilot (369 wells, 186 system and 183 control) is enrolled and reads out
   at 12 months; the test was validated on real history (4% false positives with no intervention).
7. **Deployment and next steps (0:30).** Morning list for production engineers, crew portal on site, shadow
   mode on one field, then the pilot. Limits in one line: 22-month failure log, planned work in the label.

## 5-minute video (same arc, tighter)

Cold open on the repeat number (0:20). Reliability finding (0:50). Manager demo (1:00). Crew phone demo
(1:00). Method and validation in one slide (1:00). Money, limitations, next steps (0:50). Record the
demo screens, not slides, for minutes 2 to 4. State AI use in the last 10 seconds.

## Likely questions and honest answers

- **Is 0.818 AUC just predicting planned jobs?** Partly possible: the label is any repair job in the
  next 30 days, which includes scheduled pump changes. Sensors still add on top of history (0.758 to
  0.818), and we present it as "likely to need work", not "will fail".
- **How do you know the notes model isn't learning field writing style?** We tested it: restricting
  retrieval to notes from other fields gives the same lift (+0.070 vs +0.067).
- **Why not a language model?** No generative model creates or extracts anything shown. Every note is a
  real past note, so there is nothing to hallucinate and operators can check the source. We also tested
  neural embeddings and they did slightly worse than TF-IDF on this task.
- **Is the early hazard just follow-up visits?** Some of it may be. The next job can be a planned return
  trip. Tell them we flag this caveat on the slide, and that separating planned from unplanned follow-ups
  is the first refinement.
- **Why not just simulate the trial?** A simulated outcome would be made-up data presented as a result. We
  only simulate to size the trial and to validate the test (A/A check on real history), and we say so.
- **Did you use outside data? Is there any "after" evidence?** No external dataset in any model. Data from our
  system cannot exist yet. The closest published before/after is a PCP root-cause failure program in Chad
  (IPTC 17230, not peer reviewed): failure frequency fell from 0.47 to 0.21, about 55%, between 2007 and 2013.
  It targeted short runs and repeat failures, the same problem we target, but it is uncontrolled, a different
  setting and a physical teardown program. We cite it as evidence the approach can work and to size the pilot,
  not as our saving. Disclosed in the README.
- **So what will it save?** We can't measure that from history because nothing in the data is an
  intervention. We tested three levers and report what held and what did not. The measured pool is $13.9M a
  year of repeat-repair spend; each 10% prevented is about $1.4M a year. A 12-month pilot on 100 to 150
  repeat-prone wells per arm would measure a 50% reduction with 76% to 92% power; smaller effects need a longer
  trial. That plan is the deliverable.
- **Where does the dollar figure come from?** Average repair cost ($17,461, capped at the 99th percentile)
  from the data's field estimates, lost oil per repair event measured from downtime codes, oil valued at
  $32.50 or $61.60 a barrel from Strathcona's Q3 2026 release. Only the oil part depends on price. It is
  exposure, mostly spend that happens anyway, not a measured saving. The measured number is the repeat-repair
  spend.
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
