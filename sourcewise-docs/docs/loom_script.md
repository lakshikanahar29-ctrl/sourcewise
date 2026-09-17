# Loom script — Sourcewise (3 min 30 s)

Record at 1280×720 or larger, face bubble on. Open these tabs first, in this order:

1. `docs/architecture.png` (the diagram)
2. The dashboard: https://lakshikanahar29-ctrl.github.io/sourcewise/
3. GitHub → Actions → the latest green run (expand "Generate, load, build and test")
4. HubSpot → CRM → Companies → one company record, scrolled to the Sourcewise properties
5. `metrics/metrics.yml` and `docs/incident_log.md` in GitHub

Say the numbers as "in this synthetic world" at least once. Never imply they're real client results.

---

## 0:00–0:25 · The problem (talking head, no screen)

> "Every B2B company spends on ads, cold email, and tools. Almost none of them can tell you which of those
> actually produced revenue. I built Sourcewise to answer that, and to show how much the answer depends on
> how you count. Everything you're about to see runs on synthetic data I generate myself, and it runs
> unattended every night."

## 0:25–0:55 · The diagram (tab 1)

> "Eight sources on the left: ads, website, cold email, my Signal Engine, Reply Bot and Voice Agent, the CRM
> and billing. They land in Postgres as raw text, then SQL cleans them, resolves identity — phone matching
> for duplicate contacts, cookies to people — and builds one touchpoint table.
> Every deal then gets its revenue split five ways: first touch, last non-direct, linear, W-shaped and time
> decay. Outputs are a dashboard, three fields in HubSpot, and a Slack summary."

Point at the black gate bar:

> "And 75 tests run before any of that publishes."

## 0:55–2:05 · The finding (tab 2, Model disagreement)

Open the dashboard on **Model disagreement**.

> "Here's the whole point of the project. Each row is a channel, each column is one attribution model, and the
> last column is the truth — because the data is synthetic, I know what each channel really contributed."

Point at the Direct row:

> "Direct gets 39% of won revenue under first touch and 51% under W-shaped. Its true contribution is
> effectively zero. That's because demo requests land on direct visits, and those are the sessions we can
> actually tie to a person. Every tool that reports 'direct' as your best channel has this bug."

Point at Voice Agent, then Signal Engine:

> "My Voice Agent swings from 19% to 46% depending on the model, against a true 26% — it calls every new lead
> minutes after they convert, so last-touch loves it. And the Signal Engine is under-credited by every single
> model: about 4% under linear against a true 18%."

Switch to the **Credit error against the truth** card:

> "Scored against the truth, first touch was closest on this data, averaging 8 points off. W-shaped was worst
> at 11.5. That's a statement about these models under known assumptions, not about the real world."

## 2:05–2:45 · Proof it's operated, not just built (tabs 3, 5)

Actions run, expanded:

> "This ran by itself last night: it generates a new day of data, loads it, builds the models, and runs 75
> tests — credit per deal sums to exactly 1.0 under every model, and credited revenue reconciles to CRM won
> revenue to the cent. If a test fails, the dashboard is not republished and Slack tells me."

Show `metrics.yml`, then `incident_log.md`:

> "Every number on the dashboard has a definition and a version in git. And this is the incident log: three
> real failures so far. The loader collided with the views it feeds, gross retention went negative because a
> customer expanded then churned, and the HubSpot sync broke because you can't upsert on a non-unique
> property. Each one has the fix and what now prevents it."

## 2:45–3:10 · The CRM (tab 4)

> "Finally, results go back where reps work. Each company carries its first-touch channel, attributed pipeline
> and a source quality score. Matching is by domain, so re-running never creates duplicates, and it only
> writes values that changed."

## 3:10–3:30 · Close

> "So: which source actually produces revenue, tested against a known answer, updated nightly, and pushed into
> the CRM. If I were handing this to a CMO, my recommendation would be [say your own view in one sentence —
> e.g. don't cut the Signal Engine on last-touch numbers, and stop treating direct as a channel].
> Code and dashboard are linked below."

---

**Links to paste in the Loom description**
- Dashboard: https://lakshikanahar29-ctrl.github.io/sourcewise/
- Code: https://github.com/lakshikanahar29-ctrl/sourcewise
- Note: all data is synthetic and regenerated nightly.
