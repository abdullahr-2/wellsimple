# Uzair's script (finalist talk)

**Bold** = stress · `/` = short pause · `//` = full pause · *italics* = stage direction

## 1. Repair History · 3:00

*After Hassaan: "…shows them as signals, not causes."*

Repair history is the **strongest** single signal, / and the reason **surprised** us. //
Risk is **highest right after a fix**: / about **ten times** higher in the first week / than six to twelve months later. /
And that holds even comparing each well **only with itself**, / so it isn't just bad wells failing first. //
That means **scheduled replacement wouldn't pay**, / because every new install starts in its **riskiest weeks**. /
The money is in getting each repair **right**. //
It also sizes the problem: / about **thirteen point nine million dollars a year** / goes to repairs within thirty days of a
previous one, / and the worst **ten percent** of wells / take **thirty-five percent** of the jobs. //
Combine each well's risk with an average repair cost of about seventeen and a half thousand dollars plus lost oil, /
and you get its **expected loss**. / That's what ranks the manager's list.

## 2. Crew Notes · 3:50

Crew notes do something sensors **can't**: / they're the **best predictor of how long a repair will last**, /
zero point six nine versus zero point five eight from sensors. //
For every well we show **real past jobs**, / what they cost / and how long they held. //
Every note is stored as a **vector**, / so a search finds the closest past jobs in **milliseconds**, /
and on Databricks that's **Vector Search**, / matching an exact search **ninety-nine percent** of the time. //
We **tested** a language model and **chose not to use one**: / **nothing is generated**, / so every note is a real crew's words. /
And the matching works even **across fields**, / so it isn't just copying one area's writing style. //
And it's a **closed loop**: / every note a crew submits / becomes a past job the **next crew** can find. //
Abdullah will show you why you can trust it.

## 3. Judges try it · 7:45

*Hand the judge the Crew 2 phone.*

Now we'd like **you** to try it. / Abdullah is assigning you a well right now.

- "Tap refresh: there's your well."
- "Open it. That's a real note from a crew who faced a similar well."
- "Tap what you'd have done, add a few words, and hit send."
- *(point at projector)* "And there it is in Resolved."

What you just wrote is now part of **Well Memory**. / The next crew at a similar well / will see **your** note.

## 4. Pilot · 9:10

To measure the **real** saving, / our pilot is **already randomized**: / **three hundred sixty-nine** repeat-prone wells, /
**one eighty-six** with WellSimple / and **one eighty-three** with usual practice. //
We validated the test on real history: / it raised a false alarm only **four percent** of the time, /
with **ninety-six percent** power to detect a fifty percent cut. //
The potential is **one point seven to nine point one million dollars a year**. / A **twelve-month** read gives the real number.

*Look at Hassaan for the close.*

## Numbers

| | |
|---|---|
| Week-one risk vs 6–12 months | **10×** · shape 0.61, **0.71 same well** |
| Repeat spend | **$13.9M/yr** + $2.6M lost oil |
| Worst 10% of wells | **35%** of jobs |
| Avg repair cost | ~$17,461 |
| Notes vs sensors (fix life) | **0.69 vs 0.58** |
| Pilot | **369** = 186 / 183 · **4%** false alarms · **96%** power at 50% cut |
| Potential | **$1.7M–$9.1M/yr** (10%–55% fewer repeats) |

## Your likely questions

- **Just planned follow-ups?** Some may be, but it holds within the same well (0.71). Separating planned vs unplanned is our first refinement.
- **Higher precision elsewhere?** Different targets. Ours is any repair visit in 30 days incl. scheduled work; it beats a well's own history (0.72) and field average (0.68), and it's calibrated.
- **Why not recommend a fix like a new rod string?** Our most repair-prone wells are closest to constant risk, which points to redesign, and we surface them. We didn't claim a causal saving from history; that's why the pilot.
- **$13.9M and $1.7M–$9.1M?** Field-estimated cost of repairs within 30 days of a previous one, plus $2.6M lost oil, × 10%–55%. Scenarios; the pilot measures the real figure.
- **What tech is behind it?** Risk model: gradient-boosted trees (XGBoost and LightGBM scored the same, 0.82; logistic regression 0.785). Notes: vectors in Chroma locally and Databricks Vector Search (99% agreement with exact search). Sensors to notes: a random forest. No generative language model: we tested MiniLM and the simpler method did better (0.376 vs 0.337).
- **What's 0.69?** Pick two repairs: 69% of the time it says correctly which lasts longer. Coin flip = 50%.
- **Small improvements?** 96% power at a 50% cut, only about a quarter at 20%. Smaller needs more wells or time.
- **Blank?** "Good question. The short answer is [one fact], and the method's in our repo."
