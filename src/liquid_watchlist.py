import asyncio


async def build_liquid_watchlist(ge_client, min_daily_volume=80000):
    print("Building liquidity watchlist...")

    latest = await ge_client.fetch_latest()
    item_ids = list(latest.keys())

    # limit concurrent requests to 50
    semaphore = asyncio.Semaphore(50)

    # keep track of item_id with its timeseries
    async def fetch(item_id):
        async with semaphore:
            return item_id, await ge_client.fetch_5m_timeseries(item_id)

    tasks = [fetch(item_id) for item_id in item_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    liquid_items = []

    for result in results:
        # ignore failed API calls
        if isinstance(result, Exception):
            continue

        # skip without timeseries
        item_id, ts = result

        if not ts:
            continue

        last_24h = ts[-288:]

        # calculate daily volume as sum of highPriceVolume and lowPriceVolume
        daily_volume = sum(
            row["highPriceVolume"] + row["lowPriceVolume"] for row in last_24h
        )

        # filter items based on daily volume threshold
        if daily_volume >= min_daily_volume:
            liquid_items.append(item_id)

    print(f"Found {len(liquid_items)} liquid items")

    return liquid_items
