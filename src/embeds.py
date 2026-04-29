import discord
from typing import List, Dict, Any
from slugify import slugify


def build_dump_embed(dump_data: Dict[str, Any], item_name: str) -> discord.Embed:
    """
    Embed for a single dump alert.
    Posted to #dump-alerts with an @mention.
    """
    slug = slugify(item_name)
    url = f"https://osrs.exchange/item/{slug}"

    embed = discord.Embed(
        title=f"🔴  Dump Detected — {item_name}",
        url=url,
        color=discord.Color.red(),
        description=(
            f"Price has dropped **{abs(dump_data['z_score'])}σ** below the 24h mean "
            f"with a **{dump_data['volume_ratio']}x** volume spike."
        ),
    )

    embed.add_field(
        name="Buy at",
        value=f"{dump_data['buy_price']:,} gp",
        inline=True,
    )
    embed.add_field(
        name="Sell at",
        value=f"{dump_data['sell_price']:,} gp",
        inline=True,
    )
    embed.add_field(
        name="Profit per item",
        value=f"{dump_data['profit_per_item']:,} gp",
        inline=True,
    )
    embed.add_field(
        name="Buy limit",
        value=f"{dump_data['buy_limit']:,}",
        inline=True,
    )
    embed.add_field(
        name="Expected total profit",
        value=f"{dump_data['expected_total_profit']:,} gp",
        inline=True,
    )
    embed.add_field(
        name="Z-Score",
        value=str(dump_data["z_score"]),
        inline=True,
    )
    embed.add_field(
        name="Current volume",
        value=f"{dump_data['current_volume']:,}",
        inline=True,
    )
    embed.add_field(
        name="Avg volume (24h)",
        value=f"{dump_data['avg_volume']:,}",
        inline=True,
    )

    embed.set_footer(text="OSRS Dump Scanner • #dump-alerts")

    return embed


def build_screener_embed(results: List[Dict[str, Any]]) -> discord.Embed:
    """
    Embed for the ranked screener output.
    Posted to #daily-flips on a schedule or via /flips.
    """
    if not results:
        embed = discord.Embed(
            title="📊  Top Flips Right Now",
            description="No flips currently meet the filter criteria.",
            color=discord.Color.light_grey(),
        )
        embed.set_footer(text="OSRS Flip Screener • #daily-flips")
        return embed

    embed = discord.Embed(
        title="📊  Top Flips Right Now",
        color=discord.Color.blue(),
    )

    lines = []
    for i, item in enumerate(results, start=1):
        slug = slugify(item["name"])
        url = f"https://osrs.exchange/item/{slug}"
        profit = f"{int(item['profit_per_unit']):,} gp"
        roi = f"{item['pct_roi']:.1f}%"
        adj = f"{int(item['adjusted_daily_profit']):,} gp/day"

        lines.append(
            f"**{i}. [{item['name']}]({url})**\n"
            f"  Buy `{int(item['buy_price']):,}` → Sell `{int(item['sell_price']):,}` "
            f"| +{profit} ({roi}) | Est. {adj}"
        )

    embed.description = "\n\n".join(lines)
    embed.set_footer(text="OSRS Flip Screener • #daily-flips")

    return embed


def build_watchlist_embed(
    watchlist_ids: List[str],
    item_data: Dict[str, Any],
) -> discord.Embed:
    """
    Embed showing which items are currently on the screener watchlist.
    Used by the /watchlist slash command.
    """
    embed = discord.Embed(
        title="👁️  Current Watchlist",
        color=discord.Color.og_blurple(),
        description=f"**{len(watchlist_ids):,}** items currently being monitored for dumps.",
    )

    # Show first 20 names so the embed doesn't overflow
    names = []
    for item_id in watchlist_ids[:20]:
        meta = item_data.get(str(item_id))
        if meta:
            names.append(meta["name"])

    if names:
        embed.add_field(
            name="Sample items",
            value="\n".join(f"• {n}" for n in names),
            inline=False,
        )

    footer = "OSRS Dump Scanner • #dump-alerts"
    if len(watchlist_ids) > 20:
        footer = f"OSRS Dump Scanner  •  +{len(watchlist_ids) - 20} more not shown"

    embed.set_footer(text=footer)

    return embed


def build_status_embed(
    last_dump_scan: str,
    last_screener_run: str,
    watchlist_count: int,
    active_dumps: int,
) -> discord.Embed:
    """
    Embed for /status — shows health of both systems at a glance.
    """
    embed = discord.Embed(
        title="⚙️  Bot Status",
        color=discord.Color.green(),
    )

    embed.add_field(
        name="🔴 Dump Scanner",
        value=f"Last scan: {last_dump_scan}\nActive dumps: {active_dumps}",
        inline=True,
    )
    embed.add_field(
        name="📊 Flip Screener",
        value=f"Last run: {last_screener_run}\nWatchlist size: {watchlist_count:,}",
        inline=True,
    )

    embed.set_footer(text="OSRS Dump Scanner")

    return embed
