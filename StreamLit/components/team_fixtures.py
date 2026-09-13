"""A team's row in the Home page's fixture-difficulty grid."""

from colours import difficulty_colour


def ordinal(n: int) -> str:
    """Return the ordinal suffix for n, e.g. 1 -> "st", 12 -> "th"."""
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


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
                    padding:3px;
                    margin-bottom:2px;
                    text-align:center;
                    font-size:10px;
                    font-weight:700;
                    width:62px;
                    line-height:14px;
                ">
                    {fixture['opponent']} ({fixture['venue']})
                </div>
                """
        else:
            cell_html = """
            <div style="
                width:62px;
                height:20px;
            ">
            </div>
            """

        fixture_cells += f"""
        <div style="
            width:70px;
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:center;
        ">
            {cell_html}
        </div>
        """

    return f"""

    <div style="
        display:flex;
        align-items:center;
        width:470px;
        background:white;
        border-radius:7px;
        padding:3px 6px;
        margin-bottom:3px;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
    ">


        <!-- Team -->

        <div style="
            width:120px;
            flex-shrink:0;
        ">

            <div style="
                font-size:13px;
                font-weight:700;
                line-height:14px;
            ">
                {team_name}
                <span style="
                    font-size:10px;
                    color:#777;
                    font-weight:500;
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
