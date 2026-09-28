"""The "how was this score reached" breakdown shown when a star-rated
player card (star_card.py) is expanded -- the ingredients (each already
0-10) that are blended together to make the overall star rating, plus
the minutes-security gate that scales the whole thing down when a player
isn't nailed on or has a live injury/news flag.

See transformation/models/analytics/player_rating.sql for the actual
formula this mirrors.

Round 7.1 note: this used to look up each ingredient's weight from a
fixed _POSITION_WEIGHTS table keyed by p_position, because the old model
picked weights purely by position. That's no longer true for
midfielders: an attacking midfielder's defcon_weight/quality_weight now
depend on their own defensive-contribution rate too (see
MID_DEFCON_ROLE_THRESHOLD in player_rating.sql), not just their
position. Rather than duplicate that player-level logic here in Python,
the dbt model now computes each ingredient's actual weight for that
player and carries it on the row itself (quality_weight, defcon_weight,
team_strength_weight, fixtures_weight) -- this file just reads those
back rather than looking anything up.

Round 7.1 note 2: also dropped from the differential cards entirely
(feedback: the breakdown toggle was adding a lot of visual noise across
a 20-card differentials grid meant for a quick scan) -- only star_card's
"Top rated players" section still uses this.
"""
from theme import BLUE, BORDER, PAGE_BG, RADIUS_SM, TEXT_MUTED, TEXT_PRIMARY, rgba

# (weight column, label, value column, tooltip) -- fixed display order
# (not a per-position "biggest first" ordering, since which ingredient is
# biggest varies by position/player now; this order reads naturally
# regardless: a player's own output, then the team/fixture context
# around them, then the more specialised defensive signal last).
_INGREDIENT_META = [
    (
        "quality_weight",
        "Underlying quality",
        "quality_score",
        "Recency-weighted actual + expected points per 90 -- recent gameweeks count "
        "most, but a whole season of history is never fully discarded, and each "
        "match is also weighted by how strong that specific opponent was (leaving "
        "out the match itself when judging the opponent's own strength).",
    ),
    (
        "team_strength_weight",
        "Team strength",
        "team_strength_score",
        "This player's own team's underlying attacking (npxG created) and/or "
        "defensive (xG conceded) rate, weighted by how much each matters for this "
        "position.",
    ),
    (
        "fixtures_weight",
        "Fixture outlook",
        "fixture_outlook_score",
        "The next 5 opponents' weakness where it matters most for this position, "
        "weighted towards the very next gameweek.",
    ),
    (
        "defcon_weight",
        "Defensive contribution",
        "defensive_contribution_score",
        "Recency-weighted defensive actions (tackles, interceptions, blocks, "
        "recoveries) per 90, towards the defensive-contribution bonus points. Only "
        "counted for players who realistically get near that bonus -- see "
        "player_rating.sql's MID_DEFCON_ROLE_THRESHOLD.",
    ),
]


def _meter_row(label: str, weight: str, value: float, tooltip: str) -> str:
    pct = max(0.0, min(100.0, value * 10))
    return f"""
    <div style="margin-bottom:10px;" title="{tooltip}">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px;">
            <span style="font-size:11.5px;font-weight:700;color:{TEXT_PRIMARY};">
                {label} <span style="color:{TEXT_MUTED};font-weight:600;">({weight})</span>
            </span>
            <span style="font-size:12px;font-weight:700;color:{TEXT_PRIMARY};font-variant-numeric:tabular-nums;">
                {value:.1f}
            </span>
        </div>
        <div style="height:6px;border-radius:999px;background:{rgba(BLUE, 0.12)};overflow:hidden;">
            <div style="height:100%;width:{pct:.0f}%;border-radius:999px;background:{BLUE};"></div>
        </div>
    </div>
    """


def rating_breakdown_html(row, star: float) -> str:
    """Render the ingredient breakdown behind one player's star rating.

    `star` is passed explicitly rather than read off `row` because
    get_star_top5_by_position names that column "rating" -- easier to
    just hand it in than to make the query rename it.

    Each ingredient's weight is read straight off `row` (see the Round
    7.1 note above) rather than looked up by position, and an ingredient
    is only shown at all when its weight for this specific player is
    above 0 -- which is how a goalkeeper/forward's defensive-contribution
    row disappears entirely, and how it also disappears for an
    attacking-minded midfielder specifically, without either case needing
    special-casing here.
    """
    def _val(column: str) -> float:
        value = row.get(column)
        return float(value) if value is not None else 0.0

    meters = "".join(
        _meter_row(label, f"{_val(weight_col) * 100:.0f}%", _val(value_col), tooltip)
        for weight_col, label, value_col, tooltip in _INGREDIENT_META
        if _val(weight_col) > 0
    )

    minutes_security = row.get("minutes_security_score")
    security_note = ""
    if minutes_security is not None and float(minutes_security) < 0.999:
        security_note = f"""
        <div style="
            margin-top:2px;
            font-size:11px;
            color:{TEXT_MUTED};
            font-weight:600;
        ">
            Scaled by &times;{float(minutes_security):.2f} for minutes security / a live news flag.
        </div>
        """

    return f"""
    <div style="
        background:{PAGE_BG};
        border:1px solid {BORDER};
        border-radius:{RADIUS_SM};
        padding:12px 14px;
        margin:-2px 0 8px 0;
    ">
        <div style="
            font-size:12px;
            font-weight:700;
            color:{TEXT_MUTED};
            text-transform:uppercase;
            letter-spacing:0.03em;
            margin-bottom:10px;
        ">
            Star rating: <span style="color:{TEXT_PRIMARY};">{star:.1f}/10</span>
        </div>
        {meters}
        {security_note}
    </div>
    """
