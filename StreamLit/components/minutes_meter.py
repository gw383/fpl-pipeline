"""Minutes-played meter, in place of a 2-slice donut chart.

"Minutes played vs. minutes not played" is a single ratio against a
limit (this season's total possible minutes) -- exactly the case the
dataviz skill calls out as a meter, not a pie/donut ("a single ratio
against a limit -> meter; not a pie of 2 slices"). A donut with only
two categories doesn't show anything a meter doesn't, and a meter reads
faster: one bar, one number, done.
"""
from theme import (
    CHART_SURFACE,
    NOT_PLAYED_COLOUR,
    PLAYED_COLOUR,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def minutes_meter_html(minutes: int, minutes_not_played: int, height: int = 420) -> str:
    """Render a stat-tile + meter: minutes played as the hero number,
    a meter bar for minutes played / total possible minutes, and the
    not-played minutes as the meter's own unfilled portion (rather than
    a separate lighter step of the same ramp) -- "not played" is an
    absence, not a second identity worth its own colour (see theme.py's
    NOT_PLAYED_COLOUR comment), so it's shown as a neutral remainder.
    """
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
        <div style="font-size:15px;font-weight:600;color:{TEXT_PRIMARY};margin-bottom:18px;">
            Minutes Played
        </div>

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
