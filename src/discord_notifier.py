import discord
from slugify import slugify


class DiscordNotifier(discord.Client):
    def __init__(self, token: str, channel_id: int, scanner_task):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

        self.token = token
        self.channel_id = channel_id
        self.scanner_task = scanner_task

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        self.loop.create_task(self.scanner_task())

    async def send_alert(self, dump_data: dict, item_name: str):
        channel = self.get_channel(self.channel_id)
        if not channel:
            return

        embed = self.build_dump_embed(dump_data, item_name)
        await channel.send(embed=embed)

    def run_bot(self):
        self.run(self.token)

    def build_dump_embed(self, dump_data, item_name):
        slug = slugify(item_name)
        url = f"https://osrs.exchange/item/{slug}"

        profit_per_item = dump_data["sell_price"] - dump_data["buy_price"]

        embed = discord.Embed(
            title=f"{item_name}", url=url, color=discord.Color.green()
        )

        embed.add_field(
            name="Buy at", value=f"{dump_data['buy_price']:,} gp", inline=True
        )

        embed.add_field(
            name="Sell at", value=f"{dump_data['sell_price']:,} gp", inline=True
        )

        embed.add_field(name="Z-Score", value=f"{dump_data['z_score']}", inline=True)

        embed.add_field(
            name="Profit per item",
            value=f"{profit_per_item:,} gp",
            inline=True,
        )

        embed.add_field(
            name="Buy limit", value=f"{dump_data['buy_limit']:,}", inline=True
        )

        embed.add_field(
            name="Expected profit",
            value=f"{dump_data['expected_total_profit']:,} gp",
            inline=False,
        )

        embed.set_footer(text="OSRS Dump Scanner")

        return embed
