"""The Home page's fixture-difficulty table: one row per team, one colour-coded
cell per upcoming gameweek. Header and rows share one fluid CSS grid."""

from formatting import image_base64, ordinal
from settings import BADGES_DIR
from theme import BORDER, PAGE_BG, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, difficulty_colour

GRID_TEMPLATE_COLUMNS = "minmax(190px, 1.7fr) repeat(5, minmax(64px, 1fr))"


def fixture_grid_header_html(gameweeks) -> str:
    """Header row: team column label and one "GW n" label per gameweek."""
    labels = "".join(
        f'<div style="text-align:center;font-size:11px;font-weight:700;letter-spacing:0.04em;'
        f'color:{TEXT_MUTED};">GW {gw}</div>'
        for gw in gameweeks
    )
    return f"""
    <div style="display:grid;grid-template-columns:{GRID_TEMPLATE_COLUMNS};gap:6px;padding:0 10px 8px 10px;
                border-bottom:1px solid {BORDER};margin-bottom:6px;">
        <div style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:{TEXT_MUTED};">TEAM</div>
        {labels}
    </div>
    """


def team_fixture_card(team_name: str, position: int, fixtures, gameweeks, badge_file: str | None = None) -> str:
    """One team's row: badge, name, league position and a cell per gameweek
    (stacked for a double gameweek, empty for a blank)."""
    cells = ""
    for gw in gameweeks:
        if gw in fixtures:
            inner = "".join(
                f'<div style="background:{difficulty_colour(f["difficulty"])};color:white;border-radius:6px;'
                f"padding:5px 4px;text-align:center;font-size:11.5px;font-weight:700;white-space:nowrap;"
                f'overflow:hidden;text-overflow:ellipsis;">{f["opponent"]} '
                f'<span style="opacity:0.85;font-weight:600;">({f["venue"]})</span></div>'
                for _, f in fixtures[gw].iterrows()
            )
        else:
            inner = (
                f'<div style="background:{PAGE_BG};border:1px dashed {BORDER};border-radius:6px;padding:5px 4px;'
                f'text-align:center;font-size:11px;color:{TEXT_MUTED};">Blank</div>'
            )
        cells += f'<div style="display:flex;flex-direction:column;gap:3px;min-width:0;">{inner}</div>'

    badge = image_base64(BADGES_DIR / badge_file) if badge_file else ""
    badge_html = (
        f'<img src="data:image/png;base64,{badge}" style="width:20px;height:20px;object-fit:contain;flex-shrink:0;">'
        if badge
        else ""
    )
    return f"""
    <div style="display:grid;grid-template-columns:{GRID_TEMPLATE_COLUMNS};gap:6px;align-items:center;
                padding:6px 10px;border-radius:8px;border-bottom:1px solid {BORDER};">
        <div style="display:flex;align-items:center;gap:8px;min-width:0;">
            {badge_html}
            <span style="font-size:13.5px;font-weight:600;color:{TEXT_PRIMARY};white-space:nowrap;
                         overflow:hidden;text-overflow:ellipsis;">{team_name}</span>
            <span style="font-size:11px;color:{TEXT_SECONDARY};font-weight:600;flex-shrink:0;">
                {int(position)}{ordinal(int(position))}
            </span>
        </div>
        {cells}
    </div>
    """
