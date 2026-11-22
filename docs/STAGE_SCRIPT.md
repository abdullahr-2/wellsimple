# WellSimple stage script (10-minute finalist talk + 3-minute Q&A)

**Hassaan** · Electrical engineer  **Abdullah** · Computer scientist and software engineer  **Uzair** · Data scientist

Follows the slides in `WellSimple.pdf`, then moves to a live demo and a short turn where the judges use the app
themselves. Italic lines are stage directions, not spoken.

## Slide fixes before presenting

1. **Our Solution** says the A/B pilot is "simulated" and used "to estimate what acting early could save." The pilot is
   real and randomized (369 enrolled wells); only the test's power was simulated, and the savings come from measured
   repeat spend. Suggested wording: *"…and designed a randomized A/B pilot to measure what acting early saves, all within
   software the company can use."*
2. **Research Question** typo: "How can Strathcona use prioritize wells" should read "How can Strathcona prioritize wells".
3. Move **Repeat Repairs** to right after the title slide, so the problem (61%) comes before the research question and
   the solution.

## Running order

| Part | Who | Slides | Time |
|---|---|---|---|
| Problem | Hassaan | Title → Repeat Repairs → Research Question | 0:00–1:00 |
| Solution | Abdullah | Our Solution | 1:00–1:40 |
| Risk and sensors | Hassaan | Data sources → Sensor Data | 1:40–2:55 |
| Repairs and crew notes | Uzair | Repair History → Crew Notes | 2:55–4:25 |
| Why trust it | Abdullah | Dashboard | 4:25–4:50 |
| Guided demo | Abdullah + Hassaan | Live app | 4:50–7:50 |
| Judges try it | All, Uzair narrates | Live app | 7:50–9:15 |
| Pilot and close | Uzair → Hassaan | Pilot | 9:15–10:00 |

## 1. Problem · Hassaan (0:00–1:00)

*Title slide.*

**Hassaan:** Imagine sending a crew back to a well they fixed three weeks ago. What would you want them to know before
they leave? I'm Hassaan, our electrical engineer. This is Abdullah, our software engineer, and Uzair, our data scientist.
We're WellSimple.

*Repeat Repairs slide (61%).*

**Hassaan:** Every producing well in Strathcona's heavy oil fields runs on a pump, and pumps get repaired often. In their
records, sixty-one percent of repair jobs come within ninety days of another repair on the same well. Some are planned,
but every visit costs a crew, a truck and lost oil. Today a manager picks who to send from experience, and a crew picks a
fix from memory. The sensor data sits in one system, and what the last crew actually found is buried in a job summary.

*Research Question slide.*

**Hassaan:** So we asked: how can Strathcona prioritize wells for maintenance, and can that reduce repeat repairs and costs
compared with current practice?

## 2. Solution · Abdullah (1:00–1:40)

*Our Solution slide.*

**Abdullah:** Our answer is WellSimple: two connected apps. Managers get a ranked list of which wells to visit first and
what each repair is likely to cost. Crews get a phone app that puts what past crews found in their hands before they
arrive. Behind it are a risk model, a searchable memory of nearly fourteen thousand real crew notes, and a randomized pilot
to measure the savings. It all runs on Databricks, and nothing in it is AI-generated: every note you'll see is a real
crew's own words. Hassaan will start with where risk comes from.

## 3. Risk and sensors · Hassaan (1:40–2:55)

*Data sources slide.*

**Hassaan:** We use three sources, and each answers a different question. Sensors tell us when a well needs attention.
Repair history is the strongest risk signal. Crew notes tell us what you'll find and how long a fix will last.

*Sensor Data slide.*

**Hassaan:** These wells use progressing cavity pumps: a motor at the surface turns a rod string that drives a pump
downhole. We track nine daily readings as trends, and we added features from the pump's physics, like how fast efficiency
is dropping, and a fatigue index: loaded pump revolutions since the last repair. Sensors lift accuracy from 0.76 to 0.82,
and the top five percent of wells we flag needed a repair forty-nine percent of the time, against twelve percent overall.
From sensors alone we can predict the likely failing part. And we didn't take textbook warning signs on faith. We checked
them against what crews actually found. Gas interference held up, three and a half times. Others didn't, so the app shows
them as signals, not causes.

## 4. Repairs and crew notes · Uzair (2:55–4:25)

*Repair History slide.*

**Uzair:** Repair history is the strongest single signal, and the reason surprised us. Risk is highest right after a fix:
about ten times higher in the first week than six to twelve months later, even comparing each well only with itself. That
means scheduled replacement wouldn't pay, because every new install starts in its riskiest weeks. The money is in getting
each repair right. It also sizes the problem: about thirteen point nine million dollars a year goes to repairs within
thirty days of a previous one, and the worst ten percent of wells take thirty-five percent of the jobs. Combine each
well's risk with an average repair cost of about seventeen and a half thousand dollars plus lost oil, and you get its
expected loss. That's what ranks the manager's list.

*Crew Notes slide.*

**Uzair:** Crew notes do something sensors can't: they're the best predictor of how long a repair will last, 0.69 versus
0.58 from sensors. For every well we show real past jobs, what they cost and how long they held. Nothing is generated, and
the matching works even across fields, so it isn't just copying one area's writing style. And it's a closed loop: every
note a crew submits becomes a past job the next crew can find.

## 5. Why trust it · Abdullah (4:25–4:50)

*Dashboard slide.*

**Abdullah:** Why should you trust the ranking? We tested it only on months it had never seen. It's calibrated: when it
says forty percent, about forty percent happen. And it holds up on fields it was never trained on. A Databricks pipeline
refreshes everything in about five minutes. Let's show you.

## 6. Guided demo (4:50–7:50)

*Abdullah drives the laptop on the projector. Hassaan holds the crew phone, mirrored or held to the camera.*

**Manager · Abdullah (about 1:15)**
1. Overview: point to "Act on these 10 first" and the "worst 10% of wells take 35%" chart (about 10 s each).
2. At-risk wells: click **Score producing wells** (the model scores every well live in the browser). Switch Priority to
   "Closest first", then back.
3. Click a well: why it's flagged, the likely failing part, and real past jobs with how long they lasted.
4. Assign it to **Crew 1**.

**Crew · Hassaan (about 1:15)**
1. The assignment appears. Tap **Share my location**; the map shows the well, you, and directions.
2. Read one short phrase from a real past note aloud: "That's a real crew's words."
3. Tap a work chip, dictate a short note, and submit. Mention: "No signal? It sends later."

**Close the loop · Abdullah (about 0:20):** refresh and open **Resolved**. Hassaan's note is there, and it now helps the
next crew.

## 7. Judges try it (7:50–9:15)

*Uzair narrates. Keep it to one simple task.*

**Uzair:** Now we'd like you to try it. *(Hand a judge the prepared phone, logged in as Crew 2.)* Abdullah is assigning you
a well right now.

1. Abdullah assigns a different well to **Crew 2** on the projector.
2. The judge refreshes and opens it, sees the map and reads a past crew note.
3. The judge taps a work chip, types or dictates a few words, and submits.
4. Everyone watches it land in **Resolved** on the big screen, with the judge's own note.

**Uzair:** What you just wrote is now part of Well Memory. The next crew at a similar well will see it.

*If there is time or a second judge: let them choose a priority mode (closest, riskiest, most expensive) on the laptop and
pick a well to open.*

## 8. Pilot and close (9:15–10:00)

*Pilot slide.*

**Uzair:** To measure the real saving, we designed a randomized pilot: 369 repeat-prone wells, 186 with WellSimple and 183
with usual practice. We validated the test on real history: it raised a false alarm only four percent of the time, with
96 percent power to detect a fifty percent cut. The potential is $1.7 million to $9.1 million a year. A twelve-month read
gives the real number.

**Hassaan:** We started with a crew going back to the same well. Now they arrive knowing what to look for, and every visit
makes the next one smarter. Thank you.

## What the judges must leave knowing

| Message | Rubric | Where it is said |
|---|---|---|
| Real data, tested on months it never saw, calibrated | Technical, 25% | Abdullah, Dashboard |
| The engineering: pump physics checked against real crew findings, and risk peaking right after a repair (so scheduled replacement doesn't pay) | Research depth, 25% | Hassaan Sensors, Uzair Repair History |
| Dollars stated honestly: $13.9M a year at stake, $1.7M to $9.1M potential, and a real randomized pilot to measure it | Business impact, 20% | Uzair |
| No AI-generated text: real crew words, which matters for trust in the field | Creativity, 15% | Abdullah Solution, Uzair Crew Notes |
| Runs on Databricks: pipeline, Delta tables, Vector Search | Sponsor and scalability | Abdullah |
| A working product a crew could use tomorrow, shown by the judges using it themselves | Presentation, 15% | Demo and judges' turn |

If asked, state these plainly without apologizing: the risk label includes planned work, so it predicts "needs a visit",
not only breakdowns; and the savings are scenarios until the pilot reads out.

## Demo prep checklist

- **Phones:** two phones logged in in advance, one as **Crew 1** (Hassaan) and one as **Crew 2** (for the judge). Use
  Chrome, and allow location and microphone once beforehand.
- **Wells:** pick two in advance, one for the guided demo and one for the judge, both unassigned and with a past crew note.
- **Clutter:** resolve or clear old test assignments so the Assigned and Resolved tabs look clean.
- **Deploy:** redeploy the hosted site so the "Demo build" banners are gone.
- **Backups:** if the Wi-Fi fails, run the local app (`run_demo.ps1`) on the laptop; if dictation fails, type; if
  everything fails, play the recorded demo video.
- **Rehearse the handover:** the judges' turn should take under 90 seconds. Give one clear instruction: "open your well
  and send a short note".

See also: [PRESENTATION_SCRIPT.md](PRESENTATION_SCRIPT.md) (5-minute demo video), [FINALIST_SCRIPT.md](FINALIST_SCRIPT.md)
(extra finalist material) and [PITCH.md](PITCH.md) (numbers and Q&A answers).
