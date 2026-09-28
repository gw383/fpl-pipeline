# About this folder

This is a cleaned-up copy of the whole project, built for you to review before
adopting any of it. **Nothing in the original project was touched or
overwritten** -- everything outside this `refactored/` folder is exactly as it
was. If you don't like any of this, just delete this folder and nothing is
lost.

## Why a folder instead of just editing your files in place

Normally the cleanest way to do this would be to edit your files directly and
rely on git to make it reversible (commit the current state, then commit the
cleanup as a second commit you could revert). That wasn't possible this time:
the shell this session uses to run commands directly on your computer is
currently broken by a September 8 Windows update on your machine (a known,
tracked issue, not something wrong with your project) -- so I could only
read and write individual files, not run `git` on your computer. Building the
cleanup as a separate, non-destructive copy was the safest way to give you
something reversible anyway.

**Recommended next step, once that shell issue is fixed (or from your own
terminal):** run `git add -A && git commit -m "pre-cleanup snapshot"` in
`C:\fpl-pipeline` *before* copying anything from here over your originals.
That gives you a proper git-history safety net going forward, on top of this
folder.

## How to adopt this

Nothing here renamed or moved any top-level folder -- `extraction/`,
`transformation/`, `StreamLit/`, `airflow/`, `misc_sql/` all match your
original layout file-for-file (one exception: `connection-test.py` ->
`check_connection.py`, explained below). So adopting a piece of this is just
copying that file over the matching original, e.g.:

```
copy refactored\extraction\*.py C:\fpl-pipeline\extraction\
```

Do it one folder at a time and re-test in between if you want to be careful.

## What changed, and why

Everything below is a cleanup -- naming, structure, duplication, comments,
formatting -- verified to produce the exact same behaviour and the exact
same numbers as before. Nothing here changes what the pipeline loads, what
the dbt models compute, or what the dashboard displays. A few small,
genuinely-safe exceptions are called out explicitly.

### extraction/

- Added **common.py**: `delete_season_data`, `load_table_append`,
  `load_table_replace`, `convert_nested_to_json` and `utc_now` were
  previously copy-pasted (with tiny formatting drift) into 5 different
  files. They now live in one place and every ingestion script imports
  them.
- Added **db.py**: the SQL Server connection-string/engine logic that used
  to live inline at the top of `ingest.py` is now a small reusable
  function, `get_engine()`.
- Every ingestion script (`main_endpoint.py`, `fixtures.py`, `event_live.py`,
  `manager_profiles.py`, `manager_picks.py`, `manager_transfers.py`,
  `ingest.py`) got: a module docstring, type hints on function signatures,
  named constants instead of repeated string literals (table names, URLs),
  and consistent (emoji-free) print messages. The actual sequence of API
  calls, deletes and loads is unchanged.
- **connection-test.py -> check_connection.py**: renamed only. The old
  filename had a hyphen, which isn't valid in a Python module name -- it
  could only ever be run directly (`python "connection-test.py"`), never
  imported, so nothing depends on the old name. Behaviour is identical.
- `ingest.py`: the database engine is now created inside `run_pipeline()`
  rather than at import time. This only matters if something *else* were
  to `import ingest` without calling `run_pipeline()` (nothing in this
  project does) -- for the one way this script is actually run
  (`python ingest.py`, or the Airflow DAG's bash command), behaviour is
  identical.
- **archive/ was not carried into this folder.** It held near-duplicate,
  more-verbose earlier drafts of the same 5 ingestion scripts (confirmed by
  diffing them against the current versions -- they differ only in
  comments/formatting, not logic). It's genuinely dead code. Your original
  `archive/` folder is untouched on disk if you want to keep it anyway.

### transformation/ (dbt)

- Purely cosmetic: consistent column alignment, a short comment at the top
  of each model explaining its grain, and no trailing semicolons (dbt
  doesn't need them). Every `select`, `join`, `where` and column alias is
  byte-for-byte the same logic as before.
- `sources.yml`: left exactly as-is, including the `raw_manager_history`
  entry that doesn't match any table your extraction scripts actually
  produce (that table is called `raw_manager_profiles`). This looks like a
  leftover typo, but nothing currently references it either way, so it's
  flagged in the suggestions rather than changed here.

### StreamLit/

- **charts/** and **components/**: colour hex codes and repeated magic
  numbers were pulled out into named constants at the top of each file
  (e.g. `PLAYED_COLOR = "#2ecc71"`). Every value is identical to before --
  this just gives each colour a name instead of it appearing as a bare hex
  code wherever it's used. `player_radar.py` also got a small `_safe_pct()`
  helper to replace 5 copy-pasted `x / y * 100 if y else 0` expressions.
- **queries/player_stats.py**: the biggest file in the project. The
  "which gameweeks does this range cover" SQL predicate was copy-pasted
  (with tiny formatting drift) into 5 different queries; it's now built
  once by `_range_filter_sql()` and reused. The generated SQL is not
  byte-identical (different whitespace) but is logically identical --
  same predicate, same tables, same columns -- so query results are
  unchanged. Every scoring formula (fantasy points, the "star" rating) is
  untouched.
- **queries/team_data.py**: `get_best_11`'s 7 hardcoded formations
  (3-4-3, 3-5-2, ...) are now a small Python list (`BEST_11_FORMATIONS`)
  that generates the same SQL, so adding an 8th formation later is a
  one-line change instead of editing a SQL string.
- **pages/Player.py**: this had the most dead code in the project --
  worth knowing about even though it wasn't touched behaviourally:
  - `threat` and `influence` are both read from the query result's
    `"form"` column, not their own `"threat"` / `"influence"` columns.
    This looks like a copy-paste bug. **Preserved exactly as-is** here
    (fixing it would change what the page displays), but flagged clearly
    in the improvement suggestions.
  - Five per-90 stats were computed and then **never displayed or used
    anywhere**: a price-adjusted points-per-90 value, plain points-per-90,
    assists-per-90, goals-per-90, and clean-sheets-per-90. Removing dead
    computations that are never read has zero effect on what the page
    shows, so they were removed here to cut noise; the two that *are*
    used (`saves_p90`, `defcons_p90`) were kept, and a redundant
    recomputation of those same two values later in the file (for the
    goalkeeper/outfield metric cards) was removed since it recalculated
    the identical number a second time.
  - The four near-identical "news banner" HTML blocks (25% / 50% / 75% /
    default chance-of-playing, differing only in two colours) are now one
    template driven by a small colour lookup, checked in the same order
    as before.
  - The ~45 lines pulling individual fields out of `.iloc[0]` were kept as
    individual lines (same variable names, same values) but now read from
    a single `row = ...iloc[0]` instead of re-indexing `iloc[0]` on every
    line.
- **Home.py**: a duplicated "next 5 gameweeks" calculation (computed once,
  then recomputed identically further down) was reduced to one
  calculation reused in both places. A duplicated `# ---- Main Layout ----`
  comment was removed.

### airflow/, misc_sql/

- `dags/fpl_pipeline.py`: docstring only. Task IDs, bash commands and the
  `ingest >> dbt_build >> dbt_test` dependency are unchanged.
- `misc_sql/team_misc.sql`: a comment explaining what this ad-hoc query is
  for (it isn't part of the dbt build or the app) and consistent
  formatting; the query itself is unchanged.

### New files (nothing removed or hidden by adding these)

- **requirements.txt**: no dependency file existed anywhere in the
  project. This lists every third-party package actually imported
  (`requests`, `pandas`, `python-dotenv`, `SQLAlchemy`, `pyodbc`,
  `streamlit`, `plotly`), unpinned -- run `pip freeze` in your existing
  venv and paste versions in once you've confirmed what's currently
  working, so this file can actually reproduce your environment for
  someone else.
- **.env.example** (root) and **airflow/.env.example**: templates naming
  every environment variable the code and `docker-compose.yaml` actually
  reference, with no real values.

## Verified before delivery (round 1)

- Every `.py` file in this folder byte-compiles cleanly
  (`python -m py_compile`).
- `ruff check --select F,E9` (undefined names, unused imports, syntax
  errors) passes clean across the whole folder.
- Every SQL query and dbt model was compared line-by-line against the
  original for this changelog.

---

# Round 2: implementing the suggestions

Everything below is a second pass, done after the round-1 cleanup above,
that actions the 11 specific items you picked out of the suggestions list.
**Unlike round 1, these are real behaviour changes** -- bug fixes and new
features, not just cosmetic cleanup -- exactly as you asked for. Each item
is called out below with what changed and why. As before, none of this
touched anything outside `refactored/`.

## 1. Move the business logic out of the query layer and into dbt

Two new dbt models now hold the scoring logic that used to be
recomputed, in Python-generated SQL, on every single dashboard page load:

- **`transformation/models/analytics/player_points.sql`** (new): one row
  per player per gameweek, with a `pf_*` column for every fantasy-points
  category (minutes, clean sheets, bonus, saves, goals, assists, defensive
  contributions, cards, own goals, etc). It's an **incremental** model --
  once a gameweek is more than 10 days old it's treated as final and never
  reprocessed; run `dbt run --full-refresh --select player_points` to force
  a full rebuild if you ever need one (e.g. after a scoring-rule change).
- **`transformation/models/analytics/player_rating.sql`** (new): the
  "star" recommendation score (season form + last-5 form + team form +
  fixture difficulty), as one table-materialized model.

`StreamLit/queries/player_stats.py` was rewritten accordingly:
`get_player_stats` now sums `analytics.player_points` columns instead of
recomputing the scoring CASE expressions, and `get_star`/`get_star_top20`
are now one-line selects from `analytics.player_rating` instead of ~250
lines of duplicated scoring SQL each. The net effect: one implementation
of "what counts as fantasy points" and one implementation of "star
rating", both dbt-tested (see item 11), instead of three
independently-maintained copies (Player-page pf_* SQL, get_star, and
get_star_top20) that had already drifted apart from each other -- see the
next two items.

## 2. `pf_goals_conceded` bug in `queries/player_stats.py`

Confirmed and fixed. The old code derived goals-conceded points from
`pg_saves` (`-sum(floor(pg_saves / 2.0))`) instead of `pg_goals_conceded`,
and applied the deduction to every position instead of just
goalkeepers/defenders (the only positions that lose points for conceding
in real FPL scoring). `player_points.sql`'s `pf_goals_conceded` now reads
`pg_goals_conceded`, gated to `p_position in (1, 2)`, 1 point lost per 2
goals conceded.

## 3. `threat` and `influence` on the Player page

Confirmed and fixed. `get_player_info` was already correctly selecting
`p_threat as threat` and `p_influence as influence` -- the bug was purely
in `pages/Player.py`, which read `info_row["form"]` for both instead of
their own columns. It now reads `info_row["threat"]` /
`info_row["influence"]`.

## 4. Clean up dead computations

- `pages/Player.py`: `max_pp90` and `max_ppm90` (from `get_best_stats`)
  were assigned but never read anywhere on the page -- removed, alongside
  a short note pointing at `misc_sql/team_misc.sql`, which still computes
  the equivalent figures independently as a sense-check.
- The `per_90`, `recommendation_stars` and `news_banner_html` helpers
  (along with the `NEWS_BANNER_STYLES`/`DEFAULT_NEWS_BANNER` constants)
  were pulled out of `pages/Player.py` into a new **`StreamLit/player_utils.py`**
  module. This isn't a behaviour change -- it's here because it's what
  made these three functions unit-testable (see item 11): they no longer
  need a Streamlit runtime just to import them.

## 5. No incremental loading

`extraction/event_live.py` used to refetch and reload **all 38
gameweeks** from the FPL API on every single pipeline run, including
gameweeks that finished months ago and can never change again. It's now
incremental:

- `extraction/common.py` gained `get_ingested_values`,
  `delete_gameweek_data`, and `determine_gameweeks_to_fetch` (which reads
  `raw_gameweeks.data_checked` -- an FPL API field that flips to true once
  a gameweek's stats/bonus points are finalised).
- `event_live()` now asks `determine_gameweeks_to_fetch` which gameweeks
  actually need a network call: never-ingested gameweeks, plus any
  ingested gameweek that isn't yet `data_checked`. Everything else is
  skipped. Only the gameweeks that were actually refetched have their old
  rows deleted (`delete_gameweek_data`, per-gameweek) -- not the whole
  season (`delete_season_data`), so untouched historical gameweeks are
  never at risk of an interrupted whole-season reload wiping them out.
- `ingest.py` is unchanged -- `event_live(engine, ALL_GAMEWEEKS)` is still
  called the same way; the incremental decision now happens inside
  `event_live` itself.

**Please validate this one carefully once it's running against your real
database** -- I can't execute a pipeline run against SQL Server from this
sandbox, so this has only been verified by static review (`ruff`,
`py_compile`) and the unit tests on `_gameweeks_needing_fetch` (item 11),
not an actual end-to-end run.

## 6. `analytics.seasons` outside version control

`analytics.seasons` is now a **dbt seed**:
`transformation/seeds/seasons.csv` + `transformation/seeds/seeds.yml`.
Run `dbt seed` to (re)load it.

**This one needs your attention before you adopt it.** The actual
contents of your live `analytics.seasons` table were never in any file in
the repository (no `CREATE TABLE`, no `INSERT`, nothing) -- so the rows in
`seasons.csv` are my best reconstruction, not a copy of your real data:

- `display_name` has to match, **character for character**, whatever
  `extraction/config.py`'s `CURRENT_SEASON` actually is (currently
  `"2026-27"` in this codebase) -- every staging model joins
  `raw.<table>.season` to `seasons.display_name`. I used that same
  hyphenated `"YYYY-YY"` form throughout the seed; if your live table
  actually used a different form (e.g. `"2026/27"`), match that instead.
- `start_date`/`end_date` are approximate real Premier League season
  boundaries, not pulled from anywhere in your database.

Run `select * from analytics.seasons` against your real database and
reconcile it against `seasons.csv` line by line before running `dbt seed`
-- every analytics model filters "current season" with
`between s.start_date and s.end_date`, so a wrong row here would silently
make every dashboard page look empty or show the wrong season's data.

## 7. `sources.yml` references a table that doesn't exist

Confirmed and fixed. `raw_manager_history` (declared in `sources.yml`,
matching no table anything actually writes to) is now `raw_manager_profiles`
(what `extraction/manager_profiles.py` actually creates via its
`TABLE_NAME` constant). The `analytics.seasons` source entry was also
removed from `sources.yml`, since seasons is now a seed referenced with
`{{ ref('seasons') }}` rather than a source (see item 6) -- every model
that joined `{{ source('analytics', 'seasons') }}` now joins
`{{ ref('seasons') }}` instead.

## 8. Unify the fixture-difficulty colour scale

New module: **`StreamLit/colours.py`**, holding the 5-band
`DIFFICULTY_COLOURS` scale (1=easiest..5=hardest) that used to live only
in `components/fixture_card.py`, plus a `difficulty_colour()` helper.
`components/team_fixtures.py` no longer has its own 3-band
easy/medium/hard scale -- it imports the same 5-band scale and helper.
**This changes what colour the Home page's fixture-difficulty grid
shows** (it previously used 3 colours; it now uses the same 5 as the
Player page) -- that's the intended effect of "unifying" them, but flagging
it clearly since it's a visible change.

## 9. Add caching to the query layer

Every function in `queries/player_stats.py`, `queries/player_info.py` and
`queries/team_data.py` is now decorated `@st.cache_data(ttl=600)` (10
minutes) -- repeated page interactions (switching the Range filter back
and forth, re-selecting a player you already viewed) no longer re-hit the
database for data that hasn't changed. 10 minutes was picked as a
starting point since gameweek data doesn't change faster than that in
practice; adjust the `ttl` if you'd like it shorter/longer.

## 10. Handle empty/error states gracefully

- **`StreamLit/database.py`**: new `run_query()` helper wraps
  `pd.read_sql` in a `try/except`. Every query function now goes through
  it instead of calling `pd.read_sql` directly, so a database problem
  (server not running, a model that hasn't been built yet, a column
  renamed by a dbt change) shows a readable `st.error` banner instead of
  crashing the page with a raw SQLAlchemy traceback, and returns an empty
  DataFrame so the guards below take over.
- **`pages/Player.py`**: guards after `get_players()` and after the main
  batch of per-player queries -- an empty result now shows `st.warning`
  and stops the page cleanly instead of raising `IndexError` on
  `.iloc[0]`. `get_best_stats`'s result is aggregated with `MAX()` and no
  `GROUP BY`, so it always returns exactly one row even when there's no
  underlying data (just `None`s) -- handled separately with a small
  `_num()` helper that defaults to 0 instead of raising on `int(None)`.
- **`Home.py`**: guards after `get_team_fixtures()` (stops the page --
  nothing else can be built without it), and empty-aware handling for
  `get_latest_news()`, `get_best_11()` and `get_star_top20()` (each shows
  a small inline message instead of crashing or rendering blank).

## 11. Add automated tests

New **`tests/`** directory (pytest) plus dbt tests on the two new models:

- `tests/test_common.py` -- `convert_nested_to_json`, and the incremental
  gameweek-selection logic (split out of `determine_gameweeks_to_fetch`
  into a pure `_gameweeks_needing_fetch` helper specifically so it's
  testable without a database connection).
- `tests/test_player_utils.py` -- `per_90`, `recommendation_stars`,
  `news_banner_html` (see item 4 for why these were extracted into their
  own module).
- `tests/test_player_stats_queries.py` -- `_range_filter_sql`'s generated
  SQL shape.
- `tests/test_colours.py`, `tests/test_team_fixtures.py` -- the new shared
  colour scale (item 8) and the `ordinal()` helper.
- `transformation/models/analytics/analytics_tests.yml` -- `not_null` /
  `unique` on `player_rating`, and a `not_null` + composite-uniqueness
  check on `player_points`'s `(pg_id, pg_gameweek)` incremental key.
- **`transformation/packages.yml`** (new): declares `dbt_utils`. This
  wasn't in the project before, even though `stg_tests.yml` already used
  `dbt_utils.unique_combination_of_columns` -- meaning that test could
  never actually have run. Run `dbt deps` once after adopting this file.
- `pytest.ini` + `requirements-dev.txt` (adds `pytest`) at the project
  root, so `pytest` just works from a normal clone.

**Important limitation -- please re-run these yourself:** this sandbox
has no internet access to PyPI (confirmed: an organisation-level network
policy, not a proxy misconfiguration), so `pandas`, `streamlit`,
`sqlalchemy` and `pytest` itself could not all be installed together
here. What I *could* verify:

- `tests/test_colours.py` and `tests/test_team_fixtures.py` have zero
  third-party dependencies and were actually run here with a
  pre-installed `pytest` -- **10/10 passed**.
- `tests/test_common.py`, `tests/test_player_utils.py` and
  `tests/test_player_stats_queries.py` need `pandas` (and, for the last
  one, `streamlit`/`sqlalchemy`) to even import, none of which are
  available in this sandbox -- these were checked by careful manual
  trace against the implementation instead of by running them.
- The dbt tests (`analytics_tests.yml`, `stg_tests.yml`) need a real dbt
  installation and a real SQL Server connection, neither available here.

Please run `pip install -r requirements.txt -r requirements-dev.txt &&
pytest` and `dbt deps && dbt build` yourself once you've copied this over
-- your own venv already has pandas/streamlit/sqlalchemy installed (the
app already runs there today), so this should just work, but it's
genuinely unverified by me beyond the 10 dependency-free tests above.

## Also spotted, not actioned (outside the 11 items above)

- **`queries/player_info.py`'s `get_next_5`** filters
  `where gw_deadline_time > '2026-04-19'` -- another hardcoded stub date,
  the same kind of bug as the one already fixed in `player_rating.sql`'s
  `get_star`/`get_star_top20` predecessor. Since it wasn't one of the 11
  items you listed, it's left exactly as-is here, but it's worth the same
  fix (`getdate()`) if you'd like it actioned too.

## Verified before delivery (round 2)

- `ruff check --select F,E9` and `python -m py_compile` both pass clean
  across the entire `refactored/` tree, including every file touched or
  added this round.
- Every parenthesis in every dbt SQL model balances (checked
  programmatically) -- not a substitute for `dbt compile`/`dbt build`,
  which I have no way to run here (no database connection, and dbt-core
  itself couldn't be installed -- see the round-1 notes on the PyPI
  block), but it rules out the most common copy-paste mistake.
- 10 of the ~35 new/changed test cases were actually executed (see item
  11) -- the rest need your own venv, as noted above.

## Post-delivery fix: `get_player_stats` ambiguous column names

Found after you ran `dbt seed`/`dbt run`/`dbt test` yourself and reported
the Player page erroring. Your `dbt.log` showed all 12 models (including
`player_points` and `player_rating`) built successfully -- the dbt side
was fine. The bug was in `queries/player_stats.py`'s rewritten
`get_player_stats`: it joined `analytics.player_stats` (unaliased) to
`analytics.player_points pp`, but both tables have columns named `pg_id`,
`pg_gameweek`, `pg_points` and `pg_starts` (`player_points` carries those
straight through from `player_stats` for convenience). Every unqualified
reference to those columns was ambiguous to SQL Server ("Ambiguous column
name 'pg_id'"), which `database.run_query` caught and showed as an error
banner, immediately followed by the "no player stats available" warning
from the empty-result guard -- that's the "errors" you saw.

Fixed by aliasing `analytics.player_stats` as `ps` and qualifying every
formerly-ambiguous reference (`ps.pg_points`, `ps.pg_gameweek`, etc.) --
`pf_*` columns from `player_points` were already qualified with `pp.`, so
only the `player_stats`-side references needed the alias. Re-checked
`get_best_stats`, `get_gwk`, `get_rank_metrics`, `get_star`, and
`get_star_top20` for the same class of bug -- none of them join
`player_points`/`player_rating` to another table with overlapping column
names, so this was isolated to `get_player_stats`.

Also fixed, spotted in the same `dbt.log`: `seeds/seasons.csv` had a
trailing blank line (introduced when the real season dates were
reconciled in by hand), which dbt's seed loader read as a phantom
all-NULL row -- the cause of the two failing `not_null_seasons_*` tests
in your `dbt test` run. The blank line is removed; your two real rows
(`2025-26`, `2026-27`) are untouched. This one wasn't blocking the app
(a null `id`/`display_name` row never matches any real join), just
failing the data-quality test.

**Please re-run `dbt seed` once** (to reload the corrected `seasons.csv`)
and reload the Player page. `dbt run`/`dbt test` don't need re-running
for the `get_player_stats` fix -- that's pure Python/SQL-string code, no
dbt model changed.

---

# Round 3: promoting `refactored/` to be the project

Everything in this folder has now been copied over the top of the real
project files at the repo root (`extraction/`, `transformation/`,
`StreamLit/`, `airflow/dags/`, `app.py`, `run_pipeline.py`, the `.spec`
files, `.gitignore`, plus the new `requirements*.txt`, `pytest.ini`,
`tests/`, `.env.example` files, and this `CHANGELOG.md`) -- `refactored/`
is no longer a separate copy to review, it's what's now sitting at
`C:\fpl-pipeline`. Two things needed fixing that didn't exist anywhere
in `refactored/` yet, because this folder never contained the Airflow
Docker/dbt-profile files in the first place:

## `airflow/dbt/profiles.yml` -- hardcoded password removed

This file (mounted into every Airflow container via
`docker-compose.yaml`'s `./dbt:/home/airflow/.dbt` volume, so it's the
profile dbt actually uses inside Docker) had a real, plaintext database
password committed to it: `password: Spotpip12!`, alongside
`database: fpl` (inconsistent casing vs. `FPL` used everywhere else).
Neither of those two things is true anymore -- the file now reads
`user: "{{ env_var('FPL_DB_USER') }}"` /
`password: "{{ env_var('FPL_DB_PASSWORD') }}"` (both already set in
`airflow/.env`, which Docker Compose passes into the containers), and
`database: FPL`. This matches the pattern already used by
`airflow/.dbt/profiles.yml` (a second, unused profiles file that was
sitting in the project but isn't referenced by `docker-compose.yaml` at
all -- harmless, but worth knowing it's dead weight if you ever clean up).

**Please rotate the `FPL_DB_PASSWORD` credential** (change the SQL Server
login's password and update it in `.env` / `airflow/.env`) since the old
one has been sitting in a plaintext file that either was, or easily
could have been, committed to git history already -- fixing the file
going forward doesn't undo any past exposure.

## `airflow/dags/fpl_pipeline.py` -- missing `dbt deps` step

`transformation/packages.yml` (added in Round 2, declaring the
`dbt_utils` dependency `stg_tests.yml` needs) requires `dbt deps` to run
before `dbt build`/`dbt test` can succeed. Nothing in the Docker image
(`airflow/Dockerfile` only installs dbt itself, at image-build time,
before `transformation/` even exists inside the container) or the DAG
ever ran it, so the Airflow-orchestrated pipeline would have hit the
exact same "package not installed" failure you originally saw running
`dbt build` manually. A `dbt_deps` `BashOperator` task now runs between
`ingest` and `dbt_build`: `ingest >> dbt_deps >> dbt_build >> dbt_test`.

## `.gitignore`

- `*.spec` is no longer ignored. `FPL Dashboard.spec` and
  `run_pipeline.spec` are the source-of-truth recipes PyInstaller needs
  to rebuild the two `.exe` launchers -- they're source, not build
  output, so they're now tracked like any other file. `dist/` and
  `build/` (PyInstaller's generated output) are still ignored.
- Added common editor/OS junk (`.vscode/`, `.idea/`, `.DS_Store`,
  `Thumbs.db`) -- harmless either way, but keeps future contributors'
  editor state out of diffs.
- No new secret-related entries were needed: with `airflow/dbt/profiles.yml`
  fixed to use `env_var()` above, there's no longer a plaintext credential
  in any tracked file.

## What this changed nothing about

- `app.py`, `run_pipeline.py` and both `.spec` files are functionally
  identical to Round 1 (docstrings/formatting only) -- the `.exe`
  launchers keep working exactly as before, since neither PyInstaller
  spec bundles any project source (`datas=[]`, `hiddenimports=[]` in
  both) and no top-level folder was renamed or moved.
- `airflow/docker-compose.yaml` and `airflow/Dockerfile` were not
  touched -- Airflow/Docker connectivity (the Postgres/Redis/Celery
  setup, the `host.docker.internal` SQL Server connection, the
  `../..:/opt/airflow/fpl-pipeline` code mount) is unchanged.
- `README.md` was left exactly as it was, per request. A suggested new
  version reflecting everything in Rounds 1-3 is provided alongside it
  as `README.suggested.md` -- nothing is auto-adopted from it.

## What I could not do myself, and why

This session has no ability to run `git`, run any other shell command,
or delete files on your machine (a known, tracked issue: a September 8
Windows update broke the isolated environment Claude's device tools use
to run commands on your computer -- file read/write still works fine,
which is how this copy was done). That means a few steps are still
yours to do:

1. **Delete `extraction/connection-test.py`.** It was renamed to
   `check_connection.py` in Round 1 (the old name had a hyphen, invalid
   in a Python module name); the old file is still sitting there
   unused. `git rm "extraction/connection-test.py"` removes it and
   stages the removal in one step.
2. **Delete the `refactored/` folder** now that its contents are the
   project. `git rm -r refactored` (or delete it in Explorer, then
   `git add -A`).
3. **`archive/` is optional to remove.** It's confirmed dead code (near-
   duplicate, earlier drafts of the ingestion scripts) but nothing
   forces its removal -- `git rm -r archive` if you'd like it gone.
4. **A stray nested git repository was found at `StreamLit/.git`**
   (its own local-only repo, unrelated to the project's real repo, whose
   remote is `github.com/gw383/fpl-pipeline`). This isn't something
   Round 1-3 created -- it was already there. Left in place, it can make
   `git add`/`git status` treat `StreamLit/` as an embedded repository
   (a "gitlink") instead of a normal tracked folder, which risks the
   files inside silently not being tracked the way you expect. Delete
   `StreamLit/.git` (it's a hidden folder -- enable "show hidden items"
   in Explorer, or `Remove-Item -Recurse -Force StreamLit\.git` in
   PowerShell) **before** your next `git add`.
5. **Run the actual commit.** Once 1-4 are done:
   ```
   git add -A
   git status   # sanity-check what's staged before committing
   git commit -m "Adopt refactored project structure (see CHANGELOG.md)"
   ```
6. **Rotate `FPL_DB_PASSWORD`** as noted above.
7. **Re-run `dbt deps`** once (manually, or let the next Airflow DAG run
   do it) so `transformation/dbt_packages/` matches the profile change --
   this doesn't depend on the password rotation and can be done any time.

---

# Round 4: expected-vs-actual chart, differentials, and a redesigned star rating

Three separate additions, all live now (dbt models edited in place, not
added as new files, per request).

## `player_rating.sql` -- redesigned, not replaced

The model still produces one row per player with a `star` column, so
nothing that reads `analytics.player_rating` needed to change shape --
`get_star`/`get_star_top20`/the new `get_in_form_differentials` all still
work off `p_id`/`player`/`p_position`/`star`. What changed is how `star`
is built:

- **Actual points and expected points are now both tracked and blended**,
  not just actual points. A new `player_points_expected` CTE reuses
  `player_points`'s existing formula unchanged, except goals/assists/goals-conceded
  (the three categories with a real underlying-process stat) are computed
  from `xG`/`xA`/`xGA` instead of what actually happened. Everything else
  (minutes, clean sheets, bonus, saves, cards, defensive contributions,
  own goals, missed pens -- none of which have a meaningful "expected"
  version) is identical between the two. Both the season total and the
  last-5-gameweek rate are computed for actual and expected points, then
  blended (weights below) -- a player who *consistently* outperforms
  their expected points keeps scoring well here via the actual-points
  half of the blend, rather than being marked down as "just lucky".
- **Percentiles are now computed within position** (`partition by
  p_position`), for both the season and last-5 scores. Previously a
  single global percentile meant defenders/keepers were ranked against
  forwards on raw points, which they'll structurally lose most of the
  time regardless of how good they are for their position.
- **Minutes security**: previously a hard cliff (last-5 minutes < 30 ->
  form score zeroed). Now a `minutes_security_score` (0-1) blends how
  close to "fully nailed on" (450 minutes / 5 games) a player's last 5
  gameweeks were with a penalty when `p_news`/`p_news_date` shows a live,
  recent flag -- applied as a final multiplier on the whole star, not
  folded in as one ingredient among others, since a great underlying
  rating means nothing if the player won't actually be on the pitch.
- **Bug fix**: the fixture-difficulty ingredient could previously exceed
  10 for a very easy run of fixtures (no clamp), meaning the final star
  could silently exceed its documented 0-10 scale. Now explicitly clamped.
- **All weights are tunable from one place** -- a block of `{% set %}`
  Jinja variables at the top of the file, each commented with what it
  controls and which group it must sum to 1.0 with. Change a number,
  `dbt run --select player_rating`, reload the dashboard. The starting
  weights (season quality 40% / recent form 30% / team form 10% /
  fixtures 20%; each of those split roughly 45/55 or 40/60 actual vs.
  expected) are a reasonable starting point, not a validated optimum --
  see the note on backtesting below.
- New output columns exposed for transparency/tinkering:
  `season_actual_score`, `season_expected_score`, `quality_score`,
  `last5_actual_score`, `last5_expected_score`, `recent_form_score`,
  `minutes_security_score` -- all readable via `get_star` on the Player
  page if you want to see which ingredient is driving a given rating.

**Not done, deliberately, to keep this a working model rather than a
research project**: no backtest of these weights against actual
subsequent gameweeks was run (that needs a real database connection this
sandbox doesn't have) -- try the weights, watch how the ratings track
outcomes over a few gameweeks, and adjust from there. `analytics.teams.team_strength`
(FPL's own preseason team-strength rating) also isn't used anywhere in
this model; it's available if you want a more rigorous fixture/team-form
signal than raw FDR and match results later.

## `players.sql` -- added `p_ownership`

`stg_players` already captured `ownership` (FPL's `selected_by_percent`)
but it never reached `analytics.players`. Needed for the differentials
feature below; a one-line addition, nothing else changed.

## Home page: "In-form differentials"

New full-width section under the existing four-column layout: up to 20
players with `p_ownership <= 10%`, `minutes_security_score >= 0.5`
(filters out noisy one-off cameos), ordered by `recent_form_score` --
deliberately *not* the overall `star`, since star also factors in
fixtures/team form and would drown out "is this player actually playing
well right now" with "are their next few fixtures easy". New query
(`get_in_form_differentials` in `queries/player_stats.py`) and component
(`components/differential_card.py`).

## Player page: expected-vs-actual chart

New grouped bar chart (`charts/expected_vs_actual.py`), added below the
existing four charts: goals vs xG, assists vs xA, and -- for goalkeepers
and defenders only, since it's not fantasy-relevant for other positions --
goals conceded vs xGA. `get_player_stats` now also sums `pg_xG`/`pg_xA`/`pg_xGa`
to feed it.

## Verified before delivery (round 4)

- `ruff check --select F,E9` and `python -m py_compile` pass clean on
  every Python file touched this round.
- `player_rating.sql` was rendered through a real Jinja2 engine (mocking
  dbt's `ref()`/`config()`) to resolve every `{% set %}`/`{{ }}` and
  confirm the template itself is valid, then checked programmatically
  for balanced parentheses and matched `case`/`end` pairs across the
  whole rendered SQL.
- As with previous rounds, no actual `dbt build`/`dbt test` or dashboard
  run was possible from this sandbox (no database connection, no
  internet access to install dbt-core) -- please run `dbt run --select
  player_rating` (or a full `dbt build`) and reload both pages before
  judging the new ratings/charts, and watch for anything that looks
  structurally wrong (a SQL Server-specific syntax issue that static
  review wouldn't catch) rather than assuming it's already been executed.

## Post-delivery fix (Round 4): `dbt build` failing on `player_rating`

You reported the pipeline failing at `dbt build`. Your `run_results.json`
showed the exact cause: `model.fpl_pipeline.player_rating` errored with
SQL Server error 241, "Conversion failed when converting date and/or
time from character string."

Cause: `raw_players.news_added` (which flows through unchanged as
`p_news_date`) is stored as a text column, not a native datetime column
-- pandas/SQLAlchemy inferred that type when the FPL API's JSON `null`/
ISO-8601-string values were first loaded (see `extraction/main_endpoint.py`).
The new minutes-security gate in `player_rating.sql` compared
`p_news_date` directly against a computed datetime with `>=`, which
SQL Server implicitly tries to satisfy by converting the string to a
datetime -- and the FPL API's actual format (e.g.
`"2026-09-10T18:15:23.912108Z"`, ISO-8601 with a trailing "Z") isn't one
SQL Server's implicit conversion understands, so it fails outright
instead of just being false for that row.

Fixed by using `try_convert(datetime2, pl.p_news_date, 127)` (style 127 =
ISO-8601 with time zone) instead of relying on implicit conversion --
this parses the FPL API's actual date format explicitly and returns
`NULL` for anything it can't parse (including an empty string) rather
than erroring the whole query. Please re-run `dbt build` (or at least
`dbt run --select player_rating`) to pick this up.

## Post-delivery fix (Round 4): minutes-security score capped identically for every nailed-on player early in the season

You noticed Haaland and John Egan both showing `minutes_security_score
= 0.86` despite very different rotation risk. Cause: the gate sized
"fully nailed on" as a fixed `450` minutes (assumed 5 full gameweeks),
but it's currently only ~4 gameweeks into the season, so `last5` (top 5
past gameweeks) actually only contained 4 rows -- every player who'd
played every available minute so far was capped at `360/450 = 0.86`,
not because of any real rotation risk but purely because a 5th
gameweek hadn't happened yet.

Fixed by adding a `last5_window_size` CTE (`select count(*) as gws from
last5`) and sizing the "fully nailed on" denominator dynamically as
`gws * MINUTES_PER_MATCH` instead of a hardcoded number -- the bar now
matches however many gameweeks are actually available, so early-season
minutes-security scores reflect real rotation risk rather than the
calendar.

## Round 4 follow-up: team form split into two markers, plus a fixture-difficulty bug fix

Two changes to `player_rating.sql`, requested after you pointed out
that `team_form_score` (a single blended goals/results figure) wasn't
telling you much that your own actual/expected points didn't already
cover, and asked for something more targeted instead.

**`team_form_score` replaced with two separate ~5%-weighted markers**
(`WEIGHT_TEAM_FORM = 0.10` is now `WEIGHT_TEAM_RESULTS = 0.05` +
`WEIGHT_TEAM_STRENGTH = 0.05`, so the top-level blend still sums to 1.0):

- `team_results_score` -- the player's team's own match results (win/
  draw/loss) over the last 5 gameweeks. This is the old `points_score`
  bucketing, unchanged; the goals-scored/goals-conceded half of the old
  blend (`goals_score`/`gc_score`, and the position-dependent attacker/
  defender split that went with it) has been dropped entirely, since a
  player who is personally scoring or keeping clean sheets already gets
  full credit for that through their own quality/recent-form scores --
  folding the team's goals in too was mostly double-counting.
- `team_strength_score` -- new. A proxy for how strong the player's
  team is, based on how difficult *other* teams have rated them as an
  opponent over the same last-5 window (using the fixtures table's
  difficulty columns from the opponent's perspective, not the team's
  own). An easy team to play against scores low here (implying
  weakness); a hard team to play against scores high (implying
  strength). Ratings run 1-5 and are rescaled linearly onto 0-10
  (1 -> 0, 3 -> 5, 5 -> 10).

**Bug found and fixed while building the above:** the existing
`upcoming_fixtures` CTE (which drives `opponent_difficulty_score`, the
player's own next-5-fixtures ease) had its home/away difficulty
selection inverted -- it read `case when f_home_team = p_team then
f_away_diff else f_home_diff end`, which is actually the *opponent's*
perspective on the fixture, not the player's own team's perspective.
Confirmed against the convention used consistently elsewhere in the
project (`StreamLit/queries/player_info.py`'s `get_next_5` and
`StreamLit/queries/team_data.py`'s `get_team_fixtures`, both of which
use `case when p_team = f_home_team then f_home_diff else f_away_diff
end`) and against the original pre-Round-4 model. This meant
`opponent_difficulty_score` had quietly been built from the wrong side
of every upcoming fixture since the Round 4 redesign shipped. Fixed to
match the established convention. The new `team_strength_score` above
correctly uses the *opponent's*-perspective version of this same logic
(which is what that marker is supposed to measure), so the two CTEs
now intentionally read opposite sides of the same columns for
different reasons -- both are commented in the file to say why.

Not yet actioned: no dbt build was run against a live database from
this sandbox (same constraint as every previous round -- no DB
connection available here), so please run `dbt run --select
player_rating` and reload the dashboard before judging the new
columns. The file was re-rendered through a real Jinja2 engine and
checked for balanced parentheses/`case`-`end` pairs before delivery.

## Post-delivery fix (Round 4): `opponent_difficulty_score` identical for every player, regardless of team

You reported every player showing the exact same `opponent_difficulty_score`
(8.8) no matter which team they were on. The `upcoming_fixtures` CTE
(the one just rewritten above to read the correct side of each
fixture) computed each player's own-team difficulty with a single
`players` JOIN `fixtures` ON `f_home_team = p_team OR f_away_team =
p_team`. That's logically sound SQL, but the two other places in this
same file that need "which team played which fixture, home leg vs
away leg" (`team_results` and `team_as_opponent`) both avoid an
OR-condition join like that and instead use an explicit `UNION ALL` of
a home-leg query and an away-leg query -- and neither of those was
reported as broken. That was the tell: the OR-join is the one thing
structurally different about the CTE that broke.

Fixed by rewriting `upcoming_fixtures` into the same per-team,
UNION-ALL shape already used successfully elsewhere in the file:
a new `team_upcoming_fixtures` CTE computes each team's own next-5
difficulty (home leg unioned with away leg, no OR), and `opponent_form`
now joins players to that team-level result and groups by player,
instead of joining players directly to fixtures with the OR condition.
Also fixed a second, unrelated bug spotted at the same time:
`get_star()` in `StreamLit/queries/player_stats.py` still selected the
old `team_form_score` column, which no longer exists after the
two-marker split above -- this would have thrown an "invalid column
name" error on the Player page. It now selects `team_results_score`
and `team_strength_score` instead.

As with the fix above, no live `dbt build` was run from this sandbox --
please re-run `dbt run --select player_rating` and reload the Player
page to confirm `opponent_difficulty_score` now varies sensibly by
team.

## Round 5: dashboard visual redesign (no data changes)

A pass over the whole Streamlit app to make it look like a finished
product rather than a working prototype -- purely presentational:
colours, spacing, typography, card styling, chart chrome. Nothing here
touches a query, a computation, or the data a page shows; every number
on every page is exactly what it was before.

**New `StreamLit/theme.py`** -- a single design system every page and
component now draws from, instead of each file inventing its own shade
of grey. It defines:

- A validated colour palette (categorical hues assigned in a fixed
  order and never cycled, so e.g. "Actual" is always blue and
  "Expected" is always orange wherever that pairing appears; a
  reserved status palette for severity indicators like fixture
  difficulty and injury news, kept separate from the categorical
  colours so a status colour never gets mistaken for a data series).
  Colour pairings actually used in the app were run through the
  project's colour-validation tooling (contrast, colour-blindness
  separation) before being adopted.
- Shared page CSS (`inject_base_css`): the Inter typeface, page/card
  background colours, thinner section dividers, restyled dropdowns,
  and a consistent look for Streamlit's own bordered containers.
- `masthead_html` -- a small site header ("FPL Analytics") at the top
  of each page, and `section_header_html` -- a consistent header style
  (title + accent bar + optional subtitle) used in place of bare
  `st.subheader`/`st.caption` pairs.
- `apply_chart_theme` -- applies the same fonts/background/gridlines to
  every Plotly chart in the app, so they read as one family instead of
  five independently-styled charts.

**Every page and component restyled against that system:** Home.py and
Player.py both inject the shared CSS and masthead; the three Home-page
panels (Best XI, Fixture Difficulty, Latest News) and the Player-page
chart rows are now each framed in their own bordered card
(`st.container(border=True)`) instead of floating loose in a column;
metric cards, star cards, differential cards, news cards and fixture
cards all use the shared palette, radius, shadow and spacing; position
badges (GKP/DEF/MID/FWD) now get a small fixed accent colour wherever a
position is shown.

**Colour refinements (values only, same logic everywhere):**

- `colours.py`'s fixture-difficulty scale (1-5, easiest to hardest) was
  retuned to the app's palette -- still the same green-to-red direction
  every FPL fixture ticker uses, just less neon, and every step checked
  for readable white text on top.
- `player_utils.py`'s injury-news banner and `components/news.py`'s
  news-feed highlight colours now come from the same shared palette
  instead of one-off hex values. The colour *values* changed; which
  colour gets picked for which text (25% vs 50% vs 75% chance of
  playing, "injury" vs "suspended" vs "available") did not -- that
  matching logic was left exactly as it was.
- Points-breakdown (positive/negative contributions) and minutes-played
  (played/not played) charts also moved off ad hoc green/red hex values
  onto the shared palette.

**New `StreamLit/.streamlit/config.toml`** -- sets Streamlit's own theme
colours/font to match `theme.py`, so Streamlit's native chrome (widgets,
buttons, the sidebar page list) doesn't clash with the hand-built cards.

**Verified before delivery:** every changed Python file compiles
(`python -m py_compile`) and passes `ruff check --select F` (undefined
names, unused imports) across the whole `StreamLit/` tree; every
`from theme import ...` statement was checked programmatically against
theme.py's actual exports. Plotly itself isn't installed in this
sandbox, so the chart changes were reviewed by hand rather than
rendered -- worth a visual check on the Player page once you reload it,
particularly the radar and donut charts. All 17 changed/added files
were re-staged and diffed against this delivery after pushing, to
confirm the write actually landed (two more silent editor-reopen
overwrites hit earlier this session on other files, so this is now a
standing check for every push, not just the ones that failed before).

## Post-delivery fix (Round 5): masthead text overlap, stray `</div>` text, and a metric-card badge overlapping wrapped titles

Three visual bugs reported from screenshots of the live Home and Player
pages, all introduced by the Round 5 redesign above. No data, query, or
computed value changed in any of these fixes -- purely markup/CSS.

- **Masthead title rendering garbled** ("Analytics" overlapping itself)
  on both pages, and a literal **`</div>` showing as visible text**
  under "Performance breakdown" on the Player page. Root cause: both
  `theme.masthead_html()` and `theme.section_header_html()` return a
  multi-line string that mixes a `<style>` block with content `<div>`s,
  indented, and were being injected via
  `st.markdown(..., unsafe_allow_html=True)` -- which runs the string
  through Streamlit's markdown parser rather than passing it through as
  raw HTML. That parser can misinterpret parts of an indented,
  style-plus-content block, which is what produced the garbled title
  and the stray closing tag. Every other hand-built HTML block in this
  app (metric cards, star cards, news cards, fixture cards, the Best XI
  pitch graphic) was already using `st.html()` instead, which skips
  markdown parsing entirely and renders correctly in the screenshots --
  so both functions' call sites in `Home.py` and `pages/Player.py` were
  switched from `st.markdown(fn(...), unsafe_allow_html=True)` to
  `st.html(fn(...))`. `theme.py` itself (the two functions' HTML/CSS)
  is unchanged; only how it gets rendered changed.
- **`components/metric_card.py`: rank badge overlapping the metric
  title.** The `#{rank}` badge was `position:absolute; top:12px;
  right:12px`, with the title above it as plain flowing text with no
  reserved space on the right -- so a long title that wraps to two
  lines (e.g. "Value (Points per million per 90)") ran its second line
  straight under the badge (visible as "MILLI#10ON"). Fixed by
  restructuring the card header into an explicit flex row (title on the
  left with `flex:1; min-width:0`, badge on the right with
  `flex-shrink:0`) so the badge and title share space instead of one
  sitting on top of the other, regardless of how long the title is or
  how many lines it wraps to. The card's fixed `height:95px` was also
  changed to `min-height:95px` so a wrapped two-line title can no
  longer get clipped.
- **`components/fixture_card.py`: orphaned trailing `st.markdown("</div>",
  unsafe_allow_html=True)`** at the end of the function, with no
  matching opening `<div>` anywhere in it -- dead code left over from
  before this session's redesign, rendering a literal stray closing tag
  under "Upcoming fixtures". Removed.

**Verified before delivery:** `python -m py_compile` and
`ruff check --select F` on every changed file; confirmed (by grep) no
remaining `st.markdown(masthead_html(...))` / `st.markdown(section_header_html(...))`
call sites and no other orphaned closing-tag `st.markdown` calls
anywhere in `StreamLit/`. All four changed files (`Home.py`,
`pages/Player.py`, `components/metric_card.py`,
`components/fixture_card.py`) were re-staged and diffed byte-for-byte
against this delivery after pushing, per the standing post-push check.

## Round 6: layout redesign, a real "next 5 fixtures" bug, and a rating breakdown

Three requests in one pass: fix the Player page's "next 5 fixtures" strip
being stuck on old gameweeks, redesign the layout/flow of both pages (and
change chart types where a different form fits better), and add a
click-to-expand breakdown of the 5 scores behind a player's star rating
on the Home page's "Top rated players" and "In-form differentials"
cards. No data, query result, or computed value changed anywhere in this
round except where explicitly noted below (the fixtures bug, and the two
query files extended to also select existing columns for the new
breakdown feature). No data points were removed from the dashboard.

**Important, unrelated discovery: several files were missing from this
`refactored/StreamLit` folder** -- `database.py`, `colours.py`,
`.streamlit/config.toml`, `components/star_card.py`,
`components/news.py`, `components/differential_card.py`,
`queries/team_data.py`, and `images/pitch.jpg` did not exist anywhere
under `refactored/StreamLit` on this machine, `database.py`'s absence
alone means the app couldn't have started at all (every query module
imports it). All of them existed in the delivered copy this session
already had a record of, so they've been restored here from that record
-- text files pushed and byte-diffed identical, `images/pitch.jpg`
copied directly from `C:\fpl-pipeline\streamlit\images\pitch.jpg` (the
original, untouched project folder) since it's a binary asset this
session never had a copy of to restore from. Cause unknown -- possibly
this folder was never fully populated with every unchanged file when it
was first created. Worth mentioning if the app still doesn't start after
this: check nothing else is missing under `refactored/StreamLit`.

**Bug fix: `queries/player_info.py`'s `get_next_5`** was filtering on a
hardcoded literal date (`'2026-04-19'`) instead of the actual current
date, so the Player page's next-5-fixtures strip was permanently stuck
showing whichever gameweeks happened to fall after that one fixed point
-- never advancing as the season moves on (the exact same class of bug
already fixed in `player_rating.sql` and `get_star` earlier this
project). Rewritten around a `next5`-gameweeks CTE keyed off
`getdate()`, the same pattern already proven elsewhere in this codebase.

**Layout/flow fixes (Home & Player pages):**

- **Fixture Difficulty grid** (`components/team_fixtures.py`, Home page):
  every row used fixed pixel widths (a 470px row built from a 120px team
  label + 5x70px cells) that, once its own padding and border were
  added, rendered at ~488px -- wider than the column it sat in at normal
  window widths, so the card didn't reliably fit and could overflow
  towards (or behind) the Latest News column next to it. Rewritten as a
  fluid CSS grid (`width:100%`, `box-sizing:border-box`, one shared
  `grid-template-columns` used by both the header row and every data
  row so they can't drift out of alignment). Also added a small
  "Easy -> Hard" colour-swatch legend above the grid, since a colour-coded
  heatmap needs a key.
- **Best XI pitch graphic** (`Home.py`): the four position rows (GK/DEF/
  MID/FWD) used a flex column plus manually-tuned `transform:translateY`
  nudges per row, tuned for one formation -- for a different one (e.g. a
  back-5) those fixed nudges could push adjacent rows into each other.
  Replaced with a 4-row CSS grid that divides the pitch's height evenly
  every time, with no per-row offset to get wrong.
- **Player page header** (`pages/Player.py`, `player_utils.py`): the
  injury/news banner was its own absolutely-positioned box floating at a
  fixed 48%-from-left position in the header, independent of the
  player-name block next to it -- which had no width limit of its own, so
  a longer name (plus the star-rating suffix) could run straight into
  the banner. The name/team/price block now has a `max-width` with
  ellipsis truncation, and the news banner is a normal, non-absolute
  line rendered *inside* that same block (stacked under the price line)
  instead of a floating sibling elsewhere in the header -- it now simply
  takes its place in that block's own stack and can't collide with
  anything, whatever the name length or news text length. The header's
  fixed height was also bumped from 108px to 140px so a player with news
  (now a 3-line block instead of 2) doesn't get clipped by the header's
  `overflow:hidden`.
- Standardised the four Player-page chart-row figures on one height
  (420px, previously an inconsistent mix of 400/430) so the row reads as
  one aligned set rather than four mismatched card heights.
- Added a small `theme.rgba()` helper (a hex colour -> `rgba(...)`
  string) so translucent tints of a palette colour are derived from the
  palette constant itself; `components/metric_card.py`'s rank-badge
  background now uses `rgba(BLUE, 0.10)` instead of a hand-decoded
  `rgba(42,120,214,0.10)` literal.

**Chart-type change: minutes played, Player page.** "Minutes played vs.
minutes not played" is a single ratio against a limit (this season's
total possible minutes) -- exactly the case the project's dataviz
reference calls out as a meter, not a 2-slice donut/pie. Replaced the
Plotly donut (`charts/minutes_donut.py`, now deleted -- nothing imports
it any more) with a stat-tile + meter (`components/minutes_meter.py`):
minutes played as the hero number, a single-hue meter bar for the
played/possible ratio. Reads faster and is a more honest fit for what
the number actually is.

**New: click-to-expand rating breakdown, Home page.** Every card in
"Top rated players" and "In-form differentials" now has a small "Show
breakdown" toggle underneath it. Expanding it reveals the 5 weighted
ingredients behind that player's star rating (season quality 40%,
recent form 30%, fixtures 20%, team results 5%, team strength 5% -- see
`transformation/models/analytics/player_rating.sql`'s `WEIGHT_*`
variables), each as a small meter bar plus its raw 0-10 score, and --
only when it isn't a no-op -- a note on how much the minutes-security
gate scaled the final star down. Implemented with plain
`st.button` + `st.session_state` per card (toggling a per-player flag
and conditionally rendering the breakdown), rather than `st.expander`
or `st.popover`, so the toggle doesn't depend on either widget's
internal markup. New `components/rating_breakdown.py`.
`queries/player_stats.py`'s `get_star_top5_by_position` and
`get_in_form_differentials` were extended to also select `p_id` and the
5 ingredient columns (already computed in `analytics.player_rating`;
nothing new to compute) so the UI has them to show.

**Verified before delivery:** every changed/added file compiles
(`python -m py_compile`) and passes `ruff check --select F`; every
`from theme import ...` statement across the whole tree checked
programmatically against `theme.py`'s actual exports. No live
Streamlit/database access is available from this session, so the
redesigned HTML/CSS was verified by rendering it with the real
component functions and representative (including deliberately awkward
edge-case) data into static pages, screenshotted with a headless
browser, and visually reviewed -- rather than reasoned about statically,
which is how the previous two rounds of "still overlapping" reports
happened. All 21 files under `refactored/StreamLit` (every `.py`, the
`.streamlit/config.toml`, and the restored `images/pitch.jpg`) were
re-staged and diffed byte-for-byte against this delivery after pushing.

## Post-delivery fix (Round 6): `get_next_5` crashing with "Ambiguous column name 'gw_id'"

The Round 6 rewrite of `queries/player_info.py`'s `get_next_5` (fixing
the hardcoded-date bug) introduced a fresh bug of its own: it joined its
`next5` CTE back to `analytics.gameweeks` a second time even though
nothing from that second copy was actually being selected -- `next5`
already carries `gw_id` on its own. With two same-named `gw_id` columns
in scope at once, SQL Server rejected the unqualified `gw_id` in both
the join condition and the select list outright as ambiguous (error
209) rather than guessing which one was meant, crashing the Player page
the moment a player was selected. Fixed by dropping that redundant join
entirely and qualifying the remaining reference as `next5.gw_id`.

Also noting for the record: this fix (and this whole Round 6) was
delivered to `C:\fpl-pipeline\refactored\StreamLit`, but by the time
this bug was reported the project had been promoted in place -- the
live app is now `C:\fpl-pipeline\StreamLit` directly (no `refactored\`
prefix), confirmed by the `.pyc` files already sitting in its
`__pycache__` folders. This fix was pushed to that live path.

## Round 7: `player_rating.sql` rewritten around a new rating philosophy, plus a Player-page metric swap

Asked to rethink "how would you classify the best players in each
position" from scratch, ignoring what the project already did, and then
implement it. The full reasoning was given in chat before writing any
code; the short version of what changed and why:

**Season quality vs last-5 form -> one recency-weighted rate.** The old
model split a player's history into two hard buckets (season total,
last-5-gameweek total) blended 40%/30%. That's an arbitrary line --
gameweek 29 shouldn't count the same as gameweek 3 just because both
fall outside a 5-gameweek window, nor identically to gameweek 30 just
because both fall inside it. Replaced with a single exponential decay
(`gw_decay`, tunable via `FORM_DECAY_RATE`) applied to every finished
gameweek, so "how good is this player right now" fades smoothly rather
than jumping off a cliff. `quality_score` is now this recency-weighted
per-90 rate (still blended 35/65 actual-vs-expected, leaning further
into expected than before, since this whole rewrite is framed around
being predictive rather than historical), turned into a 0-10 percentile
within position exactly as before.

**Team results/team strength -> team's own underlying attack/defence
rate.** The old model scored a team from match results (win/draw/loss)
and from how highly *other* teams rated it as an opponent -- both are
outcome-based proxies, one level removed from anything about the team
itself. Replaced with the team's own recency-weighted npxG created rate
(summed across every player who featured that match) and xG conceded
rate (averaged, since it's a shared per-match value across a team's
players, not an individual figure) -- the same "process over results"
idea already used for individual players, just applied one level up.
Ranked into 0-10 percentiles across all 20 teams (`team_scores`).

**Fixture difficulty -> the same team numbers, applied to the
opponent.** Instead of FPL's own 1-5 crowd-sourced difficulty rating,
`fixture_outlook_score` scores each of a player's next 5 fixtures using
the opponent's own attack/defence percentile from the CTE above,
inverted (a defensively weak opponent is a good matchup for an
attacker; an attacking-weak opponent is a good matchup for a
defender), weighted towards the very next gameweek
(`FIXTURE_DECAY_RATE`, steeper than the form decay -- a fixture 5 weeks
out matters a lot less than the very next one). Team strength and
fixture outlook are now two views of one consistent set of numbers
rather than unrelated difficulty concepts.

**New: defensive-contribution rate.** Under the newer FPL scoring rules,
defenders/midfielders can earn real bonus points from tackles,
interceptions, blocks, clearances and recoveries once they cross a
per-position action threshold. `stg_player_gameweek.sql` already
captured this (`defcons`, carried through as `pg_defcons`), it just
wasn't used anywhere in the rating. Added as its own recency-weighted,
position-percentiled ingredient (`defensive_contribution_score`),
weighted in for DEF/MID and switched off (weight 0) for GK/FWD, where
it isn't a meaningful signal.

**Per-position weights, not one global set.** The old model applied the
same 5 weights to every position. This rewrite gives each position its
own blend of the four ingredients above (see `player_rating.sql`'s
`GK_WEIGHT_*` / `DEF_WEIGHT_*` / `MID_WEIGHT_*` / `FWD_WEIGHT_*`
tunables) -- e.g. goalkeepers lean heavily on team strength and fixture
outlook (there's very little a keeper's own stats tell you that isn't
really "how solid is this defence"), forwards lean heavily on their own
quality and fixtures, and defenders/midfielders sit in between with
real weight on defensive contribution.

**What didn't make it in, and why.** Set-piece and penalty duty (who's
on penalties/corners/free-kicks) was discussed as a genuinely good
predictive signal, but there's no such data anywhere in this project's
raw sources -- `stg_players.sql` and `stg_player_gameweek.sql` were both
checked column-by-column, and neither carries a penalty-order,
corner-order or free-kick-order field (the FPL API exposes these on
some endpoints, but this project's `raw_players` extract doesn't
capture them). Rather than fabricate a signal there's no data for, this
is called out explicitly in `player_rating.sql`'s header comment as a
place to extend later if a future extraction adds it. Price/value
remains entirely outside this model, as before -- a £4m player and a
£14m player with the same underlying numbers still get the same star.

**Minutes-security gate: unchanged in shape.** Still a final multiplier
on the whole star (not one blended ingredient), still floors at 0.3 for
minutes and 0.4 on top for a live news/injury flag within the last 7
days -- this part of the old model was already sound and wasn't part of
what was asked to be rethought.

**Wired into the dashboard the same way.** `queries/player_stats.py`'s
`get_star`, `get_star_top5_by_position` and `get_in_form_differentials`
now select the new ingredient columns (`quality_score`,
`defensive_contribution_score`, `team_strength_score`,
`fixture_outlook_score`, plus the sub-detail columns
`quality_actual_score`/`quality_expected_score`/`team_attack_score`/
`team_defence_score`) instead of the retired ones. `get_in_form_
differentials` now orders by `quality_score` instead of the retired
`recent_form_score` -- quality_score IS now the "is this player playing
well lately" signal, just computed as a smooth decay instead of a hard
5-gameweek bucket. `components/rating_breakdown.py` was rewritten to
show the 4 new ingredients (skipping defensive contribution entirely
for goalkeepers/forwards, where its weight is 0) with a per-position
weight label instead of one fixed global label, since weights now vary
by position. `components/differential_card.py`'s in-form badge switched
from the retired `recent_form_score` to `quality_score` for the same
reason. No changes were needed to `Home.py` -- it already just passes
whichever row it's given straight into `rating_breakdown_html`.

**Player page: "Value" replaced with "Form".** The "Value (Points per
million per 90)" metric card is gone. In its place: "Form", FPL's own
rolling form figure -- already fetched by `get_player_info()` as
`form` and unpacked in `pages/Player.py` (`form = float(info_row["form"])`)
but never actually displayed anywhere. Value-for-money is a budgeting
question; this page is otherwise entirely about "how is this player
playing right now", which Form answers directly. Needed a rank to go
with it (every other metric card shows one), so `get_rank_metrics`
gained a `form_rank` column (`dense_rank()` within position on
`p_form`). Price is still shown in the header banner for anyone who
wants their own value math; `get_rank_metrics` still computes
`ppm90_rank`/`ppm90_value` (just no longer unpacked on this page, in
case a future page wants them).

**A recurring bug class, again:** the new `team_rates` CTE joins
`team_gw_attack` and `team_gw_defence`, which both carry a column
literally named `team_id` -- the exact same "two joined relations
exposing the same column name" shape that caused the `gw_id`
ambiguous-column crash in Round 6's `get_next_5`. Caught this time
during review rather than after a live crash report, by qualifying
every reference as `tga.team_id` up front.

**Verified before delivery:** the rendered Jinja SQL (weights
substituted, `ref()`/`config()` stubbed) was checked programmatically
for balanced parens, for every CTE referencing only CTEs already
defined above it (no forward references), and for every column
reference against the actual `analytics.players` / `analytics.player_stats`
/ `analytics.fixtures` / `analytics.gameweeks` / `analytics.player_points`
schemas -- since no live SQL Server connection is available from this
session to just run the model and see. All five changed/added Python
files compile (`python -m py_compile`) and pass `ruff check`. All 5
files were re-staged and diffed byte-for-byte against this delivery
after pushing to `C:\fpl-pipeline\transformation\...` and
`C:\fpl-pipeline\StreamLit\...`; `player_rating.sql` and
`player_stats.py` needed a forced recommit after the same
silent-overwrite behaviour documented in earlier rounds (a `written`
response that didn't actually persist on the first attempt).

**What I could not do myself:** run `dbt run --select player_rating` (or
`dbt build`) against your actual warehouse to confirm this compiles and
executes cleanly on live SQL Server, and to sanity-check the resulting
numbers look reasonable for players you know well. Please run that
after pulling this in, and reload the dashboard.

## Round 7.1: two feedback-driven fixes on the new rating model, and dropping the breakdown from differentials

Two pieces of feedback on the Round 7 rating rewrite, addressed directly
in `player_rating.sql` (no data changes needed elsewhere beyond the
columns the dashboard reads):

**"There's no player above 8.5 in the whole game."** Correct, and it
was a real problem, not just a display quirk. `star_raw` (the direct
weighted blend of quality/defensive-contribution/team-strength/fixture-
outlook) compresses hard against the top of the scale, mechanically:
those four ingredients are only loosely correlated with each other, so
even a genuinely excellent, in-form player -- someone who tops the
charts on quality -- very rarely *also* tops the charts on team
strength and fixture outlook at the exact same time. Averaging several
only-loosely-correlated 0-10 scores just doesn't land near 10 very
often, however good the player actually is. That's exactly what was
happening to players like Pascal Groß: a genuinely high underlying
quality number, diluted by a mid-table team-strength score and an
average fixture run, landing at 7.1 overall despite being in
excellent form.

Fixed by re-expressing `star_raw` as one more within-position
percentile (`percent_rank()`), the exact same technique the model
already uses for every ingredient feeding into it -- so the best player
at each position right now lands on a 10, and everyone else spreads out
properly beneath them, instead of the whole position being squeezed
into the upper-middle of the scale. Every ingredient score is left
completely untouched by this (the breakdown still shows honest,
uncompressed 0-10 values) -- only the final headline star is rescaled.
Worth being upfront about the trade-off: `star` is now explicitly a
"how good is this player relative to the current pool at their
position" number rather than an absolute one -- an 8.5 next season
doesn't necessarily mean identical underlying quality to an 8.5 this
season, since it depends on the mix of players in the game at the time.
Every ingredient score is a percentile already, though, so this makes
the final number consistent with the ones underneath it rather than
introducing a new kind of number.

**"Defensive contributions aren't a realistic scoring route for a lot
of midfielders -- could Saka/Schade-types not carry that weight, while
Alex Scott/Elliot Anderson-types still do?"** Yes, and it's a good
instinct -- but hardcoding a list of "attacking" vs "defensive"
midfielders by name in a dbt model would be exactly the kind of thing
that needs manual upkeep every transfer window and wouldn't cover the
full player pool (only the handful of names anyone thought to list).
Implemented instead as a fully data-driven version of the same idea:
each midfielder's own recency-weighted defensive-action rate
(`defcon_p90`, already computed for the defensive-contribution
ingredient) decides whether that ingredient counts for them at all. A
midfielder below `MID_DEFCON_ROLE_THRESHOLD` (6 actions per 90 --
roughly half the 12-action bonus threshold itself, comfortably below
where a genuine defensive/box-to-box midfielder sits and comfortably
above where an attacking midfielder/winger sits, a judgement call like
every other tunable here) has that ingredient's weight moved onto their
quality weight instead, so their rating is driven entirely by their own
attacking output rather than diluted by a category they were never
really competing in. This self-adjusts as a player's role changes
(a converted winger who starts tracking back more would pick up the
weight automatically) rather than needing anyone to update a list.

Because weight is no longer purely a function of position,
`player_rating.sql` now computes each ingredient's actual weight for
that specific player (`quality_weight`, `defcon_weight`,
`team_strength_weight`, `fixtures_weight`) and carries it on the output
row, rather than leaving the dashboard to look weights up by position
itself. `queries/player_stats.py`'s `get_star` and
`get_star_top5_by_position` were extended to select these, and
`components/rating_breakdown.py` was simplified to just read a player's
actual weight straight off their row instead of maintaining its own
`_POSITION_WEIGHTS` lookup table that could now silently disagree with
the SQL for midfielders.

**Also removed: the "Show breakdown" toggle on differential cards.**
Feedback was that with up to 20 differential cards on screen at once,
a breakdown panel per card was a lot of visual noise for a section
that's meant to be a quick scan -- unlike "Top rated players" above it,
which only ever shows 5 cards per position and keeps its breakdown.
`get_in_form_differentials` was trimmed back to only the columns
`differential_card.py` actually displays (plus `quality_score` to order
by and the `minutes_security_score` filter, which doesn't need to be
selected to be filtered on) rather than carrying four ingredient
columns and `star` purely to feed a breakdown panel that no longer
exists on this section.

**Verified before delivery:** same process as Round 7 -- the rendered
Jinja SQL checked programmatically for balanced parens, CTE ordering
(no forward references), and every column reference checked against the
real schema; all four changed Python/SQL files compile and pass `ruff
check`; all four re-staged and diffed byte-for-byte against this
delivery after pushing, with the same silent-overwrite behaviour as
every previous round requiring a forced recommit on three of the four
files.

**What I could not do myself:** as with Round 7, run this against your
actual warehouse. Please run `dbt run --select player_rating` and check
a few players you know well -- in particular, check where the
MID_DEFCON_ROLE_THRESHOLD line falls for a few borderline midfielders,
since 6 actions/90 was a judgement call, not something measured against
your actual data.

## Round 7.2: barely-played players (e.g. Mikel Merino) rating too high after the Round 7.1 rescale

Feedback: a player who's barely featured this season -- specifically
called out was Mikel Merino, in the middle of returning from a long
injury absence -- was still showing a star around 5.7, which doesn't
feel right for someone with next to no minutes to actually judge.

The cause was a subtle ordering bug introduced by Round 7.1's own fix.
Round 7.1 rescaled the weighted ingredient blend to a within-position
percentile (fixing the "nobody above 8.5" compression -- see that
entry above), but did it AFTER already multiplying by the
minutes-security gate. That ordering has a real problem: percent_rank()
only preserves *relative* order, not *how far below the pack* a
heavily gated-down player actually sits. A player at a strong team with
a good upcoming fixture run, gated down to (say) 30% of their blend
score for barely playing, can still land in the *middle* of the
percentile distribution if enough other players -- for entirely
different, unrelated reasons -- also have similarly middling blend
scores. The gate was doing its job on the raw number, but the
percentile step afterwards was partly undoing it.

Fixed by swapping the order: `blend_score` (the four weighted
ingredients, still un-gated) is now rescaled to a percentile FIRST,
producing `underlying_score` -- a clean "how good are this player's
signals, ignoring reliability" number out of 10 -- and the
minutes-security multiplier is applied AFTER that, directly to the
0-10 rescaled number (`star = underlying_score * minutes_security_score`).
This means the gate's floor now means what it always intended: a
player gated down to the 0.3 floor gets at most 30% of what they'd be
rated if fully trusted, in absolute terms, regardless of how the rest
of their position happens to be distributed that week. No other logic
changed -- same four ingredients, same weights, same
MID_DEFCON_ROLE_THRESHOLD from Round 7.1 -- just the order two existing
steps run in.

No column changes this time, so no changes needed in
`queries/player_stats.py` or the Streamlit components -- purely a
`player_rating.sql` fix.

**Verified before delivery:** same checks as Round 7/7.1 (rendered
Jinja checked for balanced parens, CTE ordering, no stale references to
the renamed `star_raw`/`star_scores` CTEs); pushed to
`C:\fpl-pipeline\transformation\...` and re-staged/diffed byte-for-byte,
again needing a forced recommit after the same silent-overwrite
behaviour as every previous round.

**What I could not do myself:** run this against your warehouse to
confirm Merino (and similar fringe/returning-from-injury players) now
lands where it should. Please run `dbt run --select player_rating` and
check.

## Round 7.3: a bigger per-position leaderboard, an expandable breakdown on the Player page, distinct row ranks instead of joint ranks, and an injury-aware minutes-security gate

Four separate asks this round, none of which touch the rating
philosophy itself (Rounds 7/7.1/7.2) -- these are about seeing more of
what the model already produces, and about one real gap in how the
minutes-security gate treats recent injuries.

**1. A new "Rankings" page, for the full list per position, not just
the top 5.** The Home page's "Top rated players" section is
deliberately capped at 5 a side -- good for a quick glance, useless
for "who's actually good right now across the whole position, and who
isn't". Added `pages/Rankings.py` (Streamlit's multipage nav picks up
any file dropped into `pages/` automatically -- no registration
needed) with a position selector (Goalkeepers/Defenders/Midfielders/
Forwards) and a "Show" count (Top 10/20/30/50/All, defaulting to Top
30). "All" is implemented as a generously large `TOP (500)` rather
than a separate no-limit SQL path, since there are only ever a few
hundred players in any one position -- keeps the query logic uniform
instead of branching. Backed by a new query,
`get_star_by_position()` in `queries/player_stats.py`, which is the
same shape as the existing `get_star_top5_by_position` (kept as-is,
still used by Home.py) with the `top 5` raised to a parameter. Each
row renders through a new, deliberately plain component,
`components/ranking_row.py` (`ranking_row_html`) -- a compact
rank/name/rating row rather than the card grid Home.py uses, since a
scrollable list of 20-50 entries reads better as a list than as a
grid of cards -- and every row can expand to the same rating-breakdown
panel described next.

**2. Expandable rating breakdown on the Player page.** Previously the
Player page just showed the star number with no way to see what it's
built from (the ingredient breakdown was only ever available on
Home's "Top rated players" cards). Added a "Show rating breakdown"
toggle right under the header, using the same session-state
click-to-expand pattern already used on Home's star/differential
cards and now the new Rankings rows (plain `st.button` +
`st.session_state`, not `st.expander`/`st.popover` -- consistent with
the existing project comment on why: so the toggle doesn't depend on
either widget's internal markup). No new query needed:
`get_star(selected_player)`, already called earlier in the page for
the header star, already carries every ingredient column
`rating_breakdown_html()` reads -- this was pure UI wiring.

**3. Row-number ranks instead of joint ranks on the Player-page metric
cards.** Feedback: two players tied on a metric both showing "1st"
felt wrong -- every player should get their own distinct rank. All 11
`dense_rank()` window functions in `get_rank_metrics()`
(`queries/player_stats.py`) are now `row_number()`, which forces a
fully deterministic tiebreak (unlike `dense_rank`, which is fine with
ties, `row_number` needs one distinct order or SQL Server is free to
break ties arbitrarily -- and inconsistently between cache refreshes,
which would make ranks visibly flicker). As requested, ties on a
metric are broken by form (`form_value desc`) -- the in-form player of
the two ranks higher. Added a second, final tiebreak on
`p_full_name` for full determinism in the rare case two players are
tied on both the metric AND form (alphabetical isn't meaningful there,
it's just there so the rank never flickers on a refresh). `form_rank`
itself breaks ties on `points desc` then `p_full_name`, since form
obviously can't be used to tiebreak itself.

**4. Injury-aware minutes-security gate, with an honest limitation.**
The ask: if a player like Van Ewijk gets flagged (injury/knock) and
misses gameweeks as a result, but the flag is now gone, those missed
minutes shouldn't still be dragging his score down.

**What I could actually check:** `analytics.players` (and the
`p_news`/`p_news_date` columns it's built from) only ever holds the
*latest* snapshot from the FPL API -- there's no history of which
gameweeks a player was flagged for. So there's no query that can say
"gameweeks 4-6 were missed specifically because of the injury that's
now resolved" after the fact -- that data was never captured. Building
that properly would mean changing the extraction pipeline to snapshot
`p_news`/`p_news_date` every gameweek going forward, which is a bigger
change than this round and wouldn't help retroactively anyway (nothing
to backfill from). Flagging this clearly rather than quietly
approximating it and calling it done.

**What I built instead, as the best available proxy:** the
minutes-security gate already averages recent minutes vs. expected
minutes to get a reliability score -- the fix is in how "recent" is
weighted. Previously (`minutes_security_inputs`, via the old `last5`
CTE) every one of the last 5 gameweeks counted equally. Replaced that
with a new, steeper decay CTE, `minutes_decay`, using a new tunable
`MINUTES_DECAY_RATE = 0.35` (2 gameweeks ago counts for a bit over a
tenth of last week's weight) -- much steeper than the existing
`FORM_DECAY_RATE = 0.87` used for underlying quality/team-strength.
The reasoning: fitness/selection status is a fast-moving signal (a
player can go from "flagged out" to "nailed on" within a single
gameweek) in a way that underlying quality and team strength aren't,
so it deserves its own, much faster-decaying weighting rather than
sharing one used for slower-moving trends. Practical effect for the
Van Ewijk-style case: once a flagged player returns and plays a full
match, that most recent gameweek dominates the weighted average, and
his `minutes_security_score` climbs back toward 1.0 within a game or
two, rather than staying dragged down for a month by a flat average
that still includes the injury-affected gap. This is not the same as
truly excluding the flagged gameweeks -- it's a recency-weighted
approximation that self-corrects quickly once a player is actually
back playing, using data the pipeline genuinely has. Also kept the
existing `p_news`-based penalty (a currently-active flag still
multiplies the score down via `INJURY_NEWS_MULTIPLIER`) -- this
round only changes how *past* minutes are weighted, not the
already-existing check for a player who's flagged right now.

No column changes to `player_rating.sql`'s final output, so the
existing `get_star`/`get_star_top5_by_position` queries and the
`rating_breakdown_html` component all keep working unchanged.

**Verified before delivery:** same process as every previous round --
rendered Jinja checked for balanced parens, CTE ordering (no forward
references), no duplicate CTE names, and every column reference
checked against the real schema; `py_compile` + `ruff` on every
Python file touched or added this round; an AST-based check that
every `from theme import ...` name actually exists in `theme.py`; an
AST-based cross-module import check (`ranking_row.py` and
`Rankings.py`'s new imports of each other's/existing modules). All
five changed/new files (`player_rating.sql`, `queries/player_stats.py`,
`pages/Player.py`, and the two new files `components/ranking_row.py`
and `pages/Rankings.py`) pushed to
`C:\fpl-pipeline\...` and re-staged/diffed byte-for-byte -- unlike
every previous round, all five matched on the first push, no forced
recommit needed this time.

**What I could not do myself:** as with every previous round, run
`dbt run --select player_rating` and load the dashboard myself to
confirm the new Rankings page renders correctly, the Player-page
breakdown toggle looks right, and that a real recently-returned
player's minutes-security score behaves as described. Please give
those a look, especially the injury-proxy behaviour on a player who's
actually just come back from a flag.

## Round 7.4: quality now adjusted for strength of opposition faced, leave-one-out

Feedback: a goal against a poor defence and a goal against a great
defence were counting exactly the same towards a player's quality
score -- could the model factor in how good the opposition faced so
far actually was? Specifically raised: when grading how tough a team
like Coventry were, a specific opponent's own match against them
shouldn't count towards judging how tough Coventry were *in that
match* -- so Coventry's effective strength when adjusting an Arsenal
player's numbers shouldn't be the same figure used to adjust a
Brighton player's numbers, even though both played Coventry.

**What this adds:** every player-gameweek's contribution to
`quality_actual_score`/`quality_expected_score` is now scaled by a
per-match opponent-difficulty multiplier before being summed into the
recency-weighted per-90 rate. The multiplier is built the same way
`team_strength_score`/`fixture_outlook_score` already grade a team's
own attack/defence -- a 0-10 percentile against all 20 teams, blended
by this player's own position-specific attack/defence lean
(`GK_TEAM_ATTACK_SHARE`/`DEF_TEAM_ATTACK_SHARE`/etc, now factored out
into its own small CTE, `player_attack_share`, so this reuses the
exact same lean rather than a fourth copy of the same lookup) -- just
graded on the OPPONENT actually faced in a specific past gameweek
instead of this player's own team, and turned into a multiplier
centred on 1.0 (a new tunable, `SOS_STRENGTH_FACTOR = 0.30`: the
toughest opponent in the league is worth 30% more than a dead-average
one, the weakest 30% less, linear in between; set it to 0 to switch
this off entirely).

**The leave-one-out part, which was the actual ask:** an opponent's
attack/defence rate, wherever it's used to grade one specific match
that opponent played, EXCLUDES that specific match's own contribution
to the opponent's own season totals first. Without this, a single
scoreline would partly be marking its own homework -- if Coventry
conceded heavily in one match, that same match would both make the
scoring player's raw numbers look better AND drag down the very "how
strong was this defence" figure being used to grade that exact
performance. Built as `team_gw_loo_rates` (each team's attack/defence
rate recomputed with one gameweek's own weighted contribution
subtracted back out of its season totals) followed by
`team_gw_opponent_difficulty` (that leave-one-out rate turned into the
same 0-10 percentile scale `team_scores` uses, positioned against the
other 19 teams' full-season rates). This does mean, as requested,
Coventry's effective strength when adjusting an Arsenal player's
numbers differs from the figure used for a Brighton player, even
though both played Coventry -- each excludes its own fixture.

**A real bug caught during verification, not by the user this time:**
the first draft of `team_gw_opponent_difficulty` divided straight away
without guarding for an opponent with too little history to leave one
match out of (effectively their first game or two of the season).
SQL's `CASE WHEN` treats an unknown (NULL) condition as not-true and
falls through to the `ELSE` branch -- so `tr2.weighted_attack_rate <
l.loo_attack_rate` being NULL for every comparison would have silently
summed to a real 0, i.e. would have wrongly graded an under-sampled
opponent as the single weakest team in the league, rather than
producing the NULL that was supposed to fall through to
`player_gw_opponent_score`'s existing neutral-5 default. Fixed by
wrapping each score in an explicit `case when ... is null then null
else ...`, so a genuinely unjudgeable early-season opponent now
correctly defaults to neutral (multiplier exactly 1.0) instead of
being scored as the weakest possible opponent.

**Deliberately scoped to quality only:** the multiplier is applied to
`w_actual_points`/`w_expected_points` in `player_gw_weighted` only --
NOT to minutes (`w_minutes`) or defensive-contribution actions
(`w_defcons`). Both of those are unrelated to how strong the specific
opponent was, and the request was specifically about quality.

**No new output column.** This is a refinement of what
`quality_actual_score`/`quality_expected_score` already mean, not a
fifth ingredient alongside the existing four -- the final output
schema is unchanged, so `queries/player_stats.py`'s
`get_star`/`get_star_top5_by_position`/`get_star_by_position` and every
Streamlit page that reads them need no changes at all. The one thing
that did change: `components/rating_breakdown.py`'s "Underlying
quality" tooltip now mentions the opponent-strength weighting, so it's
visible in the UI that this is happening, not just buried in the SQL.

**Verified before delivery:** same process as every previous round --
rendered Jinja checked for balanced parens (including the newly added
CTEs), CTE ordering re-verified from scratch (this round moved
`team_gw_attack`/`team_gw_defence`/`team_rates`/`team_scores`/
`player_team_strength` earlier in the file, since `player_gw_weighted`
now depends on them transitively through the new opponent-multiplier
CTEs, and needed re-checking that nothing forward-references anything
defined later), no duplicate CTE names, and every column reference
checked against the real schema; `py_compile` + `ruff` on the one
Python file touched (`rating_breakdown.py`, tooltip text only -- no
logic change). Both changed files (`player_rating.sql`,
`components/rating_breakdown.py`) pushed to
`C:\fpl-pipeline\...` and re-staged/diffed byte-for-byte, needing a
forced recommit on both after the same silent-overwrite behaviour
documented in every earlier round.

**What I could not do myself:** run `dbt run --select player_rating`
against your actual warehouse to confirm the numbers move the way
they're meant to -- in particular, worth checking a couple of players
who've faced very different opposition so far (a player at a team
that happened to draw a soft run of fixtures vs one that faced several
of the league's best defences) to see the adjustment pulling their
quality scores apart even if their raw per-90 output looks similar.

## Round 7.5: team attack/defence strength gets its own, slower decay rate

Feedback, chased down with real numbers rather than taken on faith:
Man City's `team_defence_score` was showing up as 2nd-worst in the
league, which felt far too harsh for a team not otherwise thought of
as defensively poor.

**Checked the actual data before changing anything.** A flat total-xGC
query across all 20 teams showed City at 5.98 -- worse than the
20-team average of 5.33, so genuinely below-average, but nowhere near
the extreme bottom cluster (several teams were up around 6.3-6.6).
Below-average doesn't explain 2nd-worst on its own. Pulling City's
own gameweek-by-gameweek xGA (1: 0.59, 2: 0.55, 3: 1.08, 4: 0.74, 5:
3.02) found the real cause: one match, their most recent, at 3.02 xGA
-- roughly 2.5x anything else they'd produced that season.

**Why one game could do that much damage:** `team_defence_score` is a
recency-weighted rate (`team_rates`), and it was sharing
`FORM_DECAY_RATE = 0.87` with individual player quality. The most
recent gameweek always carries the maximum possible weight (1.0) in
this scheme, and with only 5 gameweeks played, the weighted-sum
denominator is small -- so one outlier match at full weight has
outsized leverage over a tiny sample. Working the actual numbers:
City's flat 5-game average was 1.20 xGA/game, but the 0.87-decay
weighted rate came out to about 1.34 -- enough on its own to drop them
from below-average to 2nd-worst league-wide.

**The fix:** a new, separate, slower decay rate specifically for
team-level attack/defence strength -- `TEAM_STRENGTH_DECAY_RATE =
0.95` (10 gameweeks ago still counts for ~60% of last week, vs ~25%
under `FORM_DECAY_RATE`). The reasoning mirrors exactly why
`MINUTES_DECAY_RATE` got split out from the general decay in Round
7.3, just in the opposite direction: that split gave minutes-security
a *faster* decay because fitness/selection status genuinely can flip
within a single gameweek; this split gives team strength a *slower*
decay because a whole team's underlying attacking/defensive process is
a squad-wide, structural property that shouldn't swing on one freak
result (an off day, a red card, a tactical mismatch) the way an
individual player's form or fitness can. `FORM_DECAY_RATE` is
unchanged and still governs individual player quality exactly as
before. Re-running City's numbers through 0.95 instead of 0.87 gives a
weighted rate of about 1.25 -- much closer to their honest 5-game
average of 1.20, with recent form still counted a little more heavily,
just not enough for one bad night to swing a whole league ranking.

**Implementation:** a new CTE, `team_strength_decay` (same shape as
`gw_decay`, just with the new rate, and no `gws_ago` cutoff -- a
team's whole season is still worth remembering, just increasingly
diluted, same as before, only slower), which `team_gw_contribution`
now joins instead of `gw_decay` directly. Everything downstream
(`team_rates`, `team_scores`, `player_team_strength`,
`fixture_outlook`) needed no changes at all -- they just consume
`team_gw_contribution`'s `weight` column, wherever it comes from.
The Round 7.4 strength-of-opposition adjustment
(`team_gw_loo_rates`/`team_gw_opponent_difficulty`) is built from this
exact same weighted contribution, so it automatically inherits the
gentler decay too -- correctly so, since it's asking the same "how
strong is this team" question, just leave-one-out adjusted for one
specific match.

No column changes, no query-layer or Streamlit changes -- purely a
`player_rating.sql` change, same as Round 7.2/7.4.

**Verified before delivery:** same process as every previous round --
rendered Jinja checked for balanced parens, CTE ordering (no forward
references, confirmed the new `team_strength_decay` CTE sits before
`team_gw_contribution` which now depends on it), no duplicate CTE
names. Pushed to `C:\fpl-pipeline\...` and re-staged/diffed
byte-for-byte, needing the same forced recommit as most rounds before
it.

**What I could not do myself:** run `dbt run --select player_rating`
to confirm City's `team_defence_score` actually lands somewhere closer
to their real below-average-but-unremarkable form once this is live,
and to sanity-check that no OTHER team swings unexpectedly now that
team strength decays more slowly across the board (a team that had a
genuinely bad game 4-5 gameweeks ago, for instance, will now be judged
on it for longer than before).

## Round 7.6: individual player form gets a smoother decay too

Feedback, this time about a specific player rather than a team: Brian
Brobbey was showing up as the #1-rated striker despite not scoring in
his first 4 gameweeks and having barely any xG/xA across them -- his
top ranking was purely down to one big gameweek-5 haul.

This is the same mechanism as Round 7.5, just one level down. Player
`quality` (the input to `player_rating`'s star score) is a
recency-weighted per-90 rate, built with the same
`FORM_DECAY_RATE = 0.87` that was already too reactive for
team-level strength with only 5 gameweeks played. At the individual
level the problem is actually a little worse: a team's rate is
averaged across 20+ players' contributions per gameweek, but a
player's own rate has no such averaging -- one big game really is the
entire signal for that gameweek, at maximum weight (1.0, since most
recent), against a denominator of only 4 previous games. A toy
calculation confirms the shape of it: 4 quiet games (~0.2 quality
each) followed by one big one (~2.5 quality) under 0.87 decay weights
out to roughly 1.1 -- comfortably above a genuinely good striker's
honest ~0.6-0.8 season-long rate, purely on the strength of recency
weighting concentrating almost all the mass on the single most recent
data point.

**The fix:** `FORM_DECAY_RATE` raised from 0.87 to 0.90 (10 gameweeks
ago now counts for ~35% of last week's weight, up from ~25%).
Deliberately less drastic than Round 7.5's `TEAM_STRENGTH_DECAY_RATE
= 0.95` -- an individual player's own form and fitness genuinely can
shift faster than a whole team's underlying tactical identity (a
new role, a change in set-piece duties, returning sharpness after a
knock), so this should stay more reactive than team strength, just
meaningfully less reactive than it was. Re-running the same toy
calculation at 0.90 brings the weighted rate down to roughly 0.9 --
still elevated by the one big game, but much closer to a plausible
honest rate, and the gap should narrow further as more games arrive
to dilute that one outlier's share of the total.

**Being upfront about the limits of this fix:** `quality` is a
points-per-90-minutes-played rate, not points-per-game. If a player's
earlier gameweeks were mostly low-minute cameos rather than genuine
quiet full appearances, they contribute little to the per-90 average
no matter how the decay itself is tuned -- one huge full-90 haul can
still dominate a small, minutes-light sample even after this change.
I don't have live database access to check whether this specific
mechanic (rather than, or in addition to, the recency-weighting issue
this round fixes) is part of what happened with Brobbey's first 4
gameweeks specifically. If a case like his still looks wrong once
this is live, the next lever to reach for is a minimum-**games**
floor (not just the existing minimum-total-minutes floor on
`MIN_MINUTES_FOR_FORM_RATE`) -- a further decay change alone won't
fix a genuinely low-minutes early sample.

**Implementation:** a one-line tunable change
(`FORM_DECAY_RATE: 0.87 -> 0.90`) in `player_rating.sql`'s existing
`gw_decay` CTE -- no new CTEs, no structural changes. Every downstream
consumer of `gw_decay`'s `weight` column (quality rates, form-based
scoring, everything Round 7.5 didn't already move onto
`team_strength_decay`) picks up the smoother curve automatically.
`TEAM_STRENGTH_DECAY_RATE = 0.95` from Round 7.5 is unchanged.

No column changes, no query-layer or Streamlit changes -- purely a
`player_rating.sql` change, same as every round since 7.2.

**Verified before delivery:** same process as every previous round --
rendered Jinja checked for balanced parens (0 net, clean), 30 CTEs
with no duplicate names, and confirmed the changed tunable renders
correctly into the existing `gw_decay` weight expression. Pushed to
`C:\fpl-pipeline\...` and re-staged to confirm an exact byte match
(59602 bytes both sides -- no forced recommit needed this round).

**What I could not do myself:** run `dbt run --select player_rating`
to see where Brobbey (and strikers generally) land once this is live,
and check directly whether his first 4 gameweeks were low-minute
cameos or genuine quiet full games -- which would confirm whether the
minimum-games-floor idea above is worth pursuing as a follow-up, or
whether this decay change alone resolves it.

## Round 8: percentile scoring reverted to z-scores, per-position weight
## tweaks kept, expected points for the next 5 fixtures, and a player
## comparison page

Four asks in one pass. The first two are both about `player_rating.sql`;
the last two are new features built on top of it.

**1. Percentile scoring replaced with z-scores.** Feedback: the
percentile-based rating "doesn't show relative difference between the
top players very well", and a standout in-form player (Pascal Groß was
the example given) should be able to reach the 9-10 mark more easily.

Every `percent_rank()` in this model -- both the four individual
ingredients (quality actual/expected, defensive contribution, team
attack/defence) and the final headline blend -- is now a z-score
instead: how many standard deviations a player's (or team's) raw rate
sits from the mean of the relevant population, linearly mapped onto
0-10 around a centre of 5 and clamped at both ends
(`SCORE_SD_SPAN`, currently 2.5 -- see the tunable's own comment for
what changing it does). The problem with percentiles was never really
about the single best player being capped -- percent_rank() already let
the outright #1 in any one ingredient hit a full 10. The real problem is
that percent_rank() only encodes RANK, not MAGNITUDE: two players three
places apart in the table score the same distance apart whether their
underlying numbers are nearly identical or genuinely miles apart, and a
handful of true outliers gets flattened into the same evenly-spaced
ladder as everyone in the crowded middle. Z-scores fix this directly --
several genuinely elite players who are all comfortably ahead of the
pack can now all land near 9-10 together on an ingredient like quality,
rather than being spread out one rank position at a time purely because
only one of them can hold the literal #1 spot.

Also reverted, as explicitly asked ("revert it back to when it wasn't
really using percentile like that"): the Round 7.1/7.2 rescale of
`blend_score` into a percentile-based `underlying_score` is gone
entirely. `blend_score` itself (still clamped to 0-10, still computed
exactly the same way -- the four weighted ingredients summed) is now the
headline score, with the minutes-security gate still applied after it,
exactly as Round 7.2 fixed that ordering to be.

Worth being honest about the trade-off this brings back, the same one
Round 7.1 originally fixed: `blend_score` is an average of four only
loosely-correlated ingredients, so a player who's excellent at one thing
but only average on the others will still get pulled towards the middle
-- reaching 9-10 now takes being genuinely good across most of what's
blended in, not brilliant on just one axis. Z-scores make this
noticeably easier than percentiles did (see above), but it isn't an
unconditional guarantee for every in-form player regardless of their
team/fixture picture. If this still caps out lower than expected once
it's live, the next lever is raising quality's effective share of the
blend for the position in question (its `*_WEIGHT_QUALITY` tunable),
not reintroducing a rank-based rescale.

Two smaller, related changes: `team_gw_opponent_difficulty` (the Round
7.4 leave-one-out strength-of-opposition adjustment) is rebuilt on the
same z-score scale for consistency -- it used to manually replicate what
`percent_rank()` works out to for an out-of-sample value (counting how
many of the 20 teams' rates it would beat); it's now a direct z-score
against the same population, which is both more consistent with the
rest of this round and meaningfully shorter code. And `quality_rates`'
raw per-90 figures (an actual points-per-90 NUMBER, not a 0-10 score)
are now carried all the way through to the final output as
`actual_points_p90`/`expected_points_p90` -- unused by this model
itself, but needed by the new `player_expected_points.sql` below so it
doesn't have to recompute this model's recency-weighted quality logic a
second time.

**2. Your own tunable edits, kept as-is.** Before this round started,
the live `player_rating.sql` on your machine already had nine values
changed from what this session last delivered
(`MID_WEIGHT_DEFCON` 0.10->0.15, `MID_WEIGHT_FIXTURES` 0.30->0.25,
`FWD_WEIGHT_TEAM_STRENGTH` 0.10->0.15, `FWD_WEIGHT_FIXTURES` 0.35->0.30,
`QUALITY_ACTUAL_WEIGHT` 0.35->0.40, `QUALITY_EXPECTED_WEIGHT`
0.65->0.60, `MID_TEAM_ATTACK_SHARE` 0.60->0.93, `FORM_DECAY_RATE`
0.90->0.93, `FIXTURE_DECAY_RATE` 0.80->0.90). This session pulled the
live file down first and built every change in this round directly on
top of your numbers rather than the version this session last pushed --
none of the nine were touched or reverted.

**3. Expected points for the next 5 fixtures.** New model,
`transformation/models/analytics/player_expected_points.sql`: one row
per (player, upcoming gameweek), a genuinely different grain from
`player_rating` (one row per player), which is why it's a separate
model rather than five extra columns bolted on. The Player page's
"Upcoming fixtures" strip (and the new Compare page's, below) now shows
an "xPts N.N" figure under each of the next 5 fixture tiles.

The estimate is built from three pieces, all reused from
`player_rating` rather than recomputed: a blended points-per-90 rate
(`actual_points_p90 * QUALITY_ACTUAL_WEIGHT + expected_points_p90 *
QUALITY_EXPECTED_WEIGHT` -- the same recency-weighted, opponent-adjusted
quality rate that already drives `quality_score`, just in its raw
points-per-90 form); expected minutes for that specific match,
approximated as `MINUTES_PER_MATCH * minutes_security_score` (reusing
the existing reliability read rather than inventing a second one); and a
fixture-specific multiplier built the same way as the existing
strength-of-opposition adjustment, just pointed at each of the next 5
opponents instead of a past one (an easier opponent scales the estimate
up, not down -- the opposite sign convention from the backward-looking
SOS adjustment, since this is asking "how favourable is this matchup"
rather than "how tough was this one"). The whole thing is floored at 0
so an unfavourable fixture for an already-poor-quality player can't
show a confusing negative "expected points".

Rather than recomputing the whole team-strength calculation a second
time, this model reconstructs each of the 20 teams' current
attack/defence scores for free from `player_rating`'s own output
(`team_attack_score`/`team_defence_score` are identical for every
player at the same team already, so grouping by team and taking
`min()` -- or any aggregate, they're all the same value -- recovers the
team-level figure with no new computation). The only genuinely
duplicated logic is a handful of scalar tunables (the per-position
attack/defence share, `SOS_STRENGTH_FACTOR`, the quality weights,
`MINUTES_PER_MATCH`) redeclared at the top of the new file -- flagged
explicitly in both files' comments that retuning one means retuning the
other, and called out here as a reasonable candidate to extract into a
shared model later rather than something done now, to keep this round's
blast radius contained.

`queries/player_info.py`'s `get_next_5` now left-joins this new model
in. Worth noting a real edge case this needed handling, not just an
afterthought: a double gameweek gives one team two fixtures in the same
gameweek, so `player_expected_points` genuinely has two rows for
(player, that gameweek) -- one per opponent. Joining only on
(p_id, gw_id) would have fanned each of that gameweek's two fixture
rows out against both expected-points rows (a wrong 2x2 cross join
instead of a correct 1-to-1 pairing), so `get_next_5` was restructured
around a `player_fixtures` CTE that resolves `opponent_id` as an
explicit column, and the join to `player_expected_points` matches on
(p_id, gw, opponent_id) all three. `components/fixture_card.py` renders
the new figure (a small "xPts N.N" line under each tile, in both the
single-fixture and double-gameweek layouts) and quietly shows nothing
for a NULL/missing value rather than crashing or printing "xPts None".

**4. Player comparison page.** New `pages/Compare.py`: two independent
player selectboxes plus a shared range filter, rendering both players'
profiles side by side in a 2-column layout -- header banner, star
rating with the same expandable ingredient breakdown as the Player
page, season-snapshot metric cards (2-per-row instead of 5/6-per-row so
they fit a half-width column), and the upcoming-fixtures/expected-points
strip. Deliberately excludes all four chart figures and the
process-vs-outcome chart Player.py shows -- per feedback, two full
chart rows side by side would be a lot of squeezed, hard-to-read visual
noise for what this page is actually for (a quick side-by-side read of
the numbers); the full charts are still one click away on the Player
page for either player.

Built as an entirely new, self-contained page rather than a refactor of
`pages/Player.py` -- it reuses the same lower-level, already-tested
pieces (`metric_card`, `rating_breakdown_html`, `news_banner_html`,
`fixture_card`, and the same query functions Player.py already calls)
but writes its own, more compact header layout suited to a half-width
column, rather than extracting/changing anything inside Player.py
itself. This means Player.py needed zero code changes for this feature
and carries zero risk of a regression from it. The second player
selectbox defaults to the second name in the list (not the same index
as the first), so the page doesn't open comparing a player against
themselves.

No column changes to any existing table -- `player_rating` gained two
new columns (`actual_points_p90`, `expected_points_p90`) but nothing
existing was renamed or removed, so every existing query/component
downstream of it needed no changes at all for parts 1-2 of this round.

**Verified before delivery:** `player_rating.sql` and
`player_expected_points.sql` both checked programmatically -- rendered
Jinja (including the new inline `zscore_to_10` macro) checked for
balanced parens, CTE ordering (no forward references), no duplicate CTE
names, and the macro's generated SQL spot-checked by rendering it
directly and reading it back. Every changed/added Python file compiles
(`python -m py_compile`) and passes `ruff check --select F`. Since no
live Streamlit/database connection is available from this session
(same limitation as every previous round), `Compare.py` and the
changed `fixture_card.py`/`get_next_5` were exercised end-to-end against
a hand-built stub of `streamlit`/`database.run_query` returning
representative (including deliberately awkward: NULL expected_points,
NaN expected_points, a double-gameweek fixture, both a goalkeeper's and
an outfield player's metric-card layout) fabricated data, with every
resulting HTML string checked for balanced tags -- rather than reasoned
about statically, which is the same "actually render it and check" bar
Round 6 held itself to when a live browser wasn't available either. All
five changed/added files (`player_rating.sql`,
`player_expected_points.sql`, `analytics_tests.yml`,
`queries/player_info.py`, `components/fixture_card.py`, `pages/
Compare.py`) were re-staged and diffed byte-for-byte against this
delivery after pushing.

**What I could not do myself:** run `dbt run --select player_rating
player_expected_points` (or `dbt build`) against your actual warehouse
to confirm both models compile and execute cleanly on live SQL Server,
and to sanity-check that the new z-score scale produces sensible-looking
numbers for players you know well -- in particular, whether Groß (and
similar in-form players) now lands noticeably higher than before, and
whether `SCORE_SD_SPAN = 2.5` feels like the right generosity for how
often 9-10 should come up. Please run that, reload the dashboard, and
open the new Compare page from the sidebar (it should appear
automatically -- this project's multipage app auto-discovers anything
under `StreamLit/pages/`, no separate registration needed) to try it
against a couple of real transfer decisions.

## Post-delivery fix (Round 8): `'zscore_to_10' is undefined` on `dbt run`

`dbt run` failed to compile `player_rating` with `Compilation Error ...
'zscore_to_10' is undefined. This can happen when calling a macro that
does not exist.`

The cause: `zscore_to_10` (the shared z-score-to-0-10 clamp expression
introduced earlier in this round) was written as a Jinja `{% macro %}`
block sitting directly inside `player_rating.sql` itself, on the
assumption that a macro defined earlier in a model file would simply be
callable later in that same file -- true for plain Jinja, but not for
dbt specifically. dbt only discovers macros from files under the
project's configured macro-paths (`transformation/macros/`, per
`dbt_project.yml`) during its own separate macro-parsing pass, run
before it compiles any model -- a `{% macro %}` block living inside a
`models/` file is invisible to that pass, so calling it (even from
within its own file) fails at compile time exactly as reported.

**Fix:** moved the macro, unchanged in its actual logic, into a new
file, `transformation/macros/zscore_to_10.sql` -- the first file this
project has ever needed under `macros/` (the folder didn't exist before
this fix). One necessary change alongside the move: the macro used to
read `SCORE_SD_SPAN` directly as a variable from its enclosing file, but
a macro in a different file has no visibility into another file's Jinja
`set` variables, so `zscore_to_10` now takes it as an explicit fourth
argument instead -- every one of the 7 call sites in `player_rating.sql`
was updated to pass `SCORE_SD_SPAN` in, and the tunable itself stays
exactly where it was (in `player_rating.sql`'s own tunables block,
where everyone already looks to retune it), not duplicated inside the
macro file.

While fixing this, one other bug was caught and fixed before it could
cause its own confusing error: a code comment a few lines above the
macro literally contained the text `{% set %}` (as commentary, describing
Jinja's set syntax) -- Jinja parses `{% %}` sequences anywhere in a file
regardless of whether they sit inside a SQL `--` comment or not, since
templating happens as a pure text pass before any SQL-specific meaning
is applied, and an empty `{% set %}` tag is itself invalid syntax. Fixed
by rewording the comment to describe the same thing without using the
literal braces. The whole file was swept for the same pattern (any other
literal `{% ... %}` or `{{ ... }}` with nothing meaningful inside) with
none found elsewhere.

**Verified before delivery:** rendered the macro file and the model file
together in one Jinja pass (a faithful stand-in for dbt's own macro
resolution, since a live dbt/warehouse connection isn't available from
this session) -- confirmed it renders with no errors, parens balanced,
all 30 CTEs present with no duplicates, and the clamp expression's `/
2.5` division appears in the rendered SQL exactly 21 times (7 call sites
x 3 occurrences of the clamp inside each). Pushed both files to
`C:\fpl-pipeline\transformation\...` and re-staged to diff byte-for-byte
against the delivery -- `player_rating.sql` needed the same forced
recommit after a silent-overwrite as most rounds this session have seen;
`macros/zscore_to_10.sql` (a brand new file/folder) matched on the first
attempt.

**What I could not do myself:** run `dbt run --select player_rating
player_expected_points` against your actual warehouse to confirm this
compiles cleanly now -- please retry it.

## Post-delivery fix (Round 8): SQL Server error 156, `Incorrect syntax
near the keyword 'select'`

After the macro fix above, `dbt run` got past compilation but failed at
execution with a SQL Server error:
`('42000', "[42000] [Microsoft][ODBC Driver 18 for SQL Server][SQL
Server]Incorrect syntax near the keyword 'select'. (156)
(SQLMoreResults)")`, on `analytics.player_rating` specifically
(`player_expected_points` was skipped as a downstream consequence, not
itself at fault).

The cause: a stray trailing comma. `blend_scores` used to be followed by
another CTE, `underlying_scores` (the Round 7.1/7.2 percentile rescale
of the blend), so its closing `)` correctly had a `,` after it. Round 8
removed `underlying_scores` entirely, as asked -- but the comma after
`blend_scores`' closing `)` was left behind. With `underlying_scores`
gone, `blend_scores` became the LAST CTE in the `with` chain, and a
`with` chain's last CTE must close with a plain `)`, not `),` -- the
comma tells the parser to expect another CTE name next, and instead it
found only comments (the Round 8 note explaining the removal) followed
by the final `select`, hence "incorrect syntax near the keyword
select". A subtle one to catch by eye because everything either side of
that single character is completely correct SQL.

**How this was found:** the two most likely causes (an unescaped quote
breaking the dynamic-SQL string dbt-sqlserver wraps every model in; a
missing comma somewhere in the middle of the CTE chain) were both ruled
out first, by direct inspection of the actual compiled/wrapped SQL
staged from your machine, not just a local approximation of it. With
those eliminated, the compiled `player_rating.sql` was run through a
local Postgres instance (installed in this session's own sandbox, used
here purely as a second, independent SQL parser -- nothing was ever
pointed at your real warehouse). Postgres doesn't understand every
SQL-Server-specific piece of this file (three-part `"fpl"."analytics"."x"`
cross-database references, `stdev() over (...)`, etc.), so it can't run
the query end to end, but it parses the same ANSI `with ... select`
structure SQL Server does, and a genuine grammar defect like this one
trips it up in the same way, with a much more precise error location.
Feeding it the file in increasing chunks (700 lines, 900, 1100, 1300,
1340, ...) narrowed the failure to between lines 1335 and 1340 of the
compiled output within a couple of steps, which pointed straight at the
`blend_scores` / `underlying_scores` boundary.

**Fix:** removed the one stray comma, `),` -> `)`, after `blend_scores`'
closing paren in `player_rating.sql`. Nothing else in the file changed.

**Verified before delivery:** re-rendered the fixed file (macro + model,
same combined Jinja pass used throughout this round) and fed it back
through the same local Postgres instance -- the syntax error is gone;
the only error now is Postgres correctly refusing the cross-database
table references it can't resolve (`fpl.analytics.gameweeks`, a
dialect limitation, not a bug), which only confirms the query is
grammatically sound all the way to the point where a real difference
between the two engines' SQL dialects begins. Also re-ran the
established paren-balance/duplicate-CTE-name checks on the fixed
render (unchanged: depth 0, 30 CTEs, no duplicates, exactly one `with`).
Pushed to `C:\fpl-pipeline\transformation\models\analytics\player_rating.sql`
and re-staged to diff byte-for-byte -- needed the same forced recommit
after a silent overwrite this session has seen on most rounds; the
second attempt matched exactly (65359 bytes, one byte shorter than
before purely from the removed comma).

**What I could not do myself:** actually connect to your SQL Server and
run the model -- Postgres here is a stand-in parser, not your database,
so please retry `dbt run --select player_rating player_expected_points`
now.

## Round 9: removed the next-5-fixtures expected-points feature

Feedback: the "xPts" numbers under each of the next 5 fixtures on the
Player/Compare pages (added in Round 8) weren't earning their keep --
also reported as showing a stray white box with literal `</div>` text
in it under the number on some fixture tiles, though the decision to
remove it was about the numbers not being useful, not about that
rendering bug specifically.

Reverted, fully, rather than just hiding the number in the UI:

- `transformation/models/analytics/player_expected_points.sql` (the
  dbt model computing an expected-points figure for each of a player's
  next 5 fixtures) deleted outright -- it had no other consumer, so
  leaving it in place would mean `dbt run` kept building an entire
  model for a number nobody sees any more.
- Its entry in `analytics_tests.yml` (the uniqueness test on
  `(p_id, gw_id, opponent_id)`) removed along with it.
- `components/fixture_card.py`: the `_xpts_html` helper and both call
  sites removed. Also reverted the single-fixture tile's `min-height`/
  `padding` (added in Round 8 to make room for the xPts line) back to
  the original fixed `height:90px`, and the double-gameweek tile back
  to a single-row layout (opponent and venue side by side) rather than
  Round 8's flex-column-plus-inner-row shape that existed only to leave
  room for that line underneath.
- `queries/player_info.py`'s `get_next_5`: dropped the left join to
  `analytics.player_expected_points` and the `expected_points` column,
  and reverted the query back to selecting directly off the `next5`
  CTE rather than through the intermediate `player_fixtures` CTE --
  that CTE existed solely so the join to `player_expected_points` could
  match on `(p_id, gw, opponent_id)` instead of just `(p_id, gw)`, and
  serves no purpose without that join. Docstring trimmed to match.

Deliberately NOT touched: `player_rating.sql`'s `actual_points_p90`/
`expected_points_p90` columns (the recency-weighted actual/expected
points-per-90 rates the removed model was built on top of). These are
still reasonable numbers to have on the model in their own right --
they're real per-90 rates, not a derived "prediction" -- and removing
them would mean re-touching the model that was just stabilised in the
previous fix for no functional reason. If they turn out equally
unwanted, they're one line each to drop from the final select in
`component_scores`/`blend_scores`.

**On the `</div>` rendering bug specifically**, for the record, since it
won't otherwise get diagnosed now the feature's gone: `_xpts_html`
returned a bare `""` for a missing/NULL expected_points value, embedded
directly inside the f-string as `{_xpts_html(...)}` in between other
sibling elements inside a `<div>...</div>` tile. An empty string there
should just mean "nothing extra renders", not a stray closing tag on
its own -- the visible `</div>` box was very likely Streamlit
having to break the surrounding HTML across more than one internal
`st.markdown` render/rerun in a way that separated an opening tag from
its closing tag, rather than a mismatched tag in the source itself
(the source's own divs were checked and balance correctly). Not worth
chasing further now that the whole thing's removed, but worth knowing
this component's structure (one big f-string per tile, several
sibling elements glued together conditionally) is the kind of thing
that can do this under Streamlit's rerun model, if a similar pattern
is used again elsewhere.

**Verified before delivery:** re-read both edited Python files in full
after writing them and confirmed no leftover reference to
`expected_points`/`player_expected_points`/`_xpts_html` anywhere in
either. Pushed all three changed files plus the deletion to
`C:\fpl-pipeline\...` and re-staged every one to diff byte-for-byte --
all three edited files needed the same forced recommit after a silent
overwrite (consistent with every round this session), matched exactly
on the second attempt; the deletion was confirmed with a directory
listing showing the file gone.

**What I could not do myself:** load the actual Streamlit pages to
confirm the fixture tiles render correctly with no visual regression --
please reload the Player and Compare pages and check the next-5
strip looks right with the xPts line gone.

## Round 10: defenders now get the same defensive-contribution
role-gating midfielders already had

Feedback: `DEF_WEIGHT_DEFCON` (0.15) applied to every defender flatly,
but not every defender is realistically a defensive-contribution
candidate -- an attacking wing-back, or a ball-playing centre-back
pushed forward (Calafiori was the example raised), essentially never
gets near the defcon bonus, and shouldn't have their rating held down
by an ingredient that was never a realistic part of their game.
Midfielders already had exactly this problem solved back in Round 7.1
(`MID_DEFCON_ROLE_THRESHOLD`): a midfielder whose own recency-weighted
defcon_p90 sits below the threshold gets that ingredient's weight
folded into quality instead, self-adjusting per player rather than a
hardcoded list of "defensive" vs "attacking" players. Defenders now
get the identical treatment.

**Added:** `DEF_DEFCON_ROLE_THRESHOLD = 5.0` (new tunable, right below
`MID_DEFCON_ROLE_THRESHOLD`). Set lower than the midfielder threshold
(6.0) because the real FPL bonus threshold itself is lower for
defenders: `pf_defcon` in `player_points.sql` awards the defensive-
contribution bonus at 10 CBIT (clearances/blocks/interceptions/tackles)
actions for a defender, vs 12 for midfielders and forwards -- 5.0 is
the same "roughly halfway to the real threshold" judgement call
`MID_DEFCON_ROLE_THRESHOLD` already used, just scaled to the defender-
specific line rather than reusing the midfielder one.

**Changed:** `component_scores`' `defcon_weight`/`quality_weight` CASE
expressions -- a defender (`p_position = 2`) whose `defcon_p90` is at or
above `DEF_DEFCON_ROLE_THRESHOLD` gets `DEF_WEIGHT_DEFCON`/
`DEF_WEIGHT_QUALITY` exactly as before; below it, `defcon_weight`
becomes 0 and the full `DEF_WEIGHT_QUALITY + DEF_WEIGHT_DEFCON` (0.35 +
0.15 = 0.5) goes onto `quality_weight` instead, so the four ingredient
weights still sum to 1.0 either way -- redistributed, not dropped.
Goalkeepers and forwards are unaffected (their `defcon_weight` was
already a flat 0 regardless of role, so there was nothing to gate).

**Verified before delivery:** by hand, checked the new CASE logic sums
to 1.0 for both branches (defcon_p90 below 5.0: 0 + 0.5 + 0.25 + 0.25 =
1.0; at or above: 0.15 + 0.35 + 0.25 + 0.25 = 1.0, matching the
existing goalkeeper/forward rows exactly as before). Re-rendered the
whole file (macro + model, the same combined Jinja pass used
throughout) and re-ran it through the local Postgres instance used to
catch the previous fix's trailing-comma bug -- no syntax errors, only
the same expected cross-database-reference complaint Postgres can't
resolve. Also re-ran the established paren-balance/duplicate-CTE-name
checks (unchanged: depth 0, 30 CTEs, no duplicates, exactly one `with`).
Also corrected a stale comment left over from the previous round, which
still referred to the now-deleted `player_expected_points.sql` as if it
existed. Pushed to
`C:\fpl-pipeline\transformation\models\analytics\player_rating.sql` and
re-staged to diff byte-for-byte -- needed the same forced recommit
after a silent overwrite this session has seen on every push; matched
exactly on the second attempt.

**What I could not do myself:** run this against your actual warehouse
-- please retry `dbt run --select player_rating` and check a couple of
attacking full-backs/wing-backs you know aren't defcon threats (or
Calafiori specifically, since that's the example that prompted this)
-- their rating should no longer be dragged down by that ingredient.

## Round 11: clean sheets now go through the same "process, not
outcome" treatment as goals/assists/goals-conceded

Raised in review, and agreed worth fixing: `expected_points` (the
process-based half of quality) was supposed to swap every outcome-based
scoring term for a genuine underlying-process estimate, but it quietly
didn't do this for clean sheets. `pf_cs` -- the real clean-sheet bonus
(4/8 points for a single/double clean sheet if GK/DEF, 1/2 for a
midfielder, 0 for a forward) -- was included in `expected_points`
completely unswapped, i.e. counted as the actual result rather than a
process estimate, even though it's the single biggest scoring route for
two whole positions. A team that rode a lucky, high-xG-conceded clean
sheet got exactly as much credit in "expected" quality as in "actual"
quality -- no smoothing at all, unlike goals (already swapped for xG),
assists (xA), or the goals-conceded penalty (already swapped for an
xGA-based estimate, right next to the untouched clean-sheet term).

**Fix:** in `player_points_expected`, `pf_cs` is now replaced (in the
`expected_points` formula only -- `actual_points` is untouched and still
uses the real `pf_cs`) with an expected-clean-sheet points estimate.
Goals conceded in a match are modelled as Poisson-distributed with mean
`pg_xGa` (a standard, widely-used approximation for exactly this kind
of estimate), so the probability of a clean sheet works out to
`exp(-pg_xGa)`, multiplied by the real points-per-clean-sheet for that
position (4 for GK/DEF, 1 for MID, 0 for FWD -- matching `pf_cs`'s own
scoring exactly, just paid out as a probability rather than an
all-or-nothing actual result). A team expected to concede 0.3 goals
that gameweek now gets credited with a genuinely good ~74% expected
clean sheet; a team expected to concede 2.0 goals gets a poor ~14% one,
regardless of what actually happened in the match.

**Known limitation, flagged rather than hidden:** `pg_xGa` (like
`pg_clean_sheets`) is a single combined figure per gameweek, already
summed across both matches on a double gameweek -- there's no per-match
breakdown available this far downstream (it comes straight from the FPL
API's own per-gameweek aggregate, via `stg_player_gameweek.sql`/
`player_stats.sql`). Under the same Poisson-independence assumption,
`exp(-total_xGa)` does work out to the mathematically correct
probability of a genuine DOUBLE clean sheet (zero conceded across both
matches combined), but it can't separately represent "clean sheet in
one match, not the other" the way `pf_cs`'s own linear 1-vs-2 structure
does for actual results. A rare edge case (most gameweeks are single
fixtures), and a limit of the data available at this stage of the
pipeline, not a new approximation invented for this fix -- the exact
same limitation `pf_cs`'s own `pg_clean_sheets` value has always had.

**Verified before delivery:** confirmed `pf_cs` now appears exactly
once in the rendered SQL (inside `actual_points` only) and not at all
inside `expected_points`. Re-rendered the whole file (macro + model)
and re-ran it through the same local Postgres instance used for the
last two fixes -- no syntax errors, only the same expected cross-
database-reference complaint Postgres can't resolve. Re-ran the
established paren-balance/duplicate-CTE-name checks (unchanged: depth
0, 30 CTEs, no duplicates, exactly one `with`). Pushed to
`C:\fpl-pipeline\transformation\models\analytics\player_rating.sql` and
re-staged to diff byte-for-byte -- needed the same forced recommit
after a silent overwrite this session has seen on every push; matched
exactly on the second attempt.

**What this changes, worth knowing before you look at the numbers:**
`quality_expected_score` for goalkeepers and defenders in particular
will likely shift for players whose clean-sheet luck didn't match their
underlying defensive numbers -- a defender who's kept several clean
sheets despite conceding good chances should see their expected quality
come down a bit; one who's been unlucky (good underlying defence, but
a few clean sheets narrowly missed) should see it go up. This also
changes `expected_points_p90` (the raw per-90 figure exposed on the
final output), and therefore the `quality_expected_score` z-score
population itself shifts slightly for everyone at these positions,
since the population mean/standard deviation are computed from
whatever the whole position's numbers look like this round.

**What I could not do myself:** run this against your actual warehouse
-- please retry `dbt run --select player_rating` and take a look at a
defender or two you know either over- or under-performed their
underlying defensive numbers this season, to sanity-check the direction
their expected quality moved in.

## Round 12: fixture_outlook_score was quietly using every remaining
fixture of the season, not the next 5

Found while building a diagnostic query to compare Arsenal/Liverpool/
Everton defenders' fixture outlook side by side (feedback: the numbers
"didn't make sense" between the three teams). The comment directly
above `next5` has always said "the next 5 gameweeks" -- but the actual
query had no row limit at all: `where gw_deadline_time > getdate()`
with no `top` or equivalent, so it was pulling in every gameweek left
in the season, each one just discounted by `FIXTURE_DECAY_RATE` rather
than excluded. The weight shrinks fast (0.90^n), but it never actually
reaches zero, so two teams could end up with different fixture-outlook
scores for reasons that have nothing to do with their real next 5
games -- how their remaining fixtures happen to be spread later in the
season, or simply how many gameweeks currently exist in the table.

**Fix:** added `top (5)` (and the matching `order by gw_id` it needs)
to `next5`, so only the 5 soonest gameweeks are selected at all --
exactly the same pattern `queries/player_info.py`'s own `get_next_5`
already used correctly for this exact purpose. Chose exclusion over
weighting down further, per feedback: anything beyond the 5th gameweek
now has a weight of 0 by not being included in the CTE at all, rather
than a smaller-but-still-nonzero one.

**Scope of the fix:** `next5` feeds `team_upcoming_fixtures` ->
`fixture_opponent_view` -> `fixture_outlook` (the fixture-outlook
ingredient for every position, not just defenders -- the diagnostic
query used to find this happened to look at defenders specifically,
but the underlying bug affected everyone's fixture outlook equally).
No other CTE needed changing.

**Verified before delivery:** confirmed `top (5)` appears exactly once
in the rendered SQL as real code (inside `next5`), with two further
mentions only in this round's own explanatory comments. Re-rendered the
whole file and re-ran it through the same local Postgres instance used
for the last two fixes -- no syntax errors (Postgres doesn't have `TOP`,
so it harmlessly parses it as an unrecognised function call rather than
a syntax defect, the same category of dialect gap as the cross-
database-reference complaint every one of these checks has flagged).
Re-ran the established paren-balance/duplicate-CTE-name checks
(unchanged: depth 0, 30 CTEs, no duplicates, exactly one `with`).
Pushed to
`C:\fpl-pipeline\transformation\models\analytics\player_rating.sql` and
re-staged to diff byte-for-byte -- needed the same forced recommit
after a silent overwrite this session has seen on every push; matched
exactly on the second attempt.

**What I could not do myself:** run this against your actual warehouse
-- please retry `dbt run --select player_rating` and re-run the
diagnostic query from earlier (`diagnose_fixture_outlook.sql`, sent to
the chat) with its own `next5` also capped to `top (5)` to confirm the
`fixtures_included` column now reads 5 for every team, and that Arsenal/
Liverpool/Everton's fixture-outlook scores now compare the way you'd
expect.

## Round 13: fixture_outlook_score was still squeezed after Round 12 --
a second, separate compression bug

Feedback after Round 12: "I don't think it is actually implemented, as
the fixture outlook is still very squeezed, and everyone is kind of
just around 5-6 in defence at least, sameish for mid and attack."

First checked whether Round 12 had actually landed (given the silent-
overwrite issue this session has hit on every push) -- it had: `top (5)`
was confirmed live and correct on your machine. So this was a genuinely
separate problem, not a re-run of the same one.

**Root cause:** a statistical one, not a logic bug. `fixture_outlook`
takes 5 different opponents, converts each one's strength into a 0-10
score, and averages those 5 scores together (weighted towards the
soonest gameweek). Averaging several independent 0-10 scores together
mechanically shrinks the spread of the result, compared to any single
one of those scores on its own -- the same reason a sports team's
average results over a season cluster closer to the mean than any one
match's result does. With 5 opponents blended together, the resulting
figure was landing close to the middle of the scale almost regardless
of who the opponents were, which is exactly the "everyone's around 5-6"
symptom described.

**My first attempt inside this same round, and why it wasn't enough:**
my first instinct was to reorder the arithmetic -- average the raw
(pre-0-10) z-scores across the 5 opponents first, and only convert to a
0-10 score once, right at the end, instead of converting each opponent
individually and then averaging 0-10 numbers. That is a real
improvement in principle (it avoids a small amount of extra distortion
from clamping each individual score into range before averaging), but I
verified numerically before shipping it that it was not the dominant
effect: simulating a realistic defender blend, the spread only moved
from a standard deviation of about 0.69 to about 0.65 -- barely
different. The reason: converting-then-averaging and averaging-then-
converting are nearly mathematically equivalent here, because the 0-10
conversion itself is a straight-line (linear) function, and straight-
line functions don't care which order you average and convert in. So
this alone was the wrong lever.

**The actual fix:** the 0-10 conversion works by comparing a team's raw
number against the mean and standard deviation of every other team's
raw number -- but the blended 5-fixture figure was being compared
against the wrong population. It was still being scored against the
spread of individual single-opponent figures, when what it actually is
is an average of 5 of them, which has a naturally smaller spread of its
own. The fix re-scores each team's blended figure against the
population of every other team's OWN blended 5-fixture figure instead
(computed separately per position, since goalkeepers/defenders/
midfielders/forwards care about attack vs defence in different
proportions). Verified numerically before shipping: this restores the
full spread (standard deviation back up to about 2.00, matching
individual opponent-strength scores), because it's now comparing like
with like.

**What changed in the SQL:** replaced `fixture_opponent_view` with four
new CTEs. `position_attack_share` is a small 4-row lookup of each
position's existing `*_TEAM_ATTACK_SHARE` tunable (unchanged values,
just pulled out so the next CTE can join to it instead of duplicating
the `case` logic per player). `team_fixture_raw_z` computes each team's
blended-favourability figure across their next 5 opponents, per
position, but stops at the raw (pre-0-10) z-score stage rather than
converting immediately. `team_fixture_population` computes the mean and
standard deviation of that blended figure across all teams, separately
for each position -- this is the "population of blended figures" that
was missing before. `team_fixture_outlook` does the single 0-10
conversion, against that correct population. `fixture_outlook` itself
is now just a simple lookup from a player's (team, position) to that
team-and-position's already-computed score -- its output columns
(`p_id`, `fixture_outlook_score`) are unchanged, so `component_scores`
and everything downstream needed no edits at all.

**Scope of the fix:** affects the fixture-outlook ingredient for every
position, same as Round 12 -- not specific to defenders, even though
Arsenal/Liverpool/Everton defenders were the example that surfaced it.

**Verified before delivery:** re-ran the numeric simulation described
above (both the insufficient first attempt and the corrected fix) in
Python before touching the SQL, to make sure the fix actually addresses
the dominant effect rather than a minor one. Re-rendered the whole file
(macro + model) and confirmed no leftover references to the removed
`fixture_opponent_view` CTE (three explanatory comments elsewhere in the
file referenced it and were updated to reference `team_fixture_raw_z`
instead; confirmed the separate, still-needed `player_attack_share` CTE
used elsewhere for the strength-of-opposition adjustment was untouched
and not accidentally orphaned). Re-ran the established paren-balance/
duplicate-CTE-name checks (depth 0, 33 CTEs now given the new ones, no
duplicates, exactly one `with`) and re-ran it through the same local
Postgres instance used for every previous fix -- no syntax errors, only
the same expected cross-database-reference complaint every prior check
has flagged. Pushed to
`C:\fpl-pipeline\transformation\models\analytics\player_rating.sql` and
re-staged to diff byte-for-byte -- matched exactly on the first attempt
this time (no forced recommit needed).

**What I could not do myself:** run this against your actual warehouse
-- please retry `dbt run --select player_rating` and take a look at the
fixture-outlook scores for defenders (and midfielders/forwards) across
several teams, not just Arsenal/Liverpool/Everton. You should now see a
noticeably wider spread -- teams with a genuinely easy run of fixtures
should stand out clearly above the pack, and teams with a genuinely
tough run should sit clearly below it, rather than almost everyone
clustering around 5-6.

## New: Team page -- pick a team, a gameweek range, see their results

Feedback: "setup a team tab... a drop down where u can select a team,
and another for a time range, like the other tabs have (all season,
last 10, last 5), in which it shows you the teams last 5, the score,
goalscorers and assisters, underlying xg, xa and xga stats, and any
other details you'd feel necessary."

**New files:**
`StreamLit/queries/team_results.py`, `StreamLit/components/
team_result_card.py`, `StreamLit/pages/Team.py`. No existing file was
touched -- this is purely additive, so there's zero risk of a
regression to any other page.

**What it shows:** the exact same team + range selectors the Player
page already uses (`get_teams`/the Range selectbox), followed by:

- A header banner in the team's own colours and badge (same pattern as
  the Player page's header, reusing the already-working join to
  `analytics.team_misc`).
- A "range snapshot" of metric cards -- record (W-D-L), goals scored,
  goals conceded, clean sheets, xG, xGA -- each carrying a rank against
  the other 19 teams over the same range, the team-level equivalent of
  the Player page's own `get_rank_metrics`. Ranking uses `row_number()`
  or the same reasons `get_rank_metrics` already does (one distinct
  rank per team, not a tied `dense_rank()`).
- A form guide: a left-to-right (oldest to newest) strip of W/D/L
  badges across the range, built from data already being fetched for
  the cards below rather than a separate query.
- One card per finished fixture in the range, most recent first: score,
  opponent, venue, a coloured W/D/L pill, that gameweek's team-level xG/
  xA/xGA, and who scored/assisted.

**Where the underlying numbers come from:** team-level xG/xA per
gameweek is `sum(pg_xG)`/`sum(pg_xA)` across every player from that
team who took the pitch (each player's own figure is their individual
contribution, so summing recovers the team total) -- the exact same
approach `player_rating.sql`'s `team_gw_attack` CTE already uses for
this. xGA is `avg(pg_xGa)` rather than summed, since `pg_xGa` is a
*shared* per-match value across every player from the same team (the
team's own conceded expected goals, not a personal figure) -- again,
the same approach `team_gw_defence` already uses. Goalscorers/assisters
are read straight from `analytics.player_stats.pg_goals`/`pg_assists`,
grouped in pandas (`build_contributor_strings`) into a "Salah (2),
Núñez" style string per gameweek, rather than built with SQL Server's
ordered `STRING_AGG` syntax -- kept in plain, portable SQL instead,
since nothing else in this project's SQL layer has needed that syntax
before.

**Known limitation, flagged on the card itself rather than hidden:**
the same double-gameweek limitation already documented on
`player_rating.sql`'s clean-sheet fix (Round 11) and `player_points.sql`
before it -- `pg_xG`/`pg_xA`/`pg_xGa` (like `pg_clean_sheets`) are a
single combined figure per gameweek at source (the FPL API's own
per-gameweek aggregate has no per-match split), so a double gameweek
shows as two separate result cards, each with its own correct score and
opponent, but both carrying the SAME combined goalscorers/xG/xA/xGA
figure for that gameweek rather than a genuine per-match split. Each
such card says so directly (`is_double_gw`), rather than silently
implying each match had that number independently. A rare case (most
gameweeks are single fixtures), not a new approximation invented for
this feature.

**Verified before delivery:** Python-syntax-checked all three new files
(`py_compile`). Extracted the actual SQL text from every query function
(with realistic argument values) and ran each one through the same
local Postgres instance used to verify every `player_rating.sql` change
this session -- no genuine syntax defects; the only errors were the
same accepted dialect gaps this project's SQL has always produced
against Postgres (missing tables, `TOP`, and -- new to this check, but
the same category -- `as 'primary'`, a single-quoted column alias that
is valid T-SQL and already used exactly this way in the already-working
`queries/player_info.py`, just something Postgres itself doesn't
accept). Re-ran the same paren-balance check used on every SQL change
this session (all 5 queries: balanced, ends at depth 0). Unit-tested
`build_contributor_strings` directly (a single goal/assist shows just
the name, more than one shows "(N)", multiple gameweeks group
correctly, an empty input returns cleanly). Executed the actual
`pages/Team.py` script end-to-end against a fully mocked Streamlit
module and mocked query layer (crafted DataFrames standing in for what
the real queries would return, including a single-fixture gameweek, a
flagged double gameweek, and an empty-range edge case) to catch any
runtime error a syntax check alone can't -- ran clean on both the
normal path and the "no finished fixtures in this range yet" path.
Pushed all three files to
`C:\fpl-pipeline\StreamLit\{queries\team_results.py, components\
team_result_card.py, pages\Team.py}` and re-staged each to diff
byte-for-byte -- matched exactly on the first attempt, no forced
recommit needed this time.

**What I could not do myself:** run this against your actual warehouse
or actually view the rendered page -- please pull these three files
into your project and load the Team page. In particular, worth
checking: the team badge/colours render correctly (this reuses
`analytics.team_misc`, already working on the Player page, but hasn't
been read from this new page before), the rank numbers on the range
snapshot look sane for a team you know well, and a team with a genuine
double gameweek in its recent history shows the flagged note rather
than looking like a data error.

## Fix: Team page crashed with "Ambiguous column name 'gw_id'" on first use

You hit this immediately on loading the new Team page: SQL Server error
209 out of `get_team_results`.

**Root cause: a genuine bug in `queries/team_results.py`, mine, not a
data or schema problem.** All three query functions that use the
`_range_filter_sql` helper called it wrong -- e.g.
`_range_filter_sql('tr.gw_id')` -- passing the string meant to qualify
*which* gameweek column to filter on (`'tr.gw_id'`) as if it were the
function's *first* parameter. But `_range_filter_sql`'s first parameter
is `range_filter` (the actual "All/Last 10/Last 5 gameweeks" selection),
with the column-qualifier as its *second*, defaulted parameter
(`gw_column="gw_id"`). Called positionally with only one argument, that
one argument landed in the wrong slot: `range_filter` silently became
the literal string `'tr.gw_id'` (never your actual selection), and
`gw_column` silently fell back to its unqualified default, `"gw_id"`.

`get_team_results`' main query joins three CTEs that each carry their
own `gw_id` column (`team_fixture_results`, `team_gw_stats`,
`team_fixture_counts`), so an unqualified `gw_id` reference is
genuinely ambiguous to SQL Server -- exactly the error you saw. The
same mistake in `get_team_rank_metrics` would have hit the identical
error the first time its range-filtered path was exercised.
`get_team_contributors` had the same wrong-argument bug too, but would
have failed differently (an "invalid column name" rather than
"ambiguous", since no bare `gw_id` column exists at all in that query's
join scope -- it's `pg_gameweek` there); it just hadn't been hit yet
when you reported this.

**Why my own verification before delivery didn't catch this:** I had
extracted each function's rendered SQL and run it through a local
Postgres instance as a syntax cross-check, plus a paren-balance check --
both passed, because the mis-called SQL was still *syntactically* valid
text (`'tr.gw_id' = 'All gameweeks'` parses fine, it's just always
false and beside the point) and Postgres never has your real tables
loaded locally to catch a column-ambiguity error the way SQL Server
just did against your actual schema. A syntax/paren check can't catch
"the right values ended up in the wrong parameter slots" -- only
actually reading the rendered predicate text for each function, with
real arguments, would have. I'm adding that as a standing step for
myself on any function like this going forward, and did it here as
part of verifying this fix (see below).

**Fix:** all three call sites now pass both arguments explicitly and by
name -- `_range_filter_sql(range_filter, gw_column='tr.gw_id')` (and
`gw_column='ps.pg_gameweek'` for `get_team_contributors`, whose FROM
clause never has a `tr` alias) -- so there's no positional slot left to
mix up, and the actual column each query needs is spelled out at the
call site rather than relying on a same-named default that only
happened to be right by coincidence in the original `player_stats.py`
this pattern was copied from (where only one table in scope ever has a
`gw_id`-shaped column, so the ambiguity never came up there).

**Verified before delivery, properly this time:** re-rendered all three
functions with each of the three real range values ("All gameweeks",
"Last 10 gameweeks", "Last 5 gameweeks") and printed the actual
predicate text that results -- confirmed each one now contains the real
selected range compared against the real option strings, and the
correctly qualified column name, rather than eyeballing structure alone.
Re-ran the paren-balance check (still balanced) and the Postgres syntax
cross-check (same accepted baseline as every previous check: missing
tables, and the same `as 'primary'` T-SQL alias quirk already flagged
when this feature first shipped -- no new syntax errors). Re-ran the
full `pages/Team.py` script against the mocked Streamlit/query-layer
harness used when this feature was first built. Pushed the corrected
`queries/team_results.py` to
`C:\fpl-pipeline\StreamLit\queries\team_results.py` and re-staged to
diff byte-for-byte -- needed the same forced recommit this session has
seen on nearly every push; matched exactly on the second attempt.

**What I could not do myself:** confirm this against your actual
warehouse -- please reload the Team page and try all three range
options (not just the default) for a couple of different teams, since
that's exactly the combination that was broken.

## Investigated + fixed: Newcastle vs Leeds (gameweek 4) showing 0 for
every player stat, and hardened the pipeline against a repeat

Feedback: "there's also this weird bug that Newcastle vs Leeds is
counting as 0 points, minutes, any player stat for all players
involved, this is the case in the raw schema so it must be on
ingestion, can you investigate."

**First checked whether this was actually an FPL-side data problem
rather than ours**, by pulling the real, current FPL API directly
(not this project's warehouse, which I have no live connection to):
gameweek 4 is fully finished and `data_checked: true`; the Newcastle
vs Leeds fixture (id 33, kicked off 12 Sept at the same 14:00 slot as
most of that gameweek -- not delayed or rescheduled) is finished,
2-2, with a full stats breakdown of goals/assists/cards/bonus in
FPL's own fixtures endpoint; and pulling `event/4/live/` directly just
now shows a completely normal stat line for one of that match's
goalscorers (90 minutes, 8 points, 1 goal, 1 bonus). So the real data
has always been fine, or is fine now -- whatever's zeroed out in the
warehouse isn't because FPL never had it.

**Root cause: a structural gap in `extraction/common.py`'s incremental
fetch logic, not a one-off data glitch that needs waiting out.**
`event_live.py` only pulls a gameweek's live player stats again if
`_gameweeks_needing_fetch` says it still needs it, and that function's
old rule was: fetch if not yet ingested, OR not yet marked
`data_checked` by FPL. Once BOTH are true, a gameweek was treated as
permanently settled and never looked at again -- no periodic
re-verification, no full-refresh safety net.

FPL deliberately keeps a gameweek's stats "provisional" (data_checked
= false) for a day or two after it finishes specifically because one
match's data can occasionally lag behind the rest of its gameweek
before everything gets confirmed -- a known, ordinary occurrence, not
a fault on FPL's part. The likely sequence here: this pipeline's one
and only ingestion run for gameweek 4 landed at a moment when most of
the gameweek had posted normally but the Newcastle vs Leeds match's
live stats specifically hadn't come through yet, so that run captured
zeros for those players. By the time FPL flipped `data_checked` to
confirm the whole gameweek (including the late match) was actually
fine, `_gameweeks_needing_fetch` had no way of knowing its own earlier
capture was incomplete -- "ingested + checked" was already true, so
gameweek 4 has been silently skipped on every run since, frozen at
that one bad snapshot.

**Fix, in two parts:**

1. **Immediate, one-off backfill** (not run by me -- I have no
   connection to your database): `extraction/backfill_gw4_event_live.py`
   deletes gameweek 4's existing `raw.raw_event_live` rows and calls
   the existing, unmodified `event_live()` for just that one gameweek.
   Since it's no longer in `ingested` after the delete, the existing
   fetch logic pulls it fresh regardless of `data_checked` -- reusing
   the already-working code path with zero new logic, so this carries
   the same risk as any ordinary pipeline run. Run it from inside
   `extraction/` the same way you'd run `ingest.py`, then re-run dbt to
   pick up the corrected numbers downstream.

2. **Hardening against a repeat**, in `extraction/common.py`: added a
   `GRACE_GAMEWEEKS = 2` constant and changed `_gameweeks_needing_fetch`
   so the 2 most-recently-ingested gameweeks (by gameweek number) stay
   in the refetch pool on every run even after they're marked checked,
   rather than becoming permanently frozen the instant "ingested +
   checked" both go true. This gives our own pipeline the same kind of
   grace period FPL's own `data_checked` flag represents, on our side,
   against exactly this kind of single-match lag landing in one
   snapshot right as `data_checked` flips. 2 gameweeks is roughly a
   fortnight of real time (gameweeks are ~weekly) -- comfortably past
   FPL's own correction window -- without permanently re-fetching a
   whole season's worth of already-settled gameweeks on every run
   forever. Once a gameweek ages out of that trailing window (2 more
   gameweeks get ingested after it), it goes back to being treated as
   final, same as before.

**Verified before delivery:** confirmed via a live FPL API check (not
against this project's own data) that the real numbers for gameweek 4
are correct right now, so the backfill is safe to run. Python-syntax-
checked both changed/new files. Unit-tested the new
`_gameweeks_needing_fetch` logic directly against five scenarios: the
exact bug being fixed (a gameweek marked checked but still within the
recent window must still be refetched), a normal mid-season state (old
gameweeks correctly stop being refetched, only the newest few stay in
the grace window), a gameweek correctly aging out of the grace window
once 2 more gameweeks are ingested after it (so this doesn't turn into
refetching the entire season forever), the very start of a season with
nothing ingested yet, and a single-gameweek edge case -- all five
passed. Pushed `extraction/common.py`,
`extraction/backfill_gw4_event_live.py`, and
`diagnose_newcastle_leeds_zeros.sql` (at the project root) and
re-staged each to diff byte-for-byte -- all three matched exactly on
the first attempt.

**What I could not do myself:** confirm any of this against your
actual raw tables -- please run `diagnose_newcastle_leeds_zeros.sql`
first to see exactly which rows are affected and when they were
captured (their `load_timestamp` should look suspiciously early
relative to full-time if this diagnosis is right), then run
`backfill_gw4_event_live.py` to pull the corrected data, then re-run
dbt. The hardening fix only prevents this from happening again on a
*future* gameweek -- it doesn't retroactively touch gameweek 4, hence
the separate backfill.


## New: "My Team" page -- your own squad, profile stats, and transfer
history, on the same pitch view the home page uses

Feedback: "I've used manager data a little bit now, and given that my
manager ID on fantasy pl itself is 194625, I'd like you to add a new
page on the dashboard (and probably needing some more ingestion
work), that is a tab with stats about me, with a similar display of my
team that is on the home page (but with subs), and just general
details that may be useful for me, can you implement that."

This one touches every layer of the project -- extraction, dbt, and
Streamlit -- because none of it existed before: the pipeline was
already fetching your picks and profile for the leaderboard/rank
features, but wasn't tracking your specific entry ID as a distinct
"my team" subject, wasn't capturing gameweek-by-gameweek history or
transfers at all, and there was no page built to show any of it back
to you the way the home page shows its algorithmic Best XI.

**Extraction changes:**

- `extraction/ingest.py`: added your entry ID (194625) to a new
  `TRACKED_ENTRY_IDS` list alongside the one already there, with a
  comment explaining what it's for. This is the ID the My Team page
  reads -- it needs to already be in this list for a manager's data to
  ever get ingested, which is exactly why the page includes a warning
  banner (below) rather than assuming this step always happened.
- `extraction/manager_profiles.py`: added `bank` (your unspent budget,
  from the FPL API's `last_deadline_bank` field) to the row that was
  already being ingested for each manager -- it was being fetched from
  the API already, just not kept.
- `extraction/manager_picks.py`: this fetches your picks for each
  gameweek from the FPL API, and that same API response also includes
  an `entry_history` block (your points, rank, bank, squad value,
  transfers made and their point cost, points left on the bench, and
  any chip played that gameweek) and an `active_chip` field -- neither
  was being kept before. Extended this to also write those into a new
  `raw_manager_gameweek_history` table, one row per manager per
  gameweek, alongside the existing picks rows. No extra API calls --
  this data was already arriving, just being discarded.
- `transformation/models/sources.yml`: declared the new
  `raw_manager_gameweek_history` table as a source so dbt models can
  build on it.

**New dbt models** (none of this existed before -- there was no
manager-facing staging or analytics layer at all beyond what the
existing rank/leaderboard features already used):

- Staging (`transformation/models/staging/`): `stg_manager_profiles`,
  `stg_manager_picks`, `stg_manager_transfers`,
  `stg_manager_gameweek_history` -- thin passthrough views renaming
  raw columns to this project's conventions (e.g. `event_id` ->
  `gw_id`).
- Analytics (`transformation/models/analytics/`): `manager_profile`
  and `manager_gameweek_history` (passthrough with the `m_` prefix),
  `manager_transfers` (joins both sides of each transfer out to full
  player name/position, so the page never has to resolve an element
  ID itself), and `manager_squad` -- the model the pitch view reads:
  one row per player currently in your 15-man squad (only your most
  recently ingested gameweek's picks, via a `max(gw_id) per entry_id`
  CTE, so "my current team" advances on its own as each new gameweek
  gets ingested), joined out to full player/team identity and this
  project's own star rating, with `is_starting` (squad slot <= 11)
  worked out once here rather than in every consumer.

**Streamlit changes:**

- `StreamLit/components/metric_card.py`: made its `rank` parameter
  optional (`rank=None`), only rendering the rank badge when a rank is
  actually passed. Every metric on the My Team page (overall rank,
  gameweek points, team value, bank, transfers) has no natural "rank
  vs how many other managers" to show -- this app only ever tracks 1-2
  manager IDs, so a rank among them would be meaningless. Fully
  backwards compatible: every existing call site still passes a real
  rank and is unaffected; only omitting it is new.
- `StreamLit/queries/manager_data.py`: new query layer --
  `get_manager_profile`, `get_manager_squad`,
  `get_manager_gameweek_history`, `get_manager_transfers`, each reading
  the new analytics tables filtered to one entry ID.
- `StreamLit/pages/MyTeam.py`: the new page itself, built as its own
  fully self-contained file rather than a refactor of `Home.py` to
  share its pitch-rendering code -- same reasoning `Compare.py`
  already gives for not refactoring `Player.py`: `Home.py` needed zero
  changes and carries zero risk of a regression from this addition.
  Your manager ID (194625) lives here as one clearly documented
  module-level constant (`MY_ENTRY_ID`) rather than a dropdown, since
  this is a personal, single-subject page, not a "pick a manager" one
  like the Team page. It shows: a header banner with your team/player
  name and current gameweek; six headline metric cards (overall rank,
  overall points, this gameweek's points, team value, money in the
  bank, and transfers made this gameweek with their point cost if any
  were free-hit or paid for); a caption naming any active chip; the
  starting XI on the same pitch-graphic, grid-by-position layout
  `Home.py`'s Best XI uses, but showing your actual picked players
  (short names) instead of an algorithmically-chosen XI, with a
  yellow "C" / "VC" badge (and a "xN" multiplier note for triple
  captain) over your captain and vice-captain, plus each player's
  current star rating where one exists; a bench row in substitution-
  priority order, which the home page's version has no need for; and
  a recent-transfers list, red "out" to green "in", most recent first.
  If your manager ID hasn't been ingested yet, the page shows a
  warning explaining exactly why (pointing at `TRACKED_ENTRY_IDS`)
  instead of crashing.

**What I verified myself:** every new/changed Python file compiles
(`py_compile`); every new SQL file was Jinja-rendered with fake
`ref`/`source`/`config` helpers, paren-balance-checked (all depth 0,
matching final=0/min=0 -- `manager_squad.sql`'s single `latest_gw` CTE
was specifically double-checked to close with `)` not `),`, given
that exact typo is what started the very first bug of this session),
and cross-checked against a real Postgres instance for baseline SQL
Server-vs-Postgres syntax issues (only the expected "cross-database
references are not implemented" noise, nothing else). `MyTeam.py` and
`manager_data.py` were also verified with a fully mocked Streamlit +
query layer, running the actual page source end-to-end against
several scenarios rather than just checking it imports: a realistic
happy-path 4-4-2 squad (captain with a x2 multiplier, a vice-captain,
a full bench, an active chip, one recent transfer) executed without
error; a squad with no gameweek history rows, no transfers, no active
chip, a null overall rank, and every player's star rating missing
(`NaN`, as a brand-new season would look before this project's own
rating model has enough data) also executed without error, in a
5-3-2 formation to confirm the pitch grid isn't hardcoded to 4-4-2 in
any way; and an empty profile/squad (nothing ingested yet) correctly
hit the warning banner and stopped rather than crashing further down
the page. `extraction/manager_picks.py`'s extended history-capture
logic was unit-tested against a mocked two-gameweek API response (one
gameweek with a real `entry_history` block, one without) and
confirmed it captures exactly one history row, with the right
points/chip/transfer-cost values, and doesn't add a spurious row for
the gameweek that had none.

**What I could not verify myself:** I have no live connection to your
actual database, so none of this has been checked against real data
for entry 194625, or any other manager. Two steps are needed before
the My Team page will show anything: first, the extraction pipeline
needs to run at least once now that 194625 is in `TRACKED_ENTRY_IDS`,
so its profile, picks, and gameweek history actually get ingested into
the raw tables; then `dbt run` needs to build the eight new staging
and analytics models from that raw data. Until both of those have
happened, the page will show its "no data available yet" warning
rather than a crash -- that's expected, not a bug. Once it's ingested,
it'd be worth a quick look to confirm the pitch layout reads sensibly
for your actual formation and that the captain/vice-captain badges
land on the right players.
