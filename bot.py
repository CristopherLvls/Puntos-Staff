import asyncio
import logging
import os
import sys

import discord
from aiohttp import web
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


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def _start_health_server() -> None:
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health check en http://0.0.0.0:%s/health", port)


async def _run() -> None:
    missing = config.validate_config()
    if missing:
        logger.error("Variables de entorno faltantes: %s", ", ".join(missing))
        sys.exit(1)

    await _start_health_server()
    bot = InsightBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
