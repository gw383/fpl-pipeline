"""Line chart: a player's fantasy points across gameweeks."""

import plotly.express as px
from plotly.graph_objects import Figure

from theme import GRIDLINE, apply_chart_theme


def gameweek_trend(gwk_points, primary: str) -> Figure:
    """Build the points-by-gameweek line chart for a player.

    Args:
        gwk_points: DataFrame with "gameweek" and "points" columns.
        primary: hex colour for the line/markers (the player's team colour).
    """
    fig = px.line(
        gwk_points,
        x="gameweek",
        y="points",
        markers=True,
    )

    fig.update_traces(
        line=dict(color=primary, width=3),
        marker=dict(color=primary, size=7, line=dict(color="#ffffff", width=1)),
    )

    apply_chart_theme(fig, height=340)
    fig.update_layout(
        showlegend=False,
        xaxis_title="Gameweek",
        yaxis_title="Points",
    )

    fig.update_xaxes(dtick=1, showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRIDLINE, zeroline=False)

    return fig
