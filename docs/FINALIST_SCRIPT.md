# WellSimple finalist talk: extra material

The ten-minute finalist talk uses the demo-video script (docs/PRESENTATION_SCRIPT.md) plus these paragraphs,
moved here unchanged so the video script stays focused on the demo. Each is listed under the video section it
extends.

## 2. About our project

**Finalist · Uzair:** We linked daily operating records, maintenance jobs and failure reports by well and date. Those records answer different questions. A sensor tells us when the well behaved differently. A job tells us when someone went out. A crew note can tell us what they saw after pulling the equipment. The job log spans almost six years, but nearly all the labeled failures fall in the final twenty-two months. We used the longer history to study return visits and the shorter history to learn what crews found.

## 3. Project workflow

**Finalist · Hassaan:** There are two useful questions on this screen. What did crews find when the sensors looked like this? And when crews described a similar repair, how long was it before the next visit? *Point to the component estimate, then the days-to-next-job figure for a precedent.* The first helps me decide what to look at. The second tells me what follow-up question to ask. A short interval would make me look up why the crew returned.

**Finalist · Abdullah:** The work that reads millions of daily records runs as a Databricks job before the shift. The raw files land in Delta tables, the scoring runs on serverless compute, and every repair note is indexed in Databricks Vector Search. Each run refreshes the tables this app reads, so there is no manual export. Opening a well loads its prepared scores and cases. The phone handles a much smaller job. It records the crew’s findings and can queue a submission when the connection drops. For a field rollout, we’d start with one operating area, connect company sign-in, and agree with its supervisor on who reviews repeat visits. One command reruns every test and every number in this talk.

## 4a. Research depth and domain expertise · 25%

**Finalist · Hassaan:** The physics check is simple. Recorded pump efficiency matched actual flow divided by the pump’s rated flow on about seventy-two percent of well-days, within two points. Not every textbook signal held up: torque spikes, for example, did not predict crews finding sand. So the app shows those readings as signals, not causes. We checked the timing pattern with a reliability model called a Weibull fit. A well repaired near the end of the dataset might go only a few days before our records stop. The fit uses those observed days and leaves the remaining lifetime unknown. Its shape estimate was zero point six one. Below one, the rate of return visits falls with time. Is that just bad wells failing first? Comparing each well only with itself, the shape was still zero point seven one. To judge an individual repair, we’d still need to know whether the second visit was a planned follow-up or a new failure.

## 4b. Technical implementation and correctness · 25%

**Finalist · Uzair:** We also tested whether the sensors earned their place. Using repair history alone gave a ranking score, called AUC, of zero point seven six. Adding sensors raised it to zero point eight two, against zero point seven two for each well’s own history and zero point six eight for its field’s average. It is also calibrated: when it says forty percent, about forty percent of those wells need a repair. Trained without a field, it loses only one or two points on that field, so a new area can start from this model. We then tested a different question on 2026 jobs. Could earlier repairs on other wells tell us how long a fix might last? The crew’s note predicted it better than the sensors did, so sensors tell us when, and crew notes tell us how long. Excluding the well itself matters. Otherwise a familiar well name or a repeated description could make retrieval look better than it is.

## 4c. Insight and business impact · 20%

**Finalist · Uzair:** We looked for evidence that simply dispatching faster would help. In about ninety-four percent of recorded failures, a repair job was already dated on or before the failure date. That left little support for claiming a large dispatch saving. We also checked whether we should recommend switching pump brands. The apparent advantage changed when we compared brands within the same well. On this evidence, we’d spend the pilot budget on helping crews prepare for repeat visits before asking procurement to change suppliers.

## 4d. Creativity and innovation · 15%

**Finalist · Abdullah:** We checked that the tool was doing more than recognizing a field’s writing style. On held-out failures, it still retrieved more relevant notes than random selection when we excluded the entire field. We also tried a neural text encoder. The simpler word-based method did better on the repair-lifetime ranking, so that’s the version in the application. On Databricks the same notes sit in Vector Search, and it returned the same top ten as an exact search on ninety-nine percent of real queries.

## 4e. Presentation and communication · 15% · Pilot and close

**Finalist · Uzair:** We checked whether the pilot could detect a change at this scale. With about a hundred and eighty-three wells per group, simulations detected a fifty percent reduction about ninety-six percent of the time. They detected a twenty percent reduction only about twenty-four percent of the time. A modest improvement would take more wells or longer follow-up to establish. Before trusting that test, we ran it on real history with no intervention. It wrongly reported a difference only four percent of the time, which is what a sound test should do.
