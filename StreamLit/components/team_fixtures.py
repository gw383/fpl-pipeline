"""The Home page's fixture-difficulty grid: a header row of gameweeks
and one row per team, each cell colour-coded by fixture difficulty.

Both the header and every team row share one CSS grid template
(GRID_TEMPLATE_COLUMNS) so they can never drift out of alignment with
each other, and neither uses a fixed pixel width anywhere -- the whole
grid is fluid (box-sizing:border-box, width:100%), so it always fits
whatever width its column actually has instead of assuming one. The
previous version used fixed pixel widths throughout (a 470px row made
of a 120px team label + 5x70px cells) that summed to exactly the outer
width with zero allowance for its own padding/border -- the rendered
row was actually ~488px wide, which didn't reliably fit inside its
column at normal window widths and could overflow into (or behind)
the Latest News column next to it. A fluid grid can't have that
problem: it's always exactly as wide as its container.
"""

from colours import difficulty_colour
from theme import BORDER, RADIUS_SM, SHADOW_CARD, SURFACE, TEXT_MUTED, TEXT_PRIMARY

# One team-name column plus one column per upcoming gameweek. Shared by
# the header row and every data row below so they always line up.
GRID_TEMPLATE_COLUMNS = "minmax(96px, 1.3fr) repeat(5, 1fr)"


def ordinal(n: int) -> str:
    """Return the ordinal suffix for n, e.g. 1 -> "st", 12 -> "th"."""
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def fixture_grid_header_html(gameweeks) -> str:
    """The grid's header row: a blank team-name slot followed by one
    "GW N" label per upcoming gameweek.
    """
    gw_headers = "".join(
        f"""
        <div style="text-align:center;font-size:11px;font-weight:700;color:{TEXT_MUTED};">
            GW {gw}
        </div>
        """
        for gw in gameweeks
    )

    return f"""
    <div style="
        display:grid;
        grid-template-columns:{GRID_TEMPLATE_COLUMNS};
        gap:6px;
        font-weight:700;
        font-size:12px;
        margin-bottom:6px;
        padding-bottom:6px;
        border-bottom:1px solid {BORDER};
    ">
        <div>Team</div>
        {gw_headers}
    </div>
    """


def team_fixture_card(team_name: str, position: int, fixtures, gameweeks) -> str:
    """Render one team's row: name, league position, and a fixture
    cell for each of the given gameweeks (blank if the team has none).
    """
    fixture_cells = ""

    for gw in gameweeks:
        cell_html = ""

        if gw in fixtures:
            for _, fixture in fixtures[gw].iterrows():
                colour = difficulty_colour(fixture["difficulty"])
                cell_html += f"""
                <div style="
                    background:{colour};
                    color:white;
                    border-radius:5px;
                    padding:3px 2px;
                    margin-bottom:2px;
                    text-align:center;
                    font-size:10px;
                    font-weight:700;
                    line-height:14px;
                    overflow:hidden;
                    text-overflow:ellipsis;
                    white-space:nowrap;
                ">
                    {fixture['opponent']} ({fixture['venue']})
                </div>
                """
        else:
            cell_html = """
            <div style="height:20px;"></div>
            """

        fixture_cells += f"""
        <div style="
            display:flex;
            flex-direction:column;
            align-items:stretch;
            justify-content:center;
            min-width:0;
        ">
            {cell_html}
        </div>
        """

    return f"""
    <div style="
        display:grid;
        grid-template-columns:{GRID_TEMPLATE_COLUMNS};
        align-items:center;
        gap:6px;
        width:100%;
        box-sizing:border-box;
        background:{SURFACE};
        border:1px solid {BORDER};
        border-radius:{RADIUS_SM};
        padding:4px 8px;
        margin-bottom:4px;
        box-shadow:{SHADOW_CARD};
    ">

        <!-- Team -->
        <div style="min-width:0;">
            <div style="
                font-size:13px;
                font-weight:700;
                line-height:14px;
                color:{TEXT_PRIMARY};
                overflow:hidden;
                text-overflow:ellipsis;
                white-space:nowrap;
            ">
                {team_name}
                <span style="
                    font-size:10px;
                    color:{TEXT_MUTED};
                    font-weight:600;
                    margin-left:4px;
                ">
                    ({int(position)}{ordinal(int(position))})
                </span>
            </div>
        </div>

        <!-- Fixtures -->
        {fixture_cells}

    </div>
    """
