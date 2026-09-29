"""Compare two players side by side: rating and breakdown, headline stats
ranked within their positions, and upcoming fixtures."""

import streamlit as st

from components.banner import banner_stars_html, club_banner_html
from components.card import card
from components.fixture_card import fixture_card
from components.metric_card import metric_row
from components.rating_breakdown import rating_breakdown_html
from formatting import news_banner_html, per_90
from queries.common import RANGE_OPTIONS
from queries.player_info import get_next_5, get_player_info, get_players
from queries.player_stats import get_player_stats, get_rank_metrics, get_star
from theme import page_header_html, section_header_html

header_col, range_col = st.columns([3, 2], vertical_alignment="bottom")
with header_col:
    st.html(page_header_html("Compare players", "Two players side by side: ratings, form and fixtures."))
with range_col:
    range_label = st.segmented_control(
        "Range", list(RANGE_OPTIONS), default=next(iter(RANGE_OPTIONS)), key="compare_range"
    ) or next(iter(RANGE_OPTIONS))

players = get_players()
if players.empty:
    st.warning("No player data is available right now.")
    st.stop()

names = dict(zip(players["p_id"], players["p_full_name"], strict=False))
ids = list(names)

# Each player's selector sits directly above their card.
left, right = st.columns(2, gap="large")
with left:
    player_a = st.selectbox("Player A", ids, index=0, format_func=names.get, key="compare_player_a")
with right:
    player_b = st.selectbox("Player B", ids, index=min(1, len(ids) - 1), format_func=names.get, key="compare_player_b")

# Banner heights: both leave room for a news line if either player has one,
# so the two cards (and everything below them) stay level.
BANNER_HEIGHT = 120
BANNER_HEIGHT_WITH_NEWS = 160


def load_player(player_id: int) -> dict | None:
    """Everything one column needs, or None (with a warning) if any of it is
    missing for the selected range."""
    frames = {
        "player info": get_player_info(player_id),
        "player stats": get_player_stats(player_id, range_label),
        "rank metrics": get_rank_metrics(player_id, range_label),
        "rating": get_star(player_id),
    }
    missing = [label for label, df in frames.items() if df.empty]
    if missing:
        return {"missing": missing}
    return {label: df.iloc[0] for label, df in frames.items()}


def render_player_column(player_id: int, side: str, data: dict, banner_height: int) -> None:
    """One player's compact profile, rendered into the current column."""
    player_name = names[player_id]
    if "missing" in data:
        st.warning(f"No {', '.join(data['missing'])} available for {player_name} with the current range filter.")
        return

    info_row = data["player info"]
    stat = data["player stats"].fillna(0)
    rank = data["rank metrics"]
    rating = data["rating"]
    star = float(rating["star"])
    minutes = int(stat["minutes"])

    st.html(
        club_banner_html(
            f"""
            <div style="font-size:24px;font-weight:800;line-height:1.15;letter-spacing:-0.01em;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{player_name}</div>
            <div style="margin-top:4px;">{banner_stars_html(star, info_row["primary_colour"], size=16)}</div>
            <div style="margin-top:4px;font-size:14px;font-weight:500;opacity:0.9;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {info_row["team"]} &middot; {info_row["position"]} &middot; £{info_row["price"]}m
            </div>
            {news_banner_html(info_row["news"], single_line=True)}
            """,
            info_row["primary_colour"],
            info_row["secondary_colour"],
            info_row["badge_file"],
            size="compact",
            min_height=banner_height,
        )
    )

    with st.expander("Expected points breakdown"):
        st.html(rating_breakdown_html(rating, star=star))

    form = f"{float(info_row['form']):.1f}"
    if info_row["position"] == "Goalkeeper":
        cards = [
            ("Points", int(stat["points"]), rank["points_rank"]),
            ("Form", form, rank["form_rank"]),
            ("Saves / 90", f"{per_90(stat['saves'], minutes):.1f}", rank["saves_rank"]),
            ("Clean sheets", int(stat["clean_sheets"]), rank["cs_rank"]),
            ("Penalty saves", int(stat["pens_saved"]), rank["saved_pens_rank"]),
        ]
    else:
        cards = [
            ("Points", int(stat["points"]), rank["points_rank"]),
            ("Form", form, rank["form_rank"]),
            ("Goals", int(stat["goals"]), rank["goals_rank"]),
            ("Assists", int(stat["assists"]), rank["assists_rank"]),
            ("Def. actions / 90", f"{per_90(stat['defcons'], minutes):.1f}", rank["dcp90_rank"]),
            ("Clean sheets", int(stat["clean_sheets"]), rank["cs_rank"]),
        ]

    # Three cards per row so they fit a half-width column.
    metric_row(cards, rank_hint=f"Rank among {info_row['position'].lower()}s", per_row=3)

    st.html(section_header_html("Upcoming fixtures"))
    with card(f"compare-{side}-fixtures"):
        fixture_card(get_next_5(player_id))


data_a, data_b = load_player(player_a), load_player(player_b)
any_news = any(
    "player info" in data and isinstance(data["player info"]["news"], str) and data["player info"]["news"].strip()
    for data in (data_a, data_b)
)
banner_height = BANNER_HEIGHT_WITH_NEWS if any_news else BANNER_HEIGHT
with left:
    render_player_column(player_a, "a", data_a, banner_height)
with right:
    render_player_column(player_b, "b", data_b, banner_height)
