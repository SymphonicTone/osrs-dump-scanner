import asyncio
from ge_client import GEClient
from dump_detector import detect_dump


async def main():
    client = GEClient(user_agent="osrs-dump-scanner - personal project")

    try:
        while True:
            latest = await client.fetch_latest()
            print(f"Fetched {len(latest)} items")

            # High liquidity filter
            high_liquidity_items = [
                item_id
                for item_id, data in latest.items()
                if (data.get("highPriceVolme", 0) + data.get("lowPriceVolume", 0))
                >= 10000
            ]

            tasks = [
                client.fetch_5m_timeseries(item_id) for item_id in high_liquidity_items
            ]

            # Run tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check results
            for item_id, timeseries in zip(high_liquidity_items, results):
                if isinstance(timeseries, Exception):
                    print(f"Error fetching timeseries for item {item_id}: {timeseries}")
                    continue

                if detect_dump(timeseries):
                    print(f"Potential dump detected for {item_id}!")

            # Wait before next poll
            await asyncio.sleep(60)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
