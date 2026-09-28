"""A single top-rated player card for the Home page.

Deliberately price/ownership-free, unlike differential_card -- this list
is "who looks best going forward" on the star rating alone (which itself
never factors in price; see transformation/models/analytics/player_rating.sql),
not a value or budget view.
"""
from theme import BORDER, POSITION_COLOURS, POSITION_LABELS, RADIUS_SM, SHADOW_CARD, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY


def star_card(row) -> str:
    """Render one top-rated player as an HTML card: name, position and
    star rating.
    """
    position_id = int(row["p_position"])
    position_label = POSITION_LABELS.get(position_id, "")
    accent = POSITION_COLOURS.get(position_id, TEXT_SECONDARY)
    rating = float(row["rating"]) if row["rating"] is not None else 0.0

    return f"""
    <div style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-left:3px solid {accent};
        border-radius:{RADIUS_SM};
        padding:9px 12px;
        box-shadow:{SHADOW_CARD};
    ">

        <div style="
            font-size:13px;
            font-weight:700;
            color:{TEXT_PRIMARY};
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
            <div style="
                font-size:11px;
                font-weight:700;
                letter-spacing:0.03em;
                color:{accent};
            ">
                {position_label}
            </div>
            <div style="
                font-size:12px;
                font-weight:700;
                color:{TEXT_PRIMARY};
                font-variant-numeric:tabular-nums;
            ">
                {rating:.1f}/10
            </div>
        </div>

    </div>
    """
