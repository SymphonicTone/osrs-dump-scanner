from statistics import mean, stdev
from typing import List, Dict, Any

from config import (
    Z_THRESHOLD,
    VOLUME_MULTIPLIER,
    WINDOW,
    MIN_BUY_LIMIT,
)


def _compute_tax(price: float) -> float:
    """
    Accurate GE tax:
      - 2% of price, capped at 5,000,000 gp
      - Items below 50 gp are not taxed (tax rounds down to 0)
    """
    if price < 50:
        return 0.0
    return min(int(price * 0.02), 5_000_000)


def _get_z_threshold(mean_price: float, base_threshold: float) -> float:
    """
    Adjusts the z-score threshold based on item price tier.

    High-value items have naturally noisier price series, so we require
    a stronger signal before calling a dump. Cheap, high-volume staples
    are very mean-reverting so we can be more sensitive with them.

    Tiers:
      < 10k gp      → relaxed  (base + 0.5)   e.g. -2.0 at default
      10k – 1M gp   → standard (base)          e.g. -2.5 at default
      > 1M gp       → strict   (base - 0.5)    e.g. -3.0 at default
    """
    if mean_price < 10_000:
        return base_threshold + 0.5  # Less negative = easier to trigger
    elif mean_price > 1_000_000:
        return base_threshold - 0.5  # More negative = harder to trigger
    else:
        return base_threshold


def detect_dump(
    timeseries: List[Dict[str, Any]],
    buy_limit: int,
    item_id: str | None = None,
    watchlist: set | None = None,
    z_threshold: float = Z_THRESHOLD,
    volume_multiplier: float = VOLUME_MULTIPLIER,
    window: int = WINDOW,
) -> dict:
    """
    Detects a short-term dump using rolling z-score and volume spike.

    Improvements over original:
      - Watchlist gate: if a watchlist is provided, only items on it are processed
      - Per-tier z-threshold: stricter for expensive items, relaxed for cheap staples
      - Directional volume: checks if sell-side volume dominates the spike
      - Corrected GE tax: 2% capped at 5M, exempt below 50gp

    Expects timeseries rows containing:
        - avgLowPrice
        - highPriceVolume
        - lowPriceVolume
    """

    # ── Watchlist gate ─────────────────────────────────────────────────────────
    # If a watchlist is provided, skip items not on it entirely.
    # This prevents the dump detector firing on illiquid or unviable items.
    if watchlist is not None and item_id is not None:
        if str(item_id) not in watchlist:
            return {"is_dump": False}

    if not timeseries or len(timeseries) < window:
        return {"is_dump": False}

    recent = timeseries[-window:]

    prices = []
    volumes = []
    sell_vols = []  # lowPriceVolume  = sell-side pressure
    buy_vols = []  # highPriceVolume = buy-side pressure

    for row in recent:
        price = row.get("avgLowPrice")
        high_vol = row.get("highPriceVolume")
        low_vol = row.get("lowPriceVolume")

        if price is None or high_vol is None or low_vol is None:
            continue

        prices.append(price)
        volumes.append(high_vol + low_vol)
        sell_vols.append(low_vol)
        buy_vols.append(high_vol)

    if len(prices) < window:
        return {"is_dump": False}

    try:
        mean_price = mean(prices)
        std_price = stdev(prices)
        avg_volume = mean(volumes)
        avg_sell_vol = mean(sell_vols)
    except Exception:
        return {"is_dump": False}

    if std_price == 0:
        return {"is_dump": False}

    current_price = prices[-1]
    current_volume = volumes[-1]
    current_sell_vol = sell_vols[-1]

    # ── Z-score ────────────────────────────────────────────────────────────────
    z_score = (current_price - mean_price) / std_price

    # Adjust threshold based on item price tier
    adjusted_threshold = _get_z_threshold(mean_price, z_threshold)

    # ── Volume checks ──────────────────────────────────────────────────────────
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

    # Directional volume: is the spike driven by sellers, not buyers?
    # A real dump shows elevated lowPriceVolume (sell pressure).
    sell_ratio = current_sell_vol / avg_sell_vol if avg_sell_vol > 0 else 0
    sell_dominated = sell_ratio > volume_multiplier

    # ── Dump condition ─────────────────────────────────────────────────────────
    is_dump = (
        z_score < adjusted_threshold  # Price is abnormally low
        and volume_ratio > volume_multiplier  # Overall volume is spiking
        and sell_dominated  # Spike is sell-side driven
        and buy_limit > MIN_BUY_LIMIT  # Item is liquid enough to act on
    )

    # ── Profit calculation ─────────────────────────────────────────────────────
    tax = _compute_tax(mean_price)
    profit_per_item = int((mean_price - tax) - current_price)

    return {
        "is_dump": is_dump,
        "z_score": round(z_score, 3),
        "z_threshold": round(adjusted_threshold, 2),
        "buy_price": int(current_price),
        "sell_price": int(mean_price),
        "tax": int(tax),
        "current_volume": int(current_volume),
        "avg_volume": int(avg_volume),
        "volume_ratio": round(volume_ratio, 2),
        "sell_ratio": round(sell_ratio, 2),
        "profit_per_item": profit_per_item,
        "buy_limit": buy_limit,
    }
