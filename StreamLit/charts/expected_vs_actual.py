"""Grouped bar chart: actual output vs. underlying expected output
(goals vs xG, assists vs xA, and -- for goalkeepers/defenders -- goals
conceded vs xGA).

This is the "is this player lucky or clinical" chart: a player scoring
well above their xG/xA is either finishing chances better than average
(a repeatable skill) or running hot (variance that regresses), and this
chart is what lets you eyeball the gap for yourself rather than only
seeing it folded into the player_rating star. See
transformation/models/analytics/player_rating.sql for how the same
actual-vs-expected idea feeds into the star rating itself.
"""
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

CHART_BACKGROUND = "#f2f2f2"
ACTUAL_COLOR = "#2ecc71"
EXPECTED_COLOR = "#3498db"

# Positions (as shown on the Player page, i.e. StreamLit/queries/player_info.py's
# pos_name) that also get a goals-conceded-vs-xGA bar -- conceding goals
# only affects fantasy points for these two positions, so it's the only
# case where that comparison is meaningful here.
_GOALS_CONCEDED_POSITIONS = {"Goalkeeper", "Defender"}


def expected_vs_actual_chart(
    goals: float, xg: float,
    assists: float, xa: float,
    goals_conceded: float, xga: float,
    position: str,
) -> Figure:
    """Build the expected-vs-actual bar chart for a player.

    goals_conceded/xga are only plotted for goalkeepers and defenders --
    for other positions a third bar pair would just be noise, since
    conceding goals doesn't cost them fantasy points.
    """
    pairs = [
        ("Goals", goals, xg),
        ("Assists", assists, xa),
    ]
    if position in _GOALS_CONCEDED_POSITIONS:
        pairs.append(("Goals Conceded", goals_conceded, xga))

    rows = []
    for category, actual, expected in pairs:
        rows.append({"Category": category, "Type": "Actual", "Value": round(actual, 1)})
        rows.append({"Category": category, "Type": "Expected", "Value": round(expected, 1)})

    data = pd.DataFrame(rows)

    fig = px.bar(
        data,
        x="Category",
        y="Value",
        color="Type",
        barmode="group",
        text="Value",
        title="Actual vs Expected",
        color_discrete_map={
            "Actual": ACTUAL_COLOR,
            "Expected": EXPECTED_COLOR,
        },
    )

    fig.update_traces(textposition="outside", marker_line_width=0)

    fig.update_layout(
        paper_bgcolor=CHART_BACKGROUND,
        plot_bgcolor=CHART_BACKGROUND,
        legend_title_text="",
        title_x=0.5,
        xaxis_title="",
        yaxis_title="Total",
        height=400,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#dddddd", zeroline=False)

    return fig
