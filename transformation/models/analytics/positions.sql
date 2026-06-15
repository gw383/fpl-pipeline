{{ config(materialized='table') }}

select
    id                                as pos_id,
    name                                as pos_name,
    short_name                          as pos_short_name,
    in_team                             as pos_in_team,
    max_play                            as pos_max_play,
    max_start                           as pos_max_start
from {{ ref('stg_positions') }};