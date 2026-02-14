import asyncio
import pandas as pd


async def build_liquid_watchlist(ge_client, min_daily_volume=80000):
    print("Building liquidity watchlist...")

    latest = await ge_client.fetch_latest()
    item_ids = list(latest.keys())

    semaphore = asyncio.Semaphore(50)

    async def fetch(item_id):
        async with semaphore:
            return item_id, await ge_client.fetch_5m_timeseries(item_id)

    tasks = [fetch(item_id) for item_id in item_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    liquid_items = []

    for result in results:
        if isinstance(result, Exception):
            continue

        item_id, ts = result

        if not ts:
            continue

        df = pd.DataFrame(ts)

        if df.empty:
            continue

        df["total_volume"] = df["highPriceVolume"] + df["lowPriceVolume"]

        daily_volume = df.tail(288)["total_volume"].sum()

        if daily_volume >= min_daily_volume:
            liquid_items.append(item_id)

    print(f"Found {len(liquid_items)} liquid items")
    return liquid_items
