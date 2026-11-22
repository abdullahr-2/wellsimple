# WellSimple presentation script

**Uzair** · Data analyst  **Abdullah** · Computer scientist and software engineer  **Hassaan** · Electrical engineer

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

*Before presenting, open Manager and Crew in separate tabs. Choose an unassigned well with a historical note and a recorded outcome. During the demo, use that same well throughout. Refresh the crew list after assigning it.*

**Abdullah:** Here’s the manager’s morning view. I’ll open **At-risk wells**. This list combines the chance of a repair in the next thirty days with what that repair and its lost production could cost. I’ll select this well, show what pushed it up the list, and assign it to Crew 1. Hassaan, here’s what comes through on your side.

**Hassaan:** I can see our well, its location, and notes from earlier jobs with similar patterns. *Open the assignment. Point to one short phrase in a historical note and read it aloud.* That’s something another crew actually observed. I’d take that detail into the inspection and check whether it applies here.

**Finalist · Hassaan:** There are two useful questions on this screen. What did crews find when the sensors looked like this? And when crews described a similar repair, how long was it before the next visit? *Point to the component estimate, then the days-to-next-job figure for a precedent.* The first helps me decide what to look at. The second tells me what follow-up question to ask. A short interval would make me look up why the crew returned.

**Abdullah:** *Select a work category, enter “Demo inspection completed” and submit. Switch to Manager, refresh, and open Resolved.* There’s the same well and the note Hassaan just submitted. The manager can see what happened, and the next crew can retrieve that note.

**Finalist · Abdullah:** The work that reads millions of daily records runs in a batch before the shift. Opening a well loads its prepared scores and cases. The phone handles a much smaller job. It records the crew’s findings and can queue a submission when the connection drops. For a field rollout, we’d start with one operating area, connect company sign-in, and agree with its supervisor on who reviews repeat visits.

## 4. Evidence for the judging rubric

### 4a. Research depth and domain expertise · 25%

*Show the rod-truck return rate in the first week and at six to twelve months. Label the vertical axis “Daily chance of another repair.”*

**Hassaan:** A surface motor turns a rod string that drives the pump downhole. Speed and torque tell you how that system is running, but you still need an inspection to identify the damaged part. What surprised us was the timing. After a rod-truck job, the daily chance of another repair was about three percent in week one. Six to twelve months later it was about zero point three percent. That made the first week after a repair a sensible time to review the crew’s findings.

**Finalist · Hassaan:** We checked that pattern with a reliability model called a Weibull fit. A well repaired near the end of the dataset might go only a few days before our records stop. The fit uses those observed days and leaves the remaining lifetime unknown. Its shape estimate was zero point six one. Below one, the rate of return visits falls with time. That describes the service history. To judge the quality of an individual repair, we’d still need to know whether the second visit was a planned follow-up or a new failure.

### 4b. Technical implementation and correctness · 25%

*Show two groups of 100 dots. Highlight 12 in the overall group and 50 in the highest-risk group. Label both “Repair recorded within 30 days.”*

**Uzair:** We tested the ranking by moving forward in time. We trained on earlier records, left a thirty-day gap, then scored weekly well observations from July 2025 onward. Across the test set, about twelve in a hundred observations were followed by a repair within thirty days. Among the five percent our model ranked highest, it was about fifty in a hundred. That’s four times the overall rate. A flag means “review this well.” The outcome includes scheduled work.

**Finalist · Uzair:** We also tested whether the sensors earned their place. Using repair history alone gave a ranking score, called AUC, of zero point seven six. Adding sensors raised it to zero point eight two. We then tested a different question on 2026 jobs. Could earlier repairs on other wells tell us how long a fix might last? Retrieving jobs with similar notes beat using the same median lifetime for every repair. Excluding the well itself matters. Otherwise a familiar well name or a repeated description could make retrieval look better than it is.

### 4c. Insight and business impact · 20%

*Show “$13.9M per year” labeled “Field-estimated cost of jobs within 30 days of a prior repair.” Reveal the 10% scenario only after explaining the base.*

**Uzair:** Those thirty-day repeat jobs accounted for about thirteen point nine million dollars a year in field-estimated repair spend. If better preparation prevented ten percent of that spend, it would be worth about one point four million dollars a year before implementation costs. Ten percent is an assumption. Some follow-up work is necessary, and we have yet to measure how much the software could prevent.

**Finalist · Uzair:** We looked for evidence that simply dispatching faster would help. In about ninety-four percent of recorded failures, a repair job was already dated on or before the failure date. That left little support for claiming a large dispatch saving. We also checked whether we should recommend switching pump brands. The apparent advantage changed when we compared brands within the same well. On this evidence, we’d spend the pilot budget on helping crews prepare for repeat visits before asking procurement to change suppliers.

### 4d. Creativity and innovation · 15%

*Show a sensor trend beside one actual retrieved note. Keep the text large enough to read.*

**Abdullah:** A crew can search Well Memory even before anyone has written a description of today’s problem. The model uses the sensor pattern to find earlier notes worth reading. Each result is a crew’s own account. That lets Hassaan challenge a match, open another case, or recognize a detail that a dashboard score alone would never tell him.

**Finalist · Abdullah:** We checked that the tool was doing more than recognizing a field’s writing style. On held-out failures, it still retrieved more relevant notes than random selection when we excluded the entire field. We also tried a neural text encoder. The simpler word-based method did better on the repair-lifetime ranking, so that’s the version in the application.

### 4e. Presentation and communication · 15% · Pilot and close

*Return to the same well in Resolved, then open A/B pilot. Let the audience see the two group sizes. Finish on the logo.*

**Finalist · Uzair:** We checked whether the pilot could detect a change at this scale. With about a hundred and eighty-four wells per group, simulations detected a fifty percent reduction about ninety-six percent of the time. They detected a twenty percent reduction only about twenty-two percent of the time. A modest improvement would take more wells or longer follow-up to establish.

**Hassaan:** We started with a crew going back to the same well. You’ve seen what we can put in their hands before that visit. The next question is whether it changes how often they have to go back. Our prototype assigned 370 historical wells to two pilot groups, 186 for WellSimple and 184 for usual practice. We’re asking for a twelve-month field pilot. Count repeat repairs per well in both groups, then let that result guide the rollout. Thank you.

---

**Rehearsal notes.** Abdullah drives both screens while Hassaan speaks. Use a pre-captured walkthrough of the same assignment if the live demo stalls. Panels, stage cues and rubric labels stay unspoken. Keep the remaining finalist time for transitions before the separate three-minute Q&A.

**Evidence and credits.** The project [README](../README.md) records the results and limitations. The [risk evaluation](../scripts/eval_risk.py), [repair-note evaluation](../scripts/eval_precedent.py), [sensor-to-note evaluation](../scripts/eval_crossmodal.py), and [pilot builder](../scripts/build_pilot.py) document the methods. Include the repository’s AI-use disclosure in the submission credits and credit Codex for assistance drafting this script.
