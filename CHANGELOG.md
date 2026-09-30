# Changelog

## 1.0.0 — 2026-09-28

Portfolio release: a full review and clean-up of the project.

### Added
- **Ready to host.** `run_pipeline.py` runs extract → dbt → model in one command and waits for a paused database to wake up. Connection settings (`extraction/db.py`) now serve the pipeline, model and dashboard alike, support Azure SQL, and can use `pymssql` instead of the ODBC driver (`FPL_DB_DRIVER`). The dashboard reads Streamlit secrets and retries while the database wakes. Also added: an env-driven dbt profile, the hosted dashboard's own `requirements.txt`, a scheduled GitHub Actions job and Azure setup script in `deploy/`, and a step-by-step guide in `docs/deployment.md`.
- **Expected vs actual points on My Team.** The projection run now also stores what the model expected from every player in each gameweek that has started (`player_gameweek_expected`, predicted only from earlier data), and the team sheet shows each player's points next to his expected points once his team has kicked off (just the expected points before that; captaincy multiplier applied), with a "GWn expected" card next to the gameweek's points for the team total).
- **Squad planner** (`projections/plan.py`): the best 15 for a wildcard over a longer horizon, or the best transfers (with -4 hits only when they pay) for a manager's current squad, with later gameweeks discounted. It uses an integer programme via SciPy and writes nothing to the warehouse. `--assume-fit` (a new `fit_players` model setting) treats a flagged player as fit and ignores the games he's just missed.
- `players` now carries FPL's set-piece orders: `p_corners_order` and `p_direct_freekicks_order` alongside `p_penalties_order`.
- **Previous seasons as a prior.** A new once-a-season extraction step loads every player's previous Premier League seasons from FPL's `element-summary` history (`raw_player_history_past`), and the previous two seasons' Premier League goal events for their penalties. It feeds a new `player_past_seasons` model. The projection model uses a player's last season (open-play xG, xA, base BPS, defensive actions, saves, cards per 90) as the prior on his ability, trusted in proportion to his past minutes and fading as this season's evidence builds. It falls back to the price prior for players new to the league. `python projections/backtest.py --compare-priors` compares the settings.
- **Look up any manager on the My Team page.** Enter an FPL ID: managers already in the warehouse are shown straight away; new ones are fetched from the API, stored (reusing the extraction code) and shown, then refreshed by the daily pipeline. There's a saved-managers list, a refresh button, and a shareable `?manager=<id>` link. Manager dbt models are now views so new data appears immediately.
- **Expected-points projection model** (`projections/`), replacing the SQL star rating. It predicts every player's FPL points for each fixture in the next five gameweeks from:
  - team attack/defence ratings (opponent-adjusted, home advantage, shrunk towards average);
  - opponent-adjusted, shrunk per-90 player rates;
  - a minutes and availability model.
  It writes `player_rating`, `player_projection` and `team_rating`, and runs as a new `project` task after `dbt build`. The star rating is now expected points per gameweek on a 0–10 scale relative to the week: a typical regular starter is a 5 and the best projection a 10.
- **Penalties modelled as a role, not chance creation.** A new extraction step loads goal events from the Premier League's own match API, which types every goal as Goal / Penalty / Own. Combined with FPL's missed penalties, this gives a new `player_penalties` model: penalties taken per player per gameweek. The projection model then:
  - removes penalty xG from every player's and team's history, so ratings reflect open play;
  - projects penalties separately for FPL's designated takers (team's likely penalties × chance each taker is on the pitch);
  - shows them as their own "Penalties" line in the breakdown and a column on Rankings.
- **Bonus projected from BPS.** Each player's base BPS rate (BPS minus the parts from goals, assists, clean sheets, goals conceded, saves and missed penalties) plus the BPS from what the model expects in each fixture. This is run through the likely scenarios with a BPS → bonus curve learned from this season, and each match is scaled to the ~6.3 bonus points it hands out. Bonus now rises in easier fixtures and isn't inflated by penalties.
- The Rankings page shows every expected-points category that applies to the position (e.g. saves and goals conceded for goalkeepers, defensive contribution for defenders and midfielders, penalties for takers), and the columns add up to the five-gameweek total.
- Point-in-time backtest (`python projections/backtest.py`) comparing the model's predictions with actual points and with form/season baselines.
- `team_gameweek_stats` and `team_fixture_results` dbt models (team xG/xA/xGA per gameweek and per-fixture results), replacing SQL duplicated across the old rating model and the dashboard.
- `team_branding` seed (club colours and badge files keyed on FPL short name), replacing a hand-maintained `analytics.team_misc` table; `p_position_name` on `players`, replacing a hand-maintained `analytics.positions` table. The warehouse can now be rebuilt from scratch.
- `stg_gameweeks` staging model and a `join_current_season` macro shared by every staging model.
- Documentation and tests for every dbt model; `docs/rating_methodology.md` and `docs/data_model.md`.
- `ingest.py --refetch-all`, automatic creation of the `raw` schema on a fresh database, HTTP retries with back-off, logging throughout.
- Configuration through environment variables (`FPL_SEASON`, `FPL_ENTRY_IDS`, `FPL_MY_ENTRY_ID`, `FPL_DB_*`).
- pytest suite for extraction and dashboard logic, Ruff config, GitHub Actions CI (lint, tests, `dbt parse`), MIT licence.

### Changed
- Raw partitions are replaced with delete + insert in a **single transaction**, and the Airflow DAG allows one active run, so overlapping runs can't duplicate data.
- Live stats and manager picks are only requested for gameweeks whose deadline has passed (previously all 38 every run).
- Inserts use `fast_executemany`; the dashboard shares one pooled database engine.
- Manager raw tables are replaced one manager at a time in a single transaction (previously the whole table was replaced), with explicit column types, so one manager can be refreshed without touching the others.
- Every dashboard query uses bound parameters and selects players/teams by ID.
- Best XI selection moved from a large SQL query into a tested pandas function; one cached query now serves every metric.
- Shared banner, pitch and formatting components replace code duplicated across pages.
- The Airflow DAG no longer runs the test suite twice (`dbt build` already runs tests); Airflow example DAGs are disabled.
- Desktop launchers locate the project relative to themselves instead of hard-coded paths.
- Dashboard redesigned as a website: single `app.py` entry point with a top navigation bar and logo, a centred content column, page headers, white content cards, a site footer, and consistent chart styling (no in-chart titles, readable axes, club badges in fixture tables). Home adds a live deadline line and expandable top-rated lists; a new Rankings page shows every player's expected points and where they come from as a sortable, searchable table.
- Team sheets (Home's Team of the season, My Team's pitch and bench) show a shirt in each player's club colours above their name, with goalkeepers in reversed colours.
- Repository layout: `StreamLit/` → `dashboard/`, launchers → `launchers/`, `misc_sql/` → dbt `analyses/`; old archived scripts removed.

### Fixed
- The best players were under-predicted by about 1 point per game, because the model shrank every player and team towards the league average. Player xG, xA and base BPS are now shrunk towards what the player's start-of-season price implies, and team attack/defence towards what the squad's prices imply (new `p_start_price` column on `players`). Backtest: RMSE 2.78 → 2.74, rank correlation 0.44 → 0.45, and the premium-player gap falls from about 1.0 to 0.6 points per game.
- Defensive contribution ignored the opponent and assumed a plain Poisson count. Each team now has a "defensive actions allowed" multiplier (fitted like the team ratings, shrunk towards average), used both to adjust past counts and to scale each upcoming fixture, and the count follows a negative binomial. Checked on gameweeks 3–5, the chance of reaching the threshold is better calibrated (24% predicted, 25% actual, previously 23%) and the probability scores improve by 2–3%.
- Clean sheets were under-projected. The model predicted clean sheets in 22% of past team-matches when 30% happened, because (a) plain-Poisson goals ignore the uncertainty in a match's expected goals, and (b) xG has out-run actual goals this season. Goals conceded now follow a negative binomial and expected goals are scaled by the season's goals-per-xG (shrunk towards 1:1). The prediction is now 26%.
- New signings were projected as rotation risks: gameweeks before they joined (no FPL data yet) and before their debut counted as matches they didn't start. Players added mid-season are now judged from their debut (e.g. Affengruber's chance of starting went from 69% to 95%).
- Per-90 rankings (defensive actions, saves, points per 90) and the radar's per-90 scale ignored minutes played, so a short cameo could top the table. Players now need at least 25% of the available minutes in the selected range (minimum 90) to be ranked.
- The Compare page's player cards now always match in height, and each player's selector sits directly above their card.
- Team xG conceded averaged each player's own xGA, which only covers his minutes on the pitch, so every substitution dragged it down. It is now the opponent's xG in the same match.
- The Home page header was hidden under Streamlit's fixed top bar.
- Manager names were always blank (the FPL entry endpoint returns first and last name separately).
- Long stat values (records, overall rank) and news lines no longer get cut off in stat cards and club banners.
- Players named with an apostrophe (e.g. O'Riley) and **Nott'm Forest** broke the Player, Compare and Team pages.
- Goalkeeper "Saves / 90" and the radar's saves axis were inflated 90×.
- Exactly 60 minutes scored 1 appearance point instead of 2 (`player_points`).
- `stg_positions` returned every season's positions, not just the current one.
- Double-gameweek xG/xA/xGA was counted twice in the Team page's range totals.
- Blank gameweeks were skipped in the upcoming-fixtures strip instead of shown as "Blank".
- Club banners used white text on light club colours (e.g. Fulham, Leeds, Wolves).
- The first run against an empty database failed because raw tables didn't exist yet.
- `player_points`' incremental lookback (10 days) was shorter than the ingestion grace window; now 21 days.
