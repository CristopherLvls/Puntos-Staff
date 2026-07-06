import asyncio
import logging
import os
import sys

import discord
from aiohttp import web
from discord.ext import commands

import config
from commands import staff_chat, staff_commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("insight_ia")

_discord_connected = False


class InsightBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await staff_commands.setup(self)
        await staff_chat.setup(self)
        if not config.DISCORD_SYNC_COMMANDS:
            logger.info("Sincronización de slash commands omitida (DISCORD_SYNC_COMMANDS=false)")
            return
        guild = discord.Object(id=int(config.DISCORD_GUILD_ID)) if config.DISCORD_GUILD_ID else None
        if guild:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Comandos sincronizados en guild %s", config.DISCORD_GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Comandos sincronizados globalmente")

    async def on_ready(self):
        global _discord_connected
        _discord_connected = True
        logger.info("Conectado como %s (%s)", self.user, self.user.id)


async def _health(request: web.Request) -> web.Response:
    if request.query.get("status") == "1":
        state = "connected" if _discord_connected else "connecting"
        return web.Response(text=f"ok discord={state}")
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


async def _wait_for_rate_limit(exc: discord.HTTPException, attempt: int, delay: float) -> float:
    wait = float(exc.retry_after) if exc.retry_after else delay
    wait = max(wait, 30.0)
    logger.warning(
        "Discord rate limit global (429). Esperando %.0fs (intento %s). "
        "No redeployes: el bloqueo se levanta solo.",
        wait,
        attempt,
    )
    await asyncio.sleep(wait)
    return min(max(wait, delay) * 1.5, 600.0)


async def _discord_connect_forever() -> None:
    global _discord_connected
    attempt = 0
    delay = 30.0

    if config.DISCORD_LOGIN_INITIAL_DELAY > 0:
        logger.info(
            "Esperando %ss antes del primer intento (evita solapar con instancia anterior)...",
            config.DISCORD_LOGIN_INITIAL_DELAY,
        )
        await asyncio.sleep(config.DISCORD_LOGIN_INITIAL_DELAY)

    while True:
        attempt += 1
        _discord_connected = False
        bot = InsightBot()
        try:
            logger.info("Conectando a Discord (intento %s)...", attempt)
            async with bot:
                await bot.start(config.DISCORD_TOKEN)
        except discord.LoginFailure as exc:
            logger.error("Token de Discord inválido o revocado: %s", exc)
            await asyncio.sleep(300)
        except discord.HTTPException as exc:
            if exc.status == 429:
                delay = await _wait_for_rate_limit(exc, attempt, delay)
                continue
            logger.exception("Error HTTP de Discord (status %s)", exc.status)
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error inesperado conectando a Discord")
            await asyncio.sleep(delay)
        else:
            _discord_connected = False
            logger.info("Desconectado de Discord. Reconectando en %ss...", delay)
            await asyncio.sleep(delay)


async def _run() -> None:
    missing = config.validate_config()
    if missing:
        logger.error("Variables de entorno faltantes: %s", ", ".join(missing))
        sys.exit(1)

    await _start_health_server()
    await _discord_connect_forever()


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
