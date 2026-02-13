import pytest
from dump_detector import detect_dump


# Generate fake timeseries data
def make_timeseries(prices, volumes):
    return [
        {
            "timestamp": i * 300,
            "avgHighPrice": p + 10,
            "avgLowPrice": p,
            "highPriceVolume": v // 2,
            "lowPriceVolume": v // 2,
        }
        for i, (p, v) in enumerate(zip(prices, volumes))
    ]


# Stable prices with normal volume
def test_no_dump():
    ts = make_timeseries(prices=[100] * 300, volumes=[10] * 300)
    assert detect_dump(ts) is False


# Price drops but volume normal
def test_price_dump_low_volume():
    ts = make_timeseries(prices=[100] * 287, volumes=[10] * 288)
    assert detect_dump(ts) is False


# Price drops and volume spikes
def test_price_dump_high_volume():
    ts = make_timeseries(prices=[100] * 287 + [70], volumes=[10] * 287 + [25])
    assert detect_dump(ts) is True
