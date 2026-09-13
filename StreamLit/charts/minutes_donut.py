"""Donut chart: minutes played vs. minutes not played this season."""
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

CHART_BACKGROUND = "#f2f2f2"
PLAYED_COLOR = "#2ecc71"
NOT_PLAYED_COLOR = "#e74c3c"


def minutes_donut_chart(minutes: int, minutes_not_played: int) -> Figure:
    """Build the minutes-played donut chart for a player."""
    minutes_data = pd.DataFrame({
        "Category": ["Played", "Not Played"],
        "Minutes": [minutes, minutes_not_played],
    })

    fig = px.pie(
        minutes_data,
        values="Minutes",
        names="Category",
        hole=0.70,
        title="Minutes Played",
    )

    fig.update_traces(
        marker=dict(colors=[PLAYED_COLOR, NOT_PLAYED_COLOR]),
        textinfo="percent+label",
    )

    fig.add_annotation(
        text=f"{minutes:,}<br>mins",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=22),
    )

    fig.update_layout(
        paper_bgcolor=CHART_BACKGROUND,
        plot_bgcolor=CHART_BACKGROUND,
        showlegend=False,
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig
