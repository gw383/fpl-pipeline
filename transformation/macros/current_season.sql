{#-
    Restrict a raw source to the season that is currently in progress.

    Every raw table carries a `season` label (e.g. "2026-27", stamped by the
    extraction pipeline). This joins it to the `seasons` seed and keeps only
    rows whose season's date range contains today, exposing the seed row as
    alias `s` (so models can select `s.id as season`).

    Usage:
        from {{ source('raw', 'raw_players') }} p
        {{ join_current_season('p') }}
-#}
{% macro join_current_season(source_alias) %}
inner join {{ ref('seasons') }} s
    on {{ source_alias }}.season = s.display_name
    and cast(getdate() as date) between s.start_date and s.end_date
{% endmacro %}
