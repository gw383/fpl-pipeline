-- The four FPL positions (1 = goalkeeper ... 4 = forward) and their squad
-- rules, for the current season only (each season's bootstrap load
-- appends its own copy to the raw table).
select
    p.id                   as id,
    p.singular_name        as name,
    p.singular_name_short  as short_name,
    p.squad_select         as squad_size,
    p.squad_min_play       as min_play,
    p.squad_max_play       as max_play,
    s.id                   as season
from {{ source('raw', 'raw_positions') }} p
{{ join_current_season('p') }}
