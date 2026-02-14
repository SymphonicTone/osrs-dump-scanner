import pandas as pd


def detect_dump(
    df: pd.DataFrame,
    z_threshold: float = -2.5,
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

    required_cols = {"avgLowPrice", "highPriceVolume", "lowPriceVolume"}
    if not required_cols.issubset(df.columns):
        return {"is_dump": False}

    df = df.dropna(subset=["avgLowPrice"])

    if len(df) < window:
        return {"is_dump": False}

    # Work only with last `window` rows (faster + cleaner)
    df = df.tail(window).copy()

    # Normalize volume column
    df["total_volume"] = df["highPriceVolume"] + df["lowPriceVolume"]

    price = df["avgLowPrice"]
    volume = df["total_volume"]

    mean_price = price.mean()
    std_price = price.std()
    avg_volume = volume.mean()

    if pd.isna(std_price) or std_price == 0:
        return {"is_dump": False}

    current_price = price.iloc[-1]
    current_volume = volume.iloc[-1]

    z_score = (current_price - mean_price) / std_price
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

    is_dump = bool(z_score < z_threshold and volume_ratio > volume_multiplier)

    # Profit estimation
    buy_price = current_price
    sell_price = mean_price
    profit_per_item = sell_price - buy_price

    buy_limit = 1000
    expected_total_profit = profit_per_item * buy_limit

    return {
        "is_dump": is_dump,
        "z_score": round(z_score, 3),
        "buy_price": int(current_price),
        "sell_price": int(mean_price),
        "current_volume": int(current_volume),
        "avg_volume": int(avg_volume),
        "volume_ratio": round(volume_ratio, 2),
        "buy_limit": buy_limit,
        "expected_total_profit": int(expected_total_profit),
    }
