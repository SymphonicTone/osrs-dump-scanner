import pytest
import respx
from httpx import Response
from ge_client import GEClient


@pytest.mark.asyncio
async def test_fetch_latest():
    client = GEClient(user_agent="test")
    url = "https://prices.runescape.wiki/api/v1/osrs/latest"

    with respx.mock:
        respx.get(url).mock(
            return_value=Response(
                200,
                json={"data": {"4151": {"highPriceVolume": 3, "lowPriceVolume": 5}}},
            )
        )
        latest = await client.fetch_latest()
        assert "4151" in latest
        assert latest["4151"]["highPriceVolume"] == 3
    await client.close()


@pytest.mark.asyncio
async def test_fetch_5m_timeseries():
    client = GEClient(user_agent="test")
    url = "https://prices.runescape.wiki/api/v1/osrs/timeseries"

    with respx.mock:
        respx.get(url).mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "timestamp": 1,
                            "avgHighPrice": 100,
                            "avgLowPrice": 90,
                            "highPriceVolume": 5,
                            "lowPriceVolume": 5,
                        }
                    ]
                },
            )
        )
        ts = await client.fetch_5m_timeseries(4151)
        assert ts[0]["avgLowPrice"] == 90
    await client.close()
