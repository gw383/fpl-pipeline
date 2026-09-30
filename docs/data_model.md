# Data model

The warehouse has three schemas in SQL Server:

| Schema | Built by | Contents |
|---|---|---|
| `raw` | Python extraction + dbt seeds | One table per API dataset, stamped with `season` and `load_timestamp`; the `seasons` and `team_branding` seeds |
| `stg` | dbt (views) | Current season only, renamed and typed |
| `analytics` | dbt (tables; the `manager_*` models are views so managers loaded on demand by the dashboard appear immediately) + `projections/run.py` | Dimensional model consumed by the dashboard, plus the projection model's output (`player_rating`, `player_projection`, `team_rating`) |

## Lineage

```mermaid
flowchart LR
    api([FPL API]) --> ingest[Python extraction]
    plapi([Premier League match API]) -->|goal events| ingest
    ingest --> raw[(raw schema)]
    raw --> stg[stg_* views]
    seasons[/seasons seed/] --> stg

    stg --> players & teams & gameweeks & fixtures & player_stats
    branding[/team_branding seed/] --> teams

    player_stats --> player_points
    players --> player_points
    player_stats --> team_gameweek_stats
    fixtures --> team_fixture_results
    team_gameweek_stats --> team_fixture_results

    stg --> player_penalties
    player_stats & players & teams & fixtures --> player_penalties
    stg --> player_past_seasons
    players --> player_past_seasons

    players & player_stats & player_penalties & player_past_seasons & fixtures & gameweeks --> model{{"projections/run.py<br/>(Python model)"}}
    model --> player_rating & player_projection & team_rating & player_gameweek_expected

    stg --> managers[manager_profile / gameweek_history / transfers]
    players --> manager_squad
    teams --> manager_squad

    player_rating & player_projection & team_fixture_results & managers & manager_squad --> dash([Streamlit dashboard])
```


## Analytics tables

Columns are prefixed by entity: `p_` players, `ps_` players' previous seasons, `team_` teams, `gw_` gameweeks, `f_` fixtures, `pg_` player-gameweek, `pf_` points-by-category, `m_` managers.

![Analytics schema](analytics_data_model.png)

The same diagram as Mermaid source (key columns only):

```mermaid
erDiagram
  teams ||--o{ players : "team_id = p_team"
  team_branding ||--|| teams : "short_name"
  teams ||--o{ fixtures : "home / away"
  gameweeks ||--o{ fixtures : "gw_id = f_gameweek"

  players ||--o{ player_stats : "p_id = pg_id"
  gameweeks ||--o{ player_stats : "gw_id = pg_gameweek"
  player_stats ||--|| player_points : "pg_id, pg_gameweek"
  players ||--o{ player_penalties : "p_id"
  players ||--o{ player_past_seasons : "p_id"
  players ||--o{ player_gameweek_expected : "p_id"
  teams ||--o{ team_gameweek_stats : "team_id"
  teams ||--o{ team_fixture_results : "team_id"
  fixtures ||--|{ team_fixture_results : "f_id (one row per side)"

  players ||--|| player_rating : "p_id"
  players ||--o{ player_projection : "p_id"
  fixtures ||--o{ player_projection : "f_id"
  teams ||--|| team_rating : "team_id"

  manager_profile ||--o{ manager_squad : "m_id"
  manager_profile ||--o{ manager_gameweek_history : "m_id"
  manager_profile ||--o{ manager_transfers : "m_id"
  players ||--o{ manager_squad : "p_id"

  players {
    int p_id PK
    string p_web_name
    string p_full_name
    int p_team FK
    int p_position
    float p_price
    float p_start_price
    string p_status
    float p_chance_of_playing
    string p_news
    int p_code "Opta code"
    int p_penalties_order
    int p_corners_order
    int p_direct_freekicks_order
  }
  teams {
    int team_id PK
    string team_name
    string team_short_name
    int team_code "Opta code"
    int team_table_position
    string team_badge_file
  }
  gameweeks {
    int gw_id PK
    string gw_name
    datetime gw_deadline_time
  }
  fixtures {
    int f_id PK
    int f_gameweek FK
    int f_home_team FK
    int f_away_team FK
    int f_home_score
    int f_away_score
    int f_finished
  }
  team_branding {
    string short_name PK
    string primary_colour
    string secondary_colour
    string badge_file
  }
  seasons {
    int id PK
    string display_name
    date start_date
    date end_date
  }
  player_stats {
    int pg_id PK,FK
    int pg_gameweek PK,FK
    int pg_minutes
    int pg_points
    float pg_xg
    float pg_xa
    int pg_defcons
    int pg_bps
    int pg_saves
  }
  player_points {
    int pg_id PK,FK
    int pg_gameweek PK,FK
    int pf_minutes
    int pf_goals
    int pf_assists
    int pf_cs
    int pf_defcon
    int pf_bonus
  }
  player_penalties {
    int p_id PK,FK
    int gw_id PK,FK
    int penalty_goals
    int penalties_missed
    int penalties_taken
  }
  player_past_seasons {
    int p_id PK,FK
    string ps_season PK
    int ps_seasons_ago
    int ps_minutes
    float ps_xg
    float ps_xa
    int ps_bps
    float ps_defensive_contribution
    int ps_penalties_taken
  }
  team_gameweek_stats {
    int team_id PK,FK
    int gw_id PK,FK
    float team_xg
    float team_xa
    float team_xga
  }
  team_fixture_results {
    int f_id PK,FK
    int team_id PK,FK
    int gw_id
    string venue
    int opponent_id
    string result
    float team_xg
    float team_xga
  }
  player_rating {
    int p_id PK,FK
    float xpts_next_gw
    float xpts_horizon
    float xmins_next_gw
    float pts_goals_etc "one column per category"
    float xg_p90
    float star
    int position_rank
  }
  player_projection {
    int p_id PK,FK
    int f_id PK,FK
    int gw
    float p_start
    float xmins
    float xg
    float cs_prob
    float xpts
  }
  player_gameweek_expected {
    int p_id PK,FK
    int gw PK
    float xpts
    float xmins
  }
  team_rating {
    int team_id PK,FK
    float attack_index
    float defence_index
    float defcon_allowed_index
  }
  manager_profile {
    int m_id PK
    string m_player_name
    string m_team_name
    int m_overall_rank
  }
  manager_squad {
    int m_id PK,FK
    int gw_id PK
    int squad_position PK
    int p_id FK
    int is_captain
  }
  manager_gameweek_history {
    int m_id PK,FK
    int gw_id PK
    int gw_points
    int overall_rank
    string active_chip
  }
  manager_transfers {
    int m_id FK
    int gw_id
    string player_in
    string player_out
  }
```

`player_rating`, `player_projection`, `team_rating` and `player_gameweek_expected` are written by the Python projection model after `dbt build` (see [rating_methodology.md](rating_methodology.md)); it validates its output before replacing the first three in one transaction, and adds each started gameweek's expected points to the fourth. Every dbt model is documented and tested in [`_staging.yml`](../transformation/models/staging/_staging.yml) and [`_analytics.yml`](../transformation/models/analytics/_analytics.yml) (primary-key uniqueness/not-null, relationships and accepted values); `dbt docs generate && dbt docs serve` renders the full catalogue.
