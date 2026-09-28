"""A single in-form differential player card for the Home page."""
from theme import (
    AQUA,
    BORDER,
    POSITION_COLOURS,
    POSITION_LABELS,
    RADIUS_SM,
    SHADOW_CARD,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def differential_card(row) -> str:
    """Render one differential (low-ownership, in-form player) as an
    HTML card: name, position, price, ownership % and quality score.

    Round 7 note: this used to show recent_form_score, the old rating
    model's dedicated last-5-gameweek ingredient. That ingredient no
    longer exists as a separate column -- player_rating.sql's rewrite
    folded "is this player playing well lately" into quality_score itself
    (a recency-weighted rate that leans heavily on recent gameweeks
    without a hard cutoff), so this card now shows that instead.
    """
    position_id = int(row["p_position"])
    position_label = POSITION_LABELS.get(position_id, "")
    accent = POSITION_COLOURS.get(position_id, TEXT_MUTED)
    ownership = float(row["ownership"]) if row["ownership"] is not None else 0.0
    price = float(row["price"]) if row["price"] is not None else 0.0
    quality = float(row["quality_score"]) if row["quality_score"] is not None else 0.0

    return f"""
    <div style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-left:3px solid {accent};
        border-radius:{RADIUS_SM};
        padding:9px 12px;
        width:160px;
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

        <div style="font-size:11px;color:{TEXT_MUTED};margin-top:2px;font-weight:600;">
            {position_label} &middot; &pound;{price}m
        </div>

        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-top:8px;
        ">
            <div style="font-size:11px;color:{TEXT_MUTED};">
                {ownership:.1f}% owned
            </div>
            <div style="
                font-size:12px;
                font-weight:700;
                color:{AQUA};
                font-variant-numeric:tabular-nums;
            ">
                {quality:.1f}
            </div>
        </div>

    </div>
    """
