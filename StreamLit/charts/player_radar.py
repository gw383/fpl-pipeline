import plotly.graph_objects as go


def player_radar(
    position,
    points,
    max_points,
    goals,
    max_goals,
    assists,
    max_assists,
    bonus,
    max_bonus,
    defcons_p90,
    max_dcp90,
    clean_sheets,
    max_cs,
    saves,
    max_saves,
    pens_saved,
    max_pens_saved,
    selected_player,
    primary
):

    if position == "Goalkeeper":

        categories = [
            "Saves",
            "Penalty Saves",
            "Bonus",
            "Clean Sheets",
            "Points"
        ]

        player_values = [
            saves / max_saves * 100 if max_saves else 0,
            pens_saved / max_pens_saved * 100 if max_pens_saved else 0,
            bonus / max_bonus * 100 if max_bonus else 0,
            clean_sheets / max_cs * 100 if max_cs else 0,
            points / max_points * 100 if max_points else 0
        ]

    else:

        categories = [
            "Goals",
            "Assists",
            "Bonus",
            "Def Con /90",
            "Clean Sheets"
        ]

        player_values = [
            goals / max_goals * 100 if max_goals else 0,
            assists / max_assists * 100 if max_assists else 0,
            bonus / max_bonus * 100 if max_bonus else 0,
            defcons_p90 / max_dcp90 * 100 if max_dcp90 else 0,
            clean_sheets / max_cs * 100 if max_cs else 0
        ]


    # Close radar shape
    categories.append(categories[0])
    player_values.append(player_values[0])


    fig_radar = go.Figure()

    fig_radar.add_trace(
        go.Scatterpolar(
            r=player_values,
            theta=categories,
            fill="toself",
            name=selected_player,
            line=dict(
                color=primary,
                width=3
            ),
            fillcolor=primary,
            opacity=0.35
        )
    )


    fig_radar.update_layout(
        title="Player Profile",
        paper_bgcolor="#f2f2f2",
        plot_bgcolor="#f2f2f2",
        polar=dict(
            bgcolor="#f2f2f2",
            gridshape="linear",
            radialaxis=dict(
                visible=True,
                range=[0,100],
                showticklabels=False,
                gridcolor="#d9d9d9"
            ),
            angularaxis=dict(
                gridcolor="#d9d9d9"
            )
        ),
        showlegend=False,
        height=400,
        margin=dict(
            l=40,
            r=40,
            t=60,
            b=40
        )
    )

    return fig_radar
