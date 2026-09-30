"""Rankings: every player in one position ranked by expected points, with
where those points come from, as a sortable, searchable table."""

import streamlit as st

from queries.player_stats import get_top_rated
from theme import page_header_html

POSITIONS = {"Goalkeepers": 1, "Defenders": 2, "Midfielders": 3, "Forwards": 4}

st.html(
    page_header_html(
        "Player rankings",
        "Expected FPL points for every player over the next five gameweeks, and where they come from. "
        "Click a column heading to sort.",
    )
)

col1, col2 = st.columns([2, 1], vertical_alignment="bottom")
with col1:
    position_label = st.segmented_control("Position", list(POSITIONS), default="Midfielders") or "Midfielders"
with col2:
    search = st.text_input("Search", placeholder="Filter by player or team", label_visibility="collapsed")

players = get_top_rated(position=POSITIONS[position_label])
if players.empty:
    st.caption("No ratings available for this position right now.")
    st.stop()

if search:
    term = search.strip().lower()
    players = players[
        players["player"].str.lower().str.contains(term, regex=False)
        | players["team_short_name"].fillna("").str.lower().str.contains(term, regex=False)
    ]

# Where the expected points come from, next five gameweeks: every scoring
# category that applies to the position, in FPL's own order.
COMPONENT_COLUMNS = {
    "pts_appearance": ("Mins pts", "Appearance points: 1 for playing, 2 for 60+ minutes"),
    "pts_goals": ("Goals", "Open-play goals (penalties excluded)"),
    "pts_assists": ("Assists", "Assists"),
    "pts_penalties": ("Pens", "Taking penalties: scored, minus 2 for a miss"),
    "pts_clean_sheet": ("Clean sheets", "Clean-sheet points"),
    "pts_saves": ("Saves", "1 point per 3 saves"),
    "pts_goals_conceded": ("Conceded", "-1 per 2 goals conceded"),
    "pts_defcon": ("Def. con.", "Defensive contribution: 2 points for reaching the defensive-actions threshold"),
    "pts_bonus": ("Bonus", "Bonus points, from projected BPS for each fixture"),
    "pts_cards": ("Cards", "Yellow cards"),
}
COMPONENTS_BY_POSITION = {
    1: ["pts_appearance", "pts_clean_sheet", "pts_saves", "pts_goals_conceded", "pts_bonus", "pts_cards"],
    2: [
        "pts_appearance", "pts_goals", "pts_assists", "pts_clean_sheet", "pts_goals_conceded",
        "pts_defcon", "pts_bonus", "pts_cards",
    ],
    3: [
        "pts_appearance", "pts_goals", "pts_assists", "pts_penalties", "pts_clean_sheet",
        "pts_defcon", "pts_bonus", "pts_cards",
    ],
    4: ["pts_appearance", "pts_goals", "pts_assists", "pts_penalties", "pts_defcon", "pts_bonus", "pts_cards"],
}  # fmt: skip
# The usual categories for the position, plus any other that matters for
# someone in it this week (e.g. a defender on penalties), so the columns
# always add up to Next 5.
usual = set(COMPONENTS_BY_POSITION[POSITIONS[position_label]])
components = [
    column for column in COMPONENT_COLUMNS if column in usual or players[column].fillna(0).abs().max() >= 0.05
]

table = players[
    [
        "position_rank",
        "player",
        "team_short_name",
        "price",
        "rating",
        "xpts_next_gw",
        "xpts_horizon",
        "xmins_next_gw",
        *components,
        "xpts_per_million",
    ]
]

points = dict(format="%.1f", width="small")
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    height=min(38 + 35 * len(table), 720),
    column_config={
        # Rank and name stay put while the rest scrolls sideways on a phone.
        "position_rank": st.column_config.NumberColumn("#", width="small", pinned=True),
        "player": st.column_config.TextColumn("Player", width=170, pinned=True),
        "team_short_name": st.column_config.TextColumn("Team", width="small"),
        "price": st.column_config.NumberColumn("Price", format="£%.1fm", width="small"),
        "rating": st.column_config.ProgressColumn("Rating", min_value=0, max_value=10, format="%.1f", width=110),
        "xpts_next_gw": st.column_config.NumberColumn("Next GW", help="Expected points next gameweek", **points),
        "xpts_horizon": st.column_config.NumberColumn("Next 5", help="Expected points, next five gameweeks", **points),
        "xmins_next_gw": st.column_config.NumberColumn(
            "Mins", format="%.0f", width="small", help="Expected minutes next gameweek"
        ),
        **{
            column: st.column_config.NumberColumn(label, help=f"{help_text}, next five gameweeks", **points)
            for column, (label, help_text) in COMPONENT_COLUMNS.items()
        },
        "xpts_per_million": st.column_config.NumberColumn(
            "Pts / £m", format="%.2f", width="small", help="Next-five expected points per £1m"
        ),
    },
)
st.caption(
    "Expected points come from a projection model: team attack/defence ratings, each player's recent open-play "
    "xG, xA, defensive and BPS rates, penalties for designated takers, and how likely he is to start, for every "
    "fixture ahead. The category columns add up to Next 5. "
    "Rating = expected points per gameweek relative to this week: 5 is a typical regular starter, 10 the best "
    "projection. Full method in the project docs."
)
