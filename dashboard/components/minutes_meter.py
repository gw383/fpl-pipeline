"""Minutes played as a stat tile plus a meter against the minutes available."""

from theme import (
    CHART_SURFACE,
    NOT_PLAYED_COLOUR,
    PLAYED_COLOUR,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def minutes_meter_html(minutes: int, minutes_not_played: int, height: int = 340) -> str:
    """Minutes played as the headline number, with a meter whose unfilled
    remainder is the minutes not played."""
    total = minutes + minutes_not_played
    pct = (minutes / total * 100) if total else 0.0

    return f"""
    <div style="
        height:{height}px;
        box-sizing:border-box;
        background:{CHART_SURFACE};
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        padding:20px;
        text-align:center;
    ">

        <div style="font-size:44px;font-weight:700;color:{TEXT_PRIMARY};line-height:1;">
            {minutes:,}
        </div>
        <div style="font-size:13px;color:{TEXT_MUTED};font-weight:600;margin-top:6px;margin-bottom:22px;">
            of {total:,} possible minutes ({pct:.0f}%)
        </div>

        <div style="
            width:100%;
            max-width:260px;
            height:14px;
            border-radius:999px;
            background:{NOT_PLAYED_COLOUR};
            overflow:hidden;
        ">
            <div style="height:100%;width:{pct:.1f}%;border-radius:999px;background:{PLAYED_COLOUR};"></div>
        </div>

        <div style="
            display:flex;
            justify-content:center;
            gap:18px;
            margin-top:12px;
            font-size:12px;
            font-weight:600;
            color:{TEXT_MUTED};
        ">
            <span><span style="color:{PLAYED_COLOUR};">&#9679;</span> Played</span>
            <span><span style="color:{NOT_PLAYED_COLOUR};">&#9679;</span> Not played</span>
        </div>
    </div>
    """
