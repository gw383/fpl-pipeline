"""One past-result card for the Team page: score, opponent, a W/D/L
pill, the match's underlying xG/xA/xGA, and who scored/assisted.
"""

from theme import (
    BORDER,
    RADIUS_SM,
    RESULT_COLOURS,
    SHADOW_CARD,
    STATUS_WARNING,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    rgba,
)

_RESULT_LABEL = {"W": "Win", "D": "Draw", "L": "Loss"}


def _stat_chip(label: str, value: float) -> str:
    return f"""
    <div style="text-align:center;min-width:56px;">
        <div style="font-size:16px;font-weight:700;color:{TEXT_PRIMARY};font-variant-numeric:tabular-nums;">
            {value:.2f}
        </div>
        <div style="font-size:10px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;color:{TEXT_MUTED};">
            {label}
        </div>
    </div>
    """


def _contributor_line(label: str, names: str) -> str:
    if not names:
        return ""
    return f"""
    <div style="font-size:12.5px;color:{TEXT_SECONDARY};margin-top:3px;">
        <span style="font-weight:700;color:{TEXT_MUTED};margin-right:5px;">{label}</span>{names}
    </div>
    """


def team_result_card(row, goalscorers: str, assisters: str) -> str:
    """Render one result: ``row`` comes from
    ``queries.team_results.get_team_results``; ``goalscorers``/``assisters``
    are that gameweek's pre-formatted strings (shared by both fixtures of a
    double gameweek)."""
    result = row["result"]
    colour = RESULT_COLOURS.get(result, STATUS_WARNING)
    label = _RESULT_LABEL.get(result, result)

    double_gw_note = ""
    if row["is_double_gw"]:
        double_gw_note = f"""
        <div style="
            font-size:11px;
            color:{TEXT_MUTED};
            font-style:italic;
            margin-top:8px;
            padding-top:6px;
            border-top:1px dashed {BORDER};
        ">
            Double gameweek -- goals, assists and xG/xA/xGA are the combined
            totals for both matches (FPL doesn't split them per match).
        </div>
        """

    return f"""
    <div style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-radius:{RADIUS_SM};
        padding:14px 18px;
        margin-bottom:10px;
        box-shadow:{SHADOW_CARD};
    ">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">

            <!-- Gameweek / opponent / score -->
            <div style="min-width:0;">
                <div style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:{TEXT_MUTED};">
                    GW {int(row["gw_id"])}
                </div>
                <div style="font-size:15px;font-weight:700;color:{TEXT_PRIMARY};margin-top:2px;">
                    vs {row["opponent"]} <span style="color:{TEXT_MUTED};font-weight:600;">({row["venue"]})</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;margin-top:6px;">
                    <span style="font-size:26px;font-weight:800;color:{TEXT_PRIMARY};font-variant-numeric:tabular-nums;">
                        {int(row["own_score"])} &ndash; {int(row["opp_score"])}
                    </span>
                    <span style="
                        background:{rgba(colour, 0.14)};
                        color:{colour};
                        font-weight:700;
                        font-size:12px;
                        padding:3px 10px;
                        border-radius:999px;
                    ">
                        {label}
                    </span>
                </div>
            </div>

            <!-- Underlying xG/xA/xGA -->
            <div style="display:flex;gap:16px;">
                {_stat_chip("xG", row["team_xg"])}
                {_stat_chip("xA", row["team_xa"])}
                {_stat_chip("xGA", row["team_xga"])}
            </div>

        </div>

        {_contributor_line("Goals:", goalscorers)}
        {_contributor_line("Assists:", assisters)}
        {double_gw_note}
    </div>
    """
