import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import DISCORD_TOKEN, DUMP_CHANNEL_ID, FLIPS_CHANNEL_ID
from ge_client import GEClient
from scanner import Scanner
from cogs.dump_cog import DumpCog
from cogs.screener_cog import ScreenerCog
from cogs.control_cog import ControlCog

load_dotenv()


class OsrsBot(commands.Bot):
    """
    Main bot class. Holds all shared state that cogs read from:
        - ge_client   : GEClient instance for all Wiki API calls
        - item_data   : full item mapping (id → {name, buy_limit})
        - watchlist   : set of item_ids currently being monitored (written by ScreenerCog)
        - scanner     : Scanner instance for dump deduplication (used by DumpCog)
    """

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.ge_client: GEClient = GEClient(
            user_agent="osrs-dump-scanner - personal project"
        )
        self.scanner: Scanner = Scanner()
        self.item_data: dict = {}
        self.watchlist: set = set()
        self.paused: bool = False

    async def setup_hook(self):
        """
        Called once before the bot connects. Loads item data and registers cogs.
        setup_hook is the recommended place for async startup work in discord.py 2.x.
        """
        print("[Bot] Fetching item mapping...")
        self.item_data = await self.ge_client.fetch_item_mapping()
        print(f"[Bot] Loaded {len(self.item_data):,} items.")

        await self.add_cog(ScreenerCog(self))
        await self.add_cog(DumpCog(self))
        await self.add_cog(ControlCog(self))
        print("[Bot] Cogs loaded.")

        # Sync slash commands globally
        await self.tree.sync()
        print("[Bot] Slash commands synced.")

    async def on_ready(self):
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[Bot] Watching {len(self.watchlist)} items for dumps.")

    async def close(self):
        await self.ge_client.close()
        await super().close()


async def main():
    bot = OsrsBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
