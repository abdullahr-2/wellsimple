# Domain notes: progressing cavity pumps in heavy oil

How WellSimple connects to the engineering of the wells in this dataset, what we tested, and what held.
Every number here is produced by a script in `scripts/` (named in brackets).

## 1. The equipment

Heavy oil is too viscous to flow to surface on its own, so every producing well in this dataset is on
artificial lift (Dataset Handbook). The lift is a **progressing cavity pump (PCP)**: a steel rotor turns
inside a rubber (elastomer) stator downhole, driven from a surface drive head through a **rod string**. The
fluid moves up in sealed cavities between rotor and stator. Three consequences matter for everything below.

- **It is a positive-displacement pump.** At a given speed it should move a fixed volume:
  `Q_theoretical = displacement (m3/d at 100 RPM) x RPM / 100`.
- **Volumetric efficiency** is `eta = Q_actual / Q_theoretical`. The shortfall is **slip**: fluid leaking back
  across the rotor-stator seal lines. Slip grows as the stator wears or as the pressure the pump works against rises.
- **Torque comes from pressure, friction and viscosity.** An energy balance (hydraulic power = flow x pressure =
  torque x angular speed) gives the hydraulic torque `T_hyd = (volume per revolution) x dP / (2 pi)`. On top of
  that sit friction (sand, a swollen or tight elastomer) and viscous drag, which is large in heavy oil. Because
  the rods turn the pump, the rod string's load is mainly twisting (torsion), and it goes through one load cycle
  per revolution.

## 2. Does the data obey the physics? Yes [eval_physics.py, part A]

Recomputing efficiency as actual liquid / (displacement x RPM / 100) matches the recorded `pump_efficiency_pct`
within 0.02 on **72%** of 1.66 million producing well-days (within 0.10 on 78%). So the efficiency column is the
pump's volumetric efficiency and can be reasoned about as such. We also found the raw file repeats 58 well-days on
2 wells; they are removed in cleaning.

## 3. Features built from the physics [wellsimple/physics.py]

| Feature | Physical meaning |
|---|---|
| Efficiency drop rate | slip increasing: stator wear, or rising pressure |
| Speed variability (30-day) | unstable drive or frequent operator changes |
| Torque spikes (7-day max / 30-day median) | intermittent friction: solids slugs, sticking |
| Torque per unit displacement | torque normalised for pump size: a proxy for pressure plus friction |
| Revolutions since last repair | load cycles on pump and rods |
| Fatigue index | revolutions weighted by (relative torque)^3 since the last repair, the Miner's-rule idea that fatigue damage adds up per cycle, weighted by stress to a power (the exponent 3 is an assumption) |

**Do they help the risk model?** A little, and the gain is real: AUC +0.0022 (95% CI +0.0006 to +0.0037, resampling
wells). Most of it comes from the fatigue index, which works as an overall wear clock [eval_physics.py, part B].

## 4. Would a production engineer's reading of the sensors match what crews found? Partly [eval_physics.py, part C]

For each mechanism an engineer would infer from a sensor signature in the month before a repair, we checked
whether the crew's note for that repair mentions the matching finding more often. Keyword patterns were fixed
before looking at results. 13,462 repair jobs with notes, 2021 to 2026.

| Mechanism | Sensor signature | Note mentions it (signature vs none) | Ratio (95% CI) | Verdict |
|---|---|---|---|---|
| Gas interference | high casing pressure + low efficiency | 3.7% vs 1.0% | 3.58 (2.08 to 6.15) | **Confirmed** |
| Stator wear / slip | efficiency falling at steady speed | 69.1% vs 64.5% | 1.07 (1.01 to 1.13) | Weakly confirmed |
| Sand / solids | torque spikes or rising torque for pump size | 23.1% vs 29.1% | 0.79 (0.73 to 0.87) | Not confirmed |
| Rod fatigue / overload | high fatigue index | 65.9% vs 74.9% | 0.88 (0.85 to 0.91) | Not confirmed |
| Dry running / pump-off | very low efficiency at normal speed | 30.5% vs 48.7% | 0.63 (0.56 to 0.70) | Not confirmed |

What this means: the textbook signatures are only partly reliable in this fleet, so the product shows sensor
reasons as "unusual signals", not causes. Two cautions on the unconfirmed rows: crew notes are free text, so a
keyword miss is not proof the mechanism was absent (for example "hot" also matches hot-oiling, a routine paraffin
treatment); and sand is common in these wells (it appears in 29% of notes without any signature).

**Are rod breaks early failures?** We tested it rather than assume it [part D]. No: 35% of rod-break jobs come within
30 days of the previous repair, the same as all repair jobs (34%), and break jobs had more revolutions since the last
repair (median 15.2M vs 11.0M).

## 5. Reliability: risk is highest right after a repair [wellsimple/reliability.py]

A Weibull model of the time between repairs (right-censored at the end of the data) gives shape **k = 0.61**
(95% CI 0.60 to 0.62). Below 1 means the hazard falls with time since the fix: rod-truck jobs are about 10 times
likelier to need another visit in the first week (3.0% per day) than 6 to 12 months later (0.28% per day).

**Is it real, or just bad wells failing first?** Mixing wells that fail constantly with wells that rarely fail can
make a whole fleet look like "risk falls with time", because the bad wells drop out early. We checked
[eval_reliability.py]: within groups of similarly repair-prone wells the shape stays below 1 (0.62, 0.66, 0.71 and 0.79
for wells with 1 to 3, 4 to 8, 9 to 20 and 21+ repairs), and comparing each well only with itself gives k = 0.71 (95% CI
0.70 to 0.73). So the early-failure effect is real; mixing wells only makes it look somewhat stronger (0.61). The likely
causes are the ones a field crew would name: the root cause not being fixed (rods replaced but the sand or the pump size
was the problem), installation problems (connections, damaged rods, rotor spacing, starting dry) and new parts settling
in. The chronic wells (21+ repairs) are closest to constant risk, which points to the well itself needing a redesign.

The engineering consequence: the classic age-replacement policy (Barlow and Proschan) only pays when the hazard
rises with age (k > 1). Here, replacing equipment that is still running would put it back into the riskiest period,
so the money is in making each repair last, and in watching wells closely in the first weeks after a repair
(scheduled inspection, not scheduled replacement). This matches published practice: the
root-cause failure analysis program described in IPTC 17230 (Chad) aimed its Extended Run Life Team at short runs
under 90 days and repeat failures within 365 days, and reported PCP failure frequency falling from 0.47 to 0.21
between 2007 and 2013 (uncontrolled before/after, not peer reviewed) [ref 1].

Repeats are concentrated: the worst 10% of wells take **35%** of all repair jobs (34% of rod-truck jobs).

## 6. What the operating literature says (sources we could read)

- "A major variable in the life of a progressing cavity pump is the knowledge of those choosing and operating
  pumps" (JPT, 2022) [ref 2]. That is the case for putting past crew knowledge in front of the next crew.
- Root-cause failure analysis with weekly failure reviews, targeted at short runs and repeats, is the closest
  published analogue to WellSimple's loop [ref 1].

We could not read the SPE PetroWiki PCP pages (login required). A teammate with an SPE login should add citations
for the torque and volumetric-efficiency relations above from "PCP sizing practices", "Elastomers for PCP systems"
and "Rod and tubing design for PCP systems", which the Dataset Handbook lists as resources.

## 7. Path to deployment

- **Who uses it.** Production engineers and foremen use the manager portal each morning to pick and assign wells;
  rod-truck and service-rig crews use the crew portal on site.
- **Where it sits in the workflow.** Daily: historian data lands (Canary Historian or a Databricks table), scoring
  runs as a batch job (about 2 minutes for 1,336 wells on a laptop), and the morning list is ready. On site: the
  crew sees likely findings and past fixes, then logs the job. Nightly: new notes enter Well Memory. Monthly:
  retrain the risk model.
- **Rollout.** (1) Shadow mode on one field for about a month: scores shown, no change to dispatch, to check
  usefulness with the engineers. (2) The A/B pilot already enrolled: 369 wells, 186 system and 183 control, read at
  12 months. (3) Fleet rollout if the pilot shows a reduction.
- **What it takes.** A data engineer part-time to connect the historian and job log feeds, a production engineer
  as champion, company sign-on for the portals, and phones or tablets for crews. Costs were not estimated.
- **Vector store.** Crew notes live in a vector database (Chroma, embedded and saved to disk). It matches exact search
  on 99.8% of real queries. At production scale the same interface would sit on Databricks Vector Search or Postgres with
  pgvector so several servers share one store; exact search stays fast to millions of notes, so an approximate index is
  only worth it far beyond Strathcona's volume, and only after a recall check.
- **Scaling and new fields.** Scoring and retraining take minutes on a laptop. A field the model never saw loses
  only 0.01 to 0.02 AUC (Cactus Lake 0.703 vs 0.725, Winter 0.771 vs 0.782, Druid Main 0.748 vs 0.755, Court 0.790
  vs 0.797), so a new field can start from the fleet model. Wells with only 1 to 2 past repairs still score AUC 0.763.

## References

1. Wilson, A. (2014). Applying Root-Cause Failure Analysis Enhances Artificial-Lift Performance. *Journal of
   Petroleum Technology*, summarising Lapi, Johnson and Arisman, IPTC 17230 (2014).
   https://jpt.spe.org/applying-root-cause-failure-analysis-enhances-artificial-lift-performance
2. Rassenfoss, S. (2022). When It Comes to Progressing Cavity Pumps, Staying Loose and Running Slow Can Be Life
   Extending. *Journal of Petroleum Technology*.
   https://jpt.spe.org/when-it-comes-to-progressing-cavity-pumps-staying-loose-and-running-slow-can-be-life-extending
3. Strathcona Resources, Q3 2026 results release (price and cost assumptions).
4. Barlow, R. and Proschan, F. *Mathematical Theory of Reliability* (age-replacement policy).
