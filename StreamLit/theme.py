"""Central design system for the dashboard.

Every page and component draws its colours, spacing, shadows and fonts
from here instead of inventing its own shade of grey -- this is a purely
presentational module (colours, CSS, chart chrome). It has no opinion on
data: nothing here changes what a query returns or how a rating is
computed.

The colour palette is the dataviz skill's validated default (see the
skill's references/palette.md): categorical hues are assigned in a
fixed order and never cycled, so a given identity -- "Actual" vs
"Expected", a goalkeeper vs a forward -- is always the same colour
everywhere it appears in the app. Every pairing actually used below was
run through the skill's validator (scripts/validate_palette.js) before
being adopted.
"""

# ---------------------------------------------------------------------------
# Page / chart chrome
# ---------------------------------------------------------------------------

PAGE_BG = "#f7f7f5"           # page plane behind everything
SURFACE = "#ffffff"           # card background
CHART_SURFACE = "#fcfcfb"     # plotly paper/plot background -- close to
                               # SURFACE so charts sit inside cards seamlessly

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
# Categorical palette -- fixed order, never cycled (dataviz skill default)
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
# Status palette -- reserved for state/severity, never reused as a series
# identity colour
# ---------------------------------------------------------------------------

STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

# ---------------------------------------------------------------------------
# Fixed per-identity colour assignments. Each of these is used EVERYWHERE
# that identity appears in the app, so e.g. "Expected" is always orange
# whether you're looking at the points-breakdown chart or the
# expected-vs-actual chart.
# ---------------------------------------------------------------------------

# Positions, wherever a badge/tag/accent is shown for one.
POSITION_COLOURS = {
    1: VIOLET,   # Goalkeeper
    2: BLUE,     # Defender
    3: AQUA,     # Midfielder
    4: ORANGE,   # Forward
}
POSITION_LABELS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# "What actually happened" vs "what the underlying process (xG/xA/xGA)
# says should have happened" -- expected_vs_actual_chart.
ACTUAL_COLOUR = BLUE
EXPECTED_COLOUR = ORANGE

# points_breakdown_chart: categories that add to the total vs. subtract
# from it. Read as polarity (gain/loss) rather than a literal identity,
# so it borrows blue/red rather than a third categorical slot.
POSITIVE_COLOUR = BLUE
NEGATIVE_COLOUR = RED

# minutes_donut_chart: minutes played is the one thing being measured;
# "not played" is an absence, not a second identity, so it stays a
# neutral tint rather than competing for attention.
PLAYED_COLOUR = BLUE
NOT_PLAYED_COLOUR = "#dedcd4"


def rgba(hex_colour: str, alpha: float) -> str:
    """Return `hex_colour` (e.g. BLUE) as an "rgba(r, g, b, alpha)"
    string, for a translucent tint of a palette colour -- a badge
    background, a meter's unfilled track, and similar. Centralised here
    since a couple of components used to hardcode the equivalent
    "rgba(42,120,214,0.10)" by hand (BLUE decoded by eye) rather than
    deriving it from the palette constant itself.
    """
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def inject_base_css() -> str:
    """The shared page-chrome CSS block every page injects once via
    st.markdown(..., unsafe_allow_html=True). Centralised here so Home
    and Player can't quietly drift into two different looks.
    """
    return f"""
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: {FONT_STACK};
    }}

    .stApp {{
        background-color: {PAGE_BG};
    }}

    .block-container {{
        padding-top: 1.5rem;
        padding-left: 3rem;
        padding-right: 3rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }}

    /* Streamlit's own headings, so st.subheader/st.markdown headers pick
       up the same type scale as the hand-built HTML cards. */
    h1, h2, h3 {{
        color: {TEXT_PRIMARY};
        font-weight: 700;
        letter-spacing: -0.01em;
    }}

    h3 {{
        font-size: 20px;
        margin-bottom: 2px;
    }}

    /* Section captions under a subheader -- consistent muted, smaller
       supporting text instead of Streamlit's default caption grey. */
    [data-testid="stCaptionContainer"] {{
        color: {TEXT_MUTED};
        font-size: 13px;
    }}

    /* Thin, deliberate section dividers instead of Streamlit's default
       heavy hr. */
    hr {{
        border: none;
        border-top: 1px solid {BORDER};
        margin: 28px 0;
    }}

    /* Dropdowns (Player/Range selectors, Best-XI metric picker) */
    div[data-testid="stSelectbox"] {{
        margin-top: 4px;
    }}

    div[data-baseweb="select"] > div {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM};
        box-shadow: none;
    }}

    div[data-baseweb="select"] span {{
        color: {TEXT_PRIMARY};
    }}

    div[data-baseweb="select"] input {{
        background-color: {SURFACE};
        color: {TEXT_PRIMARY};
    }}

    div[role="listbox"] {{
        background-color: {SURFACE};
        border-radius: {RADIUS_SM};
        border: 1px solid {BORDER};
    }}

    div[role="option"] {{
        background-color: {SURFACE};
        color: {TEXT_PRIMARY};
    }}

    div[role="option"]:hover {{
        background-color: {PAGE_BG};
    }}

    div[aria-selected="true"] {{
        background-color: #eef2f8;
    }}

    /* Sidebar page nav (Home / Player), kept subtle rather than
       Streamlit's default stark white/grey. */
    [data-testid="stSidebar"] {{
        background-color: {SURFACE};
        border-right: 1px solid {BORDER};
    }}

    [data-testid="stSidebarNav"] {{
        padding-top: 12px;
    }}

    /* Bordered st.container(border=True) panels -- used to frame each
       major widget (Best XI, Fixture Difficulty, Latest News, ...) as
       its own card instead of floating loose in a column. */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: {SURFACE};
        border: 1px solid {BORDER} !important;
        border-radius: {RADIUS} !important;
        box-shadow: {SHADOW_CARD};
    }}

    /* The small "Show breakdown" toggle under a star/differential
       card -- a subtle, compact text-link look rather than Streamlit's
       full-size default button, so it reads as part of the card
       underneath it rather than a separate, competing control. */
    div[data-testid="stButton"] button {{
        font-size: 11px;
        font-weight: 600;
        padding: 3px 10px;
        min-height: 0;
        border-radius: {RADIUS_SM};
        border: 1px solid {BORDER};
        background: {SURFACE};
        color: {TEXT_SECONDARY};
        box-shadow: none;
    }}

    div[data-testid="stButton"] button:hover {{
        border-color: {BLUE};
        color: {BLUE};
    }}

    </style>
    """


def masthead_html(subtitle: str = "") -> str:
    """A slim site header/masthead, the kind a real analytics product
    would have above the dashboard body -- name, tagline, nothing more.
    """
    subtitle_html = f'<span class="fpla-masthead-subtitle">{subtitle}</span>' if subtitle else ""
    return f"""
    <style>
    .fpla-masthead {{
        display:flex;
        align-items:baseline;
        gap:14px;
        padding:2px 0 18px 0;
        border-bottom:1px solid {BORDER};
        margin-bottom:22px;
        flex-wrap:wrap;
    }}
    .fpla-masthead-mark {{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        width:34px;
        height:34px;
        border-radius:9px;
        background:linear-gradient(135deg, {VIOLET}, {BLUE});
        color:white;
        font-weight:800;
        font-size:15px;
        flex-shrink:0;
    }}
    .fpla-masthead-title {{
        font-size:22px;
        font-weight:800;
        color:{TEXT_PRIMARY};
        letter-spacing:-0.01em;
    }}
    .fpla-masthead-subtitle {{
        font-size:13px;
        color:{TEXT_MUTED};
        font-weight:500;
    }}
    </style>
    <div class="fpla-masthead">
        <div class="fpla-masthead-mark">FPL</div>
        <div class="fpla-masthead-title">Analytics</div>
        {subtitle_html}
    </div>
    """


def section_header_html(title: str, subtitle: str = "") -> str:
    """A consistent section header used above every major block on a
    page (in place of raw st.subheader + st.caption pairs), with a small
    accent bar so sections read as distinct modules on the page.
    """
    subtitle_html = f'<div class="fpla-section-sub">{subtitle}</div>' if subtitle else ""
    return f"""
    <style>
    .fpla-section {{
        display:flex;
        gap:10px;
        align-items:flex-start;
        margin: 6px 0 14px 0;
    }}
    .fpla-section-bar {{
        width:4px;
        border-radius:4px;
        background:linear-gradient(180deg, {VIOLET}, {BLUE});
        align-self:stretch;
        min-height:28px;
    }}
    .fpla-section-title {{
        font-size:19px;
        font-weight:700;
        color:{TEXT_PRIMARY};
        line-height:1.2;
    }}
    .fpla-section-sub {{
        font-size:13px;
        color:{TEXT_MUTED};
        margin-top:2px;
        max-width:70ch;
    }}
    </style>
    <div class="fpla-section">
        <div class="fpla-section-bar"></div>
        <div>
            <div class="fpla-section-title">{title}</div>
            {subtitle_html}
        </div>
    </div>
    """


def apply_chart_theme(fig, height: int | None = None):
    """Apply the shared chart chrome (fonts, backgrounds, gridlines) to
    a Plotly figure in place, and return it. Colours/data on the figure
    itself are untouched -- this only standardises the frame around
    them so every chart in the app reads as one family.
    """
    layout_kwargs = dict(
        paper_bgcolor=CHART_SURFACE,
        plot_bgcolor=CHART_SURFACE,
        font=dict(family=FONT_STACK, color=TEXT_SECONDARY, size=13),
        title_font=dict(family=FONT_STACK, color=TEXT_PRIMARY, size=15),
        legend=dict(font=dict(color=TEXT_SECONDARY, size=12)),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    if height is not None:
        layout_kwargs["height"] = height
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BORDER)
    fig.update_yaxes(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BORDER)
    return fig
