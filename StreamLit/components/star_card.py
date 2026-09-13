"""A single top-rated player card for the Home page.

Deliberately price/ownership-free, unlike differential_card -- this list
is "who looks best going forward" on the star rating alone (which itself
never factors in price; see transformation/models/analytics/player_rating.sql),
not a value or budget view.
"""

POSITION_LABELS = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}


def star_card(row) -> str:
    """Render one top-rated player as an HTML card: name, position and
    star rating.
    """
    position_label = POSITION_LABELS.get(int(row["p_position"]), "")
    rating = float(row["rating"]) if row["rating"] is not None else 0.0

    return f"""
    <div style="
        background:white;
        border-radius:8px;
        padding:8px 10px;
        width:150px;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
    ">

        <div style="
            font-size:13px;
            font-weight:700;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        ">
            {row['player']}
        </div>

        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-top:6px;
        ">
            <div style="font-size:11px;color:#777;">
                {position_label}
            </div>
            <div style="
                font-size:12px;
                font-weight:700;
                color:#333;
            ">
                {rating:.1f}/10
            </div>
        </div>

    </div>
    """
