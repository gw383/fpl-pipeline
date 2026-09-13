"""Line chart: a player's fantasy points across gameweeks."""
import plotly.express as px
from plotly.graph_objects import Figure

CHART_BACKGROUND = "#f2f2f2"
GRID_COLOR = "#dddddd"


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
        title="Points by Gameweek",
    )

    fig.update_traces(
        line=dict(color=primary, width=4),
        marker=dict(color=primary, size=8),
    )

    fig.update_layout(
        paper_bgcolor=CHART_BACKGROUND,
        plot_bgcolor=CHART_BACKGROUND,
        showlegend=False,
        title_x=0.5,
        xaxis_title="Gameweek",
        yaxis_title="Points",
        height=400,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(dtick=1, showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)

    return fig
