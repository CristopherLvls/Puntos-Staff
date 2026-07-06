"""Utilidades para identificar miembros del staff en Discord."""

import discord

import config


async def resolve_guild_member(
    guild: discord.Guild, member: discord.Member | discord.User
) -> discord.Member:
    if isinstance(member, discord.Member) and len(member.roles) > 1:
        return member

    cached = guild.get_member(member.id)
    if cached is not None:
        return cached

    return await guild.fetch_member(member.id)


async def is_staff_user(bot: discord.Client, user: discord.User | discord.Member) -> bool:
    if user.bot:
        return False

    if not config.DISCORD_GUILD_ID:
        return False

    guild = bot.get_guild(int(config.DISCORD_GUILD_ID))
    if guild is None:
        return False

    try:
        member = await resolve_guild_member(guild, user)
        return config.member_has_staff_role(member)
    except (discord.NotFound, discord.HTTPException):
        return False


def get_staff_role_name_for_user(member: discord.Member) -> str:
    return config.get_staff_role_name(member)
