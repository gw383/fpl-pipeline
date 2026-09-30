"""A headline stat card: label, big value and an optional "#rank" pill."""

import hashlib

import streamlit as st

from components.layout import metrics_container
from theme import BLUE, BORDER, RADIUS_SM, SHADOW_CARD, SURFACE, TEXT_MUTED, TEXT_PRIMARY, rgba


def metric_card_html(title: str, value, rank=None, rank_hint: str = "") -> str:
    """HTML for a stat card. ``rank_hint`` is shown as the pill's tooltip."""
    # Step the value down for long strings (records, ranks) so it never truncates.
    length = len(str(value)) + (3 if rank is not None else 0)
    value_size = 26 if length <= 7 else 22 if length <= 10 else 19
    rank_html = (
        f'<span class="fpl-metric-rank" title="{rank_hint}" style="flex-shrink:0;background:{rgba(BLUE, 0.10)};'
        f"color:{BLUE};padding:3px 9px;border-radius:999px;font-size:12px;font-weight:700;"
        f'white-space:nowrap;">#{rank}</span>'
        if rank is not None
        else ""
    )
    return f"""
    <div class="fpl-metric" style="
        background:{SURFACE};
        border:1px solid {BORDER};
        border-radius:{RADIUS_SM};
        padding:14px 16px;
        box-shadow:{SHADOW_CARD};
        min-height:92px;
        box-sizing:border-box;
    ">
        <div class="fpl-metric-title" style="
            font-size:11.5px;
            font-weight:600;
            letter-spacing:0.04em;
            text-transform:uppercase;
            color:{TEXT_MUTED};
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        " title="{title}">{title}</div>
        <div class="fpl-metric-row" style="display:flex;align-items:center;justify-content:space-between;gap:8px;
                    margin-top:10px;">
            <div class="fpl-metric-value" style="
                font-size:{value_size}px;
                font-weight:700;
                min-width:0;
                color:{TEXT_PRIMARY};
                font-variant-numeric:tabular-nums;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
                line-height:1.1;
            ">{value}</div>
            {rank_html}
        </div>
    </div>
    """


def _rank_or_none(rank) -> int | None:
    """Ranks come from SQL and may be null (e.g. per-90 ranks for players
    under the minutes bar), which shows as no pill."""
    try:
        return None if rank is None or rank != rank else int(rank)
    except (TypeError, ValueError):
        return None


def metric_card(title: str, value, rank=None, rank_hint: str = "") -> None:
    """Render a stat card into the current Streamlit container."""
    st.html(metric_card_html(title, value, rank, rank_hint))


def metric_row(cards: list[tuple], rank_hint: str = "", per_row: int | None = None, key: str = "") -> None:
    """Render ``(title, value[, rank])`` tuples as a row (or rows) of cards.

    On phones the cards wrap two per row (see components.layout). ``key``
    tells apart two rows with the same titles on one page."""
    per_row = per_row or len(cards)
    titles = "|".join(str(card[0]) for card in cards)
    container_key = f"{key}-{hashlib.md5(titles.encode()).hexdigest()[:8]}"
    with metrics_container(container_key):
        for start in range(0, len(cards), per_row):
            chunk = cards[start : start + per_row]
            for col, card in zip(st.columns(per_row), chunk):
                title, value, *rank = card
                with col:
                    metric_card(title, value, _rank_or_none(rank[0] if rank else None), rank_hint)
