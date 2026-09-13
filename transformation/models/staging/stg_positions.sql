{{ config(materialized='view') }}

-- Reference data: the four FPL positions (goalkeeper, defender,
-- midfielder, forward) and their squad-composition rules. Not
-- season-partitioned, since these rarely change.
select
    id                   as id,
    singular_name        as name,
    singular_name_short   as short_name,
    squad_select         as in_team,
    squad_min_play        as max_play,
    squad_max_play        as max_start
from {{ source('raw', 'raw_positions') }}
