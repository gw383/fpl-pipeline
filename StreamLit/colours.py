"""Shared colour scales used across the dashboard.

Previously, the Player page's fixture cards (components/fixture_card.py)
used a 5-band colour scale for FPL's 1-5 fixture-difficulty rating, while
the Home page's fixture-difficulty grid (components/team_fixtures.py) used
a coarser 3-band easy/medium/hard scale for the same numbers -- so the same
difficulty could render as a different colour depending on which page you
were looking at. Both pages now import this one scale, so a given
difficulty always means the same colour everywhere in the app.
"""

# FPL difficulty rating (1 = easiest, 5 = hardest) -> display colour.
DIFFICULTY_COLOURS = {
    1: "#375523",
    2: "#01fc7a",
    3: "#e7e7e7",
    4: "#ff1751",
    5: "#80072d",
}


def difficulty_colour(difficulty: int) -> str:
    """Map an FPL difficulty rating (1-5) to its display colour.

    Falls back to the middle (3) band for an out-of-range value rather
    than raising, since this only ever drives a background-colour style.
    """
    return DIFFICULTY_COLOURS.get(int(difficulty), DIFFICULTY_COLOURS[3])
