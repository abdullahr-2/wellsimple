# WellSimple demo video script

**Uzair** · Data scientist **Abdullah** · Computer scientist and software engineer **Hassaan** · Electrical engineer

This is the script for the **demo video** only. It is built around the live app: almost every finding is shown on the
app's own screens rather than on slides. Read the named speaker lines; the italic lines are what to do on screen.
It runs about 4:17 at a steady pace (594 spoken words, with short pauses for screen
moves), and still under 5:00 when read slowly (4:35 at 140 words per minute). Extra material for the ten-minute finalist talk is in [FINALIST_SCRIPT.md](FINALIST_SCRIPT.md).

| Section                            | Speaker  | Time      |
| ---------------------------------- | -------- | --------- |
| 1. Hook                            | Hassaan  | 0:00–0:18 |
| 2. The problem, in the app         | Uzair    | 0:18–0:40 |
| 3. Manager: which well first       | Abdullah | 0:40–1:12 |
| 4. Crew: on the phone              | Hassaan  | 1:12–1:42 |
| 5. Closing the loop                | Abdullah | 1:42–1:53 |
| 6. Can you trust the ranking?      | Uzair    | 1:53–2:28 |
| 7. What we learned about the pumps | Hassaan  | 2:28–3:04 |
| 8. What it's worth                 | Uzair    | 3:04–3:32 |
| 9. Built on Databricks             | Abdullah | 3:32–3:56 |
| 10. The A/B pilot and close        | Hassaan  | 3:56–4:17 |

## Before recording

- Record the screen, not slides. Open three windows: the **manager portal** in a desktop browser, the **crew portal** in
  phone size (a real phone, or the browser's device view at about 390 px wide), and the **Databricks workspace**.
- Use the hosted site after its latest deploy, or the local app (`run_demo.ps1`). Use Chrome or Edge so dictation works,
  and allow location and microphone access once before recording.
- Pick one unassigned well with a past crew note, and use that same well from start to finish.
- On the hosted site, click **Score producing wells** in At-risk wells before the take if the list is empty.
- Keep screen moves quick: each section allows only about two seconds for clicking and scrolling.

## 1. Hook (0:00–0:18)

_Manager overview, logo in the header._

**Hassaan:** Imagine sending a crew back to a well they repaired three weeks ago. What would you want them to know before
they leave? I'm Hassaan, our electrical engineer, with Uzair, our data scientist, and Abdullah, our software engineer.
This is WellSimple.

## 2. The problem, in the app (0:18–0:40)

_Point to the "Repairs repeating within 90 days" card, then scroll to the "worst 10% of wells" chart._

**Uzair:** This is the manager's overview, built from Strathcona's own records. Sixty-one percent of repair jobs come within
ninety days of another repair on the same well, about one in three within thirty days. And it's concentrated: the worst
ten percent of wells take a third of all repair jobs.

## 3. Manager: which well first (0:40–1:12)

_Point to "Act on these 10 first". Open At-risk wells (click Score producing wells on the hosted site). Switch Priority to
"Closest first" and back. Click the chosen well, show the detail panel, then assign it to Crew 1._

**Hassaan:** The manager starts with the ten wells to act on first, ranked by what a repair is likely to cost, including
lost oil. In At-risk wells I can rank by money at risk, risk alone, or distance from a crew. Each well shows why it was
flagged, what its sensors suggest the crew will find, and real notes from similar past jobs with how long those fixes
lasted. I'll assign this one to Crew 1.

## 4. Crew: on the phone (1:12–1:42)

_Crew portal in phone size. Tap Share my location, open the assignment, show the map, scroll to "What the system knows" and
read one short phrase from a past note. Tap a work chip, use Dictate to say "Demo inspection completed" (type it if the
browser can't dictate), and submit._

**Abdullah:** On my phone, the well is already waiting, on a map with my position and directions. Before I leave the truck,
I can read what the sensors suggest I'll find and what other crews actually wrote on similar jobs. _(read the phrase)_
That's a real crew's observation, not something a model made up. When I'm done, I log it with a few taps or by voice, and
if there's no signal it sends later.

## 5. Closing the loop (1:42–1:53)

_Switch to the manager, refresh, open Resolved._

**Abdullah:** The job is now in Resolved with the crew's note, and that note shows up for the next crew facing a similar
well.

## 6. Can you trust the ranking? (1:53–2:28)

_Overview: scroll to "Can you trust the risk score?". Point to the table, then to the calibration chart._

**Uzair:** We tested the ranking only on months it had never seen. About twelve in a hundred well-weeks were followed by a
repair within thirty days. Among the five percent our model ranked highest, it was about fifty in a hundred: four times
the rate, and better than a well's own history or its field's average. On this chart, when it says forty percent, about
forty percent really need a repair. A flag means "review this well," and the outcome includes scheduled work.

## 7. What we learned about the pumps (2:28–3:04)

_Overview: scroll to "Do fixes last?" and point to the first bar, then the 6 to 12 month bar._

**Hassaan:** These wells run progressing cavity pumps, driven by a rod string from the surface. When the sensors pointed to
gas in the pump, crews reported gas three and a half times as often. And the chance of another repair is about ten times
higher in the first week than six to twelve months later, even when we compare each well only with itself. So scheduled
replacement wouldn't pay: every new install starts in its riskiest weeks. The money is in getting each repair right.

## 8. What it's worth (3:04–3:32)

_Overview: point to the "Potential saving" card, top line first, then the table._

**Uzair:** Repeat repairs within thirty days cost about thirteen point nine million dollars a year, plus two point six
million in lost oil. If better preparation prevented ten percent, Strathcona could potentially save about one point seven
million a year, and at the fifty-five percent a published program reported, about nine point one million. Those are
scenarios before implementation costs; the pilot measures the real figure.

## 9. Built on Databricks (3:32–3:56)

_Databricks workspace: Jobs, the green run of wellsimple-pipeline; Catalog, the workspace.wellsimple_pipeline tables; the
repair_notes_index under Vector Search._

**Abdullah:** It all runs on Databricks. A serverless job retrains and scores every well from Delta tables and refreshes the
app in about five minutes. Every crew note is indexed in Databricks Vector Search, which matched an exact search on
ninety-nine percent of real queries. And nothing is generated: every note you see is a crew's own.

## 10. The A/B pilot and close (3:56–4:17)

_Manager: open the A/B pilot tab, show the two group sizes, then finish on the logo._

**Hassaan:** Finally, the pilot: three hundred sixty-nine repeat-prone wells, randomized, one hundred eighty-six with
WellSimple and one hundred eighty-three without. On real history, its test raised a false alarm only four percent of the
time. Twelve months of follow-up will show how many repeat visits this prevents.
Thank you.

---

**Credits.** Results and limitations are in the [README](../README.md); the engineering and the Databricks setup are in
[DOMAIN.md](DOMAIN.md) and [DATABRICKS.md](DATABRICKS.md). Include the repository's AI-use disclosure in the submission
credits and credit Codex and Claude Code for assistance drafting and updating this script.
