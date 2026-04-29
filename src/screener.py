from typing import Dict, Any, List
from config import (
    MIN_DAILY_VOLUME,
    MIN_PROFIT_PER_UNIT,
    MIN_DAILY_PROFIT,
    TOP_FLIPS_COUNT,
)


def _compute_tax(price: float) -> float:
    if price <= 50:
        return 0.0
    return min(round(price * 0.02), 5_000_000)


def _score_item(
    item_id: str,
    prices: Dict[str, Any],
    item_data: Dict[str, Any],
) -> Dict[str, Any] | None:
    high = prices.get("high")
    low = prices.get("low")
    high_vol = prices.get("highVolume") or 0
    low_vol = prices.get("lowVolume") or 0

    if not high or not low or high <= low:
        return None

    meta = item_data.get(str(item_id))
    if not meta:
        return None

    buy_limit = meta.get("buy_limit") or 0
    if buy_limit <= 0:
        return None

    daily_volume = high_vol + low_vol
    if daily_volume < MIN_DAILY_VOLUME:
        return None

    tax = _compute_tax(high)
    profit_per_unit = high - low - tax

    if profit_per_unit <= MIN_PROFIT_PER_UNIT:
        return None

    pct_roi = (profit_per_unit / low) * 100 if low > 0 else 0.0

    uncapped_profit = profit_per_unit * min(high_vol, low_vol)

    capped_profit = profit_per_unit * buy_limit
    adjusted_daily_profit = min(uncapped_profit, capped_profit)

    if adjusted_daily_profit < MIN_DAILY_PROFIT:
        return None

    return {
        "item_id": item_id,
        "name": meta.get("name", "Unknown"),
        "buy_price": int(low),
        "sell_price": int(high),
        "tax": int(tax),
        "profit_per_unit": int(profit_per_unit),
        "pct_roi": round(pct_roi, 2),
        "daily_volume": int(daily_volume),
        "buy_limit": int(buy_limit),
        "adjusted_daily_profit": int(adjusted_daily_profit),
    }


def build_screener_watchlist(
    latest: Dict[str, Any],
    item_data: Dict[str, Any],
) -> List[str]:
    """
    Fast watchlist builder using only /latest data (no per-item timeseries calls).
    Returns item_id strings for every item worth monitoring for dumps —
    i.e. liquid items with valid price data and a known buy limit.
    This list gates the dump detector so it only fires on viable items.
    """
    watchlist = []

    for item_id, prices in latest.items():
        high = prices.get("high")
        low = prices.get("low")
        high_vol = prices.get("highVolume") or 0
        low_vol = prices.get("lowVolume") or 0

        if not high or not low:
            continue

        if (high_vol + low_vol) < MIN_DAILY_VOLUME:
            continue

        meta = item_data.get(str(item_id))
        if not meta or not meta.get("buy_limit"):
            continue

        watchlist.append(item_id)

    return watchlist


def run_screener(
    latest: Dict[str, Any],
    item_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Scores every item in /latest and returns the top N flips ranked by
    adjusted daily profit.

    Pipeline:
      1. Score each item (tax, profit per unit, ROI, daily profit estimate)
      2. Filter by volume, profit, and ROI floors (defined in config.py)
      3. Sort by adjusted daily profit descending
      4. Return top N (TOP_FLIPS_COUNT from config.py)
    """
    results = []

    for item_id, prices in latest.items():
        scored = _score_item(item_id, prices, item_data)
        if scored:
            results.append(scored)

    results.sort(key=lambda x: x["adjusted_daily_profit"], reverse=True)

    return results[:TOP_FLIPS_COUNT]
