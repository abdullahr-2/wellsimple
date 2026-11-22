# WellSimple presentation script

**Uzair** · Data scientist  **Abdullah** · Computer scientist and software engineer  **Hassaan** · Electrical engineer

For the **five-minute video**, read the named speaker lines and follow the italicized screen cues. For the **ten-minute finalist talk**, also read the paragraphs marked **Finalist**. Elapsed times below are rehearsal targets. Allow the audience a moment to read the screen during the demo.

| Section | Video | Finalist talk |
|---|---|---|
| 1. Project title | 0:00–0:20 | 0:00–0:25 |
| 2. About our project | 0:20–0:55 | 0:25–1:25 |
| 3. Project workflow and demo | 0:55–2:10 | 1:25–3:55 |
| 4a. Why wells get a second visit | 2:10–2:45 | 3:55–5:10 |
| 4b. How well the system predicts repairs | 2:45–3:25 | 5:10–6:40 |
| 4c. What a repeat visit costs | 3:25–4:00 | 6:40–7:50 |
| 4d. What the next crew learns | 4:00–4:25 | 7:50–8:35 |
| 4e. The pilot and close | 4:25–4:55 | 8:35–9:35 |

## 1. Project title

*Show the pumpjack logo, “WellSimple,” and the three names.*

**Hassaan:** Imagine you’re sending a crew back to a well they repaired three weeks ago. What would you want them to know before they leave? I’m Hassaan, our electrical engineer. With Uzair, our data analyst, and Abdullah, our software engineer, we built WellSimple around that question.

## 2. About our project

*Show 34% beside a timeline with two repair visits to the same well.*

**Uzair:** In Strathcona’s records, about one in three rod-truck and workover jobs started within thirty days of the previous repair on that well. Some return visits were planned. But every time a crew goes back, someone has to decide what to investigate. The sensor history is in one file. What the last crew actually found is buried in a job summary. WellSimple brings those together so a manager can choose a well and a crew can arrive with a specific question.

**Finalist · Uzair:** We linked daily operating records, maintenance jobs and failure reports by well and date. Those records answer different questions. A sensor tells us when the well behaved differently. A job tells us when someone went out. A crew note can tell us what they saw after pulling the equipment. The job log spans almost six years, but nearly all the labeled failures fall in the final twenty-two months. We used the longer history to study return visits and the shorter history to learn what crews found.

## 3. Project workflow

*Before presenting, open Manager and Crew in separate tabs. Start on the Manager overview so “Act on these 10 first” and the “worst 10% of wells take 35% of repair jobs” chart are visible for a moment. Choose an unassigned well with a historical note and a recorded outcome. During the demo, use that same well throughout. Refresh the crew list after assigning it.*

**Abdullah:** Here’s the manager’s morning view, refreshed by a Databricks pipeline before the shift. I’ll open **At-risk wells**. This list combines the chance of a repair in the next thirty days with what that repair and its lost production could cost. I can rank by money at risk, by risk alone, or by distance from a crew, and switch the oil price between conservative and mid. I’ll select this well, show what pushed it up the list, and assign it to Crew 1. Hassaan, here’s what comes through on your side.

**Hassaan:** I can see our well on a map with my own position and directions, and notes from earlier jobs with similar patterns. *Open the assignment. Point to one short phrase in a historical note and read it aloud.* That’s something another crew actually observed. I’d take that detail into the inspection and check whether it applies here. When I’m done, I log it with a few taps or by voice, and if there’s no signal it waits and sends later.

**Finalist · Hassaan:** There are two useful questions on this screen. What did crews find when the sensors looked like this? And when crews described a similar repair, how long was it before the next visit? *Point to the component estimate, then the days-to-next-job figure for a precedent.* The first helps me decide what to look at. The second tells me what follow-up question to ask. A short interval would make me look up why the crew returned.

**Abdullah:** *Hassaan taps a work category, says “Demo inspection completed” using Dictate (type it if the browser can’t dictate) and submits. Switch to Manager, refresh, and open Resolved.* There’s the same well and the note Hassaan just submitted. The manager can see what happened, and the next crew can retrieve that note.

**Finalist · Abdullah:** The work that reads millions of daily records runs as a Databricks job before the shift. The raw files land in Delta tables, the scoring runs on serverless compute, and every repair note is indexed in Databricks Vector Search. Each run refreshes the tables this app reads, so there is no manual export. Opening a well loads its prepared scores and cases. The phone handles a much smaller job. It records the crew’s findings and can queue a submission when the connection drops. For a field rollout, we’d start with one operating area, connect company sign-in, and agree with its supervisor on who reviews repeat visits. One command reruns every test and every number in this talk.

## 4. Evidence for the judging rubric

### 4a. Research depth and domain expertise · 25%

*Show the rod-truck return rate in the first week and at six to twelve months. Label the vertical axis “Daily chance of another repair.” While Hassaan mentions gas, show “Crews reported gas 3.6× as often.”*

**Hassaan:** A surface motor turns a rod string that drives the pump downhole. We tested an engineer’s reading of the sensors against what crews found: when the readings pointed to gas in the pump, crews reported gas three and a half times as often. After a rod-truck job, the chance of another repair is about ten times higher in week one than six to twelve months later. That flips a common assumption: scheduled replacement wouldn’t pay, because every new install starts in its riskiest weeks. The money is in getting each repair right.

**Finalist · Hassaan:** The physics check is simple. Recorded pump efficiency matched actual flow divided by the pump’s rated flow on about seventy-two percent of well-days, within two points. Not every textbook signal held up: torque spikes, for example, did not predict crews finding sand. So the app shows those readings as signals, not causes. We checked the timing pattern with a reliability model called a Weibull fit. A well repaired near the end of the dataset might go only a few days before our records stop. The fit uses those observed days and leaves the remaining lifetime unknown. Its shape estimate was zero point six one. Below one, the rate of return visits falls with time. Is that just bad wells failing first? Comparing each well only with itself, the shape was still zero point seven one. To judge an individual repair, we’d still need to know whether the second visit was a planned follow-up or a new failure.

### 4b. Technical implementation and correctness · 25%

*Show two groups of 100 dots. Highlight 12 in the overall group and 50 in the highest-risk group. Label both “Repair recorded within 30 days.” Then show the calibration chart from the “Can you trust the risk score?” panel while Uzair explains it.*

**Uzair:** We tested the ranking only on months it had never seen. Overall, about twelve in a hundred well-weeks were followed by a repair within thirty days. Among the five percent our model ranked highest, it was about fifty in a hundred. That’s four times the overall rate, and better than ranking by each well’s own history or by its field’s average. And it’s honest about its own confidence: when it says forty percent, about forty percent of those wells really need a repair. A flag means “review this well.” The outcome includes scheduled work.

**Finalist · Uzair:** We also tested whether the sensors earned their place. Using repair history alone gave a ranking score, called AUC, of zero point seven six. Adding sensors raised it to zero point eight two, against zero point seven two for each well’s own history and zero point six eight for its field’s average. It is also calibrated: when it says forty percent, about forty percent of those wells need a repair. Trained without a field, it loses only one or two points on that field, so a new area can start from this model. We then tested a different question on 2026 jobs. Could earlier repairs on other wells tell us how long a fix might last? The crew’s note predicted it better than the sensors did, so sensors tell us when, and crew notes tell us how long. Excluding the well itself matters. Otherwise a familiar well name or a repeated description could make retrieval look better than it is.

### 4c. Insight and business impact · 20%

*Show “$13.9M per year” labeled “Field-estimated cost of jobs within 30 days of a prior repair,” then “+ $2.6M lost oil.” Show the “worst 10% of wells take 35% of repair jobs” chart, then reveal the $1.7M to $9.1M range only after explaining the base.*

**Uzair:** Those thirty-day repeat jobs cost about thirteen point nine million dollars a year in field-estimated repair spend, plus about two point six million in lost oil. And it’s concentrated: the worst ten percent of wells take a third of all repair jobs. If better preparation prevented ten percent, Strathcona could potentially save about one point seven million a year. At the fifty-five percent a published root-cause program reported, it’s about nine point one million. Those percentages are scenarios, before implementation costs. Measuring the real figure is the pilot’s job.

**Finalist · Uzair:** We looked for evidence that simply dispatching faster would help. In about ninety-four percent of recorded failures, a repair job was already dated on or before the failure date. That left little support for claiming a large dispatch saving. We also checked whether we should recommend switching pump brands. The apparent advantage changed when we compared brands within the same well. On this evidence, we’d spend the pilot budget on helping crews prepare for repeat visits before asking procurement to change suppliers.

### 4d. Creativity and innovation · 15%

*Show a sensor trend beside one actual retrieved note. Keep the text large enough to read.*

**Abdullah:** A crew can search Well Memory even before anyone has written a description of today’s problem. The model uses the sensor pattern to find earlier notes worth reading. Each result is a crew’s own account. That lets Hassaan challenge a match, open another case, or recognize a detail that a dashboard score alone would never tell him.

**Finalist · Abdullah:** We checked that the tool was doing more than recognizing a field’s writing style. On held-out failures, it still retrieved more relevant notes than random selection when we excluded the entire field. We also tried a neural text encoder. The simpler word-based method did better on the repair-lifetime ranking, so that’s the version in the application. On Databricks the same notes sit in Vector Search, and it returned the same top ten as an exact search on ninety-nine percent of real queries.

### 4e. Presentation and communication · 15% · Pilot and close

*Return to the same well in Resolved, then open A/B pilot. Let the audience see the two group sizes. Finish on the logo.*

**Finalist · Uzair:** We checked whether the pilot could detect a change at this scale. With about a hundred and eighty-three wells per group, simulations detected a fifty percent reduction about ninety-six percent of the time. They detected a twenty percent reduction only about twenty-four percent of the time. A modest improvement would take more wells or longer follow-up to establish. Before trusting that test, we ran it on real history with no intervention. It wrongly reported a difference only four percent of the time, which is what a sound test should do.

**Hassaan:** We started with a crew going back to the same well. You’ve seen what we can put in their hands before that visit. The next question is whether it changes how often they have to go back. Our prototype assigned 369 historical wells to two pilot groups, 186 for WellSimple and 183 for usual practice. We’re asking for a twelve-month field pilot. Count repeat repairs per well in both groups, then let that result guide the rollout. Thank you.

---

**Rehearsal notes.** Abdullah drives both screens while Hassaan speaks. Use a pre-captured walkthrough of the same assignment if the live demo stalls. Panels, stage cues and rubric labels stay unspoken. Keep the remaining finalist time for transitions before the separate three-minute Q&A.

**Evidence and credits.** The project [README](../README.md) records the results and limitations, and [DOMAIN.md](DOMAIN.md) and [DATABRICKS.md](DATABRICKS.md) cover the engineering and the Databricks setup. The [risk evaluation](../scripts/eval_risk.py), [physics evaluation](../scripts/eval_physics.py), [reliability evaluation](../scripts/eval_reliability.py), [repair-note evaluation](../scripts/eval_precedent.py), [sensor-to-note evaluation](../scripts/eval_crossmodal.py), and [pilot builder](../scripts/build_pilot.py) document the methods. Include the repository’s AI-use disclosure in the submission credits and credit Codex and Claude Code for assistance drafting and updating this script.
