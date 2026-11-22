# WellSimple demo video script

**Uzair** · Data scientist  **Abdullah** · Computer scientist and software engineer  **Hassaan** · Electrical engineer

This is the script for the **demo video** only. It is built around the live app: almost every finding is shown on the
app's own screens rather than on slides. Read the named speaker lines; the italic lines are what to do on screen. It runs
about 5:46 at a steady pace (814 spoken words, with short pauses for screen moves), and over 5 minutes even when
read briskly. Extra material for the ten-minute finalist talk is in
[FINALIST_SCRIPT.md](FINALIST_SCRIPT.md).

| Section | Speaker | Time |
|---|---|---|
| 1. Hook | Hassaan | 0:00–0:18 |
| 2. The problem, in the app | Uzair | 0:18–0:50 |
| 3. Manager: which well first | Abdullah | 0:50–1:34 |
| 4. Crew: on the phone | Hassaan | 1:34–2:20 |
| 5. Closing the loop | Abdullah | 2:20–2:40 |
| 6. Can you trust the ranking? | Uzair | 2:40–3:20 |
| 7. What we learned about the pumps | Hassaan | 3:20–4:10 |
| 8. What it's worth | Uzair | 4:10–4:44 |
| 9. Built on Databricks | Abdullah | 4:44–5:22 |
| 10. The A/B pilot and close | Hassaan | 5:22–5:46 |

## Before recording

- Record the screen, not slides. Open three windows: the **manager portal** in a desktop browser, the **crew portal** in
  phone size (a real phone, or the browser's device view at about 390 px wide), and the **Databricks workspace**.
- Use the hosted site after its latest deploy, or the local app (`run_demo.ps1`). Use Chrome or Edge so dictation works,
  and allow location and microphone access once before recording.
- Pick one unassigned well with a past crew note, and use that same well from start to finish.
- On the hosted site, click **Score producing wells** in At-risk wells before the take if the list is empty.

## 1. Hook (0:00–0:18)

*Manager overview, logo in the header.*

**Hassaan:** Imagine sending a crew back to a well they repaired three weeks ago. What would you want them to know before
they leave? I'm Hassaan, our electrical engineer, with Uzair, our data scientist, and Abdullah, our software engineer.
This is WellSimple.

## 2. The problem, in the app (0:18–0:50)

*Point to the "Repairs repeating within 90 days" card, then scroll to the "worst 10% of wells" chart.*

**Uzair:** This is the manager's overview, built from Strathcona's own records. Sixty-one percent of repair jobs come within
ninety days of another repair on the same well, and about one in three within thirty days. And it's concentrated: the
worst ten percent of wells take a third of all repair jobs. The sensor history sits in one place, and what the last crew
actually found is buried in a job summary. WellSimple brings them together.

## 3. Manager: which well first (0:50–1:34)

*Point to "Act on these 10 first". Open At-risk wells (click Score producing wells on the hosted site). Switch Priority to
"Closest first" and back, flip Oil value to Mid and back. Click the chosen well, show the detail panel, then assign it to
Crew 1.*

**Abdullah:** Every morning the manager starts here: the ten wells to act on first, ranked by what a repair is likely to
cost, including the oil lost while the well is down. In At-risk wells I can rank by money at risk, by risk alone, or by
distance from a crew, and switch the oil price between conservative and mid. Each well shows why it was flagged. When I
open one, I see what its sensors suggest the crew will find, and real notes from similar past jobs, with how long those
fixes lasted. This one is worth a visit, so I'll assign it to Crew 1.

## 4. Crew: on the phone (1:34–2:20)

*Crew portal in phone size. Tap Share my location, open the assignment, show the map and the directions link, scroll to
"What the system knows". Point to one short phrase in a past note and read it aloud. Then tap a work chip, use Dictate to
say "Demo inspection completed, no sand found" (type it if the browser can't dictate), and submit.*

**Hassaan:** On my phone, the well is already waiting. The map shows the well and where I am, with directions. Before I
leave the truck, I can read what the system knows: what the sensors suggest I'll find, and what other crews actually wrote
on similar jobs. *(read the phrase)* That's a real observation from a real crew, not something a model made up, so I'll
check whether it applies here. When I'm done, I log it with a few taps, or by voice. If there's no signal, it saves on the
phone and sends when I'm back in range. Every note I write becomes a past job the next crew can search.

## 5. Closing the loop (2:20–2:40)

*Switch to the manager, refresh, open Resolved.*

**Abdullah:** Back on the manager screen, the job has moved to Resolved, with the crew's note, the work done and the time on
site. And that note now shows up as a similar past job for the next crew that faces a well like this.

## 6. Can you trust the ranking? (2:40–3:20)

*Overview: scroll to "Can you trust the risk score?". Point to the table, then to the calibration chart.*

**Uzair:** We tested the ranking only on months it had never seen. Overall, about twelve in a hundred well-weeks were
followed by a repair within thirty days. Among the five percent our model ranked highest, it was about fifty in a hundred:
four times the overall rate, and better than ranking by each well's own history or its field's average. And it's honest
about its own confidence. On this chart, when it says forty percent, about forty percent of those wells really need a
repair. A flag means "review this well," and the outcome includes scheduled work.

## 7. What we learned about the pumps (3:20–4:10)

*Overview: scroll to "Do fixes last?" and point to the first bar, then the 6 to 12 month bar.*

**Hassaan:** These wells run progressing cavity pumps: a surface motor turns a rod string that drives the pump downhole. We
tested an engineer's reading of the sensors against what crews found. When the readings pointed to gas in the pump, crews
reported gas three and a half times as often. Then the timing. On this chart, after a rod-truck job, the chance of another
repair is about ten times higher in week one than six to twelve months later, and the risk falls this way even when we
compare each well only with itself. That flips a common assumption: scheduled replacement wouldn't pay, because every new
install starts in its riskiest weeks. The money is in getting each repair right.

## 8. What it's worth (4:10–4:44)

*Overview: point to the "Potential saving" card, top line first, then the table.*

**Uzair:** So what is it worth? Repair jobs within thirty days of a previous repair cost about thirteen point nine million
dollars a year in field estimates, plus about two point six million in lost oil. If better preparation prevented ten
percent, Strathcona could potentially save about one point seven million a year. At the fifty-five percent a published
root-cause program reported, about nine point one million. Those are scenarios, before implementation costs. Measuring the
real figure is the pilot's job.

## 9. Built on Databricks (4:44–5:22)

*Databricks workspace: Jobs, the green run of wellsimple-pipeline; Catalog, the workspace.wellsimple_pipeline tables; the
repair_notes_index under Vector Search.*

**Abdullah:** Under the hood, it all runs on Databricks. Five million daily records sit in Delta tables. This job retrains
and scores every well on serverless compute and refreshes the app's data in about five minutes. It could run on a schedule each morning, so the manager's list is current before the first truck leaves. Every crew note is indexed
in Databricks Vector Search, which matched an exact search on ninety-nine percent of real queries. And nothing in the app is
generated: every note you see is a crew's own.

## 10. The A/B pilot and close (5:22–5:46)

*Manager: open the A/B pilot tab, show the two group sizes and the A/A line, then finish on the logo.*

**Hassaan:** Finally, the pilot. We randomized three hundred sixty-nine repeat-prone wells: one hundred eighty-six with
WellSimple and one hundred eighty-three with usual practice. We checked the test on real history, where it raised a false
alarm only four percent of the time. Twelve months of follow-up will tell Strathcona how many repeat visits this prevents.
Thank you.

---

**Credits.** Results and limitations are in the [README](../README.md); the engineering and the Databricks setup are in
[DOMAIN.md](DOMAIN.md) and [DATABRICKS.md](DATABRICKS.md). Include the repository's AI-use disclosure in the submission
credits and credit Codex and Claude Code for assistance drafting and updating this script.
