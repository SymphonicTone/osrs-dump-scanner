import pandas as pd


def detect_dump(
    df: pd.DataFrame,
    z_threshold: float = -2.5,
    volume_multiplier: float = 1.8,
    window: int = 288,
) -> dict:
    if len(df) < window:
        return {"is_dump": False}

    price = df["avgLowPrice"]
    volume = df["volume"]

    rolling_mean = price.rolling(window=window).mean()
    rolling_std = price.rolling(window=window).std()
    avg_volume = volume.rolling(window=window).mean()

    current_price = price.iloc[-1]
    current_volume = volume.iloc[-1]
    current_mean = rolling_mean.iloc[-1]
    std_dev = rolling_std.iloc[-1]
    avg_vol = avg_volume.iloc[-1]

    if pd.isna(std_dev) or std_dev == 0:
        return {"is_dump": False}

    z_score = (current_price - current_mean) / std_dev
    volume_ratio = current_volume / avg_vol if avg_vol else 0

    is_dump = bool(z_score < z_threshold and volume_ratio > volume_multiplier)

    return {
        "is_dump": is_dump,
        "z_score": z_score,
        "current_price": current_price,
        "current_mean": current_mean,
        "std_dev": std_dev,
        "current_volume": current_volume,
        "avg_volume": avg_vol,
        "volume_ratio": volume_ratio,
    }
