"""Small, pure display-formatting helpers used by pages/Player.py.

Pulled out of Player.py so they can be unit tested without a Streamlit
runtime or a database connection (see tests/test_player_utils.py) --
none of these touch st.* or the database, they just transform values
that are already in hand.
"""
import pandas as pd

# News banners are colour-coded by the "X% chance of playing" phrase
# FPL uses in its news text. Checked in this order (first match wins).
NEWS_BANNER_STYLES = [
    ("25%", "#fff3b0", "#222"),
    ("50%", "#ffd08a", "#222"),
    ("75%", "#e8903a", "#222"),
]
DEFAULT_NEWS_BANNER = ("#d9534f", "#fff")


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
        position:absolute;
        left:48%;
        right:21%;
        top:50%;
        transform:translateY(-50%);
        color:{color};
        font-size:17px;
        font-weight:600;
        line-height:1.35;
        z-index:2;
        background:{background};
        padding:10px 16px;
        border-radius:12px;
        width:max-content;
        max-width:45%;
    ">
        ⚠️ {news}
    </div>
    """
