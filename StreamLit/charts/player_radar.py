"""Radar chart: a player's key stats as a percentage of the positional max."""
import plotly.graph_objects as go
from plotly.graph_objects import Figure

CHART_BACKGROUND = "#f2f2f2"
GRID_COLOR = "#d9d9d9"

GOALKEEPER_CATEGORIES = ["Saves", "Penalty Saves", "Bonus", "Clean Sheets", "Points"]
OUTFIELD_CATEGORIES = ["Goals", "Assists", "Bonus", "Def Con /90", "Clean Sheets"]


def _safe_pct(value: float, maximum: float) -> float:
    """Return value as a percentage of maximum, or 0 if maximum is falsy."""
    return value / maximum * 100 if maximum else 0


def player_radar(
    position,
    points, max_points,
    goals, max_goals,
    assists, max_assists,
    bonus, max_bonus,
    defcons_p90, max_dcp90,
    clean_sheets, max_cs,
    saves, max_saves,
    pens_saved, max_pens_saved,
    selected_player,
    primary: str,
) -> Figure:
    """Build the player-profile radar chart.

    Goalkeepers are plotted on save-oriented stats; every other
    position is plotted on attacking/defensive-contribution stats.
    Each axis is the player's value as a percentage of the best value
    for their position (see queries/player_stats.py get_best_stats).
    """
    if position == "Goalkeeper":
        categories = list(GOALKEEPER_CATEGORIES)
        player_values = [
            _safe_pct(saves, max_saves),
            _safe_pct(pens_saved, max_pens_saved),
            _safe_pct(bonus, max_bonus),
            _safe_pct(clean_sheets, max_cs),
            _safe_pct(points, max_points),
        ]
    else:
        categories = list(OUTFIELD_CATEGORIES)
        player_values = [
            _safe_pct(goals, max_goals),
            _safe_pct(assists, max_assists),
            _safe_pct(bonus, max_bonus),
            _safe_pct(defcons_p90, max_dcp90),
            _safe_pct(clean_sheets, max_cs),
        ]

    # Close the radar shape by repeating the first point.
    categories.append(categories[0])
    player_values.append(player_values[0])

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=player_values,
            theta=categories,
            fill="toself",
            name=selected_player,
            line=dict(color=primary, width=3),
            fillcolor=primary,
            opacity=0.35,
        )
    )

    fig.update_layout(
        title="Player Profile",
        paper_bgcolor=CHART_BACKGROUND,
        plot_bgcolor=CHART_BACKGROUND,
        polar=dict(
            bgcolor=CHART_BACKGROUND,
            gridshape="linear",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False,
                gridcolor=GRID_COLOR,
            ),
            angularaxis=dict(gridcolor=GRID_COLOR),
        ),
        showlegend=False,
        height=400,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig
