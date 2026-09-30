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
    """A low-ownership player: name, position, price, ownership and expected
    points over the projection horizon."""
    position_id = int(row["p_position"])
    position_label = POSITION_LABELS.get(position_id, "")
    accent = POSITION_COLOURS.get(position_id, TEXT_MUTED)
    ownership = float(row["ownership"]) if row["ownership"] is not None else 0.0
    price = float(row["price"]) if row["price"] is not None else 0.0
    xpts = float(row["xpts_horizon"]) if row["xpts_horizon"] is not None else 0.0

    return f"""
    <div class="fpl-diff" style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-left:3px solid {accent};
        border-radius:{RADIUS_SM};
        padding:9px 12px;
        width:100%;
        box-sizing:border-box;
        margin-bottom:10px;
        box-shadow:{SHADOW_CARD};
    ">

        <div class="fpl-diff-name" style="
            font-size:13px;
            font-weight:700;
            color:{TEXT_PRIMARY};
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        ">
            {row["player"]}
        </div>

        <div style="font-size:11px;color:{TEXT_MUTED};margin-top:2px;font-weight:600;">
            {position_label} &middot; &pound;{price}m
        </div>

        <div class="fpl-diff-foot" style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-top:8px;
        ">
            <div class="fpl-diff-owned" style="font-size:11px;color:{TEXT_MUTED};">
                {ownership:.1f}% owned
            </div>
            <div style="
                font-size:12px;
                font-weight:700;
                color:{AQUA};
                font-variant-numeric:tabular-nums;
            ">
                {xpts:.1f} xP
            </div>
        </div>

    </div>
    """
