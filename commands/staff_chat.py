import asyncio
import logging

import discord
from discord.ext import commands

import config
from services import gemini_chat
from services.discord_staff import get_staff_role_name_for_user, is_staff_user, resolve_guild_member
from services.sirgiobot_knowledge import get_sirgiobot_knowledge
from services.staff_chat_debounce import StaffChatDebouncer

logger = logging.getLogger("insight_ia.staff_chat")


class StaffChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._debouncer = StaffChatDebouncer(
            callback=self._process_batch,
            delay_seconds=config.STAFF_CHAT_DEBOUNCE_SECONDS,
            max_calls_per_minute=config.STAFF_CHAT_MAX_PER_MINUTE,
        )
        self._rate_limit_warned: set[int] = set()

    def _channel_category_id(self, channel: discord.abc.GuildChannel) -> int | None:
        if isinstance(channel, discord.Thread):
            parent = channel.parent
            return parent.category_id if parent else None
        return getattr(channel, "category_id", None)

    def _channel_allowed(self, message: discord.Message) -> bool:
        if isinstance(message.channel, discord.DMChannel):
            return False

        if not message.guild:
            return False

        if config.DISCORD_GUILD_ID and str(message.guild.id) != str(config.DISCORD_GUILD_ID):
            return False

        category_id = self._channel_category_id(message.channel)
        return category_id == config.STAFF_CHAT_CATEGORY_ID

    def _extract_content(self, message: discord.Message) -> str:
        content = (message.content or "").strip()
        if self.bot.user:
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()
            content = content.replace(f"<@!{self.bot.user.id}>", "").strip()
        return content

    async def _process_batch(self, messages: list[discord.Message]) -> None:
        latest = messages[-1]
        author = latest.author
        texts = [self._extract_content(m) for m in messages]
        texts = [t for t in texts if t]
        if not texts:
            return

        guild = self.bot.get_guild(int(config.DISCORD_GUILD_ID)) if config.DISCORD_GUILD_ID else None
        role = "Staff"
        if guild:
            try:
                member = await resolve_guild_member(guild, author)
                role = get_staff_role_name_for_user(member)
            except (discord.NotFound, discord.HTTPException):
                pass

        if isinstance(latest.channel, discord.DMChannel):
            channel_label = "Mensaje directo con Insight IA"
        else:
            channel_label = f"#{latest.channel.name}" if hasattr(latest.channel, "name") else "canal"

        async with latest.channel.typing():
            try:
                reply = await asyncio.to_thread(
                    gemini_chat.reply_to_staff,
                    author.display_name,
                    role,
                    texts,
                    channel_label,
                )
            except Exception as exc:
                logger.exception("Error generando respuesta de chat staff")
                await latest.reply(gemini_chat.format_api_error(exc), mention_author=False)
                return

        for chunk in gemini_chat.split_discord_message(reply):
            await latest.reply(chunk, mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not config.STAFF_CHAT_ENABLED:
            return
        if message.author.bot or message.author == self.bot.user:
            return
        if not self._channel_allowed(message):
            return

        content = self._extract_content(message)
        if not content:
            return

        if not await is_staff_user(self.bot, message.author):
            return

        queued = await self._debouncer.add(message)
        if queued:
            return

        if message.author.id not in self._rate_limit_warned:
            self._rate_limit_warned.add(message.author.id)
            try:
                await message.reply(
                    "⏳ Recibí varios mensajes seguidos. Espera unos segundos y vuelve a escribir; "
                    "responderé cuando baje el ritmo para no saturar la API.",
                    mention_author=False,
                )
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot):
    if config.STAFF_CHAT_ENABLED:
        await asyncio.to_thread(get_sirgiobot_knowledge)
    await bot.add_cog(StaffChatCog(bot))
    logger.info(
        "Chat staff %s (debounce %.1fs, categoría %s, API key 2)",
        "activado" if config.STAFF_CHAT_ENABLED else "desactivado",
        config.STAFF_CHAT_DEBOUNCE_SECONDS,
        config.STAFF_CHAT_CATEGORY_ID,
    )
