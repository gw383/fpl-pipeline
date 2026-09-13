# FPL Pipeline — Project Review

This covers what the project does end to end, then a set of suggestions for
where it could go next. Nothing here has been implemented — it's all
advisory. (The separate cleanup work is described in
`refactored/CHANGELOG.md`, delivered alongside this document.)

## Part 1 — What the project does, step by step

At a high level this is a small but complete data engineering pipeline: it
pulls Fantasy Premier League (FPL) data from the official API, lands it in
SQL Server, reshapes it into a proper dimensional model with dbt, and serves
it back out through a Streamlit dashboard — with Airflow tying the whole
thing together on a schedule, and two double-clickable desktop launchers so
you don't need a terminal to run any of it.

### 1. Extraction (`extraction/`) — pulling data from the FPL API

Six scripts, each responsible for one part of the FPL API, all coordinated
by `ingest.py`:

- **`main_endpoint.py`** hits the single biggest endpoint,
  `bootstrap-static`, which returns four datasets in one response:
  players, teams, positions, and gameweeks. Each becomes its own raw table
  (`raw_players`, `raw_teams`, `raw_positions`, `raw_gameweeks`).
- **`fixtures.py`** pulls the full fixture list (kickoff times, scores,
  difficulty ratings) into `raw_fixtures`.
- **`event_live.py`** is the expensive one: for every gameweek from 1 to
  38, it calls `event/<gw>/live/` to get every player's stats for that
  specific gameweek (minutes, goals, assists, bonus, xG, etc.) and
  concatenates the whole season into `raw_event_live`. This is what the
  entire "player gameweek" grain of the data model is built from.
- **`manager_profiles.py`**, **`manager_picks.py`**, **`manager_transfers.py`**
  pull data for specific FPL manager accounts (identified by an "entry
  ID") — profile summary, gameweek-by-gameweek squad picks, and transfer
  history. Currently hardcoded to a single entry ID (`146897`) in
  `ingest.py`.

Two loading patterns are used. The season-level tables (players, teams,
fixtures, gameweeks, event-live) **delete the current season's existing
rows, then append the freshly-fetched data** — so running the pipeline
again mid-season safely replaces that day's snapshot rather than
duplicating it. The manager tables instead **replace the whole table**
every run, since they only need to hold the latest pull for a small,
known list of managers, not a history.

Every ingested row is stamped with `season` (from `config.py`,
currently `"2026-27"`) and a UTC `load_timestamp`.

### 2. Orchestration (`airflow/`) — running it on a schedule

Airflow runs in Docker (via `docker-compose.yaml` — the standard
CeleryExecutor + Postgres + Redis stack, with a custom `Dockerfile` that
adds `dbt-core` and `dbt-sqlserver` to the Airflow image so dbt can run
from inside the same container).

The DAG (`airflow/dags/fpl_pipeline.py`) is three tasks in a strict chain:

```
ingest  →  dbt_build  →  dbt_test
```

`ingest` runs `python extraction/ingest.py` inside the container (the
project folder is mounted into the container at
`/opt/airflow/fpl-pipeline`). `dbt_build` and `dbt_test` then run
`dbt build` / `dbt test` from the `transformation/` folder. It's scheduled
daily at 06:00 UTC (`schedule="0 6 * * *"`).

### 3. Transformation (`transformation/`) — dbt models

This is where raw, API-shaped data becomes a clean dimensional model.
Two layers:

- **Staging** (`models/staging/`, materialized as views): one model per
  raw source, renaming columns to sensible names and — for every
  season-partitioned source — filtering down to *only the current
  season's rows*. That "current season" filter works by joining to an
  `analytics.seasons` table (today's date between that season's
  `start_date` and `end_date`). This table isn't part of the dbt project
  itself — it's assumed to already exist in the database, maintained
  outside version control.
- **Analytics** (`models/analytics/`, materialized as tables): the
  dimensional marts the dashboard actually queries — `players`, `teams`,
  `positions`, `gameweeks`, `fixtures`, and the big one, `player_stats`
  (one row per player per gameweek — the fact table everything else
  aggregates over). Column names are prefixed by table (`p_` for
  players, `pg_` for player-gameweek, `f_` for fixtures, `team_` for
  teams) which makes multi-table joins in the query layer easy to read.

dbt tests currently cover the staging layer only: uniqueness and
not-null on `player_id`, referential integrity from players to teams and
positions, and a composite-uniqueness test on (player, gameweek) in the
player-gameweek staging model.

### 4. Reporting (`StreamLit/`) — the dashboard

Two pages:

- **Home** (`Home.py`) — four columns: a "top rated players" leaderboard
  (see the star-rating explanation below), a "Best XI" pitch graphic that
  picks the highest-scoring valid formation (from 7 standard formations)
  for whichever metric you choose (points, goals, assists, xG, or
  defensive contributions), a fixture-difficulty grid for every team's
  next 5 games, and a latest-news feed.
- **Player** (`pages/Player.py`) — pick any player from a dropdown, plus a
  gameweek range filter (all / last 10 / last 5). Shows a colour-branded
  header (using each team's actual primary/secondary colours and badge,
  stored in an `analytics.team_misc` table), headline metric cards
  (points, "value", goals/assists or saves depending on position,
  defensive contributions, clean sheets — each with the player's rank
  among same-position players), and four charts: a fantasy-points
  breakdown, a radar chart of the player's stats as a percentage of the
  best in their position, a minutes-played donut, and a points-by-gameweek
  trend line.

All of the actual SQL — including the fantasy-points-scoring formula and
the "star" recommendation score below — lives in the `queries/` modules,
not in dbt. That's a meaningful design choice worth noting: the
business logic of "what counts as fantasy points" and "what makes a good
recommendation" is implemented in the presentation layer, in ad-hoc
per-page SQL, rather than in tested, version-controlled dbt models. More
on this in the suggestions below.

**The "star" recommendation score**, since it's the most complex piece
of logic in the project: each player gets a score out of 10, blended
from season-long form (their percentile rank of total points among
players who've scored any), their last 5 gameweeks' points-per-90 (with
a flat +3 adjustment, capped at 10), their team's recent results (goals
scored/conceded and league points from their last 5 games, weighted
differently for attackers vs. defenders/goalkeepers), and the average
difficulty of their next 5 fixtures. On the Player page this is a
50/25/10/15 weighted blend of those four factors; the Home page's "top
rated" leaderboard uses a related but not identical formula (see
suggestions — this is one of the more interesting findings).

### 5. Operationalisation (`app.py`, `run_pipeline.py`)

Two small Tkinter desktop apps, each packaged into a standalone
`.exe` with PyInstaller (`app.py` → `"FPL Dashboard.spec"`,
`run_pipeline.py` → `run_pipeline.spec`), so the whole thing can be
run by double-clicking rather than opening a terminal:

- **"FPL Dashboard"** starts the Streamlit server (from the project's
  venv) and opens it in your browser.
- **"FPL Pipeline"** brings up the Airflow Docker stack if it isn't
  already running, triggers the `fpl_pipeline` DAG, and opens the
  Airflow UI so you can watch it run.

### 6. Two separate database connections

Worth calling out explicitly: the pipeline (inside Docker) and the
dashboard (running directly on your machine) authenticate to SQL Server
*differently*. The pipeline uses SQL Server credentials from a `.env`
file (`FPL_DB_USER` / `FPL_DB_PASSWORD`), because the Docker container
isn't part of your Windows domain and can't use Windows-integrated auth.
The dashboard (`StreamLit/database.py`) instead uses
`Trusted_Connection=yes` — Windows-integrated auth — since it runs
directly on the same machine as SQL Server. That's a reasonable
practical choice given how the two pieces are deployed, but it does mean
there are two independent places credentials/connection logic can drift
out of sync (see suggestions).

## Part 2 — Suggestions

None of these have been actioned — this is purely a list to work from
whenever you want to.

### Functionality

**Move the business logic out of the query layer and into dbt.** The
fantasy-points formula and the "star" recommendation score are currently
implemented as raw SQL inside `StreamLit/queries/`, computed fresh on
every page load, untested, and — as noted above — implemented
*twice, slightly differently* (the Player page's per-player `get_star`
and the Home page's leaderboard `get_star_top20` use different weightings
and a different team-form calculation, so a player's "top 20" rating and
their individual star score won't necessarily agree with each other if
you cross-check them). Moving this into a dbt model (materialized once,
tested, version-controlled) would fix the inconsistency, make the scoring
logic easy to unit-test, and make every page read from one shared,
consistent number instead of recomputing it.

**Double-check `pf_goals_conceded` in `queries/player_stats.py`.** It's
computed as `-sum(floor(pg_saves / 2.0))` — derived from *saves*, not
from `pg_goals_conceded` (which exists as its own column and is queried
separately as plain `goals_conceded`). Given goalkeepers/defenders lose
points for goals conceded in real FPL scoring, this looks like it should
probably reference `pg_goals_conceded` instead. Worth checking against
the real FPL scoring rules.

**Check `threat` and `influence` on the Player page.** In
`pages/Player.py`, both variables are assigned from the query result's
`"form"` column rather than their own `"threat"` / `"influence"`
columns (which do exist in `analytics.players` and are returned by
`get_player_info`). Neither `threat` nor `influence` currently appears
to be displayed anywhere on the page, so this may be entirely harmless
today — but worth fixing before either value is wired into something
visible.

**Clean up dead computations.** Several derived stats are computed in
`Player.py` and never used anywhere: a price-adjusted points-per-90
value, plain points-per-90, assists-per-90, goals-per-90, and
clean-sheets-per-90. These were removed from the cleaned copy (see the
changelog) since they have no effect on the page — but if you originally
meant to show them (e.g. "Goals / 90" as an extra metric card), this is
a reminder that the plumbing is already there and only the display is
missing.

**Generalise beyond one hardcoded manager.** `TRACKED_ENTRY_IDS` (renamed
from an inline list in `ingest.py`) currently tracks a single FPL entry
ID. If you ever want to compare your own mini-league, or track your
whole league, this would need to become a configurable list (env var or
config file) rather than a code change each time.

**Manager tables have no history.** Because `manager_picks`,
`manager_profiles`, and `manager_transfers` all use "replace the whole
table" rather than "append with a timestamp", you only ever have the
latest snapshot — there's no way to see how a manager's rank or squad
changed over the season. If that history matters to you, switching these
to season/gameweek-partitioned appends (like the other raw tables
already do) would fix it.

**No incremental loading.** `event_live.py` re-fetches *all 38
gameweeks* from the API every single run, even though only the most
recent gameweek(s) actually changed since yesterday. This is already
listed in your own README as a future improvement — a cheap win would be
to only refetch gameweeks that are unfinished or very recent, with a
one-time full backfill for historical ones. On the dbt side, converting
the big fact models to incremental materializations (dbt's
`is_incremental()`) would avoid rebuilding the whole history as a table
every run too.

**The `analytics.seasons` table lives outside version control.** Every
"current season" filter across staging and analytics models depends on
this table existing with the right date ranges — but it's not created by
any dbt seed, model, or migration in the repo. Anyone cloning this repo
(including future-you on a new machine) can't actually build a working
database from scratch without first knowing to create this table by
hand. Turning it into a dbt seed (a small CSV of season name / start
date / end date) would make the whole project reproducible from a clean
database.

**`sources.yml` references a table that doesn't exist.** It declares
`raw_manager_history` as a source, but nothing in `extraction/` produces
a table by that name — the actual table is `raw_manager_profiles`. It's
not currently used by anything, so harmless today, but worth cleaning up
or reconciling so the source declarations match reality.

**Unify the fixture-difficulty colour scale.** `components/fixture_card.py`
(used on the Player page) uses a 5-band colour scale (one colour per FPL
difficulty rating, 1–5); `components/team_fixtures.py` (used on the Home
page's fixture grid) uses a coarser 3-band scale (easy/medium/hard). Both
are visualising the same underlying difficulty number, so a fixture that
looks "medium orange" on the Home page might look a different shade
entirely on the Player page for the same match. Worth deciding on one
scale and using it everywhere.

**Add caching to the query layer.** Every dropdown change on the Player
page re-runs several fairly complex SQL Server queries (some with window
functions over the whole player pool) with no caching. `st.cache_data`
with a short TTL on the `queries/` functions would make the dashboard
noticeably snappier without changing any behaviour, since the underlying
data only changes once a day.

**Handle empty/error states gracefully.** If a query returns zero rows
(e.g. a brand-new player with no gameweek data yet, or the database being
briefly unreachable), several places do `.iloc[0][...]` and would throw
an unhandled exception straight to the user instead of a friendly
message.

**Add automated tests.** There's currently no test coverage for the
Python ingestion logic (e.g. "does `convert_nested_to_json` correctly
flatten a dict column?") and no dbt tests at all on the analytics layer
(only staging). Given how much scoring/ranking logic lives in SQL, even
a handful of dbt tests on `player_stats` (e.g. "points per gameweek is
never negative for an unused sub") would catch regressions early.

**Consider CI.** Already on your own README's future-improvements list —
a simple GitHub Actions workflow running `dbt test` and a Python linter
on every push would catch a lot of the issues above automatically going
forward, and is a strong, easy-to-set-up portfolio signal in its own
right.

### Presentation

**Get the dashboard onto a link a reviewer can actually open.** Right
now, everything — SQL Server, Airflow, Streamlit — runs on your own
machine. That's completely reasonable for personal use, but it means
nobody else (a recruiter, a hiring manager) can see the *live* dashboard;
they can only see screenshots or a video you send them. Since the
dashboard is read-only reporting, hosting a small copy of the database
somewhere reachable (a free-tier Postgres instance, Azure SQL, even
SQLite/DuckDB for a static demo snapshot) and deploying the Streamlit app
to Streamlit Community Cloud would let you hand someone an actual URL.
This is probably the single highest-leverage change for portfolio
purposes.

**Add real screenshots to the README.** The README currently shows the
architecture and data-model diagrams, but not the dashboard itself — for
a project whose whole point is the dashboard, showing what it actually
looks like (a screenshot of Home and Player) would make a much stronger
first impression than diagrams alone.

**Clean up the README's formatting.** As currently written it has a lot
of stray blank lines, escaped characters (`\-`, `&#x20;`) and inconsistent
spacing that look like they came from pasting out of a rich-text editor.
Worth a pass to make it render cleanly on GitHub, plus adding: a "how to
run this" section (prerequisites, `.env` setup, `docker compose up`,
`dbt build`, `streamlit run`) so someone else could actually get it
running, since right now that knowledge only lives in your head.

**Fixed pixel widths throughout the dashboard.** Cards, the pitch
graphic, and the fixture grid all use hardcoded pixel widths (`width:230px`,
`width:470px`, etc.), so the layout won't adapt to a different screen
size — it'll look fine on your monitor and potentially cramped or
overflowing on someone else's. Worth revisiting with relative units if
you do end up hosting this somewhere.

**Resolve the nested git repository.** `StreamLit/` currently has its own
independent `.git` folder, separate from the one at the project root —
meaning it's effectively a second, disconnected repository sitting
inside the main one, with its own commit history that the root repo
doesn't track at all. Worth deciding whether `StreamLit/` should just be
a normal folder in the main repo (most likely what you want) or a proper
git submodule, and cleaning up whichever you don't choose.

**Drop or clearly separate the `archive/` folder and stray scripts.**
`archive/` holds older, more-verbose duplicates of every extraction
script (confirmed by diffing them — they're the same logic with
different comments/formatting), and `extraction/connection-test.py` is a
one-off diagnostic script sitting alongside the real pipeline code. For
someone browsing the repo, both currently look like they might be part
of the live pipeline when they aren't. (The cleaned copy leaves
`archive/` out entirely and renames the connection script to
`check_connection.py` — see the changelog — but your original files are
untouched either way.)

---

If it's useful, I'm happy to go deeper on any one of these — for
example, sketching out what the dbt model for the star-rating score
would actually look like, or what a minimal CI workflow would contain —
just say which one.
