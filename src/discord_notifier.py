import discord


class DiscordNotifier:
    def __init__(self, token: str, channel_id: int):
        self.token = token
        self.channel_id = channel_id
        self.client = discord.Client(intents=discord.Intents.default())

    async def start(self):
        await self.client.loogin(self.token)
        await self.client.connect()

    async def send_alert(self, message: str):
        channel = self.client.get_channel(self.channel_id)
        if channel:
            await channel.send(message)

    async def close(self):
        await self.client.close()
