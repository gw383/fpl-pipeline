"""Small, pure display-formatting helpers used by pages/Player.py.

Pulled out of Player.py so they can be unit tested without a Streamlit
runtime or a database connection (see tests/test_player_utils.py) --
none of these touch st.* or the database, they just transform values
that are already in hand.
"""
import pandas as pd

from theme import ORANGE, STATUS_CRITICAL, STATUS_SERIOUS, STATUS_WARNING

# News banners are colour-coded by the "X% chance of playing" phrase
# FPL uses in its news text. Checked in this order (first match wins).
# Colours now come from the app's shared status palette (theme.py)
# rather than one-off hex values, but the matching order/behaviour is
# unchanged from before.
NEWS_BANNER_STYLES = [
    ("25%", STATUS_WARNING, "#222"),
    ("50%", STATUS_SERIOUS, "#222"),
    ("75%", ORANGE, "#fff"),
]
DEFAULT_NEWS_BANNER = (STATUS_CRITICAL, "#fff")


def per_90(value: float, minutes: int, decimals: int = 1) -> float:
    """Prorate a season total to a per-90-minutes rate; 0 if no minutes played."""
    if minutes == 0:
        return 0
    return round(value * 90 / minutes, decimals)


def recommendation_stars(star: float) -> str:
    """Convert a recommendation score out of 10 into a 5-star rating.

    Supports half stars.
    """
    stars = star / 2
    full_stars = int(stars)
    half_star = stars - full_stars >= 0.25
    empty_stars = 5 - full_stars - int(half_star)

    return "★" * full_stars + ("⯪" if half_star else "") + "☆" * empty_stars


def news_banner_html(news) -> str:
    """Render the player-header news banner, colour-coded by the
    playing-chance percentage mentioned in the news text (if any).

    This used to be its own absolutely-positioned box floating in the
    middle of the header (left:48%), independent of the player-name
    block next to it (which has no width limit of its own, so a longer
    name/star-rating combination could run straight into it -- visible
    as the two overlapping). It's now a plain, normal-flow pill meant
    to be placed as an extra line *inside* the same name/team/price
    block (see pages/Player.py), so it can never collide with
    anything -- it just takes its place in that block's own stack,
    however wide or narrow the text next to it happens to be.
    """
    if pd.isna(news) or not news:
        return ""

    text = str(news)
    background, color = DEFAULT_NEWS_BANNER
    for token, bg, fg in NEWS_BANNER_STYLES:
        if token in text:
            background, color = bg, fg
            break

    return f"""
    <div style="
        display:inline-block;
        margin-top:8px;
        color:{color};
        font-size:14px;
        font-weight:600;
        line-height:1.3;
        background:{background};
        padding:6px 14px;
        border-radius:999px;
        max-width:100%;
    ">
        ⚠️ {news}
    </div>
    """
