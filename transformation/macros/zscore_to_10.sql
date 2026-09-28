{#-
    Round 8: shared z-score-to-0-10 expression, used by player_rating.sql
    everywhere that model used to call percent_rank() -- see the ROUND 8
    note at the top of that file, and its SCORE_SD_SPAN tunable.

    Originally written as a Jinja {% macro %} block living directly
    inside player_rating.sql itself, on the assumption that a macro
    defined earlier in a model file would simply be callable later in
    that same file, the way a plain Jinja template works. That's wrong
    for dbt specifically: dbt only discovers macros from files under the
    project's configured macro-paths (transformation/macros/, per
    dbt_project.yml) during its own separate macro-parsing pass -- a
    {% macro %} block sitting inside a models/ file is invisible to that
    pass, so calling it (even from within its own file) fails at compile
    time with "'zscore_to_10' is undefined". Moving the exact same macro
    body into this file, with no other change, is the fix -- once it's
    under macros/, dbt registers it globally and player_rating.sql (or
    any other model) can call {{ zscore_to_10(...) }} with no import/ref
    needed.

    Takes the raw value, the population mean and the population standard
    deviation (each usually a window-function column computed alongside
    the raw value in the same CTE) and returns a 0-10 score centred on 5,
    clamped at both ends. Guards against a null or zero standard
    deviation (a population of one, or a population where every value
    happens to be identical -- both realistic early in a season with
    very little data) by defaulting to the neutral 5 rather than dividing
    by zero.

    SCORE_SD_SPAN is passed in explicitly (rather than this macro reading
    a project variable) because player_rating.sql already defines it as
    an ordinary {% set %} tunable at the top of that file, right next to
    every other tunable someone would look to retune -- keeping it there,
    in the file everyone already edits, rather than hiding a second copy
    inside macros/.
-#}
{% macro zscore_to_10(raw_expr, mean_expr, stddev_expr, sd_span) %}
    case
        when {{ stddev_expr }} is null or {{ stddev_expr }} = 0 then 5.0
        else
            case
                when 5.0 + (5.0 * (({{ raw_expr }}) - ({{ mean_expr }})) / ({{ stddev_expr }}) / {{ sd_span }}) > 10.0 then 10.0
                when 5.0 + (5.0 * (({{ raw_expr }}) - ({{ mean_expr }})) / ({{ stddev_expr }}) / {{ sd_span }}) < 0.0 then 0.0
                else 5.0 + (5.0 * (({{ raw_expr }}) - ({{ mean_expr }})) / ({{ stddev_expr }}) / {{ sd_span }})
            end
    end
{% endmacro %}
