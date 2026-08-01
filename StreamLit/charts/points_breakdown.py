import pandas as pd
import plotly.express as px


def points_breakdown_chart(
    pf_goals,
    pf_assists,
    pf_minutes,
    pf_bonus,
    pf_cs,
    pf_defcon,
    pf_saves,
    pf_pen_saves,
    pf_yellow,
    pf_red,
    pf_goals_conceded,
    pf_own_goals,
    pf_pen_missed
):

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

    points_breakdown = pd.DataFrame(
        breakdown_raw,
        columns=["Category", "Points"]
    )

    points_breakdown = points_breakdown[
        points_breakdown["Points"] != 0
    ].copy()

    points_breakdown["Label"] = (
        points_breakdown["Points"].astype(int)
    )

    points_breakdown["Magnitude"] = (
        points_breakdown["Points"].abs()
    )

    points_breakdown["Type"] = points_breakdown["Points"].apply(
        lambda x: "Positive" if x > 0 else "Negative"
    )

    points_breakdown = points_breakdown.sort_values(
        "Magnitude",
        ascending=True
    )

    total_points_from_breakdown = points_breakdown["Points"].sum()

    fig_breakdown = px.bar(
        points_breakdown,
        x="Magnitude",
        y="Category",
        orientation="h",
        color="Type",
        text="Label",
        title="Points Breakdown",
        color_discrete_map={
            "Positive": "#2ecc71",
            "Negative": "#e74c3c"
        }
    )

    fig_breakdown.update_traces(
        textposition="outside",
        marker_line_width=0
    )

    fig_breakdown.update_layout(
        paper_bgcolor="#f2f2f2",
        plot_bgcolor="#f2f2f2",
        showlegend=False,
        title_x=0.5,
        xaxis_title="Fantasy Points",
        yaxis_title="",
        height=430,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        )
    )

    fig_breakdown.update_xaxes(
        showgrid=False,
        zeroline=False
    )

    fig_breakdown.update_yaxes(
        showgrid=False
    )

    return fig_breakdown, total_points_from_breakdown
