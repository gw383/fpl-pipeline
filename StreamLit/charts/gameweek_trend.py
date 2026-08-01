import plotly.express as px


def gameweek_trend(
    gwk_points,
    primary
):

    fig_gameweek = px.line(
        gwk_points,
        x="gameweek",
        y="points",
        markers=True,
        title="Points by Gameweek"
    )

    fig_gameweek.update_traces(
        line=dict(
            color=primary,
            width=4
        ),
        marker=dict(
            color=primary,
            size=8
        )
    )

    fig_gameweek.update_layout(
        paper_bgcolor="#f2f2f2",
        plot_bgcolor="#f2f2f2",
        showlegend=False,
        title_x=0.5,
        xaxis_title="Gameweek",
        yaxis_title="Points",
        height=400,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        )
    )

    fig_gameweek.update_xaxes(
        dtick=1,
        showgrid=False
    )

    fig_gameweek.update_yaxes(
        showgrid=True,
        gridcolor="#dddddd",
        zeroline=False
    )

    return fig_gameweek
