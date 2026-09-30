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
        f'<div class="fpl-pitch-row" style="display:flex;justify-content:space-evenly;align-items:center;'
        f'min-width:0;">{cards}</div>'
        for cards in rows
    )
    return f"""
    <div class="fpl-pitch" style="
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
        f'<img class="fpl-shirt" src="data:image/svg+xml;base64,{data}" width="{size}" '
        f'height="{int(size * 60 / 64)}" alt="" '
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
        f'<div class="fpl-plate-sub" style="font-size:9px;font-weight:600;color:#6b6b6b;margin-top:1px;">'
        f"{subtitle}</div>"
        if subtitle
        else ""
    )
    return f"""
    <div class="fpl-plate" style="
        background:#ffffff;
        border-radius:6px;
        padding:5px 4px;
        box-shadow:0 1px 3px rgba(0,0,0,0.18);
        font-size:11px;
        font-weight:700;
        line-height:13px;
        color:{TEXT_PRIMARY};
    ">
        <div class="fpl-plate-name">{name}</div>{subtitle_html}
    </div>
    """


def _value_pill(text: str) -> str:
    return f"""
    <div class="fpl-pill" style="
        display:inline-block;
        background:rgba(11,11,11,0.55);
        border-radius:999px;
        padding:2px 8px;
        font-size:10px;
        font-weight:700;
        color:white;
        margin-top:4px;
        white-space:nowrap;
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
    <div class="fpl-pitch-card" style="text-align:center;width:84px;">
        {_row_shirt(row)}
        {_name_plate(_display_name(row), row.get("team_short_name") or "")}
        {_value_pill(_format_metric(row["metric_value"]))}
    </div>
    """


def _number(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if value != value else value


def team_expected_points(squad: pd.DataFrame) -> float | None:
    """The team's expected points for the gameweek, counted the way FPL
    counts actual points: each pick's expected points times his multiplier
    (captain x2, triple captain x3, bench x0 unless Bench Boost). None when
    there are no expected points to count."""
    if "gw_xpts" not in squad or squad["gw_xpts"].notna().sum() == 0:
        return None
    return float((squad["gw_xpts"].fillna(0.0) * squad["multiplier"].fillna(0)).sum())


def gameweek_points_html(row: pd.Series, multiplier: int = 1) -> str:
    """Points pills for a squad player's gameweek: actual points (times the
    captaincy multiplier) next to what the model expected once his team has
    kicked off; before that, just the expected points. "Blank" when his team
    has no fixture."""
    fixtures = _number(row.get("gw_fixtures"))
    kicked_off = _number(row.get("gw_kicked_off")) or 0
    expected = _number(row.get("gw_xpts"))
    actual = _number(row.get("gw_points"))
    if fixtures == 0:
        return _value_pill("Blank")
    expected_html = _value_pill(f"{expected * multiplier:.1f} xP") if expected is not None else ""
    if kicked_off > 0:
        points = int((actual or 0) * multiplier)
        actual_html = f"""
        <div class="fpl-pill" style="display:inline-block;background:#ffffff;color:{TEXT_PRIMARY};border-radius:999px;
                    padding:2px 6px;
                    font-size:10.5px;font-weight:800;margin-top:4px;box-shadow:0 1px 2px rgba(0,0,0,0.25);
                    white-space:nowrap;">
            {points} pts
        </div>
        """
        return (
            '<div class="fpl-pills" style="display:flex;justify-content:center;gap:3px;flex-wrap:nowrap;">'
            f"{actual_html}{expected_html}</div>"
        )
    return expected_html


def squad_card(row: pd.Series) -> str:
    """Squad player with team, his points and expected points in the
    gameweek shown (see gameweek_points_html) and a captain/vice-captain
    badge. Without gameweek data it falls back to expected points next
    gameweek."""
    badge = "C" if row["is_captain"] else "VC" if row["is_vice_captain"] else ""
    badge_html = ""
    multiplier = int(row["multiplier"]) if pd.notna(row.get("multiplier")) and row["multiplier"] > 1 else 1
    if badge:
        multiplier_text = f" &times;{multiplier}" if multiplier > 1 else ""
        badge_html = f"""
        <div class="fpl-captain" style="
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
            {badge}{multiplier_text}
        </div>
        """

    if "gw_fixtures" in row.index:
        points_html = gameweek_points_html(row, multiplier)
    else:
        xpts = row.get("xpts_next_gw")
        points_html = _value_pill(f"{float(xpts):.1f} xP") if pd.notna(xpts) else ""
    return f"""
    <div class="fpl-pitch-card" style="text-align:center;width:104px;position:relative;">
        {badge_html}
        {_row_shirt(row)}
        {_name_plate(_display_name(row), row["team_short_name"])}
        {points_html}
    </div>
    """
