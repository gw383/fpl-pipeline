"""The expandable "how was this rating reached" panel: a player's expected
points for the next gameweek and the projection horizon, split by the ways
FPL awards points (see projections/model.py)."""

from theme import BLUE, STATUS_CRITICAL, TEXT_MUTED, TEXT_PRIMARY, rgba

# (column, label, tooltip) in display order.
_COMPONENTS = [
    ("pts_appearance", "Appearance", "1 point for playing, 2 for 60+ minutes, times the chance of each."),
    (
        "pts_goals",
        "Goals (open play)",
        "Open-play expected goals (penalties excluded) x points per goal for the position, adjusted for each opponent and venue.",
    ),
    ("pts_assists", "Assists", "Expected assists x 3."),
    (
        "pts_penalties",
        "Penalties",
        "Expected penalties he'll take (his team's likely penalties x the chance he's the taker on the pitch), 78% scored, -2 for a miss.",
    ),
    ("pts_clean_sheet", "Clean sheets", "Chance of a clean sheet from the opponent's expected goals, if he plays 60+."),
    (
        "pts_defcon",
        "Defensive contribution",
        "Chance of reaching the defensive-actions threshold for 2 points, from his defensive actions per 90 and how many the opponent tends to give away.",
    ),
    ("pts_saves", "Saves", "1 point per 3 expected saves."),
    (
        "pts_bonus",
        "Bonus",
        "From projected BPS in each fixture: his usual BPS plus the BPS from the goals, assists, clean sheets and saves expected in that match, as a chance of finishing top three.",
    ),
    ("pts_goals_conceded", "Goals conceded", "-1 per 2 expected goals conceded (goalkeepers and defenders)."),
    ("pts_cards", "Cards", "Yellow-card rate x expected minutes."),
]


def _val(row, column: str) -> float:
    value = row.get(column)
    return float(value) if value is not None and value == value else 0.0


def _component_row(label: str, value: float, scale: float, tooltip: str) -> str:
    pct = 0.0 if scale <= 0 else max(0.0, min(100.0, abs(value) / scale * 100))
    colour = STATUS_CRITICAL if value < 0 else BLUE
    return f"""
    <div style="margin-bottom:8px;" title="{tooltip}">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px;">
            <span style="font-size:11.5px;font-weight:700;color:{TEXT_PRIMARY};">{label}</span>
            <span style="font-size:12px;font-weight:700;color:{colour};font-variant-numeric:tabular-nums;">
                {value:+.1f}
            </span>
        </div>
        <div style="height:6px;border-radius:999px;background:{rgba(BLUE, 0.12)};overflow:hidden;">
            <div style="height:100%;width:{pct:.0f}%;border-radius:999px;background:{colour};"></div>
        </div>
    </div>
    """


def rating_breakdown_html(row, star: float) -> str:
    """Render the breakdown for one player_rating row. Components worth less
    than 0.05 points either way (e.g. saves for an outfield player) are
    omitted."""
    horizon = _val(row, "xpts_horizon")
    per_gw = _val(row, "xpts_per_gw")
    fixtures = int(_val(row, "fixtures_in_horizon"))
    components = [(label, _val(row, col), tip) for col, label, tip in _COMPONENTS if abs(_val(row, col)) >= 0.05]
    scale = max((abs(v) for _, v, _ in components), default=0.0)
    bars = "".join(_component_row(label, value, scale, tip) for label, value, tip in components)

    order = row.get("p_penalties_order")
    penalty_note = ""
    if order is not None and order == order:
        ordinal = {1: "first", 2: "second", 3: "third"}.get(int(order), f"number {int(order)}")
        penalty_note = f" On penalties: {ordinal} choice ({_val(row, 'xpens_horizon'):.1f} expected in the window)."

    availability = row.get("availability_next_gw")
    availability_note = ""
    if availability is not None and availability == availability and float(availability) < 0.999:
        availability_note = f" &middot; {float(availability):.0%} chance of being available"

    return f"""
    <div style="padding:4px 0 2px 0;">
        <div style="font-size:12px;font-weight:700;color:{TEXT_MUTED};text-transform:uppercase;
                    letter-spacing:0.03em;margin-bottom:4px;">
            Rating: <span style="color:{TEXT_PRIMARY};">{star:.1f}/10</span>
        </div>
        <div style="font-size:12px;color:{TEXT_MUTED};margin-bottom:2px;">
            {per_gw:.1f} expected points per gameweek.
        </div>
        <div style="font-size:12px;color:{TEXT_MUTED};margin-bottom:12px;line-height:1.5;">
            Next gameweek: <b style="color:{TEXT_PRIMARY};">{_val(row, "xpts_next_gw"):.1f} pts</b>,
            {_val(row, "xmins_next_gw"):.0f} expected minutes{availability_note}.<br>
            Next {fixtures} fixture{"s" if fixtures != 1 else ""}: <b style="color:{TEXT_PRIMARY};">{horizon:.1f} pts</b>,
            made up of:{penalty_note}
        </div>
        {bars}
        <div style="font-size:11px;color:{TEXT_MUTED};margin-top:6px;">
            Rating scale this week: 5 = a typical regular starter ({_val(row, "star_typical_xpts"):.1f} pts per
            gameweek), 10 = the best projection ({_val(row, "star_best_xpts"):.1f}). Price isn't part of it.
        </div>
    </div>
    """
