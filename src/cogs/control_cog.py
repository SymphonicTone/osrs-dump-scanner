import discord
from discord import app_commands
from discord.ext import commands


class ControlCog(commands.Cog):
    """
    Provides /pause and /resume commands to start and stop all scanning.
    Useful for remotely controlling the bot from Discord when running
    on a Raspberry Pi or other headless server.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="pause",
        description="Pause all scanning (dump detector and flip screener).",
    )
    async def pause_cmd(self, interaction: discord.Interaction):
        if self.bot.paused:
            await interaction.response.send_message(
                "⏸️ Scanning is already paused. Use `/resume` to restart.",
                ephemeral=True,
            )
            return

        self.bot.paused = True

        # Pause both task loops
        dump_cog = self.bot.cogs.get("DumpCog")
        screener_cog = self.bot.cogs.get("ScreenerCog")

        if dump_cog:
            dump_cog._scan_loop.stop()
        if screener_cog:
            screener_cog._screener_loop.stop()

        await interaction.response.send_message(
            "⏸️ All scanning paused. Use `/resume` to restart.",
        )

    @app_commands.command(
        name="resume",
        description="Resume all scanning (dump detector and flip screener).",
    )
    async def resume_cmd(self, interaction: discord.Interaction):
        if not self.bot.paused:
            await interaction.response.send_message(
                "▶️ Scanning is already running. Use `/pause` to stop it.",
                ephemeral=True,
            )
            return

        self.bot.paused = False

        # Resume both task loops
        dump_cog = self.bot.cogs.get("DumpCog")
        screener_cog = self.bot.cogs.get("ScreenerCog")

        if dump_cog and not dump_cog._scan_loop.is_running():
            dump_cog._scan_loop.start()
        if screener_cog and not screener_cog._screener_loop.is_running():
            screener_cog._screener_loop.start()

        await interaction.response.send_message(
            "▶️ Scanning resumed.",
        )
