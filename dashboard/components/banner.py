"""Full-width club-coloured header used by the Player, Compare and Team pages."""

from __future__ import annotations

from formatting import image_base64, stars_html
from settings import BADGES_DIR
from theme import BORDER, RADIUS, SHADOW_CARD, SURFACE, readable_text_colour

# min height, badge size, left padding, badge panel width/offset
_SIZES = {
    "large": dict(height=140, badge=100, left=40, panel_width="15%", panel_right="5%"),
    "medium": dict(height=120, badge=80, left=40, panel_width="15%", panel_right="5%"),
    "compact": dict(height=120, badge=64, left=22, panel_width="20%", panel_right="4%"),
}


def banner_text_colour(primary_colour: str | None) -> str:
    """The text colour banner bodies should use on ``primary_colour``."""
    return readable_text_colour(primary_colour or "#2a78d6")


def banner_stars_html(rating: float, primary_colour: str | None, size: int = 22) -> str:
    """Star rating plus "x.x/10", with empty stars that show on the banner colour."""
    light_text = banner_text_colour(primary_colour) == "#ffffff"
    empty = "rgba(255,255,255,0.35)" if light_text else "rgba(11,11,11,0.18)"
    return (
        f"{stars_html(rating, size=size, empty_colour=empty)}"
        f'<span style="font-size:{int(size * 0.75)}px;font-weight:700;margin-left:8px;">{rating:.1f}/10</span>'
    )


def club_banner_html(
    body_html: str,
    primary_colour: str | None,
    secondary_colour: str | None,
    badge_file: str | None,
    size: str = "large",
    min_height: int | None = None,
) -> str:
    """A banner in the club's primary colour with ``body_html`` on the left and
    the club badge on a secondary-colour panel on the right.

    ``min_height`` overrides the size's default, e.g. so two banners shown
    side by side can be given the same height."""
    dims = _SIZES[size]
    primary = primary_colour or "#2a78d6"
    secondary = secondary_colour or SURFACE
    badge = image_base64(BADGES_DIR / badge_file) if badge_file else ""
    badge_img = (
        f'<img src="data:image/png;base64,{badge}" style="position:absolute;top:50%;left:50%;'
        f"transform:translate(-50%,-50%);width:{dims['badge']}px;height:{dims['badge']}px;"
        f'object-fit:contain;">'
        if badge
        else ""
    )

    # The body sits in normal flow so a news line can grow the banner instead
    # of overflowing it; the badge panel is pinned to the right.
    return f"""
    <div style="
        min-height:{min_height or dims["height"]}px;
        width:100%;
        position:relative;
        display:flex;
        align-items:center;
        box-sizing:border-box;
        padding:16px calc({dims["panel_width"]} + {dims["panel_right"]} + 16px) 16px {dims["left"]}px;
        background:{primary};
        border-radius:{RADIUS};
        overflow:hidden;
        margin-bottom:{22 if size != "compact" else 14}px;
        box-shadow:{SHADOW_CARD};
        border:1px solid {BORDER};
    ">
        <div style="
            position:relative;
            color:{banner_text_colour(primary_colour)};
            z-index:2;
            flex:1 1 auto;
            min-width:0;
            max-width:100%;
        ">
            {body_html}
        </div>
        <div style="
            position:absolute;
            right:{dims["panel_right"]};
            top:0;
            height:100%;
            width:{dims["panel_width"]};
            background:{secondary};
        ">
            {badge_img}
        </div>
    </div>
    """
