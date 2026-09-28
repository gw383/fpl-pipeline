"""Shared colour scales used across the dashboard.

Previously, the Player page's fixture cards (components/fixture_card.py)
used a 5-band colour scale for FPL's 1-5 fixture-difficulty rating, while
the Home page's fixture-difficulty grid (components/team_fixtures.py) used
a coarser 3-band easy/medium/hard scale for the same numbers -- so the same
difficulty could render as a different colour depending on which page you
were looking at. Both pages now import this one scale, so a given
difficulty always means the same colour everywhere in the app.

This is a severity/status indicator (easy fixture -> good, hard fixture ->
bad), not a set of independent categories, so it's built from the dataviz
skill's status palette (good/warning/serious/critical) rather than five
arbitrary hues -- see theme.py for the rest of the app's colour system.
The values below are the same green -> neutral -> red direction the
original scale used (and that every FPL fixture ticker uses), just tuned
to the app's palette and checked for readable white text at every step.
"""

# FPL difficulty rating (1 = easiest, 5 = hardest) -> display colour.
DIFFICULTY_COLOURS = {
    1: "#0ca34a",   # easiest -- status "good" green
    2: "#39944f",   # easy -- lighter green
    3: "#8a8880",   # average -- neutral, dark enough to hold white text
    4: "#d4602f",   # hard -- warm red-orange
    5: "#c0392f",   # hardest -- status "critical" red
}


def difficulty_colour(difficulty: int) -> str:
    """Map an FPL difficulty rating (1-5) to its display colour.

    Falls back to the middle (3) band for an out-of-range value rather
    than raising, since this only ever drives a background-colour style.
    """
    return DIFFICULTY_COLOURS.get(int(difficulty), DIFFICULTY_COLOURS[3])
