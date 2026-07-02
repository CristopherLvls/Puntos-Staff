from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import gemini_evaluator, log_repository, mongo_write


def _is_admin(interaction: discord.Interaction) -> bool:
    if not config.ADMIN_ROLE_IDS:
        return interaction.user.guild_permissions.administrator
    user_role_ids = {r.id for r in interaction.user.roles}
    return bool(user_role_ids & config.ADMIN_ROLE_IDS) or interaction.user.guild_permissions.administrator


async def _resolve_member(
    guild: discord.Guild, member: discord.Member | discord.User
) -> discord.Member:
    if isinstance(member, discord.Member) and len(member.roles) > 1:
        return member

    cached = guild.get_member(member.id)
    if cached is not None:
        return cached

    return await guild.fetch_member(member.id)


def _has_staff_role(member: discord.Member) -> bool:
    return config.member_has_staff_role(member)


class StaffCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="evaluar",
        description="Evalúa el desempeño de un miembro del staff con IA (solo admins)",
    )
    @app_commands.describe(
        miembro="Miembro del staff a evaluar",
        dias="Días hacia atrás para analizar logs (default 7)",
    )
    async def evaluar(
        self,
        interaction: discord.Interaction,
        miembro: discord.Member,
        dias: app_commands.Range[int, 1, 90] = 7,
    ):
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "No tienes permiso para usar este comando.", ephemeral=True
            )
            return

        miembro = await _resolve_member(interaction.guild, miembro)

        if not _has_staff_role(miembro):
            role_names = ", ".join(r.name for r in miembro.roles if r.name != "@everyone")
            await interaction.response.send_message(
                "El usuario seleccionado no tiene un rol de staff (Helper, Moderador o Tester).\n"
                f"Roles detectados: {role_names or 'ninguno'}",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            since = datetime.now(timezone.utc) - timedelta(days=dias)
            staff_id = str(miembro.id)
            role = config.get_staff_role_name(miembro)

            logs = log_repository.find_staff_logs(staff_id, since=since)
            summary = log_repository.summarize_logs_for_ai(logs)

            result = gemini_evaluator.evaluate_staff(
                staff_name=miembro.display_name,
                staff_discord_id=staff_id,
                role=role,
                logs_summary=summary,
                period_days=dias,
                log_count=len(logs),
            )

            now = mongo_write.utc_now()
            mongo_write.save_evaluation(
                {
                    "staff_discord_id": staff_id,
                    "staff_display_name": miembro.display_name,
                    "role": result["role"],
                    "points": result["points"],
                    "reputation_status": result["reputation_status"],
                    "justification": result["justification"],
                    "advice": result["advice"],
                    "period_start": since,
                    "period_end": now,
                    "log_count": len(logs),
                    "evaluated_by_discord_id": str(interaction.user.id),
                    "created_at": now,
                    "model": config.GEMINI_MODEL,
                }
            )

            embed = discord.Embed(
                title="Evaluación de desempeño — Insight IA",
                description=gemini_evaluator.format_evaluation_text(result),
                color=_color_for_points(result["points"]),
            )
            embed.add_field(
                name="Consejos para mejorar",
                value="\n".join(f"• {a}" for a in result["advice"]),
                inline=False,
            )
            embed.set_footer(text=f"Logs analizados: {len(logs)} | Periodo: {dias} días")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"Error al evaluar: {e}", ephemeral=True
            )

    @app_commands.command(
        name="puntos",
        description="Consulta puntos y reputación acumulada de un staff",
    )
    @app_commands.describe(miembro="Miembro del staff (opcional, por defecto tú)")
    async def puntos(
        self,
        interaction: discord.Interaction,
        miembro: discord.Member | None = None,
    ):
        target = miembro or interaction.user
        target = await _resolve_member(interaction.guild, target)

        if miembro and not _is_admin(interaction):
            if interaction.user.id != miembro.id:
                await interaction.response.send_message(
                    "Solo puedes ver tus propios puntos.", ephemeral=True
                )
                return

        if not _has_staff_role(target) and not _is_admin(interaction):
            await interaction.response.send_message(
                "El usuario no es staff.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=miembro is None and not _is_admin(interaction))

        score = mongo_write.get_staff_score(str(target.id))
        if not score:
            await interaction.followup.send(
                f"**{target.display_name}** aún no tiene evaluaciones registradas."
            )
            return

        embed = discord.Embed(
            title=f"Puntos — {target.display_name}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Promedio", value=str(score.get("average_points", "—")), inline=True)
        embed.add_field(name="Total puntos", value=str(score.get("total_points", 0)), inline=True)
        embed.add_field(name="Evaluaciones", value=str(score.get("evaluation_count", 0)), inline=True)
        embed.add_field(
            name="Última reputación",
            value=score.get("last_reputation_status", "—"),
            inline=False,
        )
        embed.add_field(name="Último rol evaluado", value=score.get("last_role", "—"), inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="historial",
        description="Últimas evaluaciones de un miembro del staff",
    )
    @app_commands.describe(miembro="Staff a consultar", limite="Cantidad (1-10)")
    async def historial(
        self,
        interaction: discord.Interaction,
        miembro: discord.Member,
        limite: app_commands.Range[int, 1, 10] = 5,
    ):
        if not _is_admin(interaction) and interaction.user.id != miembro.id:
            await interaction.response.send_message("Sin permiso.", ephemeral=True)
            return

        miembro = await _resolve_member(interaction.guild, miembro)
        await interaction.response.defer()

        history = mongo_write.get_evaluation_history(str(miembro.id), limit=limite)
        if not history:
            await interaction.followup.send("Sin historial de evaluaciones.")
            return

        lines = []
        for ev in history:
            created = ev.get("created_at", "")
            if hasattr(created, "strftime"):
                created = created.strftime("%Y-%m-%d")
            lines.append(
                f"**{created}** — {ev.get('points')} pts ({ev.get('reputation_status')})\n"
                f"_{ev.get('justification', '')[:120]}_"
            )

        embed = discord.Embed(
            title=f"Historial — {miembro.display_name}",
            description="\n\n".join(lines),
            color=discord.Color.dark_grey(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="consejos",
        description="Consejos de mejora para un staff (IA)",
    )
    @app_commands.describe(
        miembro="Staff a asesorar",
        dias="Días de logs si no hay historial previo",
    )
    async def consejos(
        self,
        interaction: discord.Interaction,
        miembro: discord.Member,
        dias: app_commands.Range[int, 1, 90] = 7,
    ):
        if not _is_admin(interaction) and interaction.user.id != miembro.id:
            await interaction.response.send_message("Sin permiso.", ephemeral=True)
            return

        miembro = await _resolve_member(interaction.guild, miembro)
        await interaction.response.defer(thinking=True)

        try:
            history = mongo_write.get_evaluation_history(str(miembro.id), limit=5)
            role = config.get_staff_role_name(miembro)

            if history:
                advice = gemini_evaluator.generate_advice_only(
                    miembro.display_name, str(miembro.id), role, history
                )
            else:
                since = datetime.now(timezone.utc) - timedelta(days=dias)
                logs = log_repository.find_staff_logs(str(miembro.id), since=since)
                summary = log_repository.summarize_logs_for_ai(logs)
                result = gemini_evaluator.evaluate_staff(
                    staff_name=miembro.display_name,
                    staff_discord_id=str(miembro.id),
                    role=role,
                    logs_summary=summary,
                    period_days=dias,
                    log_count=len(logs),
                )
                advice = result["advice"]

            embed = discord.Embed(
                title=f"Consejos para {miembro.display_name}",
                description=gemini_evaluator.format_advice_text(advice),
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)


def _color_for_points(points: float) -> discord.Color:
    if points >= 8:
        return discord.Color.gold()
    if points >= 7:
        return discord.Color.green()
    if points >= 5:
        return discord.Color.orange()
    if points >= 1:
        return discord.Color.red()
    return discord.Color.dark_red()


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffCommands(bot))
