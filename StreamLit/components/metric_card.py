"""A single headline stat with its positional rank, e.g. "Points: 82 (#3)"."""
import streamlit as st

from theme import BLUE, BORDER, RADIUS_SM, SHADOW_CARD, SURFACE, TEXT_MUTED, TEXT_PRIMARY, rgba


def metric_card(title: str, value, rank=None) -> None:
    """Render one metric card: a title, a big value, and an optional
    rank badge.

    The title and the rank badge share one flex row (rather than the
    badge being absolutely-positioned over the title) so a long title
    that wraps to two lines pushes the row taller instead of running
    underneath the badge.

    `rank` is optional (added for the My Team page's profile stats --
    overall rank, gameweek points, team value -- which have no natural
    "rank vs N players" to show, unlike every existing caller of this
    component). Every prior call site always passed a real rank, so
    this stays fully backwards compatible: passing rank is unchanged,
    and only omitting it (or passing None explicitly) is new.
    """
    rank_badge_html = (
        f"""
        <div style="
            flex-shrink:0;
            background:{rgba(BLUE, 0.10)};
            color:{BLUE};
            padding:4px 10px;
            border-radius:999px;
            font-size:12px;
            font-weight:700;
            white-space:nowrap;
        ">
            #{rank}
        </div>
        """
        if rank is not None
        else ""
    )

    st.html(
        f"""
        <div style="
            background:{SURFACE};
            border:1px solid {BORDER};
            border-radius:{RADIUS_SM};
            padding:14px 18px;
            min-height:95px;
            box-shadow:{SHADOW_CARD};
        ">

            <div style="
                display:flex;
                align-items:flex-start;
                justify-content:space-between;
                gap:8px;
            ">
                <div style="
                    font-size:12px;
                    font-weight:600;
                    letter-spacing:0.02em;
                    text-transform:uppercase;
                    color:{TEXT_MUTED};
                    flex:1;
                    min-width:0;
                ">
                    {title}
                </div>

                {rank_badge_html}
            </div>

            <div style="
                font-size:30px;
                font-weight:700;
                margin-top:8px;
                color:{TEXT_PRIMARY};
                font-variant-numeric:tabular-nums;
            ">
                {value}
            </div>
        </div>
        """
    )
