import asyncio
import os
from ge_client import GEClient
from dump_detector import detect_dump
from scanner import Scanner
from discord_notifier import DiscordNotifier
from dotenv import load_dotenv
from liquid_watchlist import build_liquid_watchlist
import pandas as pd

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))


async def scan_loop(ge_client, scanner, notifier, watchlist, item_names):
    while True:
        print("Scanning...")

        semaphore = asyncio.Semaphore(50)

        async def fetch(item_id):
            async with semaphore:
                return item_id, await ge_client.fetch_5m_timeseries(item_id)

        tasks = [fetch(item_id) for item_id in watchlist]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue

            item_id, timeseries = result

            if not timeseries:
                continue

            df = pd.DataFrame(timeseries)

            if df.empty:
                continue

            dump_data = detect_dump(df)
            alert = scanner.process_item(item_id, dump_data)

            if alert:
                alert["item_id"] = item_id
                item_name = item_names.get(str(item_id), f"Item {item_id}")
                await notifier.send_alert(alert, item_name)

        # Wait before next poll
        await asyncio.sleep(120)


async def main():
    ge_client = GEClient(user_agent="osrs-dump-scanner - personal project")
    scanner = Scanner()

    item_names = await ge_client.fetch_item_mapping()
    watchlist = await build_liquid_watchlist(ge_client)

    async def scanner_task():
        await scan_loop(ge_client, scanner, bot, watchlist, item_names)

    bot = DiscordNotifier(DISCORD_TOKEN, CHANNEL_ID, scanner_task)
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
