import pandas as pd


def detect_dump(timeseries_data, z_threshold=-2.5, volume_multiplier=1.8):
    # timeseries_data: list of candles from /timeseries endpoint, returns true if dump detected
    timestamps = [candle["timestamp"] for candle in timeseries_data]
    prices = [candle["avgLowPrice"] for candle in timeseries_data]
    volumes = [
        candle["highPriceVolume"] + candle["lowPriceVolume"]
        for candle in timeseries_data
    ]

    df = pd.DataFrame({"timestamp": timestamps, "price": prices, "volume": volumes})
    df.set_index("timestamp", inplace=True)

    rolling_mean = df["price"].rolling(window=288).mean()
    rolling_std = df["price"].rolliing(window=288).std()

    current_price = df["price"].iloc[-1]
    current_z = (current_price - rolling_mean.iloc[-1]) / rolling_std.iloc[-1]

    avg_volume = df["volume"].rolling(window=288).mean().iloc[-1]
    current_volume = df["volume"].iloc[-1]

    if current_z < -2.5 and current_volume > 1.8 * avg_volume:
        return True

    return False
