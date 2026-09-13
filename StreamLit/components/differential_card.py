"""A single in-form differential player card for the Home page."""

POSITION_LABELS = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}


def differential_card(row) -> str:
    """Render one differential (low-ownership, in-form player) as an
    HTML card: name, position, price, ownership % and recent-form score.
    """
    position_label = POSITION_LABELS.get(int(row["p_position"]), "")
    ownership = float(row["ownership"]) if row["ownership"] is not None else 0.0
    price = float(row["price"]) if row["price"] is not None else 0.0
    recent_form = float(row["recent_form_score"]) if row["recent_form_score"] is not None else 0.0

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

        <div style="font-size:11px;color:#777;margin-top:2px;">
            {position_label} • £{price}m
        </div>

        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-top:6px;
        ">
            <div style="font-size:11px;color:#555;">
                {ownership:.1f}% owned
            </div>
            <div style="
                font-size:12px;
                font-weight:700;
                color:#2ecc71;
            ">
                {recent_form:.1f}
            </div>
        </div>

    </div>
    """
