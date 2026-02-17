from statistics import mean, stdev
from typing import List, Dict, Any


def detect_dump(
    timeseries: List[Dict[str, Any]],
    buy_limit: int,
    z_threshold: float = -3,
    volume_multiplier: float = 1.8,
    window: int = 288,
) -> dict:
    """
    Detects a short-term dump using rolling z-score and volume spike.
    Assumes df contains:
        - avgLowPrice
        - highPriceVolume
        - lowPriceVolume
    """

    if not timeseries or len(timeseries) < window:
        return {"is_dump": False}

    recent = timeseries[-window:]

    prices = []
    volumes = []

    for row in recent:
        price = row.get("avgLowPrice")
        high_vol = row.get("highPriceVolume")
        low_vol = row.get("lowPriceVolume")

        if price is None or high_vol is None or low_vol is None:
            continue

        prices.append(price)
        volumes.append(high_vol + low_vol)

    if len(prices) < window:
        return {"is_dump": False}

    try:
        mean_price = mean(prices)
        std_price = stdev(prices)
        avg_volume = mean(volumes)
    except Exception:
        return {"is_dump": False}

    if std_price == 0:
        return {"is_dump": False}

    current_price = prices[-1]
    current_volume = volumes[-1]
    z_score = (current_price - mean_price) / std_price
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    is_dump = (
        z_score < z_threshold and volume_ratio > volume_multiplier and buy_limit > 70
    )

    # GE Tax
    profit_per_item = (mean_price * (0.98 if mean_price > 50 else 1.0)) - current_price

    return {
        "is_dump": is_dump,
        "z_score": round(z_score, 3),
        "buy_price": int(current_price),
        "sell_price": int(mean_price),
        "current_volume": int(current_volume),
        "avg_volume": int(avg_volume),
        "volume_ratio": round(volume_ratio, 2),
        "profit_per_item": int(profit_per_item),
        "buy_limit": buy_limit,
    }
