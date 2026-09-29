"""Design system for the dashboard: colours, spacing, shared CSS and chart
chrome, so every page and component draws from one palette.

Categorical colours are assigned to a fixed identity (e.g. "Expected" is
always orange, forwards are always orange) and never cycled; status colours
are reserved for good/bad states.
"""

# ---------------------------------------------------------------------------
# Page / chart chrome
# ---------------------------------------------------------------------------

PAGE_BG = "#f7f7f5"  # page plane behind everything
SURFACE = "#ffffff"  # card background
CHART_SURFACE = SURFACE  # charts sit flush inside cards

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#898781"

GRIDLINE = "#e7e6e1"
BASELINE = "#c3c2b7"
BORDER = "rgba(11,11,11,0.08)"

SHADOW_CARD = "0 1px 2px rgba(11,11,11,0.04), 0 1px 8px rgba(11,11,11,0.05)"
SHADOW_HOVER = "0 6px 20px rgba(11,11,11,0.10)"

RADIUS = "14px"
RADIUS_SM = "10px"

FONT_STACK = '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

# ---------------------------------------------------------------------------
# Categorical palette -- fixed order, never cycled
# ---------------------------------------------------------------------------

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"

# ---------------------------------------------------------------------------
# Status palette -- state/severity only
# ---------------------------------------------------------------------------

STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

# ---------------------------------------------------------------------------
# Fixed per-identity colours
# ---------------------------------------------------------------------------

POSITION_COLOURS = {
    1: VIOLET,  # Goalkeeper
    2: BLUE,  # Defender
    3: AQUA,  # Midfielder
    4: ORANGE,  # Forward
}
POSITION_LABELS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# Actual outcome vs underlying expected (xG/xA/xGA).
ACTUAL_COLOUR = BLUE
EXPECTED_COLOUR = ORANGE

# Points that add to / subtract from a total.
POSITIVE_COLOUR = BLUE
NEGATIVE_COLOUR = RED

# Minutes meter: played vs a neutral "not played" remainder.
PLAYED_COLOUR = BLUE
NOT_PLAYED_COLOUR = "#dedcd4"

# FPL fixture difficulty (1 = easiest ... 5 = hardest), a green-to-red scale
# with every step dark enough to carry white text.
DIFFICULTY_COLOURS = {
    1: "#0ca34a",
    2: "#39944f",
    3: "#8a8880",
    4: "#d4602f",
    5: "#c0392f",
}

# Match results.
RESULT_COLOURS = {"W": STATUS_GOOD, "D": STATUS_WARNING, "L": STATUS_CRITICAL}


def difficulty_colour(difficulty) -> str:
    """Colour for an FPL difficulty rating; out-of-range values get the middle band."""
    try:
        return DIFFICULTY_COLOURS.get(int(difficulty), DIFFICULTY_COLOURS[3])
    except (TypeError, ValueError):
        return DIFFICULTY_COLOURS[3]


def readable_text_colour(background: str) -> str:
    """White or near-black text, whichever reads better on ``background``."""
    hex_colour = str(background).lstrip("#")
    if len(hex_colour) != 6:
        return "#ffffff"
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (0, 2, 4))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return TEXT_PRIMARY if luminance > 0.6 else "#ffffff"


def rgba(hex_colour: str, alpha: float) -> str:
    """``"#rrggbb"`` -> ``"rgba(r, g, b, alpha)"`` for translucent tints."""
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


BRAND_GRADIENT = f"linear-gradient(135deg, {VIOLET}, {BLUE})"
CONTENT_MAX_WIDTH = "1280px"


def inject_base_css() -> str:
    """Site-wide CSS, injected once per run by app.py."""
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, [class*="css"], button, input, select, textarea {{
        font-family: {FONT_STACK};
    }}
    .stApp {{ background-color: {PAGE_BG}; }}

    /* ---- Site header: Streamlit's top bar restyled as a nav bar ---- */
    header[data-testid="stHeader"] {{
        background: {SURFACE};
        border-bottom: 1px solid {BORDER};
        box-shadow: 0 1px 3px rgba(11,11,11,0.04);
    }}
    [data-testid="stAppDeployButton"], [data-testid="stDecoration"] {{ display: none; }}

    /* ---- Page body: clear the fixed header, centre like a website ---- */
    [data-testid="stMainBlockContainer"], .block-container {{
        padding-top: 5.5rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
        padding-bottom: 1.5rem;
        max-width: {CONTENT_MAX_WIDTH};
    }}

    h1, h2, h3 {{ color: {TEXT_PRIMARY}; font-weight: 700; letter-spacing: -0.01em; }}
    h3 {{ font-size: 18px; margin-bottom: 2px; }}
    [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED}; font-size: 13px; }}
    hr {{ border: none; border-top: 1px solid {BORDER}; margin: 26px 0; }}

    /* ---- Inputs ---- */
    [data-testid="stWidgetLabel"] p {{
        font-size: 12px; font-weight: 600; color: {TEXT_SECONDARY};
        text-transform: uppercase; letter-spacing: 0.04em;
    }}
    div[data-baseweb="select"] > div {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM};
        box-shadow: {SHADOW_CARD};
    }}
    div[data-baseweb="select"] > div:hover {{ border-color: {rgba(BLUE, 0.5)}; }}
    div[role="listbox"] {{ background-color: {SURFACE}; border-radius: {RADIUS_SM}; border: 1px solid {BORDER}; }}
    div[role="option"]:hover {{ background-color: {PAGE_BG}; }}

    /* Segmented controls / radios used as tabs. */
    [data-testid="stRadio"] label {{ font-weight: 600; }}

    /* ---- Cards: components.card.card() containers ---- */
    div[class*="st-key-card-"] {{
        background: {SURFACE};
        border: 1px solid {BORDER} !important;
        border-radius: {RADIUS} !important;
        box-shadow: {SHADOW_CARD};
        padding: 18px 20px !important;
    }}

    /* ---- Expanders used as list rows (ratings) ---- */
    div[data-testid="stElementContainer"]:has(> div[data-testid="stExpander"]) {{ margin-bottom: -0.45rem; }}
    [data-testid="stExpander"] details {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM};
        box-shadow: {SHADOW_CARD};
    }}
    [data-testid="stExpander"] summary {{ padding: 8px 12px; font-size: 13.5px; }}
    [data-testid="stExpander"] summary:hover {{ color: {BLUE}; }}
    [data-testid="stExpanderDetails"] {{ padding: 0 12px 10px 12px; }}

    /* ---- Tables ---- */
    [data-testid="stDataFrame"] {{
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
        overflow: hidden;
        box-shadow: {SHADOW_CARD};
    }}

    /* ---- Buttons ---- */
    div[data-testid="stButton"] button {{
        font-size: 12px; font-weight: 600; border-radius: {RADIUS_SM};
        border: 1px solid {BORDER}; background: {SURFACE}; color: {TEXT_SECONDARY};
    }}
    div[data-testid="stButton"] button:hover {{ border-color: {BLUE}; color: {BLUE}; }}

    @media (max-width: 900px) {{
        [data-testid="stMainBlockContainer"], .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    }}
    </style>
    """


def page_header_html(title: str, subtitle: str = "", eyebrow: str = "") -> str:
    """The heading block at the top of every page."""
    eyebrow_html = (
        f'<div style="font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;'
        f'color:{BLUE};margin-bottom:6px;">{eyebrow}</div>'
        if eyebrow
        else ""
    )
    subtitle_html = (
        f'<div style="font-size:15px;color:{TEXT_SECONDARY};margin-top:6px;max-width:75ch;line-height:1.5;">'
        f"{subtitle}</div>"
        if subtitle
        else ""
    )
    return f"""
    <div style="margin:0 0 22px 0;">
        {eyebrow_html}
        <div style="font-size:30px;font-weight:800;color:{TEXT_PRIMARY};letter-spacing:-0.02em;line-height:1.15;">
            {title}
        </div>
        {subtitle_html}
    </div>
    """


def section_header_html(title: str, subtitle: str = "") -> str:
    """A section title with an optional muted subtitle."""
    subtitle_html = (
        f'<div style="font-size:13px;color:{TEXT_MUTED};margin-top:3px;max-width:80ch;">{subtitle}</div>'
        if subtitle
        else ""
    )
    return f"""
    <div style="margin:8px 0 14px 0;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:4px;align-self:stretch;min-height:22px;border-radius:4px;background:{BRAND_GRADIENT};"></div>
        <div>
            <div style="font-size:18px;font-weight:700;color:{TEXT_PRIMARY};line-height:1.25;">{title}</div>
            {subtitle_html}
        </div>
    </div>
    """


def card_title_html(title: str, subtitle: str = "") -> str:
    """A compact heading for the inside of a card."""
    subtitle_html = (
        f'<div style="font-size:12.5px;color:{TEXT_MUTED};margin-top:2px;">{subtitle}</div>' if subtitle else ""
    )
    return f"""
    <div style="margin:2px 0 10px 0;">
        <div style="font-size:16px;font-weight:700;color:{TEXT_PRIMARY};">{title}</div>
        {subtitle_html}
    </div>
    """


def footer_html(repo_url: str, data_note: str = "") -> str:
    """Site footer with data attribution and a link to the source code."""
    return f"""
    <div style="
        margin-top:40px;
        padding:18px 0 6px 0;
        border-top:1px solid {BORDER};
        display:flex;
        justify-content:space-between;
        gap:16px;
        flex-wrap:wrap;
        font-size:12.5px;
        color:{TEXT_MUTED};
    ">
        <div>
            <span style="font-weight:700;color:{TEXT_SECONDARY};">FPL Analytics</span>
            &middot; Data from the official Fantasy Premier League API{f" &middot; {data_note}" if data_note else ""}
        </div>
        <div>
            Built by George Williams &middot;
            <a href="{repo_url}" target="_blank" style="color:{BLUE};text-decoration:none;font-weight:600;">
                Source on GitHub
            </a>
        </div>
    </div>
    """


def apply_chart_theme(fig, height: int | None = None):
    """Apply the shared fonts, backgrounds and gridlines to a Plotly figure."""
    layout_kwargs = dict(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT_STACK, color=TEXT_SECONDARY, size=12),
        legend=dict(font=dict(color=TEXT_SECONDARY, size=12)),
        margin=dict(l=56, r=24, t=16, b=48),
    )
    if height is not None:
        layout_kwargs["height"] = height
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BORDER, automargin=True)
    fig.update_yaxes(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BORDER, automargin=True)
    return fig
