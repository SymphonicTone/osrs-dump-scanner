import asyncio
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    DUMP_CHANNEL_ID,
    SCAN_INTERVAL_SEC,
    VOLUME_MULTIPLIER,
    WINDOW,
    Z_THRESHOLD,
)
from dump_detector import detect_dump
from embeds import build_dump_embed, build_status_embed, build_watchlist_embed


def _fmt_time(ts: float | None) -> str:
    """Formats a unix timestamp as a human-readable UTC string, or 'Never'."""
    if ts is None:
        return "Never"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


class DumpCog(commands.Cog):
    """
    Handles the dump detection scan loop and dump-related slash commands.

    Reads from shared bot state:
        bot.ge_client    — GEClient instance
        bot.item_data    — item mapping dict (id → {name, buy_limit})
        bot.watchlist    — set of item_id strings from the screener
        bot.scanner      — Scanner instance for deduplication
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_scan_ts: float | None = None
        self._scan_loop.start()

    def cog_unload(self):
        self._scan_loop.cancel()

    # ── Scan loop ──────────────────────────────────────────────────────────────

    @tasks.loop(seconds=SCAN_INTERVAL_SEC)
    async def _scan_loop(self):
        """
        Polls the Wiki API for every item on the watchlist, runs detect_dump,
        and posts an alert to #dump-alerts if a new dump is detected.
        """
        if not self.bot.is_ready():
            return

        channel = await self.bot.fetch_channel(DUMP_CHANNEL_ID)
        if not channel:
            print(
                f"[DumpCog] Channel {DUMP_CHANNEL_ID} not found — check DISCORD_DUMP_CHANNEL_ID"
            )
            return

        watchlist = getattr(self.bot, "watchlist", set())
        item_data = getattr(self.bot, "item_data", {})
        ge_client = self.bot.ge_client
        scanner = self.bot.scanner

        if not watchlist:
            print("[DumpCog] Watchlist is empty, skipping scan.")
            return

        print(f"[DumpCog] Scanning {len(watchlist)} items...")

        semaphore = asyncio.Semaphore(50)

        async def fetch(item_id):
            async with semaphore:
                return item_id, await ge_client.fetch_5m_timeseries(int(item_id))

        tasks_ = [fetch(item_id) for item_id in watchlist]
        results = await asyncio.gather(*tasks_, return_exceptions=True)

        alerts_sent = 0
        for result in results:
            if isinstance(result, Exception):
                continue

            item_id, timeseries = result
            if not timeseries:
                continue

            meta = item_data.get(str(item_id))
            if not meta:
                continue

            buy_limit = meta["buy_limit"]
            item_name = meta["name"]

            dump_data = detect_dump(
                timeseries=timeseries,
                buy_limit=buy_limit,
                item_id=item_id,
                watchlist=watchlist,
            )

            if not dump_data.get("is_dump"):
                continue

            dump_data["expected_total_profit"] = (
                dump_data["profit_per_item"] * dump_data["buy_limit"]
            )

            alert = scanner.process_item(item_id, dump_data)
            if not alert:
                continue

            alert["item_id"] = item_id
            embed = build_dump_embed(alert, item_name)

            # Ping the channel owner so the alert is impossible to miss
            await channel.send(
                content=f"<@{self.bot.owner_id}> 🔴 Dump detected!",
                embed=embed,
            )
            alerts_sent += 1

        self.last_scan_ts = time.time()
        print(f"[DumpCog] Scan complete. {alerts_sent} alert(s) sent.")

    @_scan_loop.before_loop
    async def _before_scan_loop(self):
        await self.bot.wait_until_ready()

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="item", description="Run the dump detector on a specific item right now."
    )
    @app_commands.describe(name="The item name to check (e.g. 'Abyssal whip')")
    async def item_cmd(self, interaction: discord.Interaction, name: str):
        """Manually trigger dump detection on a named item."""
        await interaction.response.defer(thinking=True)

        item_data = getattr(self.bot, "item_data", {})

        # Find item by name (case-insensitive)
        match = next(
            (
                (item_id, meta)
                for item_id, meta in item_data.items()
                if meta["name"].lower() == name.lower()
            ),
            None,
        )

        if not match:
            await interaction.followup.send(
                f"❌ Could not find an item named **{name}**. Check the spelling and try again.",
                ephemeral=True,
            )
            return

        item_id, meta = match
        timeseries = await self.bot.ge_client.fetch_5m_timeseries(int(item_id))

        if not timeseries:
            await interaction.followup.send(
                f"❌ No timeseries data available for **{name}**.",
                ephemeral=True,
            )
            return

        dump_data = detect_dump(
            timeseries=timeseries,
            buy_limit=meta["buy_limit"],
            item_id=item_id,
            # No watchlist gate for manual checks — always run
            watchlist=None,
        )

        dump_data["expected_total_profit"] = (
            dump_data["profit_per_item"] * dump_data["buy_limit"]
        )

        embed = build_dump_embed(dump_data, meta["name"])

        status = (
            "🔴 **Dump detected!**"
            if dump_data["is_dump"]
            else "✅ **No dump detected.**"
        )
        await interaction.followup.send(content=status, embed=embed)

    @app_commands.command(
        name="watchlist", description="Show items currently being monitored for dumps."
    )
    async def watchlist_cmd(self, interaction: discord.Interaction):
        """Displays the current screener watchlist."""
        watchlist = getattr(self.bot, "watchlist", set())
        item_data = getattr(self.bot, "item_data", {})

        embed = build_watchlist_embed(list(watchlist), item_data)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="status",
        description="Show the current status of both the dump scanner and flip screener.",
    )
    async def status_cmd(self, interaction: discord.Interaction):
        """Displays health and last-run info for both systems."""
        screener_cog = self.bot.cogs.get("ScreenerCog")
        last_screener_ts = getattr(screener_cog, "last_screener_ts", None)

        watchlist = getattr(self.bot, "watchlist", set())
        active_dumps = len(self.bot.scanner._state)

        embed = build_status_embed(
            last_dump_scan=_fmt_time(self.last_scan_ts),
            last_screener_run=_fmt_time(last_screener_ts),
            watchlist_count=len(watchlist),
            active_dumps=active_dumps,
        )
        await interaction.response.send_message(embed=embed)
