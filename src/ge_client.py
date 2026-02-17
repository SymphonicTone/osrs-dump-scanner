import httpx
from typing import Dict, Any

BASE_URL = "https://prices.runescape.wiki/api/v1/osrs"


class GEClient:
    def __init__(self, user_agent: str):
        self.headers = {"User-Agent": user_agent}
        self._client = httpx.AsyncClient(
            base_url=BASE_URL, headers=self.headers, timeout=10.0
        )

    async def fetch_latest(self) -> Dict[str, Any]:
        # Fetch latest price + volume data for all items
        response = await self._client.get("/latest")
        response.raise_for_status()
        return response.json()["data"]

    async def fetch_5m_timeseries(self, item_id: int):
        response = await self._client.get(
            "/timeseries", params={"id": item_id, "timestep": "5m"}
        )
        response.raise_for_status()
        return response.json()["data"]

    async def fetch_item_mapping(self):
        response = await self._client.get("/mapping")
        response.raise_for_status()
        data = response.json()
        return {
            str(item["id"]): {"name": item["name"], "buy_limit": item.get("limit", 0)}
            for item in data
        }

    async def close(self):
        await self._client.aclose()
