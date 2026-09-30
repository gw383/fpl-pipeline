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
    {_RESPONSIVE_CSS}
    </style>
    """


# Phones and narrow columns. Two mechanisms:
#  * Viewport media queries for the page chrome and for how Streamlit columns
#    behave. Streamlit stacks every st.columns() one per row below 640px; the
#    keyed containers from components.layout opt out of that: "sbs-" keeps
#    columns side by side, "grid2-" and "metrics-" wrap them two per row.
#  * Container queries for the custom HTML components: every st.html block is
#    a size container, so a component adapts to the width it's actually given
#    (a phone, or half of the Compare page) rather than to the screen.
# The HTML components set their desktop sizes inline, hence the !important.
_RESPONSIVE_CSS = """
    [data-testid="stHtml"] { container-type: inline-size; }

    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"], .block-container {
            padding-top: 4.25rem; padding-left: 0.75rem; padding-right: 0.75rem;
        }
        div[class*="st-key-card-"] { padding: 12px !important; }
        hr { margin: 16px 0; }
        h3 { font-size: 16px; }
        [data-testid="stExpander"] summary { padding: 6px 10px; font-size: 13px; }

        .fpl-page-header { margin-bottom: 14px !important; }
        .fpl-page-title { font-size: 24px !important; }
        .fpl-page-sub { font-size: 13.5px !important; margin-top: 4px !important; }
        .fpl-page-eyebrow { font-size: 11px !important; margin-bottom: 4px !important; }
        .fpl-section { margin: 2px 0 8px 0 !important; }
        .fpl-section-title { font-size: 16px !important; }
        .fpl-section-sub { font-size: 12px !important; }

        /* Stacked columns: a normal gap between them, not the desktop column gap. */
        [data-testid="stHorizontalBlock"] { row-gap: 0.75rem !important; }
        div[class*="st-key-sbs-"] [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important; gap: 0.6rem !important;
        }
        div[class*="st-key-sbs-"] [data-testid="stColumn"] {
            min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;
        }
        div[class*="st-key-grid2-"] [data-testid="stHorizontalBlock"],
        div[class*="st-key-metrics-"] [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important; gap: 0.5rem !important;
        }
        div[class*="st-key-grid2-"] [data-testid="stColumn"],
        div[class*="st-key-metrics-"] [data-testid="stColumn"] {
            min-width: calc(50% - 0.25rem) !important; max-width: calc(50% - 0.25rem) !important;
            flex: 1 1 calc(50% - 0.25rem) !important;
        }
        /* Stat cards inside a half-width Compare column: one per row. */
        div[class*="st-key-sbs-"] div[class*="st-key-metrics-"] [data-testid="stColumn"] {
            min-width: 100% !important; max-width: 100% !important; flex-basis: 100% !important;
        }
        div[class*="st-key-sbs-"] div[class*="st-key-metrics-"] [data-testid="stHorizontalBlock"] {
            gap: 0.4rem !important;
        }
        /* Top-rated lists two per row: tighter rows. */
        div[class*="st-key-grid2-"] [data-testid="stExpander"] summary { padding: 5px 8px; font-size: 12px; }
        div[class*="st-key-grid2-"] [data-testid="stExpander"] summary p { font-size: 12px; }
        /* Scrolling news list: shorter, so the page itself stays scrollable. */
        .st-key-news-feed,
        [data-testid="stLayoutWrapper"]:has(> .st-key-news-feed) {
            height: 320px !important; max-height: 320px !important;
        }
    }

    /* ---- Stat cards ---- */
    @container (max-width: 250px) {
        .fpl-metric { padding: 9px 11px !important; min-height: 0 !important; }
        .fpl-metric-title { font-size: 10px !important; letter-spacing: 0.02em !important; }
        .fpl-metric-row { margin-top: 4px !important; gap: 4px !important; }
        .fpl-metric-value { font-size: 19px !important; }
        .fpl-metric-rank { font-size: 10.5px !important; padding: 2px 6px !important; }
    }

    /* ---- Club banners ---- */
    @container (max-width: 520px) {
        .fpl-banner {
            min-height: 96px !important; margin-bottom: 12px !important;
            padding: 12px calc(22% + 12px) 12px 16px !important;
        }
        .fpl-banner-panel { width: 22% !important; right: 3% !important; }
        .fpl-banner-badge { width: 52px !important; height: 52px !important; }
        .fpl-banner-title { font-size: 22px !important; }
        .fpl-banner-meta { font-size: 13px !important; margin-top: 4px !important; }
        .fpl-banner .fpl-stars { font-size: 15px !important; }
        .fpl-banner .fpl-news-pill { font-size: 11.5px !important; padding: 4px 10px !important; margin-top: 6px !important; }
    }
    @container (max-width: 260px) {
        .fpl-banner { min-height: 74px !important; padding: 10px 10px 10px 12px !important; margin-bottom: 8px !important; }
        .fpl-banner.fpl-banner-tall { min-height: 98px !important; }
        .fpl-banner-panel { display: none !important; }
        .fpl-banner-title { font-size: 15px !important; }
        .fpl-banner-meta { font-size: 10.5px !important; margin-top: 2px !important; }
        .fpl-banner .fpl-stars { font-size: 11px !important; letter-spacing: 0 !important; }
        .fpl-banner .fpl-rating-number { font-size: 10px !important; margin-left: 4px !important; }
        .fpl-banner .fpl-news-pill { font-size: 9.5px !important; padding: 3px 7px !important; margin-top: 4px !important; }
    }

    /* ---- Fixture-difficulty table (Home) ---- */
    @container (max-width: 560px) {
        .fpl-fdr-grid {
            grid-template-columns: minmax(0, 0.8fr) repeat(5, minmax(0, 1fr)) !important;
            gap: 3px !important; padding-left: 0 !important; padding-right: 0 !important;
        }
        .fpl-fdr-name, .fpl-fdr-pos { display: none !important; }
        .fpl-fdr-short { display: inline !important; }
        .fpl-fdr-team { gap: 4px !important; }
        .fpl-fdr-team img { width: 16px !important; height: 16px !important; }
        .fpl-fdr-cell { font-size: 10px !important; padding: 5px 1px !important; border-radius: 5px !important; }
        .fpl-fdr-cell .fpl-venue { font-weight: 500 !important; }
        .fpl-fdr-gw { font-size: 10px !important; }
    }
    @container (max-width: 340px) {
        .fpl-fdr-cell .fpl-venue-long { display: none !important; }
        .fpl-fdr-cell .fpl-venue-short { display: inline !important; }
    }

    /* ---- A player's next five gameweeks ---- */
    @container (max-width: 520px) {
        .fpl-fx { gap: 6px !important; }
        .fpl-fx-gw { font-size: 11px !important; margin-bottom: 5px !important; }
        .fpl-fx-tile { height: 60px !important; }
        .fpl-fx-opp { font-size: 16px !important; }
        .fpl-fx-venue { font-size: 11px !important; }
        .fpl-fx-strip { font-size: 12px !important; padding: 3px 6px !important; margin-bottom: 4px !important; }
    }
    @container (max-width: 280px) {
        .fpl-fx { gap: 3px !important; }
        .fpl-fx-gw { font-size: 8.5px !important; letter-spacing: -0.02em !important; margin-bottom: 3px !important; }
        .fpl-fx-tile { height: 44px !important; border-radius: 6px !important; }
        .fpl-fx-opp { font-size: 11px !important; }
        .fpl-fx-venue { font-size: 9px !important; }
        .fpl-fx-blank { font-size: 9px !important; }
        .fpl-fx-strip {
            font-size: 9px !important; padding: 2px 2px !important; justify-content: center !important;
            gap: 2px !important; border-radius: 5px !important; margin-bottom: 3px !important;
        }
    }

    /* ---- Pitch (Best XI, My Team) ---- */
    @container (max-width: 560px) {
        .fpl-pitch { height: auto !important; min-height: 400px; padding: 14px 2px !important; row-gap: 8px; }
        .fpl-pitch-row { justify-content: space-around !important; gap: 2px; }
        .fpl-pitch-card { width: auto !important; flex: 0 1 20% !important; min-width: 0 !important; max-width: 96px; }
        .fpl-shirt { width: 28px !important; height: 26px !important; margin-bottom: 2px !important; }
        .fpl-plate { font-size: 9.5px !important; line-height: 11px !important; padding: 3px 2px !important; border-radius: 5px !important; }
        .fpl-plate-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .fpl-plate-sub { font-size: 8px !important; }
        .fpl-pill { font-size: 9px !important; padding: 1px 4px !important; margin-top: 3px !important; }
        .fpl-pills { flex-wrap: wrap !important; gap: 2px !important; }
        .fpl-pills .fpl-pill { margin-top: 2px !important; }
        .fpl-captain { font-size: 8.5px !important; padding: 1px 4px !important; top: -3px !important; right: 0 !important; }
        .fpl-bench { gap: 4px !important; }
        .fpl-bench-card { padding: 6px 3px !important; }
        .fpl-bench-card .fpl-shirt { width: 22px !important; height: 21px !important; }
        .fpl-bench-pos { font-size: 9px !important; }
        .fpl-bench-name { font-size: 11px !important; }
        .fpl-bench-team { font-size: 9.5px !important; }
    }

    /* ---- Team page result cards ---- */
    @container (max-width: 520px) {
        .fpl-result { padding: 10px 12px !important; margin-bottom: 0 !important; }
        .fpl-result-top { flex-wrap: nowrap !important; align-items: center !important; gap: 6px !important; }
        .fpl-result-score { font-size: 22px !important; }
        .fpl-result-chips { gap: 6px !important; flex-shrink: 0; }
        .fpl-chip { min-width: 38px !important; }
        .fpl-chip-value { font-size: 14px !important; }
    }

    /* ---- Differential cards, two per row on phones ---- */
    @container (max-width: 220px) {
        .fpl-diff { padding: 8px 9px !important; margin-bottom: 0 !important; }
        .fpl-diff-name { font-size: 12px !important; }
        .fpl-diff-foot { margin-top: 5px !important; }
        .fpl-diff-owned { font-size: 10px !important; }
    }
"""


def page_header_html(title: str, subtitle: str = "", eyebrow: str = "") -> str:
    """The heading block at the top of every page."""
    eyebrow_html = (
        f'<div class="fpl-page-eyebrow" style="font-size:12px;font-weight:700;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:{BLUE};margin-bottom:6px;">{eyebrow}</div>'
        if eyebrow
        else ""
    )
    subtitle_html = (
        f'<div class="fpl-page-sub" style="font-size:15px;color:{TEXT_SECONDARY};margin-top:6px;max-width:75ch;'
        f'line-height:1.5;">{subtitle}</div>'
        if subtitle
        else ""
    )
    return f"""
    <div class="fpl-page-header" style="margin:0 0 22px 0;">
        {eyebrow_html}
        <div class="fpl-page-title" style="font-size:30px;font-weight:800;color:{TEXT_PRIMARY};
                    letter-spacing:-0.02em;line-height:1.15;">
            {title}
        </div>
        {subtitle_html}
    </div>
    """


def section_header_html(title: str, subtitle: str = "") -> str:
    """A section title with an optional muted subtitle."""
    subtitle_html = (
        f'<div class="fpl-section-sub" style="font-size:13px;color:{TEXT_MUTED};margin-top:3px;max-width:80ch;">'
        f"{subtitle}</div>"
        if subtitle
        else ""
    )
    return f"""
    <div class="fpl-section" style="margin:8px 0 14px 0;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:4px;align-self:stretch;min-height:22px;border-radius:4px;background:{BRAND_GRADIENT};"></div>
        <div>
            <div class="fpl-section-title" style="font-size:18px;font-weight:700;color:{TEXT_PRIMARY};
                        line-height:1.25;">{title}</div>
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
