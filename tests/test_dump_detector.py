import numpy as np
from dump_detector import detect_dump


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

    return [
        {
            "avgLowPrice": float(prices[i]),
            "highPriceVolume": float(volumes[i] * 0.5),
            "lowPriceVolume": float(volumes[i] * 0.5),
        }
        for i in range(length)
    ]


def test_no_dump():
    ts = make_timeseries()
    result = detect_dump(ts)
    assert result["is_dump"] is False


def test_price_dump_low_volume():
    ts = make_timeseries(dump=True)
    ts[-1]["highPriceVolume"] = 500
    ts[-1]["lowPriceVolume"] = 500
    result = detect_dump(ts)
    assert result["is_dump"] is False


def test_price_dump_high_volume():
    ts = make_timeseries(dump=True)
    result = detect_dump(ts)
    assert result["is_dump"] is True
    assert result["z_score"] < -2.5
    assert result["volume_ratio"] > 1.8
