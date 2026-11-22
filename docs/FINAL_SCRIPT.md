# WellSimple · Final stage script

**10-minute finalist talk + 3-minute Q&A**

**Hassaan** · Electrical engineer  **Abdullah** · Computer scientist and software engineer  **Uzair** · Data scientist

*Italics* are stage directions (not spoken). **Bold** words are the ones to stress.

## Running order

| Time | Who | Part | Slides |
|---|---|---|---|
| 0:00–1:00 | Hassaan | Problem | Title, Repeat Repairs, Research Question |
| 1:00–1:45 | Abdullah | Solution | Our Solution |
| 1:45–3:00 | Hassaan | Risk and sensors | Data sources, Sensor Data |
| 3:00–4:35 | Uzair | Repairs and crew notes | Repair History, Crew Notes |
| 4:35–5:00 | Abdullah | Why trust it | Dashboard |
| 5:00–7:45 | Abdullah + Hassaan | Guided live demo | Live app |
| 7:45–9:10 | All, Uzair narrates | Judges try the app | Live app |
| 9:10–10:00 | Uzair, then Hassaan | Pilot and close | Pilot |

---

## 1. Problem · Hassaan (0:00–1:00)

*Title slide.*

**Hassaan:** Imagine sending a crew back to a well they fixed three weeks ago. What would you want them to know before they
leave? I'm Hassaan, our electrical engineer. This is Abdullah, our software engineer, and Uzair, our data scientist. We're
WellSimple.

*Repeat Repairs slide (61%).*

**Hassaan:** Every producing well in Strathcona's heavy oil fields runs on a pump, and pumps get repaired often. In their
records, **sixty-one percent** of repair jobs come within **ninety days** of another repair on the same well. Some are
planned, but every visit costs a crew, a truck and lost oil. Today a manager picks who to send from experience, and a crew
picks a fix from memory. The sensor data sits in one system, and what the last crew actually found is buried in a job
summary.

*Research Question slide.*

**Hassaan:** So we asked: how can Strathcona prioritize wells for maintenance, and can that reduce repeat repairs and costs
compared with current practice?

## 2. Solution · Abdullah (1:00–1:45)

*Our Solution slide.*

**Abdullah:** Many tools can tell you which well is at risk. WellSimple also **prepares the crew** for the visit, and
**learns** from every note they send back. It is two connected apps. Managers get a ranked list of which wells to visit
first and what each repair is likely to cost. Crews get a phone app that puts what past crews found in their hands before
they arrive. Behind it are a risk model, a searchable memory of nearly **fourteen thousand** real crew notes, and a
randomized pilot to measure the savings. It all runs on **Databricks**, and nothing in it is AI-generated: every note you'll
see is a real crew's own words. Hassaan will start with where risk comes from.

## 3. Risk and sensors · Hassaan (1:45–3:00)

*Data sources slide.*

**Hassaan:** We use three sources, and each answers a different question. **Sensors** tell us **when** a well needs
attention. **Repair history** is the **strongest** risk signal. **Crew notes** tell us **what** you'll find and **how long**
a fix will last.

*Sensor Data slide.*

**Hassaan:** These wells use progressing cavity pumps: a motor at the surface turns a rod string that drives a pump
downhole. We track nine daily readings as trends, and we added features from the pump's physics, like how fast efficiency is
dropping, and a **fatigue index**: loaded pump revolutions since the last repair. Sensors lift our **gradient-boosted**
model's accuracy from **0.76 to 0.82**, and the top five percent of wells we flag needed a repair **forty-nine percent** of
the time, against twelve percent overall. From sensors alone we can predict the likely failing part. And we didn't take
textbook warning signs on faith. We checked them against what crews actually found. **Gas interference** held up, **three
and a half times**. Others didn't, so the app shows them as signals, not causes.

## 4. Repairs and crew notes · Uzair (3:00–4:35)

*Repair History slide.*

**Uzair:** Repair history is the **strongest** single signal, and the reason **surprised** us. Risk is **highest right after
a fix**: about **ten times** higher in the first week than six to twelve months later. And that holds even comparing each
well **only with itself**, so it isn't just bad wells failing first. That means **scheduled replacement wouldn't pay**,
because every new install starts in its riskiest weeks. The money is in getting each repair **right**.

It also sizes the problem: about **thirteen point nine million dollars a year** goes to repairs within thirty days of a
previous one, and the worst **ten percent** of wells take **thirty-five percent** of the jobs. Combine each well's risk with
an average repair cost of about seventeen and a half thousand dollars plus lost oil, and you get its **expected loss**.
That's what ranks the manager's list.

*Crew Notes slide.*

**Uzair:** Crew notes do something sensors **can't**: they're the **best predictor of how long a repair will last**, 0.69
versus 0.58 from sensors. For every well we show **real past jobs**, what they cost and how long they held. Every note is
stored as a **vector**, so a search finds the closest past jobs in **milliseconds**, and on Databricks that's **Vector
Search**, matching an exact search **ninety-nine percent** of the time. We **tested** a language model and **chose not to
use one**: **nothing is generated**, so every note is a real crew's words. And the matching works even across fields, so it
isn't just copying one area's writing style. And it's a **closed loop**: every note a crew submits becomes a past job the
**next crew** can find. Abdullah will show you why you can trust it.

## 5. Why trust it · Abdullah (4:35–5:00)

*Dashboard slide.*

**Abdullah:** Why should you trust the ranking? We tested it only on months it had **never seen**. It's **calibrated**: when
it says forty percent, about forty percent happen. And it holds up on fields it was never trained on. A Databricks pipeline
refreshes everything in about five minutes. Let's show you.

---

## 6. Guided live demo · Abdullah + Hassaan (5:00–7:45)

*Abdullah drives the laptop on the projector. Hassaan holds the crew phone, mirrored or held up to the camera.*

**Manager · Abdullah (about 1:15)**

1. *Overview:* point to "Act on these 10 first" and the "worst 10% of wells take 35%" chart, about 10 seconds each.
2. *At-risk wells:* click **Score producing wells** (the model scores every well live in the browser). Switch Priority to
   "Closest first", then back.
3. *Click a well:* show why it's flagged, the likely failing part, and real past jobs with how long they lasted.
4. Assign it to **Crew 1**.

Say, in your own words:
- "These are the ten wells to act on first, ranked by what a repair is likely to cost, including lost oil."
- "I can rank by money at risk, risk alone, or distance from a crew."
- "Here's why this well is flagged, what the sensors suggest the crew will find, and real past jobs with how long those
  fixes lasted."
- "I'll assign this one to Crew 1. Hassaan?"

**Crew · Hassaan (about 1:15)**

1. The assignment appears. Tap **Share my location**: the map shows the well, you, and directions.
2. Read one short phrase from a real past note aloud.
3. Tap a work chip, **dictate** a short note, and submit.

Say:
- "The well is already on my phone, on a map with my position and directions."
- "Before I leave the truck I can read what other crews actually wrote on similar jobs." *(read the phrase)* "That's a real
  crew's words, not something a model made up."
- "When I'm done I log it with a few taps or by voice. No signal? It sends later."

**Close the loop · Abdullah (about 0:20)**

*Refresh the manager screen, open Resolved.*
- "There's Hassaan's note in Resolved, and it now shows up for the next crew facing a similar well."

## 7. Judges try it · Uzair narrates (7:45–9:10)

*Hand a judge the prepared phone, logged in as Crew 2.*

**Uzair:** Now we'd like **you** to try it. Abdullah is assigning you a well right now.

*Abdullah assigns a different well to Crew 2 on the projector.* Then guide the judge, short and calm:
- "Tap refresh: there's your well."
- "Open it. That's a real note from a crew who faced a similar well."
- "Tap what you'd have done, add a few words, and hit send."
- *(point at the projector)* "And there it is in Resolved."

**Uzair:** What you just wrote is now part of **Well Memory**. The next crew at a similar well will see **your** note.

*If there is time or a second judge: let them pick a priority mode (closest, riskiest, most expensive) on the laptop and
open a well.*

## 8. Pilot and close · Uzair, then Hassaan (9:10–10:00)

*Pilot slide.*

**Uzair:** To measure the **real** saving, our pilot is **already randomized**: **three hundred sixty-nine** repeat-prone
wells, **one eighty-six** with WellSimple and **one eighty-three** with usual practice. We validated the test on real
history: it raised a false alarm only **four percent** of the time, with **ninety-six percent** power to detect a fifty
percent cut. The potential is **one point seven to nine point one million dollars a year**. A **twelve-month** read gives
the real number.

**Hassaan:** We started with a crew going back to the same well. Now they arrive knowing what to look for, and every visit
makes the next one smarter. Thank you.

---

## Q&A · short answers (about 15 seconds each, then stop)

Never name or criticize other teams. Say what makes ours different.

| Question | Answer |
|---|---|
| How do you know it isn't overfitting? | Trained on earlier data, left a thirty-day gap, tested only on months it never saw. Beats each well's own history (0.72) and the field average (0.68), and it's calibrated: when it says 42%, 43% happen. |
| What tech is behind it? | Risk model: gradient-boosted trees; XGBoost and LightGBM scored the same, logistic regression lower (0.785). Notes: vectors in Chroma locally and Databricks Vector Search, 99% agreement with exact search. Sensors to notes: a random forest. Charts: Chart.js; map: Leaflet with OpenStreetMap. |
| Why no AI language model? | In the field, trust matters: every note is a real crew's words, so nothing can be made up. We tested a small language model (MiniLM) and the simpler method did better at predicting how long repairs last (0.376 vs 0.337). |
| Another team got higher precision in their top wells. | Different targets, so not a direct comparison. Ours predicts any repair visit in 30 days, including scheduled work, across all 1,336 wells; it beats each well's own history and is calibrated. |
| Isn't the early-failure spike just planned follow-ups? | Some may be, but the pattern holds within the same well (shape 0.71). Separating planned from unplanned visits is our first refinement. |
| Why not recommend a fix, like a new rod string? | Our most repair-prone wells sit closest to constant risk, which points to redesign, and WellSimple puts exactly those wells in front of engineers. We didn't claim a causal saving from history; that's why we built a randomized pilot. |
| Where do $13.9M and $1.7M–$9.1M come from? | Field-estimated cost of repair jobs that started within thirty days of a previous repair, averaged over the job log, plus $2.6M of lost oil, times a 10%–55% reduction (55% is a published root-cause program on these pumps). Scenarios, which is why we built the pilot. |
| What about faster dispatch? | In the failure log, 94% of failures already have a repair job dated on or before the failure date, so we found little queue to shorten. Downtime codes may capture waiting the log doesn't: worth a pilot. |
| Did you use Canary? | We built on Databricks instead: pipeline job, Delta tables and Vector Search, with the live app fed directly from it. |
| How is your search different from a plain vector search? | Every result carries its outcome (cost, how long it lasted), sensors can find notes before anyone writes one, it matches exact search 99% of the time, and it sits inside a risk model and a crew loop. |
| What does 0.69 concordance mean? | Pick two repairs: 69% of the time it correctly says which will last longer. A coin flip is 50%. |
| Can the pilot detect a small improvement? | Not reliably: at 183 wells per group it catches a 50% cut 96% of the time, but a 20% cut only about a quarter of the time. Small effects need more wells or longer. |
| Your failure data is short? | Labeled failures cover about 22 months, so component predictions use that window. The job log covers almost six years, which the repair timing and repeat analysis use. |

**If you blank:** "Good question. The short answer is [one fact], and the full method is in our repo." Then stop.

---

## Before going on stage

- [ ] Hosted site redeployed so the "Demo build" banners are gone
- [ ] Two phones logged in (username `demo`), Chrome, location and microphone allowed: Crew 1 for Hassaan, Crew 2 for the judge
- [ ] Two wells picked in advance, unassigned, each with a past crew note: one for the guided demo, one for the judge
- [ ] Old test assignments cleared so Assigned and Resolved look clean
- [ ] Backups: local app (`run_demo.ps1`) if Wi-Fi fails, type if dictation fails, recorded demo video if everything fails
- [ ] Judges' turn rehearsed to under 90 seconds, with one clear instruction: "open your well and send a short note"
- [ ] Slide fixes made: the pilot is not "simulated"; "use prioritize" typo; Repeat Repairs slide moved right after the title

**If running over, cut in this order:** the second-judge task, the "Closest first" switch, one sentence from Sensor Data.
