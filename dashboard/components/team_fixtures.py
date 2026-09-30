"""The Home page's fixture-difficulty table: one row per team, one colour-coded
cell per upcoming gameweek. Header and rows share one fluid CSS grid.

On a narrow screen (see the container queries in theme.py) the team column
shows the badge and short name only, and the cells tighten up."""

from formatting import image_base64, ordinal
from settings import BADGES_DIR
from theme import BORDER, PAGE_BG, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, difficulty_colour

GRID_TEMPLATE_COLUMNS = "minmax(190px, 1.7fr) repeat(5, minmax(64px, 1fr))"


def fixture_grid_html(rows_html: str) -> str:
    """Wrap the header and team rows (all one string) in the table."""
    return f'<div class="fpl-fdr">{rows_html}</div>'


def fixture_grid_header_html(gameweeks) -> str:
    """Header row: team column label and one "GW n" label per gameweek."""
    labels = "".join(
        f'<div class="fpl-fdr-gw" style="text-align:center;font-size:11px;font-weight:700;letter-spacing:0.04em;'
        f'color:{TEXT_MUTED};white-space:nowrap;">GW {gw}</div>'
        for gw in gameweeks
    )
    return f"""
    <div class="fpl-fdr-grid" style="display:grid;grid-template-columns:{GRID_TEMPLATE_COLUMNS};gap:6px;
                padding:0 10px 8px 10px;border-bottom:1px solid {BORDER};margin-bottom:6px;">
        <div class="fpl-fdr-gw" style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:{TEXT_MUTED};">
            TEAM
        </div>
        {labels}
    </div>
    """


def _fixture_cell(fixture) -> str:
    venue = fixture["venue"]
    return (
        f'<div class="fpl-fdr-cell" style="background:{difficulty_colour(fixture["difficulty"])};color:white;'
        f"border-radius:6px;padding:5px 4px;text-align:center;font-size:11.5px;font-weight:700;"
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{fixture["opponent"]} '
        f'<span class="fpl-venue" style="opacity:0.85;font-weight:600;">'
        f'<span class="fpl-venue-long">({venue})</span>'
        f'<span class="fpl-venue-short" style="display:none;">{str(venue).lower()}</span></span></div>'
    )


def team_fixture_card(
    team_name: str,
    position: int,
    fixtures,
    gameweeks,
    badge_file: str | None = None,
    short_name: str | None = None,
) -> str:
    """One team's row: badge, name, league position and a cell per gameweek
    (stacked for a double gameweek, empty for a blank)."""
    cells = ""
    for gw in gameweeks:
        if gw in fixtures:
            inner = "".join(_fixture_cell(f) for _, f in fixtures[gw].iterrows())
        else:
            inner = (
                f'<div class="fpl-fdr-cell" style="background:{PAGE_BG};border:1px dashed {BORDER};border-radius:6px;'
                f'padding:5px 4px;text-align:center;font-size:11px;color:{TEXT_MUTED};">Blank</div>'
            )
        cells += f'<div style="display:flex;flex-direction:column;gap:3px;min-width:0;">{inner}</div>'

    badge = image_base64(BADGES_DIR / badge_file) if badge_file else ""
    badge_html = (
        f'<img src="data:image/png;base64,{badge}" style="width:20px;height:20px;object-fit:contain;flex-shrink:0;">'
        if badge
        else ""
    )
    short = short_name or team_name[:3].upper()
    return f"""
    <div class="fpl-fdr-grid" style="display:grid;grid-template-columns:{GRID_TEMPLATE_COLUMNS};gap:6px;
                align-items:center;padding:6px 10px;border-radius:8px;border-bottom:1px solid {BORDER};">
        <div class="fpl-fdr-team" style="display:flex;align-items:center;gap:8px;min-width:0;">
            {badge_html}
            <span class="fpl-fdr-name" style="font-size:13.5px;font-weight:600;color:{TEXT_PRIMARY};white-space:nowrap;
                         overflow:hidden;text-overflow:ellipsis;">{team_name}</span>
            <span class="fpl-fdr-short" style="display:none;font-size:11px;font-weight:700;color:{TEXT_PRIMARY};">
                {short}
            </span>
            <span class="fpl-fdr-pos" style="font-size:11px;color:{TEXT_SECONDARY};font-weight:600;flex-shrink:0;">
                {int(position)}{ordinal(int(position))}
            </span>
        </div>
        {cells}
    </div>
    """
