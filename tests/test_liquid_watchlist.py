import pytest
from liquid_watchlist import build_liquid_watchlist


class FakeGEClient:
    def __init__(self, latest_map, timeseries_map):
        self._latest = latest_map
        self._timeseries = timeseries_map

    async def fetch_latest(self):
        return self._latest

    async def fetch_5m_timeseries(self, item_id):
        value = self._timeseries.get(item_id)
        if isinstance(value, Exception):
            raise value
        return value


def make_ts(high_vol, low_vol, length=288):
    return [
        {"highPriceVolume": high_vol, "lowPriceVolume": low_vol} for _ in range(length)
    ]


@pytest.mark.asyncio
async def test_includes_liquid_item():
    latest = {"1": {}, "2": {}}

    timeseries = {
        "1": make_ts(200, 200),
        "2": make_ts(10, 10),
    }

    client = FakeGEClient(latest, timeseries)

    result = await build_liquid_watchlist(client, min_daily_volume=80000)

    assert "1" in result
    assert "2" not in result


@pytest.mark.asyncio
async def test_skips_exception():
    latest = {"1": {}, "2": {}}

    timeseries = {"1": make_ts(200, 200), "2": RuntimeError("API error")}

    client = FakeGEClient(latest, timeseries)

    result = await build_liquid_watchlist(client)

    assert "1" in result
    assert "2" not in result


@pytest.mark.asyncio
async def test_skips_empty_data():
    latest = {"1": {}, "2": {}, "3": {}}

    timeseries = {
        "1": make_ts(200, 200),
        "2": [],
        "3": None,
    }

    client = FakeGEClient(latest, timeseries)

    result = await build_liquid_watchlist(client)

    assert result == ["1"]


@pytest.mark.asyncio
async def test_custom_min_volume():
    latest = {"1": {}}

    timeseries = {"1": make_ts(100, 100)}

    client = FakeGEClient(latest, timeseries)

    result = await build_liquid_watchlist(client, min_daily_volume=50000)

    assert "1" in result

    result = await build_liquid_watchlist(client, min_daily_volume=80000)

    assert "1" not in result
