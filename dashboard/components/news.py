"""A single latest-news item, colour-coded by news type."""

from theme import (
    BLUE,
    BORDER,
    RADIUS_SM,
    SHADOW_CARD,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_WARNING,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

# Keyword in the news text -> accent colour (first match wins).
_NEWS_COLOURS = [
    ("injury", STATUS_CRITICAL),
    ("suspended", STATUS_WARNING),
    ("available", STATUS_GOOD),
]


def _news_colour(text: str) -> str:
    text = text.lower()
    return next((colour for keyword, colour in _NEWS_COLOURS if keyword in text), BLUE)


def news_card(row) -> str:
    """Render one news-feed row (player, headline, date) as an HTML card."""
    colour = _news_colour(str(row["news"]))

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
            {row["player"]}
        </div>

        <div style="font-size:12px;color:{TEXT_PRIMARY};margin-top:2px;">
            {row["news"]}
        </div>

        <div style="font-size:10px;color:{TEXT_MUTED};margin-top:4px;font-weight:600;">
            {row["date"].strftime("%d %b %H:%M") if hasattr(row["date"], "strftime") else row["date"]}
        </div>

    </div>
    """
