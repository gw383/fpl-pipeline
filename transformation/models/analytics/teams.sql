-- Dimension: one row per team (prefix team_), with club colours and badge
-- file from the team_branding seed (keyed on FPL's stable short name, since
-- team IDs are reassigned every season).
select
    t.team_id                as team_id,
    t.team_name              as team_name,
    t.short_name             as team_short_name,
    t.team_code              as team_code,
    t.position               as team_table_position,
    t.strength               as team_strength,
    b.primary_colour         as team_primary_colour,
    b.secondary_colour       as team_secondary_colour,
    b.badge_file             as team_badge_file
from {{ ref('stg_teams') }} t
left join {{ ref('team_branding') }} b on b.short_name = t.short_name
