import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    FLIPS_CHANNEL_ID,
    SCREENER_INTERVAL_SEC,
)
from screener import build_screener_watchlist, run_screener
from embeds import build_screener_embed


def _fmt_time(ts: float | None) -> str:
    """Formats a unix timestamp as a human-readable UTC string, or 'Never'."""
    if ts is None:
        return "Never"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


class ScreenerCog(commands.Cog):
    """
    Handles the flip screener loop and screener-related slash commands.

    On each run:
      1. Fetches /latest from the Wiki API
      2. Rebuilds the watchlist (shared with DumpCog via bot.watchlist)
      3. Runs the full screener to rank the best flips
      4. Posts the ranked embed to #daily-flips

    Reads from shared bot state:
        bot.ge_client   — GEClient instance
        bot.item_data   — item mapping dict (id → {name, buy_limit})

    Writes to shared bot state:
        bot.watchlist   — updated set of item_id strings for DumpCog to use
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_screener_ts: float | None = None
        self._last_results: list = []
        self._screener_loop.start()

    def cog_unload(self):
        self._screener_loop.cancel()

    # ── Screener loop ──────────────────────────────────────────────────────────

    @tasks.loop(seconds=SCREENER_INTERVAL_SEC)
    async def _screener_loop(self):
        """
        Fetches /latest, rebuilds the watchlist, runs the screener,
        and posts the ranked flip list to #daily-flips.
        """
        if not self.bot.is_ready():
            return

        channel = await self.bot.fetch_channel(FLIPS_CHANNEL_ID)
        if not channel:
            print(
                f"[ScreenerCog] Channel {FLIPS_CHANNEL_ID} not found — check DISCORD_FLIPS_CHANNEL_ID"
            )
            return

        item_data = getattr(self.bot, "item_data", {})
        ge_client = self.bot.ge_client

        print("[ScreenerCog] Fetching latest prices...")

        try:
            latest = await ge_client.fetch_latest()
            six_hour = await ge_client.fetch_6h()
        except Exception as e:
            print(f"[ScreenerCog] Failed to fetch latest prices: {e}")
            return

        # Merge volume data into latest
        for item_id, data in six_hour.items():
            if item_id in latest:
                latest[item_id]["highVolume"] = data.get("highPriceVolume", 0) * 4
                latest[item_id]["lowVolume"] = data.get("lowPriceVolume", 0) * 4

        # ── Rebuild watchlist and share it with DumpCog ────────────────────────
        watchlist = build_screener_watchlist(latest, item_data)
        self.bot.watchlist = set(watchlist)
        print(f"[ScreenerCog] Watchlist rebuilt: {len(watchlist)} items.")

        # ── Run the screener ───────────────────────────────────────────────────
        results = run_screener(latest, item_data)
        self._last_results = results
        self.last_screener_ts = time.time()

        print(f"[ScreenerCog] Screener complete. {len(results)} flip(s) found.")

        embed = build_screener_embed(results)
        await channel.send(embed=embed)

    @_screener_loop.before_loop
    async def _before_screener_loop(self):
        await self.bot.wait_until_ready()

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="flips", description="Show the current top flips right now."
    )
    async def flips_cmd(self, interaction: discord.Interaction):
        """
        Returns the most recent screener results on demand.
        Uses cached results so it doesn't hammer the API on every call.
        """
        if not self._last_results:
            await interaction.response.send_message(
                "⏳ The screener hasn't run yet. Check back in a moment.",
                ephemeral=True,
            )
            return

        embed = build_screener_embed(self._last_results)
        last_run = _fmt_time(self.last_screener_ts)
        embed.set_footer(
            text=f"OSRS Flip Screener • #daily-flips • Last updated {last_run}"
        )
        await interaction.response.send_message(embed=embed)
