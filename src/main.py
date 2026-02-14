import asyncio
from ge_client import GEClient
from dump_detector import detect_dump
from scanner import Scanner
from discord_notifier import DiscordNotifier
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHHANNEL_ID"))


async def scan_loop(client, scanner, notifier):
    while True:
        latest = await client.fetch_latest()

        # High liquidity filter
        high_liquidity_items = [
            item_id
            for item_id, data in latest.items()
            if (data.get("highPriceVolume", 0) + data.get("lowPriceVolume", 0)) >= 10000
        ]

        scanner.prune(set(high_liquidity_items))

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

            result = detect_dump(timeseries)
            alert = scanner.process_item(item_id, result)

            if alert:
                print(f"Potential dump detected for {item_id}")

        # Wait before next poll
        await asyncio.sleep(60)


async def main():
    ge_client = GEClient(user_agent="osrs-dump-scanner - personal project")
    notifier = DiscordNotifier(DISCORD_TOKEN, CHANNEL_ID)
    scanner = Scanner()

    try:
        await scan_loop(ge_client, scanner, notifier)
    finally:
        await ge_client.close()
        await notifier.close()


if __name__ == "__main__":
    asyncio.run(main())
