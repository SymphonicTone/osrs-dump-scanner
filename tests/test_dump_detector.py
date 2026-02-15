import numpy as np
import pandas as pd
from dump_detector import detect_dump


# Generate fake timeseries data
def make_timeseries(
    length=300,
    base_price=100,
    base_volume=1000,
    noise_pct=0.01,
    dump=False,
):
    np.random.seed(42)

    prices = base_price * (1 + np.random.normal(0, noise_pct, length))

    volumes = base_volume * (1 + np.random.normal(0, noise_pct, length))

    if dump:
        prices[-1] = base_price * 0.85  # 15% drop
        volumes[-1] = base_volume * 3  # 3x spike

    return pd.DataFrame(
        {
            "avgLowPrice": prices,
            "highPriceVolume": volumes * 0.5,
            "lowPriceVolume": volumes * 0.5,
        }
    )


# Stable prices with normal volume
def test_no_dump():
    ts = make_timeseries()
    result = detect_dump(ts)
    assert result["is_dump"] is False


# Price drops but volume normal
def test_price_dump_low_volume():
    ts = make_timeseries(dump=True)
    ts.loc[ts.index[-1], "highPriceVolume"] = 500
    ts.loc[ts.index[-1], "lowPriceVolume"] = 500
    result = detect_dump(ts)
    assert result["is_dump"] is False


# Price drops and volume spikes
def test_price_dump_high_volume():
    ts = make_timeseries(dump=True)
    result = detect_dump(ts)
    assert result["is_dump"] is True
    assert result["z_score"] < -2.5
    assert result["volume_ratio"] > 1.8
