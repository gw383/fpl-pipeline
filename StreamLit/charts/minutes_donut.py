import pandas as pd
import plotly.express as px


def minutes_donut_chart(
    minutes,
    minutes_not_played
):

    minutes_data = pd.DataFrame({
        "Category": [
            "Played",
            "Not Played"
        ],
        "Minutes": [
            minutes,
            minutes_not_played
        ]
    })

    fig_minutes = px.pie(
        minutes_data,
        values="Minutes",
        names="Category",
        hole=0.70,
        title="Minutes Played"
    )

    fig_minutes.update_traces(
        marker=dict(
            colors=[
                "#2ecc71",
                "#e74c3c"
            ]
        ),
        textinfo="percent+label"
    )

    fig_minutes.add_annotation(
        text=f"{minutes:,}<br>mins",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(
            size=22
        )
    )

    fig_minutes.update_layout(
        paper_bgcolor="#f2f2f2",
        plot_bgcolor="#f2f2f2",
        showlegend=False,
        height=430,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        )
    )

    return fig_minutes
