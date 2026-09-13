"""A single latest-news item, colour-coded by news type."""

INJURY_COLOR = "#d9534f"
SUSPENDED_COLOR = "#f0ad4e"
AVAILABLE_COLOR = "#5cb85c"
DEFAULT_COLOR = "#428bca"


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
        background:white;
        border-left:5px solid {colour};
        border-radius:8px;
        padding:8px 10px;
        margin-bottom:5px;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
    ">

        <div style="font-weight:700;">
            {row['player']}
        </div>

        <div style="font-size:12px;">
            {row['news']}
        </div>

        <div style="font-size:10px;color:#777;">
            {row['date']}
        </div>

    </div>
    """
