"""Pure display helpers shared by the pages (no Streamlit, no database)."""

from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import pandas as pd

from theme import ORANGE, STATUS_CRITICAL, STATUS_SERIOUS, STATUS_WARNING

# News banners are coloured by the "X% chance of playing" phrase FPL uses;
# checked in order, first match wins.
NEWS_BANNER_STYLES = [
    ("25%", STATUS_WARNING, "#222"),
    ("50%", STATUS_SERIOUS, "#222"),
    ("75%", ORANGE, "#fff"),
]
DEFAULT_NEWS_BANNER = (STATUS_CRITICAL, "#fff")


def per_90(value: float, minutes: int, decimals: int = 1) -> float:
    """Pro-rate a total to a per-90-minutes rate; 0 if no minutes were played."""
    if not minutes:
        return 0
    return round(value * 90 / minutes, decimals)


def ordinal(n: int) -> str:
    """Ordinal suffix for ``n``: 1 -> "st", 12 -> "th", 22 -> "nd"."""
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def star_fill(rating: float) -> list[float]:
    """How full each of five stars is (0, 0.5 or 1) for a 0-10 rating.

    A star is half-filled when the remainder is at least a quarter star,
    e.g. 5.0 -> [1, 1, 0.5, 0, 0].
    """
    stars = max(0.0, min(10.0, float(rating))) / 2
    full = int(stars)
    half = 0.5 if stars - full >= 0.25 else 0.0
    return [1.0] * full + ([half] if full < 5 else []) + [0.0] * (4 - full)


def stars_html(
    rating: float, size: int = 20, colour: str = "#f5b301", empty_colour: str = "rgba(255,255,255,0.35)"
) -> str:
    """Five stars drawn with CSS (full, half or empty) so they render the same
    in every font; callers add the numeric rating alongside."""
    spans = []
    for fill in star_fill(rating):
        if fill == 1:
            style = f"color:{colour};"
        elif fill == 0.5:
            style = (
                f"background:linear-gradient(90deg,{colour} 50%,{empty_colour} 50%);"
                "-webkit-background-clip:text;background-clip:text;color:transparent;"
            )
        else:
            style = f"color:{empty_colour};"
        spans.append(f'<span style="{style}">★</span>')
    return (
        f'<span class="fpl-stars" style="font-size:{size}px;letter-spacing:1px;line-height:1;">{"".join(spans)}</span>'
    )


def news_banner_html(news, single_line: bool = False) -> str:
    """An inline pill showing a player's latest news, coloured by severity.

    Returns an empty string when there is no news. ``single_line`` truncates
    long news with an ellipsis (full text on hover) so the pill's height is
    predictable.
    """
    if news is None or pd.isna(news) or not news:
        return ""

    text = str(news)
    background, color = DEFAULT_NEWS_BANNER
    for token, bg, fg in NEWS_BANNER_STYLES:
        if token in text:
            background, color = bg, fg
            break

    truncate = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" if single_line else ""
    return f"""
    <div class="fpl-news-pill" title="{html.escape(text, quote=True)}" style="
        {truncate}
        display:inline-block;
        box-sizing:border-box;
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
        ⚠️ {text}
    </div>
    """


def build_contributor_strings(contributors: pd.DataFrame) -> dict[int, tuple[str, str]]:
    """``{gw_id: (scorers, assisters)}``, e.g. ``{11: ("Salah (2), Gakpo", "Robertson")}``.

    A count is shown only when a player scored/assisted more than once.
    """

    def fmt(rows: pd.DataFrame, column: str) -> str:
        rows = rows[rows[column] > 0].sort_values(column, ascending=False, kind="stable")
        return ", ".join(
            f"{player} ({int(count)})" if count > 1 else str(player)
            for player, count in zip(rows["player"], rows[column], strict=False)
        )

    if contributors.empty:
        return {}
    return {int(gw_id): (fmt(group, "goals"), fmt(group, "assists")) for gw_id, group in contributors.groupby("gw_id")}


@lru_cache(maxsize=64)
def image_base64(path: Path) -> str:
    """Base64-encode an image file for inline ``data:`` URIs ("" if missing)."""
    try:
        return base64.b64encode(Path(path).read_bytes()).decode()
    except OSError:
        return ""
