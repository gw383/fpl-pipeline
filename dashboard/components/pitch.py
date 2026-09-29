"""The football-pitch graphic used for the Home page's Best XI and My Team."""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterable

import pandas as pd

from formatting import image_base64
from settings import PITCH_IMAGE
from theme import TEXT_PRIMARY, YELLOW


def pitch_html(players: pd.DataFrame, card: Callable[[pd.Series], str], height: int = 540) -> str:
    """Lay ``players`` out on a pitch: one row per position (GK at the top),
    each rendered with ``card``. ``players`` needs a ``p_position`` column."""
    rows: Iterable[str] = (
        "".join(card(row) for _, row in players[players["p_position"] == position].iterrows())
        for position in (1, 2, 3, 4)
    )
    row_html = "".join(
        f'<div style="display:flex;justify-content:space-evenly;align-items:center;min-width:0;">{cards}</div>'
        for cards in rows
    )
    return f"""
    <div style="
        width:100%;
        height:{height}px;
        margin-top:5px;
        border-radius:12px;
        padding:20px 8px;
        box-sizing:border-box;
        background-image:linear-gradient(rgba(0,0,0,0.05), rgba(0,0,0,0.05)),
            url('data:image/jpeg;base64,{image_base64(PITCH_IMAGE)}');
        background-size:100% 100%;
        background-repeat:no-repeat;
        display:grid;
        grid-template-rows:repeat(4, 1fr);
    ">
        {row_html}
    </div>
    """


# A plain football shirt (not any club's actual kit): body in the club's
# primary colour, collar and cuffs in its secondary colour. Goalkeepers swap
# the two so they stand out, as on FPL's own team sheet.
_SHIRT_BODY = "M22 4 L12 7 L2 18 L10 27 L16 22 L16 58 L48 58 L48 22 L54 27 L62 18 L52 7 L42 4 Q32 13 22 4 Z"
_SHIRT_CUFFS = "M2 18 L10 27 L12.5 25.3 L4.6 16.2 Z M62 18 L54 27 L51.5 25.3 L59.4 16.2 Z"
_SHIRT_COLLAR = "M22 4 Q32 13 42 4 L39 3.2 Q32 9.5 25 3.2 Z"


def _colour(value, fallback: str) -> str:
    return value if isinstance(value, str) and value.startswith("#") else fallback


def shirt_svg(primary: str | None, secondary: str | None, goalkeeper: bool = False, size: int = 38) -> str:
    """A shirt in club colours, as an ``<img>`` holding an SVG data URI.

    Streamlit's ``st.html`` sanitises with DOMPurify's HTML-only profile,
    which strips inline ``<svg>`` elements, so the SVG goes in an image
    instead (data-URI images are allowed).
    """
    body, trim = _colour(primary, "#9aa0a6"), _colour(secondary, "#ffffff")
    if goalkeeper:
        body, trim = trim, body
    outline = "rgba(0,0,0,0.35)"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 60">'
        f'<path d="{_SHIRT_BODY}" fill="{body}" stroke="{outline}" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<path d="{_SHIRT_CUFFS}" fill="{trim}"/>'
        f'<path d="{_SHIRT_COLLAR}" fill="{trim}" stroke="{outline}" stroke-width="1"/>'
        "</svg>"
    )
    data = base64.b64encode(svg.encode()).decode()
    return (
        f'<img src="data:image/svg+xml;base64,{data}" width="{size}" height="{int(size * 60 / 64)}" alt="" '
        'style="display:block;margin:0 auto 3px auto;filter:drop-shadow(0 1px 1.5px rgba(0,0,0,0.3));">'
    )


def _row_shirt(row: pd.Series) -> str:
    return shirt_svg(
        row.get("team_primary_colour"),
        row.get("team_secondary_colour"),
        goalkeeper=int(row["p_position"]) == 1,
    )


def _display_name(row: pd.Series) -> str:
    web_name = row.get("web_name")
    return web_name if isinstance(web_name, str) and web_name else row["player"]


def _name_plate(name: str, subtitle: str = "") -> str:
    subtitle_html = (
        f'<div style="font-size:9px;font-weight:600;color:#6b6b6b;margin-top:1px;">{subtitle}</div>' if subtitle else ""
    )
    return f"""
    <div style="
        background:#ffffff;
        border-radius:6px;
        padding:5px 4px;
        box-shadow:0 1px 3px rgba(0,0,0,0.18);
        font-size:11px;
        font-weight:700;
        line-height:13px;
        color:{TEXT_PRIMARY};
    ">
        {name}{subtitle_html}
    </div>
    """


def _value_pill(text: str) -> str:
    return f"""
    <div style="
        display:inline-block;
        background:rgba(11,11,11,0.55);
        border-radius:999px;
        padding:2px 8px;
        font-size:10px;
        font-weight:700;
        color:white;
        margin-top:4px;
    ">
        {text}
    </div>
    """


def _format_metric(value) -> str:
    value = float(value)
    return f"{value:.0f}" if value.is_integer() else f"{value:.2f}"


def best_xi_card(row: pd.Series) -> str:
    """Club shirt, player name and team, with the selected metric underneath."""
    return f"""
    <div style="text-align:center;width:84px;">
        {_row_shirt(row)}
        {_name_plate(_display_name(row), row.get("team_short_name") or "")}
        {_value_pill(_format_metric(row["metric_value"]))}
    </div>
    """


def squad_card(row: pd.Series) -> str:
    """Squad player with team, expected points next gameweek and a
    captain/vice-captain badge."""
    badge = "C" if row["is_captain"] else "VC" if row["is_vice_captain"] else ""
    badge_html = ""
    if badge:
        multiplier = f" &times;{int(row['multiplier'])}" if row["multiplier"] and row["multiplier"] > 1 else ""
        badge_html = f"""
        <div style="
            position:absolute;
            top:-4px;
            right:2px;
            z-index:2;
            background:{YELLOW};
            color:white;
            font-size:10px;
            font-weight:800;
            border-radius:999px;
            padding:2px 6px;
            box-shadow:0 1px 3px rgba(0,0,0,0.3);
        ">
            {badge}{multiplier}
        </div>
        """

    xpts = row.get("xpts_next_gw")
    xpts_html = _value_pill(f"{float(xpts):.1f} xP") if pd.notna(xpts) else ""
    return f"""
    <div style="text-align:center;width:84px;position:relative;">
        {badge_html}
        {_row_shirt(row)}
        {_name_plate(_display_name(row), row["team_short_name"])}
        {xpts_html}
    </div>
    """
