"""A single latest-news item, colour-coded by news type."""
from theme import BLUE, BORDER, RADIUS_SM, SHADOW_CARD, STATUS_CRITICAL, STATUS_GOOD, STATUS_WARNING, SURFACE, TEXT_MUTED, TEXT_PRIMARY

INJURY_COLOR = STATUS_CRITICAL
SUSPENDED_COLOR = STATUS_WARNING
AVAILABLE_COLOR = STATUS_GOOD
DEFAULT_COLOR = BLUE


def _news_colour(text: str) -> str:
    """Pick a highlight colour based on keywords in the news text."""
    if "injury" in text:
        return INJURY_COLOR
    if "suspended" in text:
        return SUSPENDED_COLOR
    if "available" in text:
        return AVAILABLE_COLOR
    return DEFAULT_COLOR


def news_card(row) -> str:
    """Render one news-feed row (player, headline, date) as an HTML card."""
    colour = _news_colour(row["news"].lower())

    return f"""
    <div style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-left:4px solid {colour};
        border-radius:{RADIUS_SM};
        padding:9px 11px;
        margin-bottom:6px;
        box-shadow:{SHADOW_CARD};
    ">

        <div style="font-weight:700;font-size:13px;color:{TEXT_PRIMARY};">
            {row['player']}
        </div>

        <div style="font-size:12px;color:{TEXT_PRIMARY};margin-top:2px;">
            {row['news']}
        </div>

        <div style="font-size:10px;color:{TEXT_MUTED};margin-top:4px;font-weight:600;">
            {row['date']}
        </div>

    </div>
    """
