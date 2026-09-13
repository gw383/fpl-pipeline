"""Horizontal bar chart: how a player's fantasy points break down by category."""
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

CHART_BACKGROUND = "#f2f2f2"
POSITIVE_COLOR = "#2ecc71"
NEGATIVE_COLOR = "#e74c3c"


def points_breakdown_chart(
    pf_goals, pf_assists, pf_minutes, pf_bonus, pf_cs, pf_defcon,
    pf_saves, pf_pen_saves, pf_yellow, pf_red,
    pf_goals_conceded, pf_own_goals, pf_pen_missed,
) -> tuple[Figure, int]:
    """Build the points-breakdown bar chart for a player.

    Each argument is that category's contribution to total fantasy
    points (see queries/player_stats.py get_player_stats, columns
    prefixed pf_). Categories contributing zero points are hidden.

    Returns the figure and the total points implied by the visible
    categories (a cross-check against the "Points" metric card).
    """
    breakdown_raw = [
        ("Goals", pf_goals),
        ("Assists", pf_assists),
        ("Minutes", pf_minutes),
        ("Bonus", pf_bonus),
        ("Clean Sheets", pf_cs),
        ("Defensive Contributions", pf_defcon),
        ("Saves", pf_saves),
        ("Penalty Saves", pf_pen_saves),
        ("Yellow Cards", pf_yellow),
        ("Red Cards", pf_red),
        ("Goals Conceded", pf_goals_conceded),
        ("Own Goals", pf_own_goals),
        ("Penalties Missed", pf_pen_missed),
    ]

    breakdown = pd.DataFrame(breakdown_raw, columns=["Category", "Points"])
    breakdown = breakdown[breakdown["Points"] != 0].copy()

    breakdown["Label"] = breakdown["Points"].astype(int)
    breakdown["Magnitude"] = breakdown["Points"].abs()
    breakdown["Type"] = breakdown["Points"].apply(
        lambda x: "Positive" if x > 0 else "Negative"
    )
    breakdown = breakdown.sort_values("Magnitude", ascending=True)

    total_points_from_breakdown = breakdown["Points"].sum()

    fig = px.bar(
        breakdown,
        x="Magnitude",
        y="Category",
        orientation="h",
        color="Type",
        text="Label",
        title="Points Breakdown",
        color_discrete_map={
            "Positive": POSITIVE_COLOR,
            "Negative": NEGATIVE_COLOR,
        },
    )

    fig.update_traces(textposition="outside", marker_line_width=0)

    fig.update_layout(
        paper_bgcolor=CHART_BACKGROUND,
        plot_bgcolor=CHART_BACKGROUND,
        showlegend=False,
        title_x=0.5,
        xaxis_title="Fantasy Points",
        yaxis_title="",
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False)

    return fig, total_points_from_breakdown
