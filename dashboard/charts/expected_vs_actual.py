"""Grouped bar chart of actual output vs expected output (goals vs xG,
assists vs xA and, for goalkeepers/defenders, goals conceded vs xGA) --
is a player finishing above their chances, or running hot?"""

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from theme import ACTUAL_COLOUR, EXPECTED_COLOUR, GRIDLINE, apply_chart_theme

# Only these positions lose points for goals conceded.
_GOALS_CONCEDED_POSITIONS = {"Goalkeeper", "Defender"}


def expected_vs_actual_chart(
    goals: float,
    xg: float,
    assists: float,
    xa: float,
    goals_conceded: float,
    xga: float,
    position: str,
) -> Figure:
    """Build the chart; the goals-conceded pair only appears for GK/DEF."""
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
        color_discrete_map={
            "Actual": ACTUAL_COLOUR,
            "Expected": EXPECTED_COLOUR,
        },
    )

    fig.update_traces(textposition="outside", marker_line_width=0, cliponaxis=False)

    apply_chart_theme(fig, height=360)
    fig.update_layout(
        legend_title_text="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=56, r=24, t=40, b=40),
        xaxis_title="",
        yaxis_title="Total",
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRIDLINE, zeroline=False)

    return fig
