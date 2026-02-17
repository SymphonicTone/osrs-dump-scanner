import asyncio
import os
from ge_client import GEClient
from dump_detector import detect_dump
from scanner import Scanner
from discord_notifier import DiscordNotifier
from dotenv import load_dotenv
from liquid_watchlist import build_liquid_watchlist

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))


async def scan_loop(ge_client, scanner, notifier, watchlist, item_data):
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

            item_meta = item_data.get(str(item_id))
            if not item_meta:
                continue

            buy_limit = item_meta["buy_limit"]
            item_name = item_meta["name"]

            dump_data = detect_dump(timeseries, buy_limit)

            if not dump_data.get("is_dump"):
                continue

            dump_data["expected_total_profit"] = (
                dump_data["profit_per_item"] * dump_data["buy_limit"]
            )

            alert = scanner.process_item(item_id, dump_data)

            if alert:
                alert["item_id"] = item_id
                await notifier.send_alert(alert, item_name)

        # Wait before next poll
        await asyncio.sleep(120)


async def main():
    ge_client = GEClient(user_agent="osrs-dump-scanner - personal project")
    scanner = Scanner()

    item_data = await ge_client.fetch_item_mapping()
    watchlist = await build_liquid_watchlist(ge_client)

    bot = None

    async def scanner_task():
        await scan_loop(ge_client, scanner, bot, watchlist, item_data)

    bot = DiscordNotifier(DISCORD_TOKEN, CHANNEL_ID, scanner_task)
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
