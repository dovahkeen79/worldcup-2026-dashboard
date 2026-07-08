# World Cup 2026 Match Analyser

Scrapes the whole FIFA World Cup 2026 from Wikipedia (+ 11v11 for head-to-head),
analyses form / H2H / squads, predicts every upcoming result with a transparent
weighted model, and presents it as an **interactive web dashboard** — plus a
static six-agent HTML report.

All kick-offs are shown in **London time**.

## Quick start — interactive dashboard (recommended)

Just double-click **`WorldCup.bat`** (Windows). It starts the server and opens
your browser at `http://127.0.0.1:5000`.

Or manually:

```bash
pip install -r requirements.txt
python app.py         # then open http://127.0.0.1:5000
```

The dashboard has:
- **Tabs** per round (Group stage → Final) plus **Overview** and a **Bracket**
- **Group standings** for all 12 groups
- **Click-to-expand match cards** — probability bar, both teams' form,
  all-time head-to-head (with last meeting), key players, and the rationale
- **Team filter/search**
- A **Refresh data** button that re-scrapes everything live (~15s)
- **Live scores** (see below)

Data is cached in `data/tournament.json` (built on first run).

## Live scores & prediction accuracy

The dashboard enriches match cards in real time using the **free TheSportsDB API**
(no key, no payment), polled **client-side** — so live scores work even on the
static GitHub Pages site with no redeploy.

- **Live cards** — while a match is playing, its card shows a red
  `🔴 LIVE 2-1 · 67'` line and "LIVE NOW", with the prediction still visible.
- **Adaptive polling** — no fetch when nothing's live; every 20s for 1–2 live
  matches, 30s for 3+, 15s in stoppage time (85'+); one final fetch when a match
  ends, then it stops.
- **Final verdict** — when a match finishes, the card shows
  `Prediction: ✅ Correct` / `❌ Wrong`.
- **Accuracy tile** (Overview) — forward-only: counts only genuine *pre-match*
  predictions, resolved against real results. Predictions are logged to
  `predictions_log.json` (committed back by the Action) so accuracy accumulates
  permanently. No back-testing.
- If TheSportsDB is unreachable it shows *"Live scores temporarily unavailable"*
  and retries — the dashboard never breaks.

## Share it online (GitHub Pages)

The dashboard can be published as a **static website** anyone can open via a link
— no Python, no install. A GitHub Action re-scrapes and redeploys it
automatically (every 3 hours by default), so it stays fresh through each match
day.

**One-time setup:**
1. Create a GitHub repo and push this project to it (`main` branch).
2. In the repo: **Settings → Pages → Build and deployment → Source = GitHub Actions**.
3. Done. The included workflow (`.github/workflows/deploy.yml`) builds and
   deploys on every push, on a 3-hour schedule, and on manual trigger
   (Actions tab → *Run workflow*).

Your site appears at `https://<your-username>.github.io/<repo-name>/`.
Share that link with anyone.

**Build the static site locally** (to preview before pushing):
```bash
python build_static.py          # re-scrapes, writes docs/index.html
```
Then open `docs/index.html` in a browser, or serve it:
`python -m http.server -d docs`.

To change how often it auto-refreshes, edit the `cron` line in
`.github/workflows/deploy.yml`.

## Static report (the original six-agent pipeline)

```bash
python run.py
```

Writes `reports/worldcup_analysis_<date>.html` — a self-contained report of the
next few fixtures. Open it in any browser.

## Architecture

```
run.py  (orchestrator)
│
├─ PHASE 1
│   ├─ Agent 1  Fixtures Scout   → data/fixtures.json   (runs first)
│   └─ in parallel (ThreadPoolExecutor):
│       ├─ Agent 2  Form Analyst   → data/form.json
│       ├─ Agent 3  H2H Historian  → data/h2h.json
│       └─ Agent 4  Squad Reporter → data/squads.json
│
└─ PHASE 2
    ├─ Agent 5  Match Analyst    → data/analysis.json   (predictions)
    └─ Agent 6  Report Formatter → reports/*.html
```

- **Agent 1 – Fixtures Scout** parses the 2026 FIFA World Cup Wikipedia article's
  `footballbox` blocks for the next upcoming matches (date, teams, venue, stage),
  filtering out TBD placeholder pairings.
- **Agent 2 – Form Analyst** derives each team's recent W/D/L from the tournament's
  completed results (real, self-consistent data).
- **Agent 3 – H2H Historian** scrapes the all-time head-to-head record from national
  team pages, plus direct/common-opponent analysis. Degrades gracefully when a
  pairing has no published record.
- **Agent 4 – Squad Reporter** pulls real key players, caps/goals and the coach from
  the *2026 FIFA World Cup squads* article.
- **Agent 5 – Match Analyst** combines everything into win/draw/loss probabilities
  with a confidence % and a plain-English rationale.
- **Agent 6 – Report Formatter** renders a self-contained, responsive HTML report
  (team crests with initials-badge fallback, probability bars, form pills).

## Prediction model

A deliberately explainable weighted score. Each signal produces an "edge" in
`[-1, +1]` favouring the home side:

| Signal | Weight | Basis |
|--------|--------|-------|
| Form   | 40%    | points-per-game difference over recent results |
| H2H    | 30%    | all-time win-rate difference |
| Squad  | 20%    | key-player attacking/experience index, minus injuries |
| Host   | 10%    | host-nation home advantage (USA/Canada/Mexico) |

Missing signals are dropped and the remaining weights **renormalised**, so the
model always works with whatever data Phase 1 gathered.

## Design notes

- **Sources:** Wikipedia for fixtures/results/standings/squads; **11v11.com** for
  all-time head-to-head (it has a page for every pairing, unlike Wikipedia's
  inconsistent per-team tables). Per-source graceful degradation throughout.
- **Times:** kick-offs are parsed with their UTC offset and converted to
  Europe/London (BST/GMT) for display.
- **Resilience:** every agent is isolated — a failure is logged and the pipeline
  continues using available JSON artefacts. 4xx responses fail fast (no retry);
  5xx / network errors retry with backoff.
- **Fallback data:** if live scraping yields nothing, a bundled sample dataset
  keeps the pipeline producing an end-to-end report, clearly flagged
  "SAMPLE DATA" in the report and logs.
- **Logging:** every run writes a timestamped log to `logs/run_<timestamp>.log`.

## Layout

```
WorldCup.bat         one-click launcher (starts the dashboard)
app.py               Flask web app (dashboard + /api + refresh)
build_data.py        builds data/tournament.json (whole tournament + predictions)
run.py               static six-agent report pipeline
config.py            URLs, weights, colour maps
core/                http (retries), logger, storage, timeutil (London time)
agents/              base + six agents + tournament/H2H scrapers + sample data
templates/           dashboard.html (interactive) + report.html.j2 (static)
data/ logs/ reports/ generated output
```

## Disclaimer

Predictions are a transparent statistical model for educational/entertainment
purposes — not betting advice.
