"""A single compact row for the Rankings page's bigger per-position
leaderboard -- rank number, player name, star rating -- one row per
player rather than the card grid Home.py uses, since a list of 20-50
entries reads better as a scannable list than as a grid of cards.
"""
from theme import BORDER, POSITION_COLOURS, RADIUS_SM, SHADOW_CARD, SURFACE, TEXT_MUTED, TEXT_PRIMARY


def ranking_row_html(rank: int, row) -> str:
    """Render one leaderboard row: `rank` is this row's position in the
    list as displayed (1, 2, 3, ... -- see pages/Rankings.py for why
    this is a plain running count rather than a SQL rank column), not
    read off the row itself.
    """
    position_id = int(row["p_position"]) if row.get("p_position") is not None else 0
    accent = POSITION_COLOURS.get(position_id, TEXT_MUTED)
    rating = float(row["rating"]) if row["rating"] is not None else 0.0

    return f"""
    <div style="
        display:flex;
        align-items:center;
        gap:14px;
        background:{SURFACE};
        border:1px solid {BORDER};
        border-left:3px solid {accent};
        border-radius:{RADIUS_SM};
        padding:9px 16px;
        box-shadow:{SHADOW_CARD};
    ">
        <div style="
            font-size:12px;
            font-weight:700;
            color:{TEXT_MUTED};
            width:26px;
            flex-shrink:0;
            font-variant-numeric:tabular-nums;
        ">
            #{rank}
        </div>
        <div style="
            font-size:14px;
            font-weight:700;
            color:{TEXT_PRIMARY};
            flex:1;
            min-width:0;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        ">
            {row['player']}
        </div>
        <div style="
            font-size:13px;
            font-weight:700;
            color:{TEXT_PRIMARY};
            font-variant-numeric:tabular-nums;
            flex-shrink:0;
        ">
            {rating:.1f}/10
        </div>
    </div>
    """
