import logging
import sys

import discord
from discord.ext import commands

import config
from commands import staff_commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("insight_ia")


class InsightBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await staff_commands.setup(self)
        guild = discord.Object(id=int(config.DISCORD_GUILD_ID)) if config.DISCORD_GUILD_ID else None
        if guild:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Comandos sincronizados en guild %s", config.DISCORD_GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Comandos sincronizados globalmente")

    async def on_ready(self):
        logger.info("Conectado como %s (%s)", self.user, self.user.id)


def main():
    missing = config.validate_config()
    if missing:
        logger.error("Variables de entorno faltantes: %s", ", ".join(missing))
        sys.exit(1)

    bot = InsightBot()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
